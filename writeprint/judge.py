"""Optional LLM judge for nuanced cases. Disabled by default.

The statistical engine stays offline and dependency-free. This module adds
an opt-in second opinion: it describes the student's baseline habits to
any OpenAI-compatible chat endpoint and asks for a structured consistency
assessment. Standard library only (urllib) — no SDKs, no new dependencies.

Privacy warning: using this sends student text to a third party. Get
consent, prefer a local model (e.g. Ollama) or your institution's
endpoint, and never use it as the sole basis for an accusation.

Config (flags override env):
  WRITEPRINT_JUDGE_URL    chat-completions endpoint URL
  WRITEPRINT_JUDGE_KEY    bearer token (may be empty for local servers)
  WRITEPRINT_JUDGE_MODEL  model name
"""

import json
import os
import urllib.request

JUDGE_SYSTEM = (
    "You compare a student's new submission against a profile of their "
    "known writing habits. Reply with JSON only: "
    '{"consistency": "consistent" | "uncertain" | "divergent", '
    '"confidence": 0.0-1.0, '
    '"reasons": ["short, specific observations"], '
    '"caveat": "one sentence on why this is advisory, not proof"}. '
    "A single unusual feature is curiosity, not evidence. Only call a "
    "submission divergent when several independent habits all point the "
    "same way."
)


class JudgeError(Exception):
    """Configuration or transport failure (not a model verdict)."""


def summarize_baseline(profile, top_n=12):
    """Render baseline means as compact prose for the prompt."""
    feats = profile["features"]
    # Lead with the most human-readable habits, then the rest.
    first = ["avg_sentence_len", "avg_word_len", "type_token_ratio",
             "contractions_per_100", "first_person_per_100",
             "commas_per_100", "semicolons_per_100", "exclaim_per_100"]
    names = first + [n for n in sorted(feats) if n not in first]
    lines = []
    for name in names[:top_n]:
        lines.append("  - %s: usually %.2f" % (name, feats[name]["mean"]))
    lines.append("  (plus %d more measured habits)" % (len(feats) - top_n))
    return "\n".join(lines)


def build_prompt(profile, submission, student="student", max_chars=3000):
    """Build the (system, user) messages for the judge call."""
    excerpt = submission[:max_chars]
    if len(submission) > max_chars:
        excerpt += "\n[... truncated for length ...]"
    user = (
        "Student '%s' baseline writing habits "
        "(averages over %d known-genuine samples):\n%s\n\n"
        "New submission to assess:\n---\n%s\n---\n"
        "How consistent is this submission with the baseline habits?"
        % (student, profile.get("n_samples", "?"),
           summarize_baseline(profile), excerpt)
    )
    return JUDGE_SYSTEM, user


def parse_response(text):
    """Parse the model's reply into an assessment dict. Never raises:
    unparseable output becomes an explicit 'uncertain' verdict."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        cleaned = "\n".join(lines[1:-1] if len(lines) > 2 else lines[1:])
    try:
        data = json.loads(cleaned)
    except (ValueError, TypeError):
        return {"consistency": "uncertain", "confidence": 0.0,
                "reasons": ["Judge output was not valid JSON."],
                "caveat": "Unparseable response; treat as no opinion."}
    if not isinstance(data, dict) or data.get("consistency") not in (
            "consistent", "uncertain", "divergent"):
        return {"consistency": "uncertain", "confidence": 0.0,
                "reasons": ["Judge output missed the required fields."],
                "caveat": "Malformed verdict; treat as no opinion."}
    try:
        confidence = float(data.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    reasons = data.get("reasons", [])
    if not isinstance(reasons, list):
        reasons = [str(reasons)]
    return {"consistency": data["consistency"],
            "confidence": max(0.0, min(1.0, confidence)),
            "reasons": [str(r) for r in reasons][:6],
            "caveat": str(data.get("caveat", "Advisory only, not proof."))}


def judge_config(endpoint=None, api_key=None, model=None):
    """Resolve config from flags-or-env. Raises JudgeError if unusable."""
    url = endpoint or os.environ.get("WRITEPRINT_JUDGE_URL", "")
    key = api_key if api_key is not None else os.environ.get("WRITEPRINT_JUDGE_KEY", "")
    name = model or os.environ.get("WRITEPRINT_JUDGE_MODEL", "")
    missing = [n for n, v in (("endpoint URL", url), ("model", name)) if not v]
    if missing:
        raise JudgeError(
            "LLM judge not configured (missing %s). Set WRITEPRINT_JUDGE_URL "
            "and WRITEPRINT_JUDGE_MODEL (plus WRITEPRINT_JUDGE_KEY unless "
            "your endpoint needs none), or pass --endpoint/--model. "
            "Any OpenAI-compatible /chat/completions endpoint works, "
            "including a local Ollama server." % " and ".join(missing))
    return url, key, name


def call_judge(system, user, endpoint, api_key, model, timeout=60):
    """POST to the endpoint, return the parsed assessment. Transport
    problems raise JudgeError; model-output problems become 'uncertain'."""
    body = json.dumps({
        "model": model,
        "temperature": 0,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
    }).encode("utf-8")
    req = urllib.request.Request(
        endpoint, data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer %s" % api_key})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except OSError as exc:
        raise JudgeError("Could not reach judge endpoint: %s" % exc)
    except (ValueError, UnicodeDecodeError) as exc:
        raise JudgeError("Judge endpoint returned invalid JSON: %s" % exc)
    try:
        text = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise JudgeError("Judge endpoint reply missed choices[0].message.content.")
    return parse_response(text)


def render_assessment(student, filename, assessment):
    """Render the assessment for the terminal."""
    lines = [
        "Writeprint LLM assessment (second opinion — advisory only)",
        "  Student:    %s" % student,
        "  Submission: %s" % filename,
        "  Reading:    %s (confidence %.2f)" % (
            assessment["consistency"].upper(), assessment["confidence"]),
        "",
    ]
    for reason in assessment["reasons"]:
        lines.append("    - %s" % reason)
    lines += ["", "  Caveat: %s" % assessment["caveat"],
              "A statistical check plus a teacher's judgment outrank this."]
    return "\n".join(lines)
