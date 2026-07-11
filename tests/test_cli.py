from __future__ import annotations

from pathlib import Path

import pytest

from mygrader.cli import main

_TEXT = (
    "The EM algorithm alternates an E-step and an M-step. The E-step computes "
    "responsibilities. PCA projects onto the leading eigenvectors of the covariance matrix."
)
_EXAM = (
    '[[answer]]\ntopic = "EM algorithm"\nquestion = "What is the E-step?"\n'
    'answer = "computes responsibilities"\n\n'
    '[[answer]]\ntopic = "PCA"\nquestion = "What is PCA?"\nanswer = "no idea"\n'
)


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    p = tmp_path / "notes.txt"
    p.write_text(_TEXT, encoding="utf-8")
    return p


@pytest.fixture
def exam(tmp_path: Path) -> Path:
    p = tmp_path / "exam.toml"
    p.write_text(_EXAM, encoding="utf-8")
    return p


def _fake_engine(monkeypatch) -> None:
    from mythings.engine import EngineResult

    import mygrader.cli as cli

    reply = (
        '{"grades": [{"verdict": "correct", "score": 1.0},'
        '{"verdict": "incorrect", "score": 0.0, "gaps": ["eigenvectors"]}]}'
    )

    class Fake:
        def run(self, _request):
            return EngineResult(text=reply)

    monkeypatch.setattr(cli, "_engine", lambda _name: Fake())


def test_grade_reports_and_records(corpus: Path, exam: Path, tmp_path: Path, monkeypatch,
                                   capsys: pytest.CaptureFixture[str]) -> None:
    _fake_engine(monkeypatch)
    ledger = tmp_path / "mastery.jsonl"
    rc = main(["grade", "--exam", str(exam), "--corpus", str(corpus),
               "--engine", "claude", "--ledger", str(ledger)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Overall" in out and "pca" in out.lower()
    # one recorded attempt per question
    assert len(ledger.read_text(encoding="utf-8").strip().splitlines()) == 2


def test_no_record_leaves_ledger_untouched(corpus: Path, exam: Path, tmp_path: Path, monkeypatch,
                                           capsys: pytest.CaptureFixture[str]) -> None:
    _fake_engine(monkeypatch)
    ledger = tmp_path / "mastery.jsonl"
    main(["grade", "--exam", str(exam), "--corpus", str(corpus),
          "--engine", "claude", "--ledger", str(ledger), "--no-record"])
    assert not ledger.exists()


def test_missing_exam_answers_is_error(corpus: Path, tmp_path: Path,
                                       capsys: pytest.CaptureFixture[str]) -> None:
    empty = tmp_path / "empty.toml"
    empty.write_text("", encoding="utf-8")
    rc = main(["grade", "--exam", str(empty), "--corpus", str(corpus)])
    assert rc == 1
    assert "no answers found" in capsys.readouterr().out


def test_missing_corpus_is_error(exam: Path, tmp_path: Path,
                                 capsys: pytest.CaptureFixture[str]) -> None:
    rc = main(["grade", "--exam", str(exam), "--corpus", str(tmp_path / "none")])
    assert rc == 1
    assert "no corpus files found" in capsys.readouterr().out
