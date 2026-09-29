"""Local browser UI for HonorCode. Standard library only.

Serves a single page on 127.0.0.1: paste baseline samples and a
submission, get the report rendered with band coloring and a
print-friendly layout. No external assets, no network calls — the page
works fully offline and student text never leaves the machine.
"""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from .compare import build_baseline, compare
from .features import extract

DEFAULT_PORT = 8765

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>HonorCode — authorship check</title>
<style>
  :root { --green: #1a7f37; --amber: #9a6700; --red: #b42318;
          --ink: #1f2328; --muted: #59636e; --line: #d0d7de; --bg: #f6f8fa; }
  * { box-sizing: border-box; }
  body { font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
         color: var(--ink); margin: 0; background: #fff; }
  header { background: var(--bg); border-bottom: 1px solid var(--line);
           padding: 20px 28px; }
  header h1 { margin: 0 0 4px; font-size: 22px; }
  header p { margin: 0; color: var(--muted); font-size: 14px; }
  main { max-width: 860px; margin: 0 auto; padding: 24px 28px 60px; }
  label { display: block; font-weight: 600; margin: 18px 0 6px; }
  .hint { font-weight: 400; color: var(--muted); font-size: 13px; }
  input[type=text] { width: 100%; padding: 8px 10px; font-size: 15px;
                     border: 1px solid var(--line); border-radius: 6px; }
  textarea { width: 100%; min-height: 110px; padding: 8px 10px; font-size: 14px;
             border: 1px solid var(--line); border-radius: 6px; resize: vertical; }
  .row { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; }
  button { margin-top: 20px; padding: 10px 22px; font-size: 15px; font-weight: 600;
           color: #fff; background: #0969da; border: 0; border-radius: 6px;
           cursor: pointer; }
  button:hover { background: #0550ae; }
  button.secondary { background: #fff; color: var(--ink);
                     border: 1px solid var(--line); margin-left: 8px; }
  #error { display: none; margin-top: 16px; padding: 12px 14px; font-size: 14px;
           color: var(--red); background: #ffebe9; border: 1px solid #ff8182;
           border-radius: 6px; }
  #report { display: none; margin-top: 24px; border: 1px solid var(--line);
            border-radius: 8px; padding: 20px 22px; }
  #report .band { display: inline-block; padding: 4px 14px; border-radius: 999px;
                  color: #fff; font-weight: 700; font-size: 15px; }
  #report .band.consistent { background: var(--green); }
  #report .band.mild { background: var(--amber); }
  #report .band.review { background: var(--red); }
  #report .score { font-size: 28px; font-weight: 700; margin: 10px 0 2px; }
  #report table { width: 100%; border-collapse: collapse; margin-top: 14px;
                  font-size: 13px; }
  #report th, #report td { text-align: left; padding: 6px 8px;
                           border-bottom: 1px solid var(--line); }
  #report th { color: var(--muted); font-weight: 600; }
  #report .note { margin-top: 16px; font-size: 13px; color: var(--muted);
                  border-top: 1px solid var(--line); padding-top: 12px; }
  @media print {
    header, #input-section, #actions { display: none; }
    main { max-width: none; padding: 0; }
    #report { display: block !important; border: none; }
  }
  @media (max-width: 700px) { .row { grid-template-columns: 1fr; } }
</style>
</head>
<body>
<header>
  <h1>✒️ HonorCode</h1>
  <p>Authorship verification for the classroom — advisory only, never a verdict.</p>
</header>
<main>
  <div id="input-section">
    <label>Student name</label>
    <input type="text" id="student" value="student_a">
    <label>Baseline samples <span class="hint">— 2+ pieces of known-genuine writing by this student</span></label>
    <div class="row">
      <textarea id="b1" placeholder="Baseline sample 1"></textarea>
      <textarea id="b2" placeholder="Baseline sample 2"></textarea>
      <textarea id="b3" placeholder="Baseline sample 3 (optional)"></textarea>
    </div>
    <label>Submission to check</label>
    <textarea id="sub" style="min-height:140px" placeholder="Paste the submission here"></textarea>
    <div id="actions">
      <button onclick="check()">Check submission</button>
      <button class="secondary" onclick="window.print()">Print report</button>
    </div>
    <div id="error"></div>
  </div>
  <div id="report"></div>
</main>
<script>
async function check() {
  const err = document.getElementById("error");
  const rep = document.getElementById("report");
  err.style.display = "none";
  const baselines = ["b1", "b2", "b3"].map(id => document.getElementById(id).value);
  const submission = document.getElementById("sub").value;
  const student = document.getElementById("student").value || "student";
  let data;
  try {
    const res = await fetch("/api/check", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({baselines, submission})
    });
    data = await res.json();
    if (!res.ok) throw new Error(data.error || ("HTTP " + res.status));
  } catch (e) {
    err.textContent = "Could not check: " + e.message;
    err.style.display = "block";
    rep.style.display = "none";
    return;
  }
  const cls = data.band === "consistent" ? "consistent"
            : data.band === "mild divergence" ? "mild" : "review";
  let rows = data.flags.map(f =>
    "<tr><td><code>" + f.feature + "</code></td><td>" + f.value.toFixed(3) +
    "</td><td>" + f.baseline_mean.toFixed(3) + "</td><td>" + f.z.toFixed(2) + "</td></tr>"
  ).join("");
  if (!rows) rows = '<tr><td colspan="4">No strongly divergent habits.</td></tr>';
  const today = new Date().toLocaleDateString();
  rep.innerHTML =
    "<div><strong>HonorCode report</strong> — " + escapeHtml(student) + " — " + today + "</div>" +
    '<div class="score">' + data.score.toFixed(3) + "</div>" +
    '<span class="band ' + cls + '">' + data.band.toUpperCase() + "</span>" +
    "<table><tr><th>Habit</th><th>Submission</th><th>Baseline avg</th><th>z</th></tr>" +
    rows + "</table>" +
    '<div class="note">This report flags writing habits worth a conversation. ' +
    "It does not determine who wrote a text. A teacher always decides what happens next.</div>";
  rep.style.display = "block";
  rep.scrollIntoView();
}
function escapeHtml(s) {
  return s.replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}
</script>
</body>
</html>
"""


def check_payload(payload):
    """Validate and score an /api/check payload.

    Returns (status_code, dict). Pure function — easy to test.
    """
    baselines = [b for b in payload.get("baselines", []) if b.strip()]
    submission = payload.get("submission", "")
    if len(baselines) < 2:
        return 400, {"error": "Need at least 2 non-empty baseline samples."}
    if not submission.strip():
        return 400, {"error": "Submission is empty."}
    try:
        profile = build_baseline([extract(b) for b in baselines])
    except ValueError as exc:
        return 400, {"error": str(exc)}
    result = compare(extract(submission), profile)
    return 200, {
        "score": round(result["score"], 3),
        "band": result["band"],
        "flags": result["flags"],
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "HonorCode/1"

    def log_message(self, *args):  # keep the console to startup/errors only
        pass

    def _send(self, code, body, content_type):
        data = body.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if urlparse(self.path).path == "/":
            self._send(200, PAGE, "text/html")
        else:
            self._send(404, json.dumps({"error": "not found"}), "application/json")

    def do_HEAD(self):
        if urlparse(self.path).path == "/":
            data = PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
        else:
            self.send_response(404)
            self.send_header("Content-Length", "0")
            self.end_headers()

    def do_POST(self):
        if urlparse(self.path).path != "/api/check":
            self._send(404, json.dumps({"error": "not found"}), "application/json")
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
        except (TypeError, ValueError):
            length = 0
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, UnicodeDecodeError):
            self._send(400, json.dumps({"error": "Invalid JSON."}), "application/json")
            return
        if not isinstance(payload, dict):
            self._send(400, json.dumps({"error": "Invalid JSON."}), "application/json")
            return
        code, body = check_payload(payload)
        self._send(code, json.dumps(body), "application/json")


def serve(port=DEFAULT_PORT):
    """Serve the UI on 127.0.0.1 only — student text never leaves the machine."""
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print("HonorCode UI at http://127.0.0.1:%d  (local only — Ctrl+C to stop)" % port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
