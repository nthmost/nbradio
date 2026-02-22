"""
File discovery and change detection for the genre indexer.

Walks /media/radio/, identifies audio files, detects content types
(song vs callsign vs commercial), and handles incremental re-indexing.
"""

import os
import time
from .taxonomy import content_type_from_dir, CONTENT_TYPE_DIRS

MEDIA_ROOT = "/media/radio/"

AUDIO_EXTENSIONS = {".mp3", ".ogg", ".flac", ".wav", ".m4a", ".opus", ".wma"}

# Directories to skip entirely (not music, not station content)
SKIP_DIRS = {
    "lost+found", "configs", "html", "random_assets", "scripts",
    "log", "kstk", "gdrive", "radiobot", "__pycache__",
}


def is_audio_file(filename):
    """Check if a file has an audio extension."""
    return os.path.splitext(filename)[1].lower() in AUDIO_EXTENSIONS


def scan_files(media_root=None):
    """Walk the media directory and yield file info dicts.

    Yields dicts with: path (relative), filename, directory (relative),
    filesize, mtime, content_type.
    """
    root = media_root or MEDIA_ROOT
    root = os.path.normpath(root)

    for dirpath, dirnames, filenames in os.walk(root):
        # Skip non-music directories
        rel_dir = os.path.relpath(dirpath, root)
        top_dir = rel_dir.split(os.sep)[0]
        if top_dir in SKIP_DIRS:
            dirnames.clear()
            continue

        for filename in sorted(filenames):
            if not is_audio_file(filename):
                continue

            filepath = os.path.join(dirpath, filename)
            try:
                stat = os.stat(filepath)
            except OSError:
                continue

            rel_path = os.path.relpath(filepath, root)

            # Determine content type from directory
            ct = content_type_from_dir(rel_dir)
            content_type = ct if ct else "song"

            yield {
                "path": rel_path,
                "filename": filename,
                "directory": rel_dir,
                "filesize": stat.st_size,
                "mtime": stat.st_mtime,
                "content_type": content_type,
            }


def scan_to_db(db, media_root=None, verbose=False):
    """Scan files and upsert into the database.

    Returns (new_count, updated_count, removed_count).
    """
    existing_paths = db.get_all_paths()
    seen_paths = set()
    new_count = 0
    updated_count = 0

    for file_info in scan_files(media_root):
        path = file_info["path"]
        seen_paths.add(path)

        if path in existing_paths:
            # Check if file changed
            if db.needs_rescan(path, file_info["mtime"], file_info["filesize"]):
                db.upsert_track(file_info)
                updated_count += 1
                if verbose:
                    print(f"  updated: {path}")
            # else: unchanged, skip
        else:
            db.upsert_track(file_info)
            new_count += 1
            if verbose:
                print(f"  new: {path}")

    # Remove tracks whose files no longer exist
    removed_count = 0
    for path in existing_paths - seen_paths:
        db.remove_track(path)
        removed_count += 1
        if verbose:
            print(f"  removed: {path}")

    return new_count, updated_count, removed_count
