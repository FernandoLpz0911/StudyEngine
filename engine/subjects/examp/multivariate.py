"""Generators for multivariate topics: joint distributions, marginals,
conditional distributions, covariance, order statistics, CLT, and
multivariate transformations."""
from __future__ import annotations

import numpy as np
from scipy.stats import norm

from engine.generation.base import Problem, make_mc_choices, register


def _joint_table(rng: np.random.Generator, m: int = 2, n: int = 3) -> np.ndarray:
    """Random m×n joint PMF table (probabilities sum to 1)."""
    counts = rng.integers(1, 10, size=(m, n)).astype(float)
    return counts / counts.sum()


@register("joint_basics")
def gen_joint_basics(ask: str, ranges: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    k = int(rng.integers(1, 4))  # f(x,y) = c * x^k * y on [0,1]×[0,1]
    # ∫₀¹ ∫₀¹ x^k * y dx dy = 1/(k+1) * 1/2 = 1/(2(k+1))
    c = 2 * (k + 1)

    if ask == "normalize_constant":
        ans = float(c)
        stmt = (
            f"f(x,y) = c·x^{k}·y for 0 < x < 1, 0 < y < 1. "
            f"Find c so that f is a valid joint PDF."
        )
        wrongs = [float(k + 1), float(2 * k), float(c / 2)]
    elif ask == "joint_prob_region":
        x0 = round(float(rng.uniform(0.3, 0.7)), 2)
        y0 = round(float(rng.uniform(0.3, 0.7)), 2)
        # P(X < x0, Y < y0) = c * x0^(k+1)/(k+1) * y0²/2
        ans = round(c * x0 ** (k + 1) / (k + 1) * y0 ** 2 / 2, 4)
        stmt = (
            f"f(x,y) = {c}·x^{k}·y for 0 < x, y < 1. "
            f"Find P(X < {x0}, Y < {y0})."
        )
        wrongs = [round(x0 ** (k + 1) * y0 ** 2, 4), round(ans * 2, 4), round(1 - ans, 4)]
    else:
        raise ValueError(f"Unknown ask '{ask}' for joint_basics")

    extra = {"x0": x0, "y0": y0} if ask == "joint_prob_region" else {}
    return Problem("joint_basics", ask, stmt, ans, make_mc_choices(ans, wrongs, rng),
                   params={"k": k, **extra}, seed=seed)


@register("marginal")
def gen_marginal(ask: str, ranges: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    table = np.round(_joint_table(rng, m=2, n=3), 4)
    px = table.sum(axis=1)  # P(X=x), x ∈ {0, 1}
    py = table.sum(axis=0)  # P(Y=y), y ∈ {0, 1, 2}

    if ask == "marginal_pdf":
        # Find P(X=1)
        ans = round(float(px[1]), 4)
        stmt = (
            f"Joint PMF: P(X=0,Y=0)={table[0,0]:.4f}, P(X=0,Y=1)={table[0,1]:.4f}, "
            f"P(X=0,Y=2)={table[0,2]:.4f}, P(X=1,Y=0)={table[1,0]:.4f}, "
            f"P(X=1,Y=1)={table[1,1]:.4f}, P(X=1,Y=2)={table[1,2]:.4f}. "
            f"Find P(X = 1)."
        )
        wrongs = [round(float(px[0]), 4), round(float(table[1, 0]), 4),
                  round(float(table[1, 1]), 4)]
    elif ask == "marginal_prob":
        # Find P(Y ≤ 1)
        ans = round(float(py[0] + py[1]), 4)
        stmt = (
            f"Joint PMF: P(X=0,Y=0)={table[0,0]:.4f}, P(X=0,Y=1)={table[0,1]:.4f}, "
            f"P(X=0,Y=2)={table[0,2]:.4f}, P(X=1,Y=0)={table[1,0]:.4f}, "
            f"P(X=1,Y=1)={table[1,1]:.4f}, P(X=1,Y=2)={table[1,2]:.4f}. "
            f"Find P(Y ≤ 1)."
        )
        wrongs = [round(float(py[0]), 4), round(float(py[1]), 4), round(1 - ans, 4)]
    else:
        raise ValueError(f"Unknown ask '{ask}' for marginal")

    return Problem("marginal", ask, stmt, ans, make_mc_choices(ans, wrongs, rng),
                   params={"table": table.tolist()}, seed=seed)


@register("conditional_dist")
def gen_conditional_dist(ask: str, ranges: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    table = np.round(_joint_table(rng, m=2, n=3), 4)
    px = table.sum(axis=1)
    py = table.sum(axis=0)

    # Conditional: P(Y=j | X=1)
    cond_y_given_x1 = table[1, :] / px[1]

    if ask == "cond_pdf":
        j = int(rng.integers(0, 3))
        ans = round(float(cond_y_given_x1[j]), 4)
        stmt = (
            f"Joint PMF table (rows=X∈{{0,1}}, cols=Y∈{{0,1,2}}): "
            f"{table.tolist()}. Find P(Y = {j} | X = 1)."
        )
        wrongs = [round(float(table[1, j]), 4), round(float(py[j]), 4),
                  round(float(table[0, j] / px[0]), 4)]
    elif ask == "cond_prob":
        # P(Y ≤ 1 | X = 0)
        cond_y_given_x0 = table[0, :] / px[0]
        ans = round(float(cond_y_given_x0[0] + cond_y_given_x0[1]), 4)
        stmt = (
            f"Joint PMF table (rows=X∈{{0,1}}, cols=Y∈{{0,1,2}}): "
            f"{table.tolist()}. Find P(Y ≤ 1 | X = 0)."
        )
        wrongs = [round(float(py[0] + py[1]), 4), round(float(table[0, 0] + table[0, 1]), 4),
                  round(1 - ans, 4)]
    else:
        raise ValueError(f"Unknown ask '{ask}' for conditional_dist")

    return Problem("conditional_dist", ask, stmt, ans, make_mc_choices(ans, wrongs, rng),
                   params={"table": table.tolist()}, seed=seed)


@register("independence_rv")
def gen_independence_rv(ask: str, ranges: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    if ask == "is_independent":
        # Create a table where X and Y ARE independent
        px = rng.dirichlet([2, 3])
        py = rng.dirichlet([3, 2, 3])
        table = np.outer(px, py)
        table = np.round(table, 4)
        # Verify via f(x,y) = f_X(x)*f_Y(y)
        px_r = table.sum(axis=1)
        ans = round(float(px_r[0] * table.sum(axis=0)[0]), 4)
        actual = round(float(table[0, 0]), 4)
        stmt = (
            f"Joint PMF: {table.tolist()}. "
            f"Check if X,Y are independent by computing P(X=0)·P(Y=0)."
        )
        col_sum = round(float(table[0, 0] + table[0, 1]), 4)
        wrongs = [round(actual * 2, 4), round(ans / 2, 4), col_sum]
        ans = actual  # P(X=0,Y=0), which should equal px[0]*py[0] — the "independent" answer
    else:
        raise ValueError(f"Unknown ask '{ask}' for independence_rv")

    return Problem("independence_rv", ask, stmt, ans, make_mc_choices(ans, wrongs, rng),
                   params={"table": table.tolist()}, seed=seed)


@register("covariance")
def gen_covariance(ask: str, ranges: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    table = np.round(_joint_table(rng, m=2, n=2), 4)
    x_vals = np.array([0.0, 1.0])
    y_vals = np.array([0.0, 1.0])

    ex = float(np.dot(x_vals, table.sum(axis=1)))
    ey = float(np.dot(y_vals, table.sum(axis=0)))
    exy = float(sum(x_vals[i] * y_vals[j] * table[i, j]
                    for i in range(2) for j in range(2)))
    cov = round(exy - ex * ey, 4)
    vx = float(np.dot(x_vals ** 2, table.sum(axis=1))) - ex ** 2
    vy = float(np.dot(y_vals ** 2, table.sum(axis=0))) - ey ** 2

    if ask == "covariance":
        ans = cov
        stmt = (
            f"Joint PMF: P(X=0,Y=0)={table[0,0]:.4f}, P(X=0,Y=1)={table[0,1]:.4f}, "
            f"P(X=1,Y=0)={table[1,0]:.4f}, P(X=1,Y=1)={table[1,1]:.4f}. "
            f"Find Cov(X, Y)."
        )
        wrongs = [round(exy, 4), round(ex * ey, 4), round(cov ** 2, 4)]
    elif ask == "var_of_sum":
        ans = round(vx + vy + 2 * cov, 4)
        stmt = (
            f"Same joint PMF as above. Var(X) = {round(vx,4)}, Var(Y) = {round(vy,4)}, "
            f"Cov(X,Y) = {cov}. Find Var(X + Y)."
        )
        wrongs = [round(vx + vy, 4), round(vx + vy - 2 * cov, 4), round(vx * vy, 4)]
    else:
        raise ValueError(f"Unknown ask '{ask}' for covariance")

    return Problem("covariance", ask, stmt, ans, make_mc_choices(ans, wrongs, rng),
                   params={"table": table.tolist()}, seed=seed)


@register("correlation")
def gen_correlation(ask: str, ranges: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    table = np.round(_joint_table(rng, m=2, n=2), 4)
    x_vals = np.array([0.0, 1.0])
    y_vals = np.array([0.0, 1.0])

    px = table.sum(axis=1)
    py = table.sum(axis=0)
    ex = float(np.dot(x_vals, px))
    ey = float(np.dot(y_vals, py))
    exy = float(sum(x_vals[i] * y_vals[j] * table[i, j] for i in range(2) for j in range(2)))
    cov = exy - ex * ey
    vx = float(np.dot(x_vals ** 2, px)) - ex ** 2
    vy = float(np.dot(y_vals ** 2, py)) - ey ** 2
    sx, sy = vx ** 0.5, vy ** 0.5

    if ask == "correlation":
        denom = sx * sy
        if denom < 1e-9:
            ans = 0.0
        else:
            ans = round(cov / denom, 4)
        stmt = (
            f"Joint PMF: P(X=0,Y=0)={table[0,0]:.4f}, P(X=0,Y=1)={table[0,1]:.4f}, "
            f"P(X=1,Y=0)={table[1,0]:.4f}, P(X=1,Y=1)={table[1,1]:.4f}. "
            f"Find ρ(X, Y) = Cov(X,Y) / (σ_X · σ_Y)."
        )
        cov_norm = round(cov / (vx * vy), 4) if vx * vy > 0 else 0.1
        wrongs = [round(cov, 4), round(ans ** 2, 4), cov_norm]
    else:
        raise ValueError(f"Unknown ask '{ask}' for correlation")

    return Problem("correlation", ask, stmt, ans, make_mc_choices(ans, wrongs, rng),
                   params={"table": table.tolist()}, seed=seed)


@register("expectation_joint")
def gen_expectation_joint(ask: str, ranges: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    table = np.round(_joint_table(rng, m=2, n=2), 4)
    x_vals = np.array([1.0, 2.0])
    y_vals = np.array([1.0, 2.0])

    ex = float(np.dot(x_vals, table.sum(axis=1)))
    ey = float(np.dot(y_vals, table.sum(axis=0)))
    exy = float(sum(x_vals[i] * y_vals[j] * table[i, j] for i in range(2) for j in range(2)))

    if ask == "E_XY":
        ans = round(exy, 4)
        stmt = (
            f"X ∈ {{1,2}}, Y ∈ {{1,2}}. Joint PMF: {table.tolist()}. Find E[XY]."
        )
        wrongs = [round(ex * ey, 4), round(ex + ey, 4), round(exy ** 2, 4)]
    elif ask == "E_sum":
        ans = round(ex + ey, 4)
        stmt = (
            f"X ∈ {{1,2}}, Y ∈ {{1,2}}. Joint PMF: {table.tolist()}. Find E[X + Y]."
        )
        wrongs = [round(exy, 4), round(ex * ey, 4), round(ex, 4)]
    else:
        raise ValueError(f"Unknown ask '{ask}' for expectation_joint")

    return Problem("expectation_joint", ask, stmt, ans, make_mc_choices(ans, wrongs, rng),
                   params={"table": table.tolist()}, seed=seed)


@register("conditional_expectation")
def gen_conditional_expectation(ask: str, ranges: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    table = np.round(_joint_table(rng, m=2, n=3), 4)
    y_vals = np.array([0.0, 1.0, 2.0])
    px = table.sum(axis=1)
    ey = float(np.dot(y_vals, table.sum(axis=0)))

    # E[Y | X=1]
    ey_given_x1 = float(np.dot(y_vals, table[1, :] / px[1]))

    if ask == "cond_expectation":
        ans = round(ey_given_x1, 4)
        stmt = (
            f"Joint PMF (rows=X∈{{0,1}}, cols=Y∈{{0,1,2}}): {table.tolist()}. "
            f"Find E[Y | X = 1]."
        )
        wrongs = [round(ey, 4), round(float(np.dot(y_vals, table[0, :] / px[0])), 4),
                  round(ey_given_x1 ** 2, 4)]
    elif ask == "double_expectation":
        # E[Y] = E[E[Y|X]] = E[Y|X=0]*P(X=0) + E[Y|X=1]*P(X=1)
        ey_given_x0 = float(np.dot(y_vals, table[0, :] / px[0]))
        tower = ey_given_x0 * px[0] + ey_given_x1 * px[1]
        ans = round(float(tower), 4)
        stmt = (
            f"Joint PMF: {table.tolist()}. Verify the tower property: "
            f"find E[Y] = E[E[Y|X]] = E[Y|X=0]·P(X=0) + E[Y|X=1]·P(X=1)."
        )
        wrongs = [round(ey_given_x1, 4), round(ey_given_x0, 4), round(ey + 0.1, 4)]
    else:
        raise ValueError(f"Unknown ask '{ask}' for conditional_expectation")

    return Problem("conditional_expectation", ask, stmt, ans, make_mc_choices(ans, wrongs, rng),
                   params={"table": table.tolist()}, seed=seed)


@register("total_variance")
def gen_total_variance(ask: str, ranges: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    table = np.round(_joint_table(rng, m=2, n=3), 4)
    y_vals = np.array([0.0, 1.0, 2.0])
    px = table.sum(axis=1)

    ey_given_x = [float(np.dot(y_vals, table[i, :] / px[i])) for i in range(2)]
    e2y_given_x = [float(np.dot(y_vals ** 2, table[i, :] / px[i])) for i in range(2)]
    var_y_given_x = [e2y_given_x[i] - ey_given_x[i] ** 2 for i in range(2)]

    e_var = float(np.dot(var_y_given_x, px))
    e_ey_given_x = float(np.dot(ey_given_x, px))
    var_ey = float(np.dot(np.array(ey_given_x) ** 2, px)) - e_ey_given_x ** 2
    total_var = e_var + var_ey

    if ask == "total_variance":
        ans = round(total_var, 4)
        stmt = (
            f"Joint PMF: {table.tolist()}. "
            f"Find Var(Y) using the law of total variance: "
            f"Var(Y) = E[Var(Y|X)] + Var(E[Y|X])."
        )
        wrongs = [round(e_var, 4), round(var_ey, 4),
                  round(float(np.dot(y_vals ** 2, table.sum(axis=0))) - e_ey_given_x ** 2, 4)]
    else:
        raise ValueError(f"Unknown ask '{ask}' for total_variance")

    return Problem("total_variance", ask, stmt, ans, make_mc_choices(ans, wrongs, rng),
                   params={"table": table.tolist()}, seed=seed)


@register("sum_distribution")
def gen_sum_distribution(ask: str, ranges: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    n = int(rng.integers(2, 6))
    lam = round(float(rng.uniform(0.5, 3.0)), 2)

    # S = X₁ + ... + Xₙ, Xᵢ ~ Exp(λ) iid → S ~ Gamma(n, 1/λ)
    mean_s = round(n / lam, 4)
    var_s = round(n / lam ** 2, 4)

    if ask == "sum_mean_var":
        ans = mean_s
        stmt = (
            f"X₁, …, X_{n} are iid Exponential(λ = {lam}). "
            f"Let S = X₁ + … + X_{n}. Find E[S]."
        )
        wrongs = [round(lam * n, 4), round(1 / lam, 4), var_s]
    elif ask == "identify_sum_dist":
        # S ~ Gamma(n, 1/lam); variance = n/lam²
        ans = var_s
        stmt = (
            f"X₁, …, X_{n} are iid Exponential(λ = {lam}). "
            f"S = X₁ + … + X_{n} ~ Gamma({n}, 1/λ). Find Var(S)."
        )
        wrongs = [mean_s, round(n / lam ** 2 * 2, 4), round(1 / lam ** 2, 4)]
    else:
        raise ValueError(f"Unknown ask '{ask}' for sum_distribution")

    return Problem("sum_distribution", ask, stmt, ans, make_mc_choices(ans, wrongs, rng),
                   params={"n": n, "lam": lam}, seed=seed)


@register("order_statistics")
def gen_order_statistics(ask: str, ranges: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    n = int(rng.integers(ranges["n"][0], ranges["n"][1] + 1))
    lam = round(float(rng.uniform(0.3, 2.0)), 2)
    t = round(float(rng.uniform(0.3, 2.0 / lam)), 2)
    ft = round(float(1 - np.exp(-lam * t)), 4)  # F(t) for Exp(λ)

    if ask == "max_cdf":
        # F_max(t) = F(t)^n
        ans = round(ft ** n, 4)
        stmt = (
            f"X₁, …, X_{n} iid Exp(λ = {lam}). M = max(X₁,…,X_{n}). "
            f"Find P(M ≤ {t}) = [F({t})]^{n}."
        )
        wrongs = [round(ft * n, 4) if ft * n <= 1 else round(ft, 4),
                  round(1 - (1 - ft) ** n, 4), round(ft ** (n - 1), 4)]
    elif ask == "min_cdf":
        # F_min(t) = 1 - (1-F(t))^n = 1 - e^{-nlambda*t}
        ans = round(1 - (1 - ft) ** n, 4)
        stmt = (
            f"X₁, …, X_{n} iid Exp(λ = {lam}). m = min(X₁,…,X_{n}). "
            f"Find P(m ≤ {t}) = 1 - [1-F({t})]^{n}."
        )
        wrongs = [round(ft ** n, 4), round(ft, 4), round(1 - ft ** n, 4)]
    elif ask == "min_max_prob":
        # P(min > t) = (1-F(t))^n = e^{-nlambda*t}
        ans = round((1 - ft) ** n, 4)
        stmt = (
            f"X₁, …, X_{n} iid Exp(λ = {lam}). Find P(min > {t})."
        )
        wrongs = [round(1 - ft, 4), round(ft ** n, 4), round(1 - (1 - ft) ** n, 4)]
    else:
        raise ValueError(f"Unknown ask '{ask}' for order_statistics")

    return Problem("order_statistics", ask, stmt, ans, make_mc_choices(ans, wrongs, rng),
                   params={"n": n, "lam": lam, "t": t}, seed=seed)


@register("clt")
def gen_clt(ask: str, ranges: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    n = int(rng.integers(ranges["n"][0], ranges["n"][1] + 1))
    lam = round(float(rng.uniform(0.5, 3.0)), 2)
    # Xᵢ ~ Exp(λ): mean=1/λ, var=1/λ²
    mu = round(1 / lam, 4)
    sigma2 = round(1 / lam ** 2, 4)

    extra: dict = {}
    if ask == "clt_prob":
        # P(X̄ ≤ c) — approximate using CLT
        c = round(mu * rng.uniform(0.8, 1.2), 2)
        z = round((c - mu) / (sigma2 / n) ** 0.5, 4)
        extra = {"c": c, "z": z}
        ans = round(float(norm.cdf(z)), 4)
        stmt = (
            f"X₁, …, X_{n} iid Exp(λ = {lam}). E[X] = {mu}, Var(X) = {sigma2}. "
            f"Using CLT, find P(X̄ ≤ {c})."
        )
        wrongs = [round(1 - ans, 4), round(float(norm.cdf(-z)), 4),
                  round(float(norm.cdf(z, scale=sigma2)), 4)]
    elif ask == "clt_sum_prob":
        # P(S_n > c) where S_n = ΣXᵢ
        c = round(n * mu * rng.uniform(0.8, 1.2), 1)
        z = round((c - n * mu) / (n * sigma2) ** 0.5, 4)
        extra = {"c": c, "z": z}
        ans = round(float(norm.sf(z)), 4)
        stmt = (
            f"X₁, …, X_{n} iid Exp(λ = {lam}). S = X₁+…+X_{n}. "
            f"Using CLT, find P(S > {c})."
        )
        wrongs = [round(1 - ans, 4), round(float(norm.cdf(z)), 4),
                  round(float(norm.sf(-z)), 4)]
    else:
        raise ValueError(f"Unknown ask '{ask}' for clt")

    return Problem("clt", ask, stmt, ans, make_mc_choices(ans, wrongs, rng),
                   params={"n": n, "lam": lam, "mu": mu, "sigma2": sigma2, **extra}, seed=seed)


@register("chebyshev")
def gen_chebyshev(ask: str, ranges: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    mu = round(float(rng.uniform(2, 10)), 1)
    sigma2 = round(float(rng.uniform(1, 5)), 1)
    k = round(float(rng.uniform(1.5, 4.0)), 1)
    sigma = round(sigma2 ** 0.5, 4)

    extra: dict = {}
    if ask == "chebyshev_bound":
        # P(|X - μ| ≥ k·σ) ≤ 1/k²
        ans = round(1 / k ** 2, 4)
        stmt = (
            f"X has mean {mu} and variance {sigma2}. "
            f"Find an upper bound on P(|X - {mu}| ≥ {k}·σ) via Chebyshev's inequality."
        )
        wrongs = [round(sigma2 / (k * sigma) ** 2, 4),
                  round(1 / k, 4), round(sigma2 / k ** 2, 4)]
    elif ask == "markov_bound":
        # P(X ≥ t) ≤ E[X]/t (assumes X ≥ 0)
        t = round(mu * rng.uniform(1.5, 3.0), 1)
        extra = {"t": t}
        ans = round(mu / t, 4)
        stmt = (
            f"X ≥ 0, E[X] = {mu}. Find an upper bound on P(X ≥ {t}) via Markov's inequality."
        )
        wrongs = [round(mu / t ** 2, 4), round(sigma2 / t ** 2, 4), round(1 / t, 4)]
    else:
        raise ValueError(f"Unknown ask '{ask}' for chebyshev")

    return Problem("chebyshev", ask, stmt, ans, make_mc_choices(ans, wrongs, rng),
                   params={"mu": mu, "sigma2": sigma2, "k": k, **extra}, seed=seed)


@register("transformations_multi")
def gen_transformations_multi(ask: str, ranges: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)

    if ask == "min_of_exp":
        n = int(rng.integers(2, 6))
        lam = round(float(rng.uniform(0.5, 2.0)), 2)
        t = round(float(rng.uniform(0.1, 1.5 / lam)), 2)
        ans = round(float(np.exp(-n * lam * t)), 4)
        stmt = (
            f"X₁, …, X_{n} are iid Exp(λ = {lam}). "
            f"Let M = min(X₁, …, X_{n}) ~ Exp({n}λ). "
            f"Find P(M > {t}) = exp(−{n}λt)."
        )
        wrongs = [round(float(np.exp(-lam * t)), 4),
                  round(float(1 - np.exp(-n * lam * t)), 4),
                  round(float(np.exp(-n * lam * t)) * n, 4)]
        params = {"n": n, "lam": lam, "t": t}

    elif ask == "sum_uniform_prob":
        z = round(float(rng.uniform(0.1, 0.9)), 2)
        # Z = X+Y, X,Y ~ U(0,1). CDF: P(Z ≤ z) = z²/2 for 0 < z ≤ 1
        ans = round(z ** 2 / 2, 4)
        stmt = (
            f"X and Y are independent Uniform(0,1). Let Z = X + Y. "
            f"Using the PDF of Z (triangular distribution on [0,2]), "
            f"find P(Z ≤ {z})."
        )
        wrongs = [round(z / 2, 4), round(z ** 2, 4),
                  round(1 - z ** 2 / 2, 4)]
        params = {"z": z}

    elif ask == "jacobian_abs":
        a = int(rng.integers(2, 5))
        b = int(rng.integers(2, 5))
        # Ensure det ≠ 0 and not trivially 1
        if a * b - 1 == 0:
            b = b + 1
        det = a * b - 1
        ans = round(1 / abs(det), 4)
        stmt = (
            f"Apply the bivariate transformation U = {a}X + Y, V = X + {b}Y. "
            f"Find |∂(x,y)/∂(u,v)|, the absolute Jacobian of the inverse "
            f"transformation. [Hint: |J| = 1/|det(∂(u,v)/∂(x,y))|]"
        )
        wrongs = [float(abs(det)),
                  round(1 / (a * b), 4),
                  round(1 / (a + b), 4)]
        params = {"a": a, "b": b}

    else:
        raise ValueError(f"Unknown ask '{ask}' for transformations_multi")

    return Problem("transformations_multi", ask, stmt, ans,
                   make_mc_choices(ans, wrongs, rng),
                   params=params, seed=seed)
