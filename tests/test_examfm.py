"""Answer keys for the Exam FM (financial mathematics) generators."""
import engine.subjects  # noqa: F401  (registers generators + solvers)
from engine.feedback.solve import worked_solution
from engine.generation.base import generate

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
