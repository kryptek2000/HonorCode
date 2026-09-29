"""Threshold calibration on labeled classroom data.

Methodology:
- Genuine scores come from leave-one-out cross-validation: each
  known-genuine sample is scored against a baseline built from the
  *other* samples. This measures how much a student's own writing
  naturally varies, without any in-sample optimism.
- Suspect scores come from known-suspect pieces scored against the
  full baseline.
- Candidate thresholds are swept and scored with precision/recall/F1.
  The recommended threshold maximizes F1; ties break toward the
  *higher* threshold, because a false flag (accusing a student) is
  the costlier error for this tool.
"""

from .compare import build_baseline, compare
from .features import extract


def loo_genuine_scores(texts):
    """Score each genuine sample against a baseline of the others."""
    if len(texts) < 3:
        raise ValueError(
            "Leave-one-out needs at least 3 genuine samples, got %d" % len(texts)
        )
    feats = [extract(t) for t in texts]
    scores = []
    for i in range(len(feats)):
        others = feats[:i] + feats[i + 1:]
        baseline = build_baseline(others)
        scores.append(compare(feats[i], baseline)["score"])
    return scores


def suspect_scores(texts, baseline):
    """Score known-suspect pieces against the full baseline."""
    return [compare(extract(t), baseline)["score"] for t in texts]


def confusion(scores_labels, threshold):
    """Count (tp, fp, tn, fn) flagging score >= threshold as suspect."""
    tp = fp = tn = fn = 0
    for score, is_suspect in scores_labels:
        flagged = score >= threshold
        if is_suspect and flagged:
            tp += 1
        elif is_suspect:
            fn += 1
        elif flagged:
            fp += 1
        else:
            tn += 1
    return tp, fp, tn, fn


def sweep(scores_labels):
    """Sweep each distinct score as a candidate threshold.

    Returns rows sorted by threshold, each with tp/fp/tn/fn,
    precision, recall, f1, accuracy.
    """
    rows = []
    for threshold in sorted({s for s, _ in scores_labels}):
        tp, fp, tn, fn = confusion(scores_labels, threshold)
        precision = tp / (tp + fp) if (tp + fp) else 1.0
        recall = tp / (tp + fn) if (tp + fn) else 1.0
        f1 = (
            2 * precision * recall / (precision + recall)
            if (precision + recall)
            else 0.0
        )
        total = tp + fp + tn + fn
        rows.append({
            "threshold": threshold,  # full precision; round only for display
            "tp": tp, "fp": fp, "tn": tn, "fn": fn,
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "accuracy": round((tp + tn) / total, 3) if total else 0.0,
        })
    return rows


def recommend(rows):
    """Pick the best row: highest F1, ties toward fewer false flags."""
    return max(rows, key=lambda r: (r["f1"], r["threshold"]))


def render_table(rows, best):
    """Render the sweep as a teacher-readable table."""
    lines = [
        "threshold | flagged tp/fp | missed fn | precision | recall | f1",
        "----------|---------------|-----------|-----------|--------|----",
    ]
    for r in rows:
        mark = "  <-- recommended" if r is best else ""
        lines.append(
            "%9.3f | %5d / %-5d | %9d | %9.3f | %6.3f | %.3f%s"
            % (r["threshold"], r["tp"], r["fp"], r["fn"],
               r["precision"], r["recall"], r["f1"], mark)
        )
    lines.append("")
    lines.append(
        "Recommended flag threshold %.3f: precision %.3f, recall %.3f, F1 %.3f "
        "(%d genuine, %d suspect samples)."
        % (best["threshold"], best["precision"], best["recall"], best["f1"],
           best["tn"] + best["fp"], best["tp"] + best["fn"])
    )
    return "\n".join(lines)
