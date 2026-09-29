# Writeprint

**Authorship verification for the classroom — not an AI detector.**

Writeprint compares a student's submission against that student's *own*
known-genuine writing and reports how far their writing habits diverge.
The output is a reading — *consistent*, *mild divergence*, or
*worth a conversation* — never a verdict. A human teacher always decides
what happens next.

## Why this instead of an "AI detector"?

Generic "was this written by AI?" classifiers are unreliable: meaningful
false-positive rates, bias against non-native English writers, and trivial
evasion via paraphrasing. Accusing a student on that basis is unjust.

Asking "was this written by *this student*?" is a far more tractable
question. Individual writing habits — sentence length, favorite transitions,
punctuation, contractions, function-word rates — form a *writeprint* that is
stable per author and hard to fake wholesale. Writeprint measures divergence
from that baseline.

## Quickstart (no dependencies, Python 3.8+)

```bash
# 1. Build a baseline from 2+ samples of known-genuine writing
python -m writeprint.cli build samples/student_a_baseline1.txt \
    samples/student_a_baseline2.txt \
    -o baselines/student_a.json --student student_a

# 2. Check a submission
python -m writeprint.cli check baselines/student_a.json \
    samples/student_a_homework_genuine.txt
```

## Browser UI (no dependencies, runs offline)

```bash
python -m writeprint.cli serve
# → open http://127.0.0.1:8765
```

Paste 2+ baseline samples and a submission into the page and get the
report rendered with band coloring — plus a print-friendly layout for
parent/teacher conferences (just hit *Print report*). The server binds
to localhost only, ships zero external assets, and makes zero network
calls: student text never leaves the machine.

## Batch scoring to CSV

```bash
python -m writeprint.cli batch baselines/student_a.json \
    homework1.txt homework2.txt homework3.txt \
    -o results.csv [--thresholds baselines/student_a.thresholds.json]
```

One row per submission — student, file, score, band, flag count, top
divergent habits — ready for gradebook-adjacent workflows.

## Validation: baselines are student-specific

The bundled two-student corpus proves the point of the tool. Scored
with default bands:

| Baseline ↓ / Submission → | A's genuine | B's genuine | A's suspect |
|---|---|---|---|
| **A's baseline** | 0.83 consistent | 1.59 conversation | 2.01 conversation |
| **B's baseline** | 1.88 conversation | 0.47 consistent | 1.72 conversation |

Own work passes; anyone else's — even genuine homework by a real
classmate on the same assignment — gets flagged. A shared cheat sheet
or one student's essay submitted under another name lights up both
baselines. (Scores from the bundled toy corpus; re-run on real data.)

Try the bundled demo: the genuine homework reads **CONSISTENT**
(score ~0.8) while the suspect piece reads **WORTH A CONVERSATION**
(score ~2.0), with the divergent habits listed per feature.

```bash
python -m unittest discover -s tests   # smoke tests + demo expectations
```

## Calibrating thresholds (do this on real data)

The built-in bands are tuned on toy samples. For classroom use, calibrate
on your own labeled set — genuine pieces plus known-suspect ones:

```bash
# Leave-one-out scores each genuine sample against the others,
# sweeps candidate thresholds, and recommends one (max F1,
# ties break toward fewer false flags).
python -m writeprint.cli calibrate \
    --samples genuine1.txt genuine2.txt genuine3.txt \
    --suspect suspect1.txt \
    --student student_a -o baselines/student_a.thresholds.json

# Use the calibrated threshold when checking
python -m writeprint.cli check baselines/student_a.json submission.txt \
    --thresholds baselines/student_a.thresholds.json
```

Two warnings, both serious:

1. **Sample size.** The math needs dozens of labeled pieces per class to
   mean anything. With a handful of samples the "recommended" threshold is
   a knife-edge fit to your tiny dataset — better than a guess, but only
   just. Collect broadly before trusting it.
2. **Full precision internally, rounded for display.** Scores are computed
   at full float precision and only rounded when printed, so a report
   showing `2.007` against a threshold of `2.007` can still read either
   side of the line. The band is always computed on the unrounded value.

## How it works

1. **Extract** (`writeprint/features.py`) — 33 stylometric features per text:
   sentence/word length, type-token ratio, long-word ratio, first-person and
   contraction rates, punctuation rates, and 20 function-word rates.
   All rates are per-100-words so texts of different lengths compare fairly.
2. **Baseline** (`writeprint/compare.py`) — per-feature mean/std across the
   student's samples, with a variance floor so rare habits can't produce
   explosive z-scores from sparse data.
3. **Compare** — mean absolute z-score across features, with per-feature
   capping so no single habit dominates. Bands (`BAND_CONSISTENT`,
   `BAND_REVIEW`) are tuned on the bundled samples.

## Honest limitations (read before using on real students)

- Thresholds are calibrated on toy data. **Re-calibrate on real classroom
  writing before relying on them**, and treat every flag as the start of a
  conversation, not evidence.
- Two baseline samples is the minimum; more is better. Baselines go stale as
  students grow — refresh them each term.
- A skilled mimic (human or machine) imitating the student's own style can
  pass. This raises the bar; it does not end cheating.
- Draft history and process-based assessment remain the gold standard.
  Use this *alongside* them, not instead of them.

## Roadmap

- [x] Per-classroom calibration helper (`writeprint calibrate`, v1.1)
- [x] Local browser UI + print-friendly report (`writeprint serve`, v1.2)
- [x] Two-student validation corpus + CSV batch export (`writeprint batch`, v1.3)
- [ ] Larger validation corpus (real classroom data)
- [ ] Optional LLM judge for nuanced cases (v1 is fully offline by design)
