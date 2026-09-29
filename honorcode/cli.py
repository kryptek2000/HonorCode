"""HonorCode command line: build baselines, check submissions."""

import argparse
import json
import os
import sys

from .features import extract
from .compare import BAND_CONSISTENT, build_baseline, compare, render_report
from .calibrate import (
    loo_genuine_scores,
    suspect_scores,
    sweep,
    recommend,
    render_table,
)
from .web import DEFAULT_PORT, serve
from .export import rows_for, write_csv
from .judge import (JudgeError, build_prompt, call_judge, judge_config,
                    render_assessment)


def cmd_build(args):
    texts = []
    for path in args.samples:
        with open(path, encoding="utf-8") as fh:
            texts.append(fh.read())
    profile = build_baseline([extract(t) for t in texts])
    profile["student"] = args.student
    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(profile, fh, indent=2)
    print("Baseline for '%s' written to %s (%d samples)" % (args.student, args.out, len(texts)))


def cmd_check(args):
    with open(args.baseline, encoding="utf-8") as fh:
        baseline = json.load(fh)
    with open(args.submission, encoding="utf-8") as fh:
        text = fh.read()
    bands = None
    if args.thresholds:
        with open(args.thresholds, encoding="utf-8") as fh:
            cfg = json.load(fh)
        bands = (BAND_CONSISTENT, cfg["flag_threshold"])
    result = compare(extract(text), baseline, bands=bands)
    print(render_report(baseline.get("student", "?"), args.submission, result))


def cmd_serve(args):
    serve(args.port)


def cmd_judge(args):
    with open(args.baseline, encoding="utf-8") as fh:
        baseline = json.load(fh)
    with open(args.submission, encoding="utf-8") as fh:
        text = fh.read()
    try:
        endpoint, api_key, model = judge_config(
            args.endpoint, args.key, args.model)
        system, user = build_prompt(
            baseline, text, baseline.get("student", "?"))
        assessment = call_judge(system, user, endpoint, api_key, model)
    except JudgeError as exc:
        print("honorcode judge: %s" % exc)
        raise SystemExit(2)
    print(render_assessment(baseline.get("student", "?"),
                            args.submission, assessment))


def cmd_batch(args):
    with open(args.baseline, encoding="utf-8") as fh:
        baseline = json.load(fh)
    bands = None
    if args.thresholds:
        with open(args.thresholds, encoding="utf-8") as fh:
            cfg = json.load(fh)
        bands = (BAND_CONSISTENT, cfg["flag_threshold"])
    submissions = []
    for path in args.submissions:
        with open(path, encoding="utf-8") as fh:
            submissions.append((path, fh.read()))
    n = write_csv(rows_for(baseline, submissions, bands=bands), args.out)
    print("Wrote %d rows to %s" % (n, args.out))


def cmd_calibrate(args):
    def read_many(paths):
        texts = []
        for path in paths:
            with open(path, encoding="utf-8") as fh:
                texts.append(fh.read())
        return texts

    genuine_texts = read_many(args.samples)
    suspect_texts = read_many(args.suspect)
    genuine = loo_genuine_scores(genuine_texts)
    full_baseline = build_baseline([extract(t) for t in genuine_texts])
    suspect = suspect_scores(suspect_texts, full_baseline)
    labeled = [(s, False) for s in genuine] + [(s, True) for s in suspect]
    rows = sweep(labeled)
    best = recommend(rows)
    print("Calibration for '%s' (%d genuine via leave-one-out, %d suspect)"
          % (args.student, len(genuine), len(suspect)))
    print(render_table(rows, best))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump({
                "student": args.student,
                "flag_threshold": best["threshold"],
                "precision": best["precision"],
                "recall": best["recall"],
                "f1": best["f1"],
                "n_genuine": len(genuine),
                "n_suspect": len(suspect),
            }, fh, indent=2)
        print("Thresholds written to %s" % args.out)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="honorcode", description="Authorship verification for the classroom.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_build = sub.add_parser("build", help="Build a baseline from known-genuine samples.")
    p_build.add_argument("samples", nargs="+", help="2+ baseline text files.")
    p_build.add_argument("-o", "--out", required=True, help="Where to write the baseline JSON.")
    p_build.add_argument("--student", required=True, help="Student label for the profile.")
    p_build.set_defaults(func=cmd_build)

    p_check = sub.add_parser("check", help="Check a submission against a baseline.")
    p_check.add_argument("baseline", help="Baseline JSON from 'build'.")
    p_check.add_argument("submission", help="Submission text file to check.")
    p_check.add_argument("--thresholds", default=None,
                         help="Thresholds JSON from 'calibrate --out' (overrides the review band).")
    p_check.set_defaults(func=cmd_check)

    p_cal = sub.add_parser("calibrate", help="Calibrate the flag threshold on labeled data.")
    p_cal.add_argument("--samples", nargs="+", required=True,
                       help="3+ known-genuine sample files (leave-one-out gives genuine scores).")
    p_cal.add_argument("--suspect", nargs="+", required=True,
                       help="Known-suspect sample files.")
    p_cal.add_argument("--student", required=True, help="Student label for the report.")
    p_cal.add_argument("-o", "--out", default=None,
                       help="Write recommended thresholds JSON for 'check --thresholds'.")
    p_cal.set_defaults(func=cmd_calibrate)

    p_serve = sub.add_parser("serve", help="Serve the local browser UI (127.0.0.1 only).")
    p_serve.add_argument("--port", type=int, default=DEFAULT_PORT,
                         help="Local port (default %d)." % DEFAULT_PORT)
    p_serve.set_defaults(func=cmd_serve)

    p_batch = sub.add_parser("batch", help="Score many submissions to a CSV file.")
    p_batch.add_argument("baseline", help="Baseline JSON from 'build'.")
    p_batch.add_argument("submissions", nargs="+", help="Submission text files.")
    p_batch.add_argument("-o", "--out", required=True, help="Where to write the CSV.")
    p_batch.add_argument("--thresholds", default=None,
                         help="Thresholds JSON from 'calibrate --out'.")
    p_batch.set_defaults(func=cmd_batch)

    p_judge = sub.add_parser("judge", help="Ask an LLM for a second opinion (opt-in).")
    p_judge.add_argument("baseline", help="Baseline JSON from 'build'.")
    p_judge.add_argument("submission", help="Submission text file to assess.")
    p_judge.add_argument("--endpoint", default=None,
                         help="Chat-completions URL (or HONORCODE_JUDGE_URL).")
    p_judge.add_argument("--key", default=None,
                         help="Bearer token (or HONORCODE_JUDGE_KEY).")
    p_judge.add_argument("--model", default=None,
                         help="Model name (or HONORCODE_JUDGE_MODEL).")
    p_judge.set_defaults(func=cmd_judge)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
