from __future__ import annotations

from pathlib import Path

from mythings.corpus import chunk, ingest
from mythings.engine import NoopEngine
from mythings.testing import ScriptedEngine

from mygrader.grader import (
    Answer,
    ItemGrade,
    Report,
    grade_exam,
    load_exam,
    render_report,
    slug,
    to_attempts,
)

_TEXT = (
    "The EM algorithm alternates an E-step and an M-step. The E-step computes "
    "responsibilities; the M-step maximizes the expected complete-data log-likelihood. "
    "PCA projects data onto the leading eigenvectors of the covariance matrix."
)


def _chunks():
    docs = ingest([Path("notes.txt")], extractor=lambda _p: _TEXT)
    return [c for d in docs for c in chunk(d, target_chars=300)]


_ANSWERS = [
    Answer("EM algorithm", "What is the E-step?", "computes responsibilities"),
    Answer("PCA", "What is PCA?", "no idea"),
]
_REPLY = (
    '{"grades": ['
    '{"verdict": "correct", "score": 1.0, "gaps": []},'
    '{"verdict": "incorrect", "score": 0.0, "gaps": ["leading eigenvectors"]}]}'
)


def test_grade_exam_is_one_engine_call_for_the_whole_paper() -> None:
    engine = ScriptedEngine(_REPLY)
    grades = grade_exam(_ANSWERS, _chunks(), engine)
    assert len(engine.calls) == 1  # the whole exam graded in a single call
    assert [g.verdict for g in grades] == ["correct", "incorrect"]
    assert [g.topic for g in grades] == ["em-algorithm", "pca"]
    assert grades[1].gaps == ("leading eigenvectors",)


def test_grade_strips_fences() -> None:
    grades = grade_exam(_ANSWERS[:1], _chunks(), ScriptedEngine(f"```json\n{_REPLY}\n```"))
    assert grades[0].verdict == "correct"


def test_short_reply_degrades_missing_items_not_drops_them() -> None:
    # Reply grades only the first question; the second must still appear as a stub.
    reply = '{"grades": [{"verdict": "correct", "score": 1.0}]}'
    grades = grade_exam(_ANSWERS, _chunks(), ScriptedEngine(reply))
    assert len(grades) == 2
    assert grades[1].verdict == "partial" and grades[1].score == 0.5


def test_noop_degrades_every_item_to_partial() -> None:
    grades = grade_exam(_ANSWERS, _chunks(), NoopEngine())
    assert [g.score for g in grades] == [0.5, 0.5]


def test_report_overall_and_weakest_first() -> None:
    report = Report(items=tuple(grade_exam(_ANSWERS, _chunks(), ScriptedEngine(_REPLY))))
    assert report.overall == 0.5
    ordered = report.by_topic()
    assert ordered[0][0] == "pca"  # weakest topic first
    assert "pca" in render_report(report).lower()


def test_to_attempts_records_one_per_question_as_exam_kind() -> None:
    grades = grade_exam(_ANSWERS, _chunks(), ScriptedEngine(_REPLY))
    attempts = to_attempts(grades)
    assert [a.topic for a in attempts] == ["em-algorithm", "pca"]
    assert all(a.kind == "exam" and a.source == "my-grader" for a in attempts)


def test_load_exam_reads_toml_and_derives_missing_topic(tmp_path: Path) -> None:
    exam = tmp_path / "exam.toml"
    exam.write_text(
        '[[answer]]\ntopic = "EM algorithm"\nquestion = "Q1?"\nanswer = "a1"\n\n'
        '[[answer]]\nquestion = "What is a martingale?"\nanswer = ""\n',
        encoding="utf-8",
    )
    answers = load_exam(exam)
    assert answers[0].topic == "EM algorithm"
    assert answers[1].topic == "What is a martingale?"  # derived from the question
    assert slug(answers[1].topic) == "what-is-a-martingale"


def test_empty_exam_yields_no_grades() -> None:
    assert grade_exam([], _chunks(), ScriptedEngine(_REPLY)) == []
    assert Report(items=()).overall == 0.0
    assert render_report(Report(items=())) == "no answers graded"
    assert ItemGrade("t", "partial", 0.5, ()).topic == "t"
