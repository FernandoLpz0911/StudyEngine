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
