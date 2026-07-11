# my-grader — agent instructions

You are developing **my-grader**, a MyThingsLab My[X] tool.

**Inherited rules:** obey [`./HARNESS.md`](./HARNESS.md) in full — the vendored
MyThingsLab build-harness rules. Do not restate or override them. Anything not
covered here defers to `HARNESS.md`, then `my-things-core/docs/CONVENTIONS.md`.

## This tool

- **Purpose:** the learn-loop's **summative assessment** step. `grade` takes a
  whole mock exam or past paper (a TOML file of question/answer entries) and
  grades every answer against a document corpus (via `mythings.corpus`) in one
  pass, records a per-question `Attempt` to the mastery ledger
  (`mythings.mastery`, `kind="exam"`), and prints a per-topic report ordered
  weakest-first — the bulk re-rank signal the study loop acts on. Where
  `my-professor grade` scores one answer interactively, `my-grader` scores an
  entire paper at once.
- **The single Engine call:** exactly one per run — the whole exam is graded in a
  single call ("grade each answer against its excerpts; reply per question, in
  order"). Against `NoopEngine` every item degrades to a fixed `partial` (0.5)
  stub, never a fabricated grade.
- **Invariants / rules:** exactly one Engine call per run, regardless of exam
  length. Grading rests only on the shown excerpts; never invents a correct
  answer. A short or malformed reply degrades the missing questions to a stub —
  questions are never silently dropped. Per-question attempts append to the
  append-only local mastery ledger; never a PR. No `Workspace`, no GitHub.
- **Backlog label:** `my-grader`
