# HonorCode

**Authorship verification for the classroom — not an AI detector.**

HonorCode compares a student's submission against that student's *own*
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
punctuation, contractions, function-word rates — form a writing
fingerprint that is stable per author and hard to fake wholesale. HonorCode measures divergence
from that baseline.

## Quickstart (no dependencies, Python 3.8+)

```bash
# 1. Build a baseline from 2+ samples of known-genuine writing
python -m honorcode.cli build samples/student_a_baseline1.txt \
    samples/student_a_baseline2.txt \
    -o baselines/student_a.json --student student_a

# 2. Check a submission
python -m honorcode.cli check baselines/student_a.json \
    samples/student_a_homework_genuine.txt
```

## Browser UI (no dependencies, runs offline)

```bash
python -m honorcode.cli serve
# → open http://127.0.0.1:8765
```

Paste 2+ baseline samples and a submission into the page and get the
report rendered with band coloring — plus a print-friendly layout for
parent/teacher conferences (just hit *Print report*). The server binds
to localhost only, ships zero external assets, and makes zero network
calls: student text never leaves the machine.

## Batch scoring to CSV

```bash
python -m honorcode.cli batch baselines/student_a.json \
    homework1.txt homework2.txt homework3.txt \
    -o results.csv [--thresholds baselines/student_a.thresholds.json]
```

One row per submission — student, file, score, band, flag count, top
divergent habits — ready for gradebook-adjacent workflows.

## LLM judge (opt-in second opinion, v1.6)

For the nuanced middle (`mild divergence`), an optional LLM pass can
weigh the habits in prose. Offline-first: it does nothing unless you
configure it.

```bash
export HONORCODE_JUDGE_URL=https://your-endpoint/v1/chat/completions
export HONORCODE_JUDGE_MODEL=your-model
export HONORCODE_JUDGE_KEY=...   # omit for local servers like Ollama
python -m honorcode.cli judge baselines/student_a.json submission.txt
```

Any OpenAI-compatible endpoint works, including a fully local Ollama
server. Three rules, enforced by design:

1. **It can only advise.** Output is consistency + confidence + reasons,
   always labeled advisory; unparseable replies degrade to `uncertain`,
   never to a false verdict.
2. **Student text leaves the machine only if you say so.** No endpoint,
   no call. Prefer local models; get consent otherwise.
3. **Statistics + teacher outrank it.** The last line of every
   assessment says so.

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

## Validation on real prose (Project Gutenberg)

Short informal writing separates well. Long-form literary prose is
harder — and we publish the miss, not just the hits. Three public-domain
authors (Twain, Austen, Doyle), ~500-word passages from different parts
of each book, default bands:

| Baseline ↓ / Held-out → | Twain | Austen | Doyle |
|---|---|---|---|
| **Twain** | 0.99 consistent | 1.06 consistent | 1.12 consistent |
| **Austen** | 1.11 consistent | 0.78 consistent | 0.74 consistent |
| **Doyle** | 1.11 consistent | 1.03 consistent | 0.84 consistent |

Two findings:

1. **Within-author stability holds on real data.** Every held-out
   passage reads *consistent* against its own author's baseline —
   the method recognizes the same hand across different chapters.
2. **Cross-author separation fails here.** Twain, Austen, and Doyle
   all read "consistent" against each other's baselines. Long formal
   prose shares function-word distributions; the habit markers that
   separate casual student writing (contractions, first person,
   exclamation) barely vary across novels. Even dialogue density
   (Twain/Doyle quote heavily, Austen doesn't) proved scene-dependent
   rather than author-stable, so it was left out.

Honest scope: HonorCode distinguishes voices with strong personal
habit markers. Telling apart polished authors in a shared register —
or a student paraphrasing *well* — is beyond v1's features. Corpus:
`samples/gutenberg_*` (Huck Finn, Pride & Prejudice, The Adventures
of Sherlock Holmes; all public domain).

## Validation on real student writing (ASAP)

Literature was step one; real classroom writing is step two. The
Hewlett Foundation's ASAP set 1 — ~1,700 de-identified persuasive
letters by US students in grades 7–10 — studied 300 essays at default
bands. One essay per student, so each essay was split into thirds
(leave-one-out within, cross-student across, same prompt throughout):

| Check (n) | Consistent | Mild | Review | Mean score |
|---|---|---|---|---|
| Within-essay thirds (900) | 856 (95.1%) | 41 | 3 | 0.815 |
| Cross-student, same prompt (300) | 266 (88.7%) | 28 | 6 | 0.924 |

What this means, plainly:

- **False alarms are rare (good).** Genuine student writing almost
  never strongly flags against itself — 258 of 300 essays fully
  consistent across all three thirds.
- **Same-prompt catch rate is weak (limitation).** Different students
  answering the same prompt write similarly enough that only 11.3%
  flag at all, 2.0% strongly. Topic-locked school writing is
  homogeneous; the tool's strength is strongly divergent work
  (our LLM-polished suspect scores 2.0 — far above this whole
  distribution), not subtle same-assignment substitution.
- Caveats both ways: thirds share topic/vocabulary (optimistic for
  within-rates) but are short and same-prompt (pessimistic for
  cross-rates). Fixture essays in `samples/asap/` (with `SOURCE.md`
  attribution); study script kept out of the repo, method above is
  the full spec.

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
python -m honorcode.cli calibrate \
    --samples genuine1.txt genuine2.txt genuine3.txt \
    --suspect suspect1.txt \
    --student student_a -o baselines/student_a.thresholds.json

# Use the calibrated threshold when checking
python -m honorcode.cli check baselines/student_a.json submission.txt \
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

1. **Extract** (`honorcode/features.py`) — 33 stylometric features per text:
   sentence/word length, type-token ratio, long-word ratio, first-person and
   contraction rates, punctuation rates, and 20 function-word rates.
   All rates are per-100-words so texts of different lengths compare fairly.
2. **Baseline** (`honorcode/compare.py`) — per-feature mean/std across the
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

- [x] Per-classroom calibration helper (`honorcode calibrate`, v1.1)
- [x] Local browser UI + print-friendly report (`honorcode serve`, v1.2)
- [x] Two-student validation corpus + CSV batch export (`honorcode batch`, v1.3)
- [x] Real-prose validation: Gutenberg corpus, honest negative result (v1.4)
- [x] Real student writing: ASAP false-flag study, published rates (v1.5)
- [x] Opt-in LLM judge for nuanced cases, offline by default (v1.6)
- [ ] Classroom pilot: multi-sample baselines from live student work
