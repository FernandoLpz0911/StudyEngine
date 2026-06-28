"""Answer keys for the Exam FM (financial mathematics) generators."""
from math import exp, log

import engine.subjects  # noqa: F401  (registers generators + solvers)
from engine.feedback.solve import worked_solution
from engine.generation.base import generate
from engine.subjects.examfm.generators import (
    ANNUITY,
    BOND,
    COMPOUND,
    DURATION,
    LOAN,
    TERM,
    VARFORCE,
    YIELD,
    _afv,
    _apv,
    _irr,
)

SEEDS = range(60)


def _has_answer(p) -> bool:
    return f"{p.correct_answer:.3f}" in p.choices


class TestCompound:
    def test_future_value(self):
        for seed in SEEDS:
            p = generate("fm_compound", "future_value", {}, seed)
            pv, i, n = p.params["pv"], p.params["i"], p.params["n"]
            assert p.correct_answer == round(pv * (1 + i) ** n, 3)
            assert _has_answer(p)
            assert worked_solution("fm_compound", "future_value", p.params)

    def test_present_value(self):
        for seed in SEEDS:
            p = generate("fm_compound", "present_value", {}, seed)
            fv, i, n = p.params["fv"], p.params["i"], p.params["n"]
            assert p.correct_answer == round(fv * (1 + i) ** -n, 3)
            assert _has_answer(p)

    def test_effective_rate(self):
        for seed in SEEDS:
            p = generate("fm_compound", "effective_rate", {}, seed)
            nominal, m = p.params["nominal"], p.params["m"]
            assert p.correct_answer == round(((1 + nominal / m) ** m - 1) * 100, 3)


class TestAnnuity:
    def test_annuity_pv(self):
        for seed in SEEDS:
            p = generate("fm_annuity", "annuity_pv", {}, seed)
            pmt, i, n = p.params["pmt"], p.params["i"], p.params["n"]
            assert p.correct_answer == round(pmt * (1 - (1 + i) ** -n) / i, 3)
            assert _has_answer(p)
            assert worked_solution("fm_annuity", "annuity_pv", p.params)

    def test_annuity_fv(self):
        for seed in SEEDS:
            p = generate("fm_annuity", "annuity_fv", {}, seed)
            pmt, i, n = p.params["pmt"], p.params["i"], p.params["n"]
            assert p.correct_answer == round(pmt * ((1 + i) ** n - 1) / i, 3)

    def test_perpetuity(self):
        for seed in SEEDS:
            p = generate("fm_annuity", "perpetuity", {}, seed)
            assert p.correct_answer == round(p.params["pmt"] / p.params["i"], 3)
            assert worked_solution("fm_annuity", "perpetuity", p.params)

    def test_loan_payment(self):
        for seed in SEEDS:
            p = generate("fm_annuity", "loan_payment", {}, seed)
            loan, i, n = p.params["loan"], p.params["i"], p.params["n"]
            assert p.correct_answer == round(loan * i / (1 - (1 + i) ** -n), 3)
            assert _has_answer(p)


# Every kind/ask: the formatted answer is one of the choices and a worked
# solution exists. Guards against drift between generators, choices, and solvers.
_ALL = {
    "fm_compound": COMPOUND, "fm_varforce": VARFORCE, "fm_annuity": ANNUITY,
    "fm_loan": LOAN, "fm_bond": BOND, "fm_yield": YIELD,
    "fm_termstructure": TERM, "fm_duration": DURATION,
}


def test_every_ask_consistent():
    for kind, asks in _ALL.items():
        for ask in asks:
            for seed in SEEDS:
                p = generate(kind, ask, {}, seed)
                assert _has_answer(p), (kind, ask, seed)
                assert worked_solution(kind, ask, p.params), (kind, ask)


class TestRateConversions:
    def test_discount_factor(self):
        for seed in SEEDS:
            p = generate("fm_compound", "discount_factor", {}, seed)
            assert p.correct_answer == round(1 / (1 + p.params["i"]), 3)

    def test_effective_discount(self):
        for seed in SEEDS:
            p = generate("fm_compound", "effective_discount", {}, seed)
            i = p.params["i"]
            assert p.correct_answer == round(i / (1 + i), 3)

    def test_force_from_i(self):
        for seed in SEEDS:
            p = generate("fm_compound", "force_from_i", {}, seed)
            assert p.correct_answer == round(log(1 + p.params["i"]), 3)

    def test_real_rate(self):
        for seed in SEEDS:
            p = generate("fm_compound", "real_rate", {}, seed)
            i, r = p.params["i"], p.params["infl"]
            assert p.correct_answer == round((1 + i) / (1 + r) - 1, 3)


class TestVarForce:
    def test_accum(self):
        for seed in SEEDS:
            p = generate("fm_varforce", "accum", {}, seed)
            a, b, t, pp = p.params["a"], p.params["b"], p.params["t"], p.params["p"]
            assert p.correct_answer == round(pp * exp(a * t + b * t * t / 2), 3)

    def test_accum_const(self):
        for seed in SEEDS:
            p = generate("fm_varforce", "accum_const", {}, seed)
            d, t, pp = p.params["delta"], p.params["t"], p.params["p"]
            assert p.correct_answer == round(pp * exp(d * t), 3)


class TestAnnuityAdvanced:
    def test_annuity_due_pv(self):
        for seed in SEEDS:
            p = generate("fm_annuity", "annuity_due_pv", {}, seed)
            pmt, i, n = p.params["pmt"], p.params["i"], p.params["n"]
            assert p.correct_answer == round(pmt * _apv(i, n) * (1 + i), 3)

    def test_perpetuity_due(self):
        for seed in SEEDS:
            p = generate("fm_annuity", "perpetuity_due", {}, seed)
            pmt, i = p.params["pmt"], p.params["i"]
            assert p.correct_answer == round(pmt * (1 + i) / i, 3)

    def test_continuous(self):
        for seed in SEEDS:
            p = generate("fm_annuity", "continuous", {}, seed)
            pmt, i, n = p.params["pmt"], p.params["i"], p.params["n"]
            ans = pmt * (1 - (1 + i) ** -n) / log(1 + i)
            assert p.correct_answer == round(ans, 3)

    def test_geometric(self):
        for seed in SEEDS:
            p = generate("fm_annuity", "geometric", {}, seed)
            pmt, i, n, g = (p.params[k] for k in ("pmt", "i", "n", "g"))
            ratio = (1 + g) / (1 + i)
            assert p.correct_answer == round(pmt * (1 - ratio ** n) / (i - g), 3)

    def test_solve_term(self):
        for seed in SEEDS:
            p = generate("fm_annuity", "solve_term", {}, seed)
            loan, i, pmt = p.params["loan"], p.params["i"], p.params["pmt"]
            assert p.correct_answer == round(-log(1 - loan * i / pmt) / log(1 + i), 3)


class TestLoan:
    def test_balance_methods_agree(self):
        for seed in SEEDS:
            pp = generate("fm_loan", "balance_prospective", {}, seed)
            i, n, loan, k = (pp.params[x] for x in ("i", "n", "loan", "k"))
            pmt = loan * i / (1 - (1 + i) ** -n)
            assert pp.correct_answer == round(pmt * _apv(i, n - k), 3)
            pr = generate("fm_loan", "balance_retrospective", {}, seed)
            i, n, loan, k = (pr.params[x] for x in ("i", "n", "loan", "k"))
            pmt = loan * i / (1 - (1 + i) ** -n)
            assert pr.correct_answer == round(loan * (1 + i) ** k - pmt * _afv(i, k), 3)

    def test_interest_plus_principal(self):
        for seed in SEEDS:
            pi = generate("fm_loan", "interest_portion", {}, seed)
            i, n, loan, k = (pi.params[x] for x in ("i", "n", "loan", "k"))
            pmt = loan * i / (1 - (1 + i) ** -n)
            assert pi.correct_answer == round(pmt * (1 - (1 + i) ** -(n - k + 1)), 3)

    def test_sinking_fund(self):
        for seed in SEEDS:
            p = generate("fm_loan", "sinking_fund", {}, seed)
            i, n, loan, j = (p.params[x] for x in ("i", "n", "loan", "j"))
            assert p.correct_answer == round(loan * i + loan / _afv(j, n), 3)


class TestBond:
    def test_price(self):
        for seed in SEEDS:
            p = generate("fm_bond", "price", {}, seed)
            face, r, i, n = (p.params[x] for x in ("face", "r", "i", "n"))
            ans = face * r * _apv(i, n) + face * (1 + i) ** -n
            assert p.correct_answer == round(ans, 3)

    def test_callable_is_minimum(self):
        for seed in SEEDS:
            p = generate("fm_bond", "callable_price", {}, seed)
            face, r, i, n1, n2 = (p.params[x] for x in ("face", "r", "i", "n1", "n2"))
            c = face
            p1 = face * r * _apv(i, n1) + c * (1 + i) ** -n1
            p2 = face * r * _apv(i, n2) + c * (1 + i) ** -n2
            assert p.correct_answer == round(min(p1, p2), 3)


class TestYieldTermDuration:
    def test_irr(self):
        for seed in SEEDS:
            p = generate("fm_yield", "irr", {}, seed)
            assert p.correct_answer == round(_irr(p.params["cfs"]), 3)

    def test_forward(self):
        for seed in SEEDS:
            p = generate("fm_termstructure", "forward", {}, seed)
            s1, s2 = p.params["s1"], p.params["s2"]
            assert p.correct_answer == round((1 + s2) ** 2 / (1 + s1) - 1, 3)

    def test_macaulay_then_modified(self):
        for seed in SEEDS:
            p = generate("fm_duration", "macaulay", {}, seed)
            i, cfs = p.params["i"], p.params["cfs"]
            v = 1 / (1 + i)
            pv = [c * v ** t for c, t in zip(cfs, [1, 2, 3, 4], strict=True)]
            mac = sum(t * x for t, x in zip([1, 2, 3, 4], pv, strict=True)) / sum(pv)
            assert p.correct_answer == round(mac, 3)
