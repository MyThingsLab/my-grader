# my-grader

[![CI](https://github.com/MyThingsLab/my-grader/actions/workflows/ci.yml/badge.svg)](https://github.com/MyThingsLab/my-grader/actions/workflows/ci.yml) [![codecov](https://codecov.io/gh/MyThingsLab/my-grader/branch/main/graph/badge.svg)](https://codecov.io/gh/MyThingsLab/my-grader) ![Python](https://img.shields.io/badge/python-3.11%2B-blue) [![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

The learn-loop's **summative assessment** step. Grade a whole mock exam or past
paper against a document corpus in one pass — get a per-topic report, weakest
first, and record every question as mastery so the next study session targets
your real gaps.

Where [`my-professor`](../my-professor) grades one answer interactively,
`my-grader` scores an entire paper at once and produces the bulk re-rank signal
for the loop. It sits on the [MyThingsLab](../my-things-core) `mythings.corpus`
(grounding) and `mythings.mastery` (per-topic feedback) seams.

## Usage

Write your answers as a TOML exam file:

```toml
[[answer]]
topic = "EM algorithm"
question = "State the two steps of EM and what each does."
answer = "E-step computes responsibilities; M-step maximizes the expected log-likelihood."

[[answer]]
topic = "PCA"
question = "What does PCA maximize?"
answer = "variance along the leading eigenvectors"
```

```bash
mygrader grade --exam exam.toml --corpus ~/Desktop/unsupervised_learning.pdf \
  --engine claude --ledger .mythings/mastery.jsonl
```

`--engine noop` (default) grades every answer to a fixed `partial` stub (no Engine
call); use `--engine claude` for a real grade. `--no-record` prints the report
without touching the ledger. `topic` is optional per answer (derived from the
question if absent).

## How it works

The whole exam is graded in **one Engine call**: each question is shown with the
corpus excerpts shortlisted for it, and the model returns a verdict, score, and
gaps per question, in order. A short or malformed reply degrades the missing
questions to a stub — questions are never silently dropped. Each result appends a
per-question `Attempt` (`kind="exam"`) to the local mastery ledger, and the report
orders topics weakest-first.

## Install (development)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ../my-things-core -e ".[dev]"
pytest
```

## License

MIT — see [`LICENSE`](LICENSE).
