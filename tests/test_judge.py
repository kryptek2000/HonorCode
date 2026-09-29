"""Tests for the opt-in LLM judge (no real API calls)."""

import json
import os
import sys
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from honorcode.compare import build_baseline
from honorcode.features import extract
from honorcode.judge import (JudgeError, build_prompt, call_judge,
                              judge_config, parse_response)

SAMPLES = os.path.join(os.path.dirname(__file__), "..", "samples")


def read(name):
    with open(os.path.join(SAMPLES, name), encoding="utf-8") as fh:
        return fh.read()


def sample_baseline():
    texts = [read("student_a_baseline%d.txt" % i) for i in (1, 2, 3)]
    profile = build_baseline([extract(t) for t in texts])
    profile["student"] = "student_a"
    return profile


class TestPrompt(unittest.TestCase):
    def test_prompt_contains_habits_and_submission(self):
        system, user = build_prompt(
            sample_baseline(), "Some new text here.", "student_a")
        self.assertIn("JSON", system)
        self.assertIn("advisory", system)
        self.assertIn("avg_sentence_len", user)
        self.assertIn("Some new text here.", user)
        self.assertIn("student_a", user)

    def test_long_submission_truncated(self):
        _, user = build_prompt(sample_baseline(), "x" * 5000)
        self.assertIn("truncated", user)
        self.assertLess(len(user), 4500)


class TestParse(unittest.TestCase):
    def test_valid_json(self):
        out = parse_response(json.dumps({
            "consistency": "divergent", "confidence": 0.8,
            "reasons": ["No contractions at all."],
            "caveat": "Advisory."}))
        self.assertEqual(out["consistency"], "divergent")
        self.assertEqual(out["confidence"], 0.8)
        self.assertEqual(out["reasons"], ["No contractions at all."])

    def test_fenced_json(self):
        out = parse_response("```json\n" + json.dumps({
            "consistency": "consistent", "confidence": 0.6,
            "reasons": [], "caveat": "c"}) + "\n```")
        self.assertEqual(out["consistency"], "consistent")

    def test_garbage_becomes_uncertain(self):
        out = parse_response("The student definitely cheated, trust me")
        self.assertEqual(out["consistency"], "uncertain")
        self.assertEqual(out["confidence"], 0.0)

    def test_wrong_shape_becomes_uncertain(self):
        out = parse_response(json.dumps({"verdict": "guilty"}))
        self.assertEqual(out["consistency"], "uncertain")

    def test_confidence_clamped(self):
        out = parse_response(json.dumps({
            "consistency": "consistent", "confidence": 99,
            "reasons": [], "caveat": "c"}))
        self.assertEqual(out["confidence"], 1.0)


class TestConfig(unittest.TestCase):
    def test_missing_config_raises_helpfully(self):
        env = {"HONORCODE_JUDGE_URL": "", "HONORCODE_JUDGE_MODEL": ""}
        old = {k: os.environ.get(k) for k in env}
        try:
            os.environ.update(env)
            os.environ.pop("HONORCODE_JUDGE_KEY", None)
            with self.assertRaises(JudgeError) as ctx:
                judge_config()
            self.assertIn("HONORCODE_JUDGE_URL", str(ctx.exception))
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

    def test_flags_beat_env(self):
        url, key, model = judge_config("http://x/v1", "k", "m")
        self.assertEqual((url, key, model), ("http://x/v1", "k", "m"))


class StubHandler(BaseHTTPRequestHandler):
    mode = "ok"

    def log_message(self, *args):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        if self.mode == "error":
            self.send_response(500)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if self.mode == "bad-shape":
            body = json.dumps({"nope": True}).encode()
        elif self.mode == "garbage-text":
            body = json.dumps({
                "choices": [{"message": {"content": "just vibes"}}]}).encode()
        else:
            body = json.dumps({"choices": [{"message": {"content": json.dumps({
                "consistency": "uncertain", "confidence": 0.4,
                "reasons": ["Mixed signals."],
                "caveat": "Stub."})}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class TestCallJudge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), StubHandler)
        cls.url = "http://127.0.0.1:%d/chat" % cls.server.server_address[1]
        cls.thread = threading.Thread(
            target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join()
        cls.server.server_close()

    def test_roundtrip(self):
        out = call_judge("sys", "user", self.url, "k", "m")
        self.assertEqual(out["consistency"], "uncertain")
        self.assertEqual(out["reasons"], ["Mixed signals."])

    def test_garbage_text_becomes_uncertain(self):
        StubHandler.mode = "garbage-text"
        try:
            out = call_judge("sys", "user", self.url, "k", "m")
            self.assertEqual(out["consistency"], "uncertain")
        finally:
            StubHandler.mode = "ok"

    def test_bad_shape_raises(self):
        StubHandler.mode = "bad-shape"
        try:
            with self.assertRaises(JudgeError):
                call_judge("sys", "user", self.url, "k", "m")
        finally:
            StubHandler.mode = "ok"

    def test_http_error_raises(self):
        StubHandler.mode = "error"
        try:
            with self.assertRaises(JudgeError):
                call_judge("sys", "user", self.url, "k", "m")
        finally:
            StubHandler.mode = "ok"

    def test_unreachable_raises(self):
        with self.assertRaises(JudgeError):
            call_judge("sys", "user", "http://127.0.0.1:1/nope", "k", "m",
                       timeout=2)


if __name__ == "__main__":
    unittest.main()
