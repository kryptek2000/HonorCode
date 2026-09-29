"""Smoke tests for Writeprint v1 (stdlib unittest)."""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from writeprint.features import extract, feature_names
from writeprint.compare import build_baseline, compare

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


if __name__ == "__main__":
    unittest.main()
