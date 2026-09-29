"""Baseline profiles and submission comparison."""

import math

# Mean-absolute-z bands. Tuned on the bundled samples; re-calibrate on
# real classroom data before relying on them (see README).
BAND_CONSISTENT = 1.2
BAND_REVIEW = 1.5


def build_baseline(feature_dicts):
    """Build a baseline profile from 2+ samples of known-genuine writing.

    Returns {"features": {name: {"mean": ..., "std": ...}}, "n_samples": N}.
    """
    if len(feature_dicts) < 2:
        raise ValueError("Need at least 2 baseline samples, got %d" % len(feature_dicts))
    names = feature_dicts[0].keys()
    profile = {}
    for name in names:
        vals = [fd[name] for fd in feature_dicts]
        mean = sum(vals) / len(vals)
        var = sum((v - mean) ** 2 for v in vals) / len(vals)
        std = math.sqrt(var)
        # Floor: with few baseline samples a feature can show zero
        # variance, which would make any tiny deviation an infinite
        # z-score (and a false accusation). The floor keeps rare
        # features calm while preserving sensitivity on stable ones.
        std = max(std, 0.25 * abs(mean) + 0.05)
        profile[name] = {"mean": mean, "std": std}
    return {"features": profile, "n_samples": len(feature_dicts)}


def compare(features, baseline, bands=None, eps=1e-9):
    """Compare a submission against a baseline profile.

    bands overrides (BAND_CONSISTENT, BAND_REVIEW), e.g. with values
    from `writeprint calibrate --out`. Returns {"score": mean |z| (full precision — round only for display),
 "band": ..., "flags": [...]} where flags are per-feature
 divergences with |z| >= 2, sorted worst first.
 """
    consistent_band, review_band = bands or (BAND_CONSISTENT, BAND_REVIEW)
    prof = baseline["features"]
    scored = {}
    for name, stats in prof.items():
        z = abs(features.get(name, 0.0) - stats["mean"]) / stats["std"]
        # Cap: no single habit may dominate the overall score.
        scored[name] = min(z, 5.0)
    score = sum(scored.values()) / len(scored) if scored else 0.0
    if score < consistent_band:
        band = "consistent"
    elif score < review_band:
        band = "mild divergence"
    else:
        band = "worth a conversation"
    flags = [
        {
            "feature": name,
            "value": round(features.get(name, 0.0), 3),
            "baseline_mean": round(prof[name]["mean"], 3),
            "z": round(z, 2),
        }
        for name, z in sorted(scored.items(), key=lambda kv: kv[1], reverse=True)
        if z >= 2.0
    ]
    return {"score": score, "band": band, "flags": flags}


def render_report(student, filename, result):
    """Render a teacher-readable report (advisory, never a verdict)."""
    lines = [
        "Writeprint report",
        "  Student:    %s" % student,
        "  Submission: %s" % filename,
        "  Score:      %.3f (mean |z| vs. baseline)" % result["score"],
        "  Reading:    %s" % result["band"].upper(),
        "",
    ]
    if result["flags"]:
        lines.append("  Most divergent habits:")
        for f in result["flags"][:8]:
            lines.append(
                "    - %s: submission %.3f vs. baseline avg %.3f (z=%s)"
                % (f["feature"], f["value"], f["baseline_mean"], f["z"])
            )
        lines.append("")
    lines.append(
        "Note: this report flags writing habits worth a conversation. "
        "It does not determine who wrote a text."
    )
    return "\n".join(lines)
