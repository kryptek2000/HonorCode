"""Writeprint command line: build baselines, check submissions."""

import argparse
import json
import os
import sys

from .features import extract
from .compare import build_baseline, compare, render_report


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
    result = compare(extract(text), baseline)
    print(render_report(baseline.get("student", "?"), args.submission, result))


def main(argv=None):
    parser = argparse.ArgumentParser(prog="writeprint", description="Authorship verification for the classroom.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_build = sub.add_parser("build", help="Build a baseline from known-genuine samples.")
    p_build.add_argument("samples", nargs="+", help="2+ baseline text files.")
    p_build.add_argument("-o", "--out", required=True, help="Where to write the baseline JSON.")
    p_build.add_argument("--student", required=True, help="Student label for the profile.")
    p_build.set_defaults(func=cmd_build)

    p_check = sub.add_parser("check", help="Check a submission against a baseline.")
    p_check.add_argument("baseline", help="Baseline JSON from 'build'.")
    p_check.add_argument("submission", help="Submission text file to check.")
    p_check.set_defaults(func=cmd_check)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
