"""Turn the generators' plain-text math into KaTeX-ready LaTeX (web rendering only).

Generators emit human-readable statements that mix prose with math, e.g.
``Solve dy/dt = -0.32·y with y(0) = 7.6. Find y(3).``. The CLI prints these as-is;
the web client renders math properly, so the HTTP layer runs each generator string
through :func:`latexify`, which wraps the math fragments in ``$...$`` and maps the
ASCII/Unicode operators to LaTeX. Prose words are left untouched.

Heuristic, not a parser: it groups runs of "mathy" whitespace-separated tokens,
delimits them, and translates operators inside each run. Recall (prose) items are
never passed through here.
"""
from __future__ import annotations

import re

# Multi-/single-char → LaTeX, applied inside a math run only (after tokenising, so
# the inserted spaces can't break word boundaries).
_SYMBOLS = {
    "·": r"\cdot ",
    "*": r"\cdot ",
    "×": r"\times ",
    "÷": r"\div ",
    "∩": r"\cap ",
    "∪": r"\cup ",
    "≤": r"\le ",
    "≥": r"\ge ",
    "≠": r"\ne ",
    "≈": r"\approx ",
    "∞": r"\infty ",
    "√": r"\sqrt ",
    "∈": r"\in ",
    "∉": r"\notin ",
    "⊆": r"\subseteq ",
    "→": r"\to ",
    "∑": r"\sum ",
    "∏": r"\prod ",
    "λ": r"\lambda ",
    "μ": r"\mu ",
    "σ": r"\sigma ",
    "π": r"\pi ",
    "ρ": r"\rho ",
    "θ": r"\theta ",
    "Φ": r"\Phi ",
    "α": r"\alpha ",
    "β": r"\beta ",
}

# Presence of these chars marks a token as math. `+`/`-` are excluded so word
# hyphens ("non-trivial") aren't mistaken for minus; a signed number still wins on
# the digit test, and a standalone "+"/"-" wins via _OPERATOR_ONLY.
_OPS = set("*/^·×÷∩∪√∈∉⊆=≤≥≠<>")
_OPERATOR_ONLY = {"+", "-", "=", "*", "/", "<", ">"}
# A run is only wrapped if it actually contains an operator/grouping — a lone
# number or word is left as plain text rather than rendered as italic math.
_WRAP_TRIGGER = re.compile(r"[=+\-*/^·×÷∩∪√∈∉⊆≤≥≠<>()]")
_PRIME = re.compile(r"^[A-Za-z]+'$")          # y', f'
_FUNC = re.compile(r"^[A-Za-z]+'?\([^)]*\)$")  # y(t), P(A), f'(x), μ(2)


def _core(tok: str) -> str:
    return tok.strip(" .,;:?!")


def _is_math(tok: str) -> bool:
    c = _core(tok)
    if not c:
        return False
    if c in _OPERATOR_ONLY:
        return True
    if any(ch.isdigit() for ch in c):
        return True
    if any(ch in _OPS for ch in c):
        return True
    if _PRIME.match(c) or _FUNC.match(c):
        return True
    return False


def _to_latex(expr: str) -> str:
    expr = re.sub(r"\^\(([^()]*)\)", r"^{\1}", expr)  # e^(-0.32·t) → e^{-0.32·t}
    for sym, rep in _SYMBOLS.items():
        expr = expr.replace(sym, rep)
    return re.sub(r"\s+", " ", expr).strip()


def latexify(text: str) -> str:
    """Wrap the math fragments of a mixed prose/math string in ``$...$`` LaTeX."""
    if not text:
        return text
    text = re.sub(r"\$(?=\d)", r"\\$", text)  # keep currency literal, not a delimiter

    tokens = text.split(" ")
    out: list[str] = []
    buf: list[str] = []

    def flush() -> None:
        if not buf:
            return
        raw = " ".join(_core(t) for t in buf)
        # A single bare number/word with no operator: leave it untouched as text.
        if len(buf) == 1 and not _WRAP_TRIGGER.search(raw):
            out.append(buf[0])
            buf.clear()
            return
        m = re.search(r"[.,;:?!]+$", buf[-1])
        trail = m.group(0) if m else ""
        body = _to_latex(raw)
        out.append(f"${body}${trail}" if body else trail)
        buf.clear()

    for tok in tokens:
        if _is_math(tok):
            buf.append(tok)
        else:
            flush()
            out.append(tok)
    flush()
    return " ".join(out)
