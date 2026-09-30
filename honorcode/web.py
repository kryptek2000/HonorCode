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
  :root {
    --paper: #f7f4ec; --card: #fffdf8; --ink: #1c1814; --muted: #5f574d;
    --hair: #ddd3bf; --gold: #a8842c; --oxford: #23406b;
    --green: #1e7e46; --amber: #9a6700; --red: #b42318;
    --serif: "Didot", "Bodoni MT", "Playfair Display", Georgia, "Times New Roman", serif;
    --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--paper); color: var(--ink);
         font-family: var(--sans); -webkit-font-smoothing: antialiased; }
  .rule-gold { height: 4px; background: linear-gradient(90deg, var(--gold), #d9bd7a 40%, var(--gold)); }
  .masthead { max-width: 960px; margin: 0 auto; padding: 34px 32px 22px;
              display: flex; justify-content: space-between; align-items: flex-end; gap: 16px; }
  .overline { font-size: 11px; letter-spacing: 3px; text-transform: uppercase;
              color: var(--muted); margin: 0 0 8px; }
  .masthead h1 { font-family: var(--serif); font-weight: 400; font-size: 46px;
                 margin: 0; letter-spacing: 0.5px; }
  .masthead h1 em { font-style: italic; }
  .stamp { flex-shrink: 0; font-size: 11px; letter-spacing: 2px; text-transform: uppercase;
           color: var(--oxford); border: 1px solid var(--oxford); border-radius: 4px;
           padding: 8px 12px; opacity: 0.9; text-align: center; }
  main { max-width: 960px; margin: 0 auto; padding: 6px 32px 70px; }
  .card { background: var(--card); border: 1px solid var(--hair); border-radius: 4px;
          box-shadow: 0 1px 2px rgba(28,24,20,0.05), 0 12px 32px -18px rgba(28,24,20,0.25);
          padding: 28px 30px; }
  .secnum { font-family: var(--serif); font-style: italic; color: var(--gold);
            font-size: 15px; margin-right: 8px; }
  label.seclabel { display: block; font-size: 12px; letter-spacing: 2px; text-transform: uppercase;
                   color: var(--muted); margin: 24px 0 8px; font-weight: 600; }
  label.seclabel:first-child { margin-top: 0; }
  .hint { text-transform: none; letter-spacing: 0; font-weight: 400; font-size: 13px; }
  input[type=text] { width: 100%; padding: 10px 12px; font-size: 16px; font-family: var(--serif);
                     background: #fff; color: var(--ink);
                     border: 1px solid var(--hair); border-radius: 4px; }
  textarea { width: 100%; min-height: 118px; padding: 10px 12px; font-size: 14px; line-height: 1.55;
             font-family: var(--sans); background: #fff; color: var(--ink);
             border: 1px solid var(--hair); border-radius: 4px; resize: vertical; }
  input:focus, textarea:focus { outline: 2px solid var(--oxford); outline-offset: 1px; border-color: var(--oxford); }
  .row { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; }
  #actions { margin-top: 26px; display: flex; gap: 10px; align-items: center; }
  button { padding: 12px 26px; font-size: 14px; letter-spacing: 1.5px; text-transform: uppercase;
           font-weight: 700; color: #fffdf8; background: var(--ink);
           border: 1px solid var(--ink); border-radius: 4px; cursor: pointer;
           transition: background 0.15s ease, transform 0.1s ease; }
  button:hover { background: #000; }
  button:active { transform: translateY(1px); }
  button.secondary { background: transparent; color: var(--ink); border: 1px solid var(--hair); }
  button.secondary:hover { border-color: var(--ink); background: transparent; }
  ::placeholder { color: #8a8177; opacity: 1; }
  .legend { margin-top: 22px; border-top: 1px solid var(--hair); padding-top: 14px;
            display: grid; gap: 7px; }
  .legend div { font-size: 13px; color: var(--muted); }
  .dot { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin-right: 8px; }
  .fineprint { font-size: 12px; color: var(--muted); margin-top: 8px; }
  #error { display: none; margin-top: 18px; padding: 12px 16px; font-size: 14px;
           color: var(--red); background: #fbeeec; border-left: 3px solid var(--red); }
  #report { display: none; margin-top: 28px; animation: rise 0.35s ease; }
  @keyframes rise { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: none; } }
  .rep-head { text-align: center; border-bottom: 1px solid var(--hair); padding-bottom: 18px; }
  .rep-head .overline { margin-bottom: 6px; }
  .rep-head h2 { font-family: var(--serif); font-weight: 400; font-size: 30px; margin: 0; }
  .rep-head .sub { color: var(--muted); font-size: 13px; margin-top: 6px; }
  .verdict { display: flex; gap: 28px; align-items: center; padding: 22px 6px 6px; }
  .gauge { flex-shrink: 0; }
  .vtext .band { display: inline-block; padding: 5px 16px; border-radius: 999px;
                 color: #fff; font-weight: 700; font-size: 14px; letter-spacing: 1.5px;
                 text-transform: uppercase; }
  .vtext .band.consistent { background: var(--green); }
  .vtext .band.mild { background: var(--amber); }
  .vtext .band.review { background: var(--red); }
  .vtext .mean { font-size: 13px; color: var(--muted); margin-top: 10px; line-height: 1.6; max-width: 420px; }
  #report table { width: 100%; border-collapse: collapse; margin-top: 20px; font-size: 13px; }
  #report th { text-align: left; font-size: 11px; letter-spacing: 1.5px; text-transform: uppercase;
               color: var(--muted); font-weight: 600; padding: 8px 10px;
               border-bottom: 1px solid var(--ink); }
  #report td { padding: 8px 10px; border-bottom: 1px solid var(--hair); vertical-align: middle; }
  #report td code { font-size: 12px; background: var(--paper); padding: 1px 5px; border-radius: 4px; }
  .zbar { height: 5px; background: #ece5d3; border-radius: 4px; min-width: 70px; }
  .zbar i { display: block; height: 5px; border-radius: 4px; background: var(--oxford); }
  #report .note { margin-top: 20px; font-size: 13px; line-height: 1.65; color: var(--muted);
                  border: 1px solid var(--hair); background: var(--paper);
                  padding: 12px 16px; border-radius: 4px; }
  #report .note strong { color: var(--ink); }
  footer { max-width: 960px; margin: 0 auto; padding: 0 32px 40px;
           display: flex; justify-content: space-between; gap: 12px;
           font-size: 12px; color: var(--muted); }
  footer a { color: var(--oxford); }
  @media print {
    body { background: #fff; }
    #input-section, #actions, footer, .rule-gold { display: none; }
    main { max-width: none; padding: 0 8px; }
    .card { box-shadow: none; }
    #report { display: block !important; animation: none; }
  }
  @media (max-width: 700px) {
    .row { grid-template-columns: 1fr; }
    .masthead { flex-direction: column; align-items: flex-start; }
    .masthead h1 { font-size: 34px; }
    .verdict { flex-direction: column; }
  }
</style>
</head>
<body>
<div class="rule-gold"></div>
<div class="masthead">
  <div>
    <p class="overline">Authorship verification &middot; For the classroom</p>
    <h1>Honor<em>Code</em></h1>
  </div>
  <div class="stamp">Advisory only<br>Never a verdict</div>
</div>
<main>
  <div class="card" id="input-section">
    <label class="seclabel"><span class="secnum">01.</span>Student</label>
    <input type="text" id="student" value="student_a">
    <label class="seclabel"><span class="secnum">02.</span>Baseline samples
      <span class="hint">&mdash; two or more pieces of known-genuine writing</span></label>
    <div class="row">
      <textarea id="b1" placeholder="Baseline sample 1"></textarea>
      <textarea id="b2" placeholder="Baseline sample 2"></textarea>
      <textarea id="b3" placeholder="Baseline sample 3 (optional)"></textarea>
    </div>
    <label class="seclabel"><span class="secnum">03.</span>Submission under examination</label>
    <textarea id="sub" style="min-height:150px" placeholder="Paste the submission here"></textarea>
    <div id="actions">
      <button onclick="check()">Examine submission</button>
      <button class="secondary" onclick="window.print()">Print report</button>
    </div>
    <div class="legend">
      <div><span class="dot" style="background:#1e7e46"></span><strong>Consistent</strong> &mdash; within this student&rsquo;s own variation.</div>
      <div><span class="dot" style="background:#9a6700"></span><strong>Mild divergence</strong> &mdash; some habits drift; worth a look, not a conclusion.</div>
      <div><span class="dot" style="background:#b42318"></span><strong>Worth a conversation</strong> &mdash; several habits diverge; talk, don&rsquo;t accuse.</div>
    </div>
    <div id="error"></div>
  </div>
  <div class="card" id="report"></div>
</main>
<footer>
  <span>HonorCode &middot; human-in-the-loop, never a verdict.</span>
  <span>Local only &mdash; text never leaves this machine. <a href="https://github.com/kryptek2000/HonorCode">Source</a></span>
</footer>
<script>
var BAND_MEANING = {
  "consistent": "Within the range of this student's own variation.",
  "mild divergence": "Some habits drift from baseline — worth a look, not a conclusion.",
  "worth a conversation": "Several independent habits diverge. Time for a conversation, not an accusation."
};
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
  const ink = cls === "consistent" ? "#1e7e46" : cls === "mild" ? "#9a6700" : "#b42318";
  const pct = Math.min(data.score / 3, 1) * 100;
  let rows = data.flags.map(f => {
    const w = Math.min(f.z / 5 * 100, 100).toFixed(0);
    const zshow = f.z >= 5 ? "≥5" : f.z.toFixed(2);
    return "<tr><td><code>" + f.feature + "</code></td><td>" + f.value.toFixed(3) +
      "</td><td>" + f.baseline_mean.toFixed(3) + "</td>" +
      "<td><div class='zbar'><i style='width:" + w + "%;background:" + ink + "'></i></div></td>" +
      "<td>" + zshow + "</td></tr>";
  }).join("");
  if (!rows) rows = '<tr><td colspan="5">No strongly divergent habits.</td></tr>';
  const today = new Date().toLocaleDateString();
  rep.innerHTML =
    '<div class="rep-head"><p class="overline">Report of examination</p>' +
    "<h2>" + escapeHtml(student) + "</h2>" +
    '<div class="sub">' + today + " &middot; mean absolute z " + data.score.toFixed(3) + " vs. baseline</div></div>" +
    '<div class="verdict">' +
    '<svg class="gauge" width="190" height="118" viewBox="0 0 200 130">' +
    '<path d="M 20 105 A 80 80 0 0 1 180 105" fill="none" stroke="#ece5d3" stroke-width="16"/>' +
    '<path d="M 20 105 A 80 80 0 0 1 180 105" fill="none" stroke="' + ink + '" stroke-width="16" pathLength="100" stroke-dasharray="' + pct.toFixed(1) + ' 100"/>' +
    '<line x1="75.3" y1="28.9" x2="75.3" y2="38" stroke="#5f574d" stroke-width="1"/>' +
    '<line x1="100" y1="25" x2="100" y2="34" stroke="#5f574d" stroke-width="1"/>' +
    '<text x="75.3" y="22" font-size="9" text-anchor="middle" fill="#5f574d">1.2</text>' +
    '<text x="100" y="18" font-size="9" text-anchor="middle" fill="#5f574d">1.5</text>' +
    '<text x="20" y="122" font-size="9" text-anchor="middle" fill="#5f574d">0</text>' +
    '<text x="180" y="122" font-size="9" text-anchor="middle" fill="#5f574d">3+</text>' +
    '<text x="100" y="97" font-size="26" text-anchor="middle" font-weight="bold" fill="#1c1814">' + data.score.toFixed(2) + "</text></svg>" +
    '<div class="vtext"><span class="band ' + cls + '">' + data.band + "</span>" +
    '<div class="mean">' + BAND_MEANING[data.band] + "</div></div></div>" +
    '<table><tr><th>Habit</th><th>Submission</th><th>Baseline</th><th colspan="2">Divergence (z)</th></tr>' +
    rows + "</table>" +
    '<div class="fineprint">z caps at 5, so no single habit dominates the overall score.</div>' +
    '<div class="note"><strong>Advisory only.</strong> This report flags writing habits ' +
    "worth a conversation. It does not determine who wrote a text. " +
    "A teacher always decides what happens next.</div>";
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
