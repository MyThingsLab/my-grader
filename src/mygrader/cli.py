from __future__ import annotations

import argparse
from pathlib import Path

from mythings.engine import build_engine_from_args
from mythings.mastery import record

from mygrader.grader import (
    Report,
    grade_exam,
    load_corpus,
    load_exam,
    render_report,
    resolve_extractor,
    to_attempts,
)

BACKLOG_LABEL = "my-grader"
DEFAULT_LEDGER = Path(".mythings/mastery.jsonl")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mygrader",
        description="Grade a whole mock exam against a corpus and record per-topic mastery.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    grade_p = sub.add_parser("grade", help="grade a mock-exam file and report per-topic results")
    grade_p.add_argument("--exam", type=Path, required=True,
                         help="TOML file of [[answer]] entries (topic, question, answer)")
    grade_p.add_argument("--corpus", type=Path, action="append", required=True,
                         help="file or directory of source material (repeatable)")
    grade_p.add_argument("--top", type=int, default=6, help="excerpts per question")
    grade_p.add_argument("--engine", choices=("noop", "claude"), default="noop")
    grade_p.add_argument("--cache", type=Path, help="cache extracted PDF text under this directory")
    grade_p.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER,
                         help="mastery ledger to append per-question attempts to")
    grade_p.add_argument("--no-record", action="store_true", help="grade but do not record")

    args = parser.parse_args(argv)

    answers = load_exam(args.exam)
    if not answers:
        print("no answers found in the exam file")
        return 1

    documents, chunks = load_corpus(args.corpus, extractor=resolve_extractor(args.cache))
    if not documents:
        print("no corpus files found")
        return 1

    grades = grade_exam(answers, chunks, build_engine_from_args(args), top=args.top)
    print(render_report(Report(items=tuple(grades))))
    if not args.no_record:
        for attempt in to_attempts(grades):
            record(args.ledger, attempt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
