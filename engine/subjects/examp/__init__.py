"""Exam P (Probability) — ported from the LearningModel ancestor.

Importing this package registers all probability generators and their worked
solutions. The generator modules and solver share the same closed-form math, so
shown solutions never diverge from graded answers.
"""
from engine.subjects.examp import (
    continuous,  # noqa: F401
    discrete,  # noqa: F401
    multivariate,  # noqa: F401
    probability,  # noqa: F401
    solve,  # noqa: F401
)
