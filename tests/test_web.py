"""Tests for the Writeprint browser UI (stdlib only)."""

import json
import os
import sys
import threading
import unittest
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from writeprint.web import Handler, check_payload

SAMPLES = os.path.join(os.path.dirname(__file__), "..", "samples")


def read(name):
    with open(os.path.join(SAMPLES, name), encoding="utf-8") as fh:
        return fh.read()


BASELINES = ["student_a_baseline1.txt", "student_a_baseline2.txt",
             "student_a_baseline3.txt"]


class TestCheckPayload(unittest.TestCase):
    def samples(self):
        return [read(n) for n in BASELINES]

    def test_suspect_scores_review(self):
        code, body = check_payload({
            "baselines": self.samples(),
            "submission": read("student_a_homework_suspect.txt"),
        })
        self.assertEqual(code, 200)
        self.assertEqual(body["band"], "worth a conversation")

    def test_genuine_scores_consistent(self):
        code, body = check_payload({
            "baselines": self.samples(),
            "submission": read("student_a_homework_genuine.txt"),
        })
        self.assertEqual(code, 200)
        self.assertEqual(body["band"], "consistent")

    def test_needs_two_baselines(self):
        code, body = check_payload({
            "baselines": [self.samples()[0]],
            "submission": read("student_a_homework_genuine.txt"),
        })
        self.assertEqual(code, 400)
        self.assertIn("error", body)

    def test_empty_submission_rejected(self):
        code, body = check_payload({
            "baselines": self.samples(),
            "submission": "   \n ",
        })
        self.assertEqual(code, 400)
        self.assertIn("error", body)


class TestHttpServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join()
        cls.server.server_close()

    def request(self, method, path, body=None):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=10)
        headers = {}
        data = None
        if body is not None:
            data = json.dumps(body)
            headers["Content-Type"] = "application/json"
        conn.request(method, path, body=data, headers=headers)
        resp = conn.getresponse()
        raw = resp.read()
        conn.close()
        return resp.status, resp.getheader("Content-Type"), raw

    def test_root_serves_html(self):
        status, ctype, raw = self.request("GET", "/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", ctype)
        self.assertIn(b"Writeprint", raw)
        self.assertIn(b"/api/check", raw)

    def test_api_check_roundtrip(self):
        status, ctype, raw = self.request("POST", "/api/check", {
            "baselines": [read(n) for n in BASELINES],
            "submission": read("student_a_homework_suspect.txt"),
        })
        self.assertEqual(status, 200)
        self.assertIn("application/json", ctype)
        body = json.loads(raw)
        self.assertEqual(body["band"], "worth a conversation")
        self.assertIn("flags", body)

    def test_api_check_bad_request(self):
        status, _, raw = self.request("POST", "/api/check", {
            "baselines": ["only one"],
            "submission": "hello",
        })
        self.assertEqual(status, 400)
        self.assertIn("error", json.loads(raw))

    def test_api_check_invalid_json(self):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("POST", "/api/check", body="{not json",
                     headers={"Content-Type": "application/json"})
        resp = conn.getresponse()
        self.assertEqual(resp.status, 400)
        conn.close()

    def test_unknown_paths_404(self):
        status, _, _ = self.request("GET", "/nope")
        self.assertEqual(status, 404)
        status, _, _ = self.request("POST", "/api/nope", {})
        self.assertEqual(status, 404)

    def test_head_root(self):
        conn = HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("HEAD", "/")
        resp = conn.getresponse()
        self.assertEqual(resp.status, 200)
        self.assertIn("text/html", resp.getheader("Content-Type"))
        self.assertEqual(resp.read(), b"")
        conn.close()


if __name__ == "__main__":
    unittest.main()
