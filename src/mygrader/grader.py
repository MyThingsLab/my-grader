from __future__ import annotations

import json
import re
import tomllib
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from mythings.corpus import (
    Chunk,
    Document,
    Extractor,
    cached_extractor,
    chunk,
    extract,
    ingest,
    shortlist,
)
from mythings.engine import Engine, EngineRequest
from mythings.mastery import Attempt, now_iso

TOOL = "mygrader"
SOURCE = "my-grader"

TEXT_SUFFIXES = frozenset({".md", ".txt", ".rst", ".tex"})
CORPUS_SUFFIXES = TEXT_SUFFIXES | {".pdf"}

_FENCE_RE = re.compile(r"^```[a-zA-Z0-9]*\n?|\n?```$")
_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)
_VERDICT_SCORE = {"correct": 1.0, "partial": 0.5, "incorrect": 0.0}


def corpus_files(paths: Iterable[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files.extend(p for p in sorted(path.rglob("*")) if p.suffix.lower() in CORPUS_SUFFIXES)
        elif path.is_file():
            files.append(path)
    return files


def load_corpus(
    paths: Iterable[Path],
    *,
    target_chars: int = 1200,
    extractor: Extractor = extract,
) -> tuple[list[Document], list[Chunk]]:
    documents = ingest(corpus_files(paths), extractor=extractor)
    chunks = [c for doc in documents for c in chunk(doc, target_chars=target_chars)]
    return documents, chunks


def resolve_extractor(cache_dir: Path | None) -> Extractor:
    return extract if cache_dir is None else cached_extractor(cache_dir)


def _excerpts(chunks: Iterable[Chunk]) -> str:
    return "\n".join(
        f"[{c.doc_id}:{c.ordinal}] {' '.join(c.text.split())}" for c in chunks
    ) or "(no matching source excerpts)"


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "topic"


def _load_json(text: str) -> dict | None:
    # Strip the ```json fences the ClaudeCLIEngine sometimes emits (known core bug),
    # then fall back to the first {...} block. Copied across the study tools.
    stripped = _FENCE_RE.sub("", text.strip()).strip()
    if not stripped:
        return None
    candidates = [stripped]
    match = _OBJECT_RE.search(stripped)
    if match:
        candidates.append(match.group(0))
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


@dataclass(frozen=True)
class Answer:
    topic: str  # a topic label; slugged for the ledger
    question: str
    answer: str


@dataclass(frozen=True)
class ItemGrade:
    topic: str  # Topic.slug
    verdict: str  # correct | partial | incorrect
    score: float
    gaps: tuple[str, ...]


@dataclass(frozen=True)
class Report:
    items: tuple[ItemGrade, ...]

    @property
    def overall(self) -> float:
        return sum(i.score for i in self.items) / len(self.items) if self.items else 0.0

    def by_topic(self) -> list[tuple[str, float, int]]:
        # (topic, mean score, count), weakest first — the summative re-rank signal.
        buckets: dict[str, list[float]] = {}
        for i in self.items:
            buckets.setdefault(i.topic, []).append(i.score)
        rows = [(t, sum(s) / len(s), len(s)) for t, s in buckets.items()]
        return sorted(rows, key=lambda r: r[1])


def load_exam(path: str | Path) -> list[Answer]:
    data = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    answers: list[Answer] = []
    for row in data.get("answer", []):
        question = str(row.get("question", "")).strip()
        answer = str(row.get("answer", "")).strip()
        if not question:
            continue
        topic = str(row.get("topic", "")).strip() or question[:40]
        answers.append(Answer(topic=topic, question=question, answer=answer))
    return answers


SYSTEM = (
    "You grade a student's mock-exam answers against the source excerpts given for "
    "each question, and only those excerpts. Grade every question, in order. Reply as "
    'JSON: {"grades": [{"verdict": "correct|partial|incorrect", "score": 0.0-1.0, '
    '"gaps": ["short phrase the answer missed", ...]}, ...]} and nothing else, one '
    "entry per question in the same order. Never invent a correct answer the excerpts "
    "do not support."
)


def build_prompt(
    answers: list[Answer], excerpts: list[str]
) -> str:
    blocks = []
    for i, (ans, ex) in enumerate(zip(answers, excerpts, strict=True), 1):
        blocks.append(
            f"Question {i} (topic: {ans.topic}):\n{ans.question}\n"
            f"Student answer:\n{ans.answer or '(blank)'}\n"
            f"Excerpts:\n{ex}"
        )
    joined = "\n\n".join(blocks)
    return f"{joined}\n\nGrade all {len(answers)} answers, as JSON:"


def _item(topic: str, row: dict | None) -> ItemGrade:
    if not row:
        return ItemGrade(topic=topic, verdict="partial", score=0.5, gaps=())
    verdict = str(row.get("verdict", "partial")).lower()
    if verdict not in _VERDICT_SCORE:
        verdict = "partial"
    raw = row.get("score")
    score = float(raw) if isinstance(raw, (int, float)) else _VERDICT_SCORE[verdict]
    score = max(0.0, min(1.0, score))
    gaps = tuple(str(g) for g in row.get("gaps", []) if str(g).strip())
    return ItemGrade(topic=topic, verdict=verdict, score=score, gaps=gaps)


def grade_exam(
    answers: list[Answer],
    chunks: list[Chunk],
    engine: Engine,
    *,
    top: int = 6,
) -> list[ItemGrade]:
    if not answers:
        return []
    excerpts = [
        _excerpts(shortlist(chunks, f"{a.topic} {a.question}", top=top)) for a in answers
    ]
    reply = engine.run(EngineRequest(prompt=build_prompt(answers, excerpts), system=SYSTEM))
    parsed = _load_json(reply.text) or {}
    rows = parsed.get("grades", [])
    # Map by position; a short or empty reply degrades the missing items to a
    # partial stub rather than dropping questions from the exam.
    return [
        _item(slug(a.topic), rows[i] if i < len(rows) and isinstance(rows[i], dict) else None)
        for i, a in enumerate(answers)
    ]


def to_attempts(grades: Iterable[ItemGrade], *, now: str | None = None) -> list[Attempt]:
    stamp = now or now_iso()
    return [
        Attempt(topic=g.topic, at=stamp, score=g.score, kind="exam", gaps=g.gaps, source=SOURCE)
        for g in grades
    ]


def render_report(report: Report) -> str:
    if not report.items:
        return "no answers graded"
    lines = [
        f"Overall: {report.overall:.0%}  ({len(report.items)} questions)",
        "",
        "By topic (weakest first):",
    ]
    for topic, score, count in report.by_topic():
        lines.append(f"  {topic:<30} {score:5.0%}  ({count})")
    weak_gaps = [g for i in report.items if i.score < 1.0 for g in i.gaps]
    if weak_gaps:
        lines += ["", "Gaps to review:"]
        lines += [f"  - {g}" for g in dict.fromkeys(weak_gaps)]
    return "\n".join(lines)
