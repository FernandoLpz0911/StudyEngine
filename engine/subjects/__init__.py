"""Subject registry: metadata + which generators back each subject.

Importing this package runs every subject module's @register decorators, so the
problem generators are available to engine.generation.generate.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SubjectInfo:
    key: str
    title: str
    blurb: str


SUBJECTS: dict[str, SubjectInfo] = {
    "diffeq": SubjectInfo(
        "diffeq", "MATH 220 — Differential Equations",
        "Generator mode: ODEs, Laplace transforms — closed-form, auto-graded.",
    ),
    "databases": SubjectInfo(
        "databases", "CS 480 — Database Systems",
        "Mixed: normalization generators + recall cards for design/recovery/concurrency.",
    ),
    "proofs": SubjectInfo(
        "proofs", "MATH 250 — Intro to Advanced Maths",
        "Recall mode: definitions, theorems, and proof techniques.",
    ),
    "econ": SubjectInfo(
        "econ", "ECON 111 — Freakonomics",
        "Recall mode: incentives, concepts, and case studies.",
    ),
}

from engine.subjects.diffeq import generators as _diffeq_generators  # noqa: E402, F401
