"""Smoke tests for Writeprint v1 (stdlib unittest)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from writeprint.features import extract, feature_names
from writeprint.compare import build_baseline, compare
from writeprint.calibrate import (
    loo_genuine_scores,
    suspect_scores,
    sweep,
    recommend,
)

SAMPLES = os.path.join(os.path.dirname(__file__), "..", "samples")


def read(name):
    with open(os.path.join(SAMPLES, name), encoding="utf-8") as fh:
        return fh.read()


class TestFeatures(unittest.TestCase):
    def test_feature_names_stable(self):
        feats = extract("Hello world. This is a test!")
        self.assertEqual(sorted(feats.keys()), sorted(feature_names()))

    def test_empty_text_is_zeros(self):
        feats = extract("")
        self.assertTrue(all(v == 0.0 for v in feats.values()))

    def test_contractions_counted(self):
        feats = extract("I don't like it. It's bad.")
        self.assertGreater(feats["contractions_per_100"], 0)


class TestComparison(unittest.TestCase):
    def setUp(self):
        self.baseline = build_baseline([
            extract(read("student_a_baseline1.txt")),
            extract(read("student_a_baseline2.txt")),
        ])

    def test_needs_two_samples(self):
        with self.assertRaises(ValueError):
            build_baseline([extract("hello")])

    def test_genuine_reads_consistent(self):
        result = compare(extract(read("student_a_homework_genuine.txt")), self.baseline)
        self.assertEqual(result["band"], "consistent", msg=result)

    def test_suspect_flagged(self):
        result = compare(extract(read("student_a_homework_suspect.txt")), self.baseline)
        self.assertEqual(result["band"], "worth a conversation", msg=result)


class TestCalibration(unittest.TestCase):
    def test_sweep_finds_perfect_threshold(self):
        labeled = [(0.5, False), (0.8, False), (1.8, True), (2.2, True)]
        best = recommend(sweep(labeled))
        self.assertEqual(best["f1"], 1.0)
        self.assertEqual(best["precision"], 1.0)
        self.assertEqual(best["recall"], 1.0)

    def test_ties_break_toward_fewer_false_flags(self):
        # All-negative set: every threshold scores F1 0, so the
        # highest (strictest) one must win.
        labeled = [(1.0, False), (2.0, False)]
        best = recommend(sweep(labeled))
        self.assertEqual(best["threshold"], 2.0)

    def test_loo_needs_three_samples(self):
        with self.assertRaises(ValueError):
            loo_genuine_scores(["hello world", "second sample"])

    def test_bundled_corpus_separates(self):
        texts = [read(n) for n in (
            "student_a_baseline1.txt",
            "student_a_baseline2.txt",
            "student_a_baseline3.txt",
        )]
        genuine = loo_genuine_scores(texts)
        full = build_baseline([extract(t) for t in texts])
        suspect = suspect_scores([read("student_a_homework_suspect.txt")], full)
        labeled = [(s, False) for s in genuine] + [(s, True) for s in suspect]
        best = recommend(sweep(labeled))
        self.assertEqual(best["f1"], 1.0)
        self.assertGreater(best["threshold"], max(genuine))
        self.assertLessEqual(best["threshold"], min(suspect))


if __name__ == "__main__":
    unittest.main()
