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
    "examfm": SubjectInfo(
        "examfm", "Exam FM — Financial Mathematics",
        "Generator mode: compound interest, annuities, perpetuities, loans.",
    ),
    "examp": SubjectInfo(
        "examp", "Exam P — Probability",
        "Generator mode: combinatorics, distributions, expectation, joint/CLT.",
    ),
}

from engine.subjects import examp as _examp  # noqa: E402, F401
from engine.subjects.databases import generators as _db_gen  # noqa: E402, F401
from engine.subjects.databases import solve as _db_solve  # noqa: E402, F401
from engine.subjects.diffeq import generators as _diffeq_gen  # noqa: E402, F401
from engine.subjects.diffeq import solve as _diffeq_solve  # noqa: E402, F401
from engine.subjects.econ import generators as _econ_gen  # noqa: E402, F401
from engine.subjects.econ import solve as _econ_solve  # noqa: E402, F401
from engine.subjects.examfm import generators as _fm_gen  # noqa: E402, F401
from engine.subjects.examfm import solve as _fm_solve  # noqa: E402, F401
from engine.subjects.proofs import generators as _proofs_gen  # noqa: E402, F401
from engine.subjects.proofs import solve as _proofs_solve  # noqa: E402, F401
