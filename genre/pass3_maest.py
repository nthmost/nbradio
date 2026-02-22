"""
Pass 3: MAEST ML audio classification.

Uses the mtg-upf/discogs-maest-30s-pw-73e-ts model to classify audio
files using the Discogs taxonomy, then maps labels to our KNOB taxonomy.

Requires: torch, transformers, librosa, numpy, soundfile

CPU inference: ~8-15 sec/track on Intel N100.
"""

import os
import sys

try:
    import torch
    import numpy as np
    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

try:
    import librosa
    HAS_LIBROSA = True
except ImportError:
    HAS_LIBROSA = False

try:
    from transformers import AutoFeatureExtractor, AutoModelForAudioClassification
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False

from .taxonomy import DISCOGS_TO_KNOB

MODEL_ID = "mtg-upf/discogs-maest-30s-pw-73e-ts"
SAMPLE_RATE = 16000
MAX_DURATION = 30  # seconds - model was trained on 30s clips
TOP_K = 5  # number of top predictions to consider


def check_dependencies():
    """Check if ML dependencies are available."""
    errors = []
    if not HAS_TORCH:
        errors.append("torch not installed (pip install torch --index-url https://download.pytorch.org/whl/cpu)")
    if not HAS_LIBROSA:
        errors.append("librosa not installed (pip install librosa)")
    if not HAS_TRANSFORMERS:
        errors.append("transformers not installed (pip install transformers)")
    return errors


class MAESTClassifier:
    """Wrapper around the MAEST audio classification model."""

    def __init__(self, device=None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None
        self.feature_extractor = None
        self.labels = None

    def load(self):
        """Load the model and feature extractor. Call once before classifying."""
        print(f"Loading MAEST model ({MODEL_ID}) on {self.device}...")
        self.feature_extractor = AutoFeatureExtractor.from_pretrained(MODEL_ID)
        self.model = AutoModelForAudioClassification.from_pretrained(MODEL_ID)
        self.model.to(self.device)
        self.model.eval()
        self.labels = self.model.config.id2label
        print(f"Model loaded. {len(self.labels)} labels available.")

    def classify_file(self, filepath):
        """Classify an audio file.

        Returns list of (discogs_label, probability) tuples, sorted by prob desc.
        """
        # Load audio
        try:
            audio, sr = librosa.load(filepath, sr=SAMPLE_RATE, duration=MAX_DURATION, mono=True)
        except Exception as e:
            return []

        if len(audio) == 0:
            return []

        # Extract features and run inference
        inputs = self.feature_extractor(
            audio, sampling_rate=SAMPLE_RATE, return_tensors="pt"
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model(**inputs)
            probs = torch.nn.functional.sigmoid(outputs.logits)[0]

        # Get top predictions
        top_indices = probs.argsort(descending=True)[:TOP_K]
        results = []
        for idx in top_indices:
            idx = idx.item()
            label = self.labels[idx]
            prob = probs[idx].item()
            results.append((label, prob))

        return results

    def classify_to_knob(self, filepath):
        """Classify a file and map to KNOB taxonomy.

        Returns (parent, sub, confidence, raw_label) or (None, None, None, None).
        """
        predictions = self.classify_file(filepath)
        if not predictions:
            return None, None, None, None

        # Try each prediction in order of confidence
        for label, prob in predictions:
            mapping = DISCOGS_TO_KNOB.get(label)
            if mapping is not None:
                return mapping[0], mapping[1], prob, f"maest:{label}"

        # No mapping found - return top prediction info for logging
        top_label, top_prob = predictions[0]
        return None, None, None, f"maest:{top_label} (unmapped)"


def classify_track(db, track, classifier, verbose=False):
    """Classify a single track using MAEST.

    Returns (genre_parent, genre_sub) or (None, None).
    """
    track_id = track["id"]
    filepath = f"/media/radio/{track['path']}"

    parent, sub, confidence, raw_label = classifier.classify_to_knob(filepath)

    if parent:
        db.update_classification(
            track_id, parent, sub,
            "maest", confidence, raw_label, pass_num=3,
        )
        if verbose:
            print(f"  [maest] {track['path']} -> {parent}/{sub} ({confidence:.2f})")
    else:
        db.mark_pass_done(track_id, 3)
        if verbose:
            detail = f" ({raw_label})" if raw_label else ""
            print(f"  [skip] {track['path']}{detail}")

    return parent, sub


def run_pass3(db, verbose=False, limit=None):
    """Run Pass 3 on all unclassified tracks that need it.

    Returns (classified_count, skipped_count).
    """
    errors = check_dependencies()
    if errors:
        print("Pass 3 dependency errors:")
        for e in errors:
            print(f"  - {e}")
        return 0, 0

    # Only run on tracks that still have no genre
    tracks = db.get_tracks_needing_pass(3, limit=limit)
    tracks = [t for t in tracks if t["genre_parent"] is None]

    if not tracks:
        print("No unclassified tracks need Pass 3.")
        return 0, 0

    print(f"Pass 3: {len(tracks)} tracks to process")

    classifier = MAESTClassifier()
    classifier.load()

    classified = 0
    skipped = 0

    for i, track in enumerate(tracks, 1):
        if i % 10 == 0 or verbose:
            print(f"  [{i}/{len(tracks)}]", end="" if verbose else "\n")
        parent, sub = classify_track(db, track, classifier, verbose=verbose)
        if parent:
            classified += 1
        else:
            skipped += 1

    return classified, skipped
