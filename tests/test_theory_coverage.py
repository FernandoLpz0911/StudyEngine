"""Every concept must ship teachable theory so a beginner can learn it cold."""
import json
import re
from pathlib import Path

import pytest

SEEDS = sorted(Path("data/subjects").glob("*/concept_graph.seed.json"))
MIN_CHARS = 120

# theory_md renders through react-markdown + remark-math (frontend/src/components/
# Markdown.tsx), not the backend's Tex component, and remark-math's `$` delimiter
# scanner has an asymmetric escaping bug: a backslash-escaped `\$` correctly fails
# to *open* a math span, but does NOT stop an already-open span from *closing* on
# it — so `\$` nested inside real math (e.g. currency inside `$\mu = \$500$`)
# truncates or corrupts the formula and can cascade into a KaTeX parse error for
# the rest of the page. Use the `&#36;` HTML entity for a literal dollar sign
# instead. Separately, a `$$...$$` block whose fence isn't alone on its own line
# isn't recognized as block math at all and falls into the same trap.
_DISPLAY_MATH = re.compile(r"\$\$(.*?)\$\$", re.DOTALL)


def _escaped_dollar_breaks_math(theory: str) -> list[str]:
    """Paragraphs where remark-math's asymmetric \\$ escaping bug (see module
    docstring above) leaves a math span open at paragraph end — the tell that an
    escaped dollar sign got consumed as a closer instead of staying literal."""
    broken = []
    for para in re.split(r"\n\s*\n", theory):
        in_math = False
        for i, ch in enumerate(para):
            if ch != "$":
                continue
            if in_math:
                in_math = False
            elif not (i > 0 and para[i - 1] == "\\"):
                in_math = True
        if in_math:
            broken.append(para)
    return broken


def _concepts():
    for seed in SEEDS:
        data = json.loads(seed.read_text())
        for c in data["concepts"]:
            yield seed.parent.name, c


@pytest.mark.parametrize("subject,concept",
                         [(s, c) for s, c in _concepts()],
                         ids=[f"{s}:{c['id']}" for s, c in _concepts()])
def test_concept_has_theory(subject, concept):
    theory = (concept.get("theory_md") or "").strip()
    assert len(theory) >= MIN_CHARS, (
        f"{subject}/{concept['id']} has thin/missing theory_md "
        f"({len(theory)} chars)"
    )


@pytest.mark.parametrize("subject,concept",
                         [(s, c) for s, c in _concepts()],
                         ids=[f"{s}:{c['id']}" for s, c in _concepts()])
def test_theory_math_is_remark_safe(subject, concept):
    theory = concept.get("theory_md") or ""
    for m in _DISPLAY_MATH.finditer(theory):
        assert "\n" not in m.group(1), (
            f"{subject}/{concept['id']}: multi-line $$...$$ block — remark-math only "
            "recognizes a $$ fence alone on its own line; join the block to one line."
        )
    broken = _escaped_dollar_breaks_math(theory)
    assert not broken, (
        f"{subject}/{concept['id']}: \\$ inside a math span will truncate/corrupt it "
        f"(remark-math doesn't honor the escape there). Use &#36; instead. Paragraph: "
        f"{broken[0]!r}"
    )


def test_all_subjects_present():
    names = {s.parent.name for s in SEEDS}
    assert {"databases", "diffeq", "econ", "proofs", "examp", "examfm"} <= names
