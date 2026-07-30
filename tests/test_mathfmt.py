"""latexify: math fragments wrapped, prose and gradable choice strings untouched."""
from engine.mathfmt import latexify


def test_bare_number_unchanged():
    # Generator choices are bare numbers and are echoed back for grading — they
    # must pass through verbatim so the answer key still matches.
    assert latexify("4.000") == "4.000"
    assert latexify("15120.000") == "15120.000"


def test_lone_numbers_in_prose_not_wrapped():
    out = latexify("Round to 3 decimals.")
    assert "$" not in out


def test_equation_wrapped():
    out = latexify("Solve dy/dt = -0.32·y with y(0) = 7.6. Find y(3).")
    assert "$dy/dt = -0.32\\cdot y$" in out
    assert "$y(0) = 7.6$" in out
    assert "Solve" in out and "Find" in out  # prose survives


def test_hyphenated_word_not_treated_as_minus():
    out = latexify("a non-trivial FD whose left-hand side is not a superkey")
    assert "$" not in out


def test_currency_escaped_not_delimited():
    out = latexify("A loan of $9459.04 is repaid.")
    assert "\\$9459.04" in out
    # the only dollar signs are the escaped currency ones, not math delimiters
    assert out.count("$") == out.count("\\$")


def test_exponent_braces():
    assert latexify("y(t) = 7.6·e^(-0.32·t)") == "$y(t) = 7.6\\cdot e^{-0.32\\cdot t}$"


def test_empty_and_plain():
    assert latexify("") == ""
    assert latexify("How many candidate keys does R have?") == (
        "How many candidate keys does R have?"
    )


def test_interior_punctuation_survives():
    # A math run used to keep only its *last* token's punctuation and silently
    # eat the rest, collapsing a PMF list into one unreadable expression.
    out = latexify("P(X=1) = 0.229, P(X=2) = 0.393, P(X=3) = 0.378. Find Var(X).")
    assert "$P(X=1) = 0.229$, $P(X=2) = 0.393$, $P(X=3) = 0.378$." in out


def test_bracketed_expression_stays_whole():
    # `P(A`, `∩`, `B)` are three space-separated tokens; only the operator looks
    # mathy on its own, so without rejoining the expression shatters.
    out = latexify("Given P(A ∩ B) = 0.12, find P(A ∪ B).")
    assert "$P(A \\cap B) = 0.12$" in out
    assert "$P(A \\cup B)$" in out


def test_set_braces_are_escaped():
    # `{}` groups in LaTeX: unescaped, KaTeX renders {1,2} as a brace-less "1,2".
    out = latexify("X ∈ {1,2}. Find E[X].")
    assert "\\{1,2\\}" in out


def test_exponent_braces_not_escaped():
    # The grouping braces the exponent rule inserts must stay real braces.
    assert latexify("y(t) = 7.6·e^(-0.32·t)") == "$y(t) = 7.6\\cdot e^{-0.32\\cdot t}$"


def test_unclosed_bracket_in_prose_does_not_swallow_the_line():
    out = latexify("An unclosed ( bracket in prose should not eat the line.")
    assert "$" not in out


def test_parenthetical_prose_untouched():
    assert "$" not in latexify("Use the identity (see the notes) carefully.")
