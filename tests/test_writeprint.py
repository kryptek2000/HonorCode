"""Smoke tests for Writeprint v1 (stdlib unittest)."""

import csv
import os
import sys
import tempfile
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
from writeprint.export import COLUMNS, rows_for, write_csv

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


def student_baseline(letter):
    texts = [read("student_%s_baseline%d.txt" % (letter, i)) for i in (1, 2, 3)]
    profile = build_baseline([extract(t) for t in texts])
    profile["student"] = "student_%s" % letter
    return profile


class TestSpecificity(unittest.TestCase):
    """Baselines must be student-specific: another student's genuine
    work must NOT pass as your own."""

    @classmethod
    def setUpClass(cls):
        cls.base_a = student_baseline("a")
        cls.base_b = student_baseline("b")

    def band(self, baseline, sample):
        return compare(extract(read(sample)), baseline)["band"]

    def test_own_work_passes(self):
        self.assertEqual(
            self.band(self.base_a, "student_a_homework_genuine.txt"), "consistent")
        self.assertEqual(
            self.band(self.base_b, "student_b_homework_genuine.txt"), "consistent")

    def test_other_students_work_flagged(self):
        self.assertNotEqual(
            self.band(self.base_a, "student_b_homework_genuine.txt"), "consistent")
        self.assertNotEqual(
            self.band(self.base_b, "student_a_homework_genuine.txt"), "consistent")

    def test_suspect_flagged_under_both(self):
        self.assertEqual(
            self.band(self.base_a, "student_a_homework_suspect.txt"),
            "worth a conversation")
        self.assertEqual(
            self.band(self.base_b, "student_a_homework_suspect.txt"),
            "worth a conversation")


class TestExport(unittest.TestCase):
    def test_rows_for_bundled_samples(self):
        baseline = student_baseline("a")
        rows = rows_for(baseline, [
            ("genuine.txt", read("student_a_homework_genuine.txt")),
            ("suspect.txt", read("student_a_homework_suspect.txt")),
        ])
        self.assertEqual([r["band"] for r in rows],
                         ["consistent", "worth a conversation"])
        self.assertEqual(rows[0]["student"], "student_a")
        self.assertTrue(float(rows[1]["score"]) > float(rows[0]["score"]))

    def test_write_csv_roundtrip(self):
        baseline = student_baseline("a")
        rows = rows_for(baseline, [
            ("genuine.txt", read("student_a_homework_genuine.txt")),
        ])
        with tempfile.NamedTemporaryFile("r", suffix=".csv",
                                         delete=False) as tmp:
            path = tmp.name
        try:
            self.assertEqual(write_csv(rows, path), 1)
            with open(path, encoding="utf-8", newline="") as fh:
                back = list(csv.DictReader(fh))
            self.assertEqual(back[0]["band"], "consistent")
            self.assertEqual(set(back[0].keys()), set(COLUMNS))
        finally:
            os.unlink(path)


GUTENBERG_AUTHORS = ("twain", "austen", "doyle")


def gutenberg_baseline(author):
    texts = [read("gutenberg_%s_%s.txt" % (author, kind))
             for kind in ("baseline1", "baseline2", "baseline3")]
    profile = build_baseline([extract(t) for t in texts])
    profile["student"] = author
    return profile


class TestGutenberg(unittest.TestCase):
    """Real-world prose (Project Gutenberg, public domain).

    Within-author stability holds: a held-out passage by the same
    author reads consistent against their baseline. Cross-author
    separation does NOT hold for long-form literary prose in a shared
    formal register — documented in the README, not hidden.
    """

    @classmethod
    def setUpClass(cls):
        cls.baselines = {a: gutenberg_baseline(a) for a in GUTENBERG_AUTHORS}

    def test_own_heldout_reads_consistent(self):
        for author in GUTENBERG_AUTHORS:
            with self.subTest(author=author):
                heldout = read("gutenberg_%s_heldout.txt" % author)
                result = compare(extract(heldout), self.baselines[author])
                self.assertEqual(result["band"], "consistent", msg=result)


ASAP_IDS = ("679", "318", "825", "1362")
ASAP_DIR = os.path.join(SAMPLES, "asap")


def asap_text(eid):
    with open(os.path.join(ASAP_DIR, "asap_set1_id%s.txt" % eid),
              encoding="utf-8") as fh:
        return fh.read()


def thirds(text):
    words = text.split()
    n = len(words) // 3
    return [" ".join(words[:n]), " ".join(words[n:2 * n]),
            " ".join(words[2 * n:])]


class TestASAP(unittest.TestCase):
    """De-identified real student essays (ASAP set 1, persuasive letters).

    Fixture essays live in samples/asap/ with SOURCE.md attribution.
    Full study (300 essays): 95.1% of within-essay chunk checks read
    consistent; same-prompt cross-student checks flag only 11.3%.
    """

    def test_within_essay_never_strong_flags(self):
        # No chunk of genuine student writing may read
        # "worth a conversation" against the rest of its own essay.
        for eid in ASAP_IDS:
            with self.subTest(essay=eid):
                scores = loo_genuine_scores(thirds(asap_text(eid)))
                self.assertLess(max(scores), 1.5, msg=scores)

    def test_majority_fully_consistent(self):
        fully = 0
        for eid in ASAP_IDS:
            scores = loo_genuine_scores(thirds(asap_text(eid)))
            if all(s < 1.2 for s in scores):
                fully += 1
        self.assertGreaterEqual(fully, 3)

    def test_same_prompt_cross_stays_consistent(self):
        # Documents the measured limitation: same-prompt writing by
        # different real students does NOT separate at default bands.
        base = build_baseline(
            [extract(c) for c in thirds(asap_text("679"))])
        for eid in ASAP_IDS:
            with self.subTest(essay=eid):
                chunk = thirds(asap_text(eid))[0]
                result = compare(extract(chunk), base)
                self.assertEqual(result["band"], "consistent", msg=result)


if __name__ == "__main__":
    unittest.main()
