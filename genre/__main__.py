"""
CLI for the KNOB Radio genre indexer.

Usage:
    python -m nbradio.genre scan                          # discover files
    python -m nbradio.genre classify --pass 1             # metadata only
    python -m nbradio.genre classify --pass 2             # + acoustid
    python -m nbradio.genre classify --pass 3             # + ML
    python -m nbradio.genre classify                      # all passes
    python -m nbradio.genre report                        # summary
    python -m nbradio.genre report --by parent            # genre breakdown
    python -m nbradio.genre report --by sub               # subgenre breakdown
    python -m nbradio.genre report --by unclassified      # what's left
    python -m nbradio.genre export --format m3u --genre Bass
    python -m nbradio.genre export --format json
    python -m nbradio.genre export --format csv
"""

import argparse
import sys
import os
import time

from .db import GenreDB, DEFAULT_DB_PATH
from .scanner import scan_to_db


def cmd_scan(args, db):
    """Scan media directory for audio files."""
    print(f"Scanning {args.media_root or '/media/radio/'}...")
    t0 = time.time()
    new, updated, removed = scan_to_db(
        db, media_root=args.media_root, verbose=args.verbose,
    )
    elapsed = time.time() - t0
    print(f"\nScan complete in {elapsed:.1f}s:")
    print(f"  New:     {new:,}")
    print(f"  Updated: {updated:,}")
    print(f"  Removed: {removed:,}")
    print(f"  Total:   {db.count_tracks():,}")

    # Show content type breakdown
    with db.connection() as conn:
        rows = conn.execute(
            "SELECT content_type, COUNT(*) as cnt FROM tracks GROUP BY content_type ORDER BY cnt DESC"
        ).fetchall()
    print("\n  Content types:")
    for row in rows:
        print(f"    {row['content_type']:15s} {row['cnt']:5,}")


def cmd_classify(args, db):
    """Run classification passes."""
    passes = []
    if args.pass_num:
        passes = [args.pass_num]
    else:
        passes = [1, 2, 3]

    for pass_num in passes:
        print(f"\n{'='*60}")
        print(f"  Pass {pass_num}")
        print(f"{'='*60}")
        t0 = time.time()

        if pass_num == 1:
            from .pass1_metadata import run_pass1
            classified, skipped = run_pass1(
                db, verbose=args.verbose, limit=args.limit,
            )
        elif pass_num == 2:
            from .pass2_acoustid import run_pass2
            classified, skipped = run_pass2(
                db, verbose=args.verbose, limit=args.limit,
            )
        elif pass_num == 3:
            from .pass3_maest import run_pass3
            classified, skipped = run_pass3(
                db, verbose=args.verbose, limit=args.limit,
            )
        else:
            print(f"Unknown pass number: {pass_num}")
            continue

        elapsed = time.time() - t0
        print(f"\nPass {pass_num} complete in {elapsed:.1f}s:")
        print(f"  Classified: {classified:,}")
        print(f"  Skipped:    {skipped:,}")

    # Show quick summary
    total_songs = db.count_tracks("content_type = 'song'")
    classified = db.count_tracks("content_type = 'song' AND genre_parent IS NOT NULL")
    print(f"\nOverall: {classified:,}/{total_songs:,} songs classified "
          f"({classified/total_songs*100:.1f}%)" if total_songs else "")


def cmd_report(args, db):
    """Generate reports."""
    from .report import (
        report_summary, report_by_parent, report_by_sub, report_unclassified,
    )

    if args.by == "parent":
        report_by_parent(db)
    elif args.by == "sub":
        report_by_sub(db)
    elif args.by == "unclassified":
        report_unclassified(db)
    else:
        report_summary(db)
        report_by_parent(db)


def cmd_export(args, db):
    """Export genre data."""
    from .report import export_json, export_csv, export_m3u

    fmt = args.format or "json"
    genre_parent = args.genre
    genre_sub = args.subgenre
    output = args.output

    if not output:
        label = genre_sub or genre_parent or "all"
        label = label.replace("/", "-").replace(" ", "_").lower()
        output = f"knob_{label}.{fmt}"

    if fmt == "json":
        export_json(db, output, genre_parent=genre_parent, genre_sub=genre_sub)
    elif fmt == "csv":
        export_csv(db, output, genre_parent=genre_parent, genre_sub=genre_sub)
    elif fmt == "m3u":
        export_m3u(
            db, output,
            genre_parent=genre_parent, genre_sub=genre_sub,
            media_root=args.media_root or "/media/radio/",
        )
    else:
        print(f"Unknown format: {fmt}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        prog="python -m nbradio.genre",
        description="KNOB Radio genre indexer",
    )
    parser.add_argument(
        "--db", default=DEFAULT_DB_PATH,
        help=f"Database path (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--media-root", default=None,
        help="Media root directory (default: /media/radio/)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # scan
    subparsers.add_parser("scan", help="Discover and index audio files")

    # classify
    classify_parser = subparsers.add_parser("classify", help="Run classification passes")
    classify_parser.add_argument(
        "--pass", dest="pass_num", type=int, choices=[1, 2, 3],
        help="Run only this pass (default: all)",
    )
    classify_parser.add_argument(
        "--limit", type=int, default=None,
        help="Limit number of tracks to process",
    )

    # report
    report_parser = subparsers.add_parser("report", help="Generate reports")
    report_parser.add_argument(
        "--by", choices=["parent", "sub", "unclassified", "summary"],
        default="summary", help="Report type",
    )

    # export
    export_parser = subparsers.add_parser("export", help="Export genre data")
    export_parser.add_argument(
        "--format", choices=["json", "csv", "m3u"], default="json",
    )
    export_parser.add_argument("--genre", help="Filter by parent genre")
    export_parser.add_argument("--subgenre", help="Filter by subgenre")
    export_parser.add_argument("--output", "-o", help="Output file path")

    args = parser.parse_args()

    # Initialize database
    db = GenreDB(args.db)
    db.init_schema()

    try:
        if args.command == "scan":
            cmd_scan(args, db)
        elif args.command == "classify":
            cmd_classify(args, db)
        elif args.command == "report":
            cmd_report(args, db)
        elif args.command == "export":
            cmd_export(args, db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
