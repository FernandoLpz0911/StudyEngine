"""Answer keys for the MATH 250 set-counting and ECON 111 decision generators."""
import engine.subjects  # noqa: F401  (registers generators + solvers)
from engine.feedback.solve import worked_solution
from engine.generation.base import generate

SEEDS = range(60)


class TestSetCounting:
    def test_union_inclusion_exclusion(self):
        for seed in SEEDS:
            p = generate("set_counting", "union2", {}, seed)
            a, b, inter = p.params["a"], p.params["b"], p.params["inter"]
            assert p.correct_answer == float(a + b - inter)
            assert f"{p.correct_answer:.3f}" in p.choices

    def test_powerset_size(self):
        for seed in SEEDS:
            p = generate("set_counting", "powerset", {}, seed)
            assert p.correct_answer == float(2 ** p.params["n"])
            assert f"{p.correct_answer:.3f}" in p.choices
            assert worked_solution("set_counting", "powerset", p.params)


class TestEconDecision:
    def test_opportunity_cost_is_second_best(self):
        for seed in SEEDS:
            p = generate("econ_decision", "opportunity_cost", {}, seed)
            values = p.params["values"]
            assert p.correct_answer == float(sorted(values, reverse=True)[1])
            assert f"{p.correct_answer:.3f}" in p.choices

    def test_marginal_net_benefit(self):
        for seed in SEEDS:
            p = generate("econ_decision", "marginal_net", {}, seed)
            assert p.correct_answer == float(p.params["mb"] - p.params["mc"])
            assert worked_solution("econ_decision", "marginal_net", p.params)

    def test_expected_value(self):
        for seed in SEEDS:
            p = generate("econ_decision", "expected_value", {}, seed)
            pct, win = p.params["pct"], p.params["win"]
            assert p.correct_answer == round(pct / 100 * win, 3)
