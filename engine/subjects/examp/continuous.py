"""Generators for continuous distributions: Uniform, Exponential, Gamma, Normal,
Beta, LogNormal, Chi-Square, Moments, Pareto, and Weibull."""
from __future__ import annotations

import numpy as np
from scipy.special import gamma as gamma_fn
from scipy.stats import beta as beta_dist
from scipy.stats import gamma as gamma_dist
from scipy.stats import lognorm, norm

from engine.generation.base import Problem, make_mc_choices, register


@register("continuous_uniform")
def gen_continuous_uniform(ask: str, ranges: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    a = round(float(rng.uniform(*ranges["a"])), 1)
    b = round(float(rng.uniform(max(a + 1, ranges["b"][0]), ranges["b"][1])), 1)
    width = b - a
    extra: dict = {}

    if ask == "prob_interval":
        lo = round(float(rng.uniform(a, (a + b) / 2)), 2)
        hi = round(float(rng.uniform(lo + 0.5, b)), 2)
        ans = round((hi - lo) / width, 4)
        stmt = f"X ~ Uniform({a}, {b}). Find P({lo} < X < {hi})."
        wrongs = [round((hi - lo), 4), round(ans ** 2, 4), round(1 - ans, 4)]
        extra = {"lo": lo, "hi": hi}
    elif ask == "mean":
        ans = round((a + b) / 2, 4)
        stmt = f"X ~ Uniform({a}, {b}). Find E[X]."
        wrongs = [round(width, 4), round(width ** 2 / 12, 4), round(a, 4)]
    elif ask == "variance":
        ans = round(width ** 2 / 12, 4)
        stmt = f"X ~ Uniform({a}, {b}). Find Var(X)."
        wrongs = [round((a + b) / 2, 4), round(width / 2, 4), round(width ** 2 / 6, 4)]
    elif ask == "percentile":
        p = round(float(rng.choice([0.25, 0.5, 0.75, 0.9])), 2)
        ans = round(a + p * width, 4)
        stmt = f"X ~ Uniform({a}, {b}). Find the {int(p * 100)}th percentile."
        wrongs = [round(a + p * width / 2, 4), round(b - p * width, 4), round((a + b) / 2, 4)]
        extra = {"p": p}
    else:
        raise ValueError(f"Unknown ask '{ask}' for continuous_uniform")

    return Problem("continuous_uniform", ask, stmt, ans, make_mc_choices(ans, wrongs, rng),
                   params={"a": a, "b": b, **extra}, seed=seed)


@register("exponential")
def gen_exponential(ask: str, ranges: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    lam = round(float(rng.uniform(*ranges["lam"])), 2)
    scale = round(1 / lam, 4)
    extra: dict = {}

    if ask == "survival":
        t = round(float(rng.uniform(0.2, 2.0 / lam)), 2)
        ans = round(float(np.exp(-lam * t)), 4)
        stmt = f"X ~ Exponential(λ = {lam}). Find P(X > {t})."
        wrongs = [round(1 - ans, 4), round(float(np.exp(-lam * t / 2)), 4),
                  round(lam * float(np.exp(-lam * t)), 4)]
        extra = {"t": t}
    elif ask == "prob_interval":
        lo = round(float(rng.uniform(0, 1.0 / lam)), 2)
        hi = round(float(rng.uniform(lo + 0.1, 2.5 / lam)), 2)
        ans = round(float(np.exp(-lam * lo) - np.exp(-lam * hi)), 4)
        stmt = f"X ~ Exponential(λ = {lam}). Find P({lo} < X < {hi})."
        wrongs = [round(float(np.exp(-lam * hi)), 4), round(float(np.exp(-lam * lo)), 4),
                  round(1 - ans, 4)]
        extra = {"lo": lo, "hi": hi}
    elif ask == "mean":
        ans = scale
        stmt = f"X ~ Exponential(λ = {lam}). Find E[X]."
        wrongs = [round(lam, 4), round(1 / lam ** 2, 4), round(2 / lam ** 2, 4)]
    elif ask == "percentile":
        p = round(float(rng.choice([0.5, 0.75, 0.9, 0.95])), 2)
        ans = round(float(-np.log(1 - p) / lam), 4)
        stmt = f"X ~ Exponential(λ = {lam}). Find the {int(p * 100)}th percentile."
        wrongs = [round(p / lam, 4), round(float(-np.log(p) / lam), 4), round((1 - p) / lam, 4)]
        extra = {"p": p}
    elif ask == "memoryless":
        s = round(float(rng.uniform(0.5, 2.0 / lam)), 2)
        t = round(float(rng.uniform(0.1, 1.0 / lam)), 2)
        ans = round(float(np.exp(-lam * t)), 4)
        stmt = (
            f"X ~ Exponential(λ = {lam}). By the memoryless property, "
            f"find P(X > {s} + {t} | X > {s})."
        )
        wrongs = [round(float(np.exp(-lam * (s + t))), 4), round(float(np.exp(-lam * s)), 4),
                  round(1 - ans, 4)]
        extra = {"s": s, "t": t}
    else:
        raise ValueError(f"Unknown ask '{ask}' for exponential")

    return Problem("exponential", ask, stmt, ans, make_mc_choices(ans, wrongs, rng),
                   params={"lam": lam, **extra}, seed=seed)


@register("gamma")
def gen_gamma(ask: str, ranges: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    alpha = round(float(rng.uniform(*ranges["alpha"])), 1)
    theta = round(float(rng.uniform(*ranges["theta"])), 2)
    extra: dict = {}

    if ask == "mean":
        ans = round(alpha * theta, 4)
        stmt = f"X ~ Gamma(α = {alpha}, θ = {theta}) [mean = αθ]. Find E[X]."
        wrongs = [round(alpha * theta ** 2, 4), round(alpha / theta, 4),
                  round((alpha * theta) ** 0.5, 4)]
    elif ask == "variance":
        ans = round(alpha * theta ** 2, 4)
        stmt = f"X ~ Gamma(α = {alpha}, θ = {theta}). Find Var(X)."
        wrongs = [round(alpha * theta, 4), round(alpha ** 2 * theta ** 2, 4),
                  round((alpha * theta ** 2) ** 0.5, 4)]
    elif ask == "prob_interval":
        lo = round(float(rng.uniform(0, alpha * theta * 0.5)), 2)
        hi = round(float(rng.uniform(alpha * theta, alpha * theta * 2.5)), 2)
        ans = round(float(gamma_dist.cdf(hi, a=alpha, scale=theta)
                          - gamma_dist.cdf(lo, a=alpha, scale=theta)), 4)
        stmt = f"X ~ Gamma(α = {alpha}, θ = {theta}). Find P({lo} < X < {hi})."
        wrongs = [round(1 - ans, 4), round(float(gamma_dist.cdf(hi, a=alpha, scale=theta)), 4),
                  round(float(gamma_dist.sf(lo, a=alpha, scale=theta)), 4)]
        extra = {"lo": lo, "hi": hi}
    else:
        raise ValueError(f"Unknown ask '{ask}' for gamma")

    return Problem("gamma", ask, stmt, ans, make_mc_choices(ans, wrongs, rng),
                   params={"alpha": alpha, "theta": theta, **extra}, seed=seed)


@register("normal")
def gen_normal(ask: str, ranges: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    mu = round(float(rng.uniform(*ranges["mu"])), 1)
    sigma = round(float(rng.uniform(*ranges["sigma"])), 1)
    extra: dict = {}

    if ask == "prob_interval":
        lo = round(float(rng.uniform(mu - 2 * sigma, mu)), 1)
        hi = round(float(rng.uniform(mu, mu + 2 * sigma)), 1)
        ans = round(float(norm.cdf(hi, mu, sigma) - norm.cdf(lo, mu, sigma)), 4)
        stmt = f"X ~ N(μ = {mu}, σ = {sigma}). Find P({lo} < X < {hi})."
        wrongs = [round(1 - ans, 4), round(float(norm.cdf(hi, mu, sigma)), 4),
                  round(float(norm.sf(lo, mu, sigma)), 4)]
        extra = {"lo": lo, "hi": hi}
    elif ask == "survival":
        x = round(float(rng.uniform(mu, mu + 2 * sigma)), 1)
        ans = round(float(norm.sf(x, mu, sigma)), 4)
        stmt = f"X ~ N(μ = {mu}, σ = {sigma}). Find P(X > {x})."
        wrongs = [round(float(norm.cdf(x, mu, sigma)), 4), round(1 - ans, 4),
                  round(float(norm.sf(x, mu, sigma)) * 2, 4)]
        extra = {"x": x}
    elif ask == "percentile":
        p = round(float(rng.choice([0.1, 0.25, 0.75, 0.9, 0.95])), 2)
        ans = round(float(norm.ppf(p, mu, sigma)), 4)
        stmt = f"X ~ N(μ = {mu}, σ = {sigma}). Find the {int(p * 100)}th percentile."
        wrongs = [round(mu + sigma, 4), round(float(norm.ppf(1 - p, mu, sigma)), 4),
                  round(float(norm.ppf(p, mu, sigma ** 2)), 4)]
        extra = {"p": p}
    elif ask == "standardize":
        x = round(float(rng.uniform(mu - 2 * sigma, mu + 2 * sigma)), 1)
        z = round((x - mu) / sigma, 4)
        ans = round(float(norm.cdf(z)), 4)
        stmt = (
            f"X ~ N(μ = {mu}, σ = {sigma}). Standardize and find P(X ≤ {x}), "
            f"i.e. P(Z ≤ {z})."
        )
        wrongs = [round(1 - ans, 4), round(float(norm.cdf(-z)), 4),
                  round(float(norm.cdf(z, loc=mu, scale=sigma)), 4)]
        extra = {"x": x, "z": z}
    else:
        raise ValueError(f"Unknown ask '{ask}' for normal")

    return Problem("normal", ask, stmt, ans, make_mc_choices(ans, wrongs, rng),
                   params={"mu": mu, "sigma": sigma, **extra}, seed=seed)


@register("beta")
def gen_beta(ask: str, ranges: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    a = int(rng.integers(ranges["alpha"][0], ranges["alpha"][1] + 1))
    b = int(rng.integers(ranges["beta"][0], ranges["beta"][1] + 1))
    extra: dict = {}

    if ask == "mean":
        ans = round(a / (a + b), 4)
        stmt = f"X ~ Beta(α = {a}, β = {b}). Find E[X]."
        wrongs = [round(b / (a + b), 4), round(a / (a + b) ** 2, 4),
                  round(a * b / (a + b) ** 2, 4)]
    elif ask == "prob_interval":
        lo = round(float(rng.uniform(0.1, 0.4)), 2)
        hi = round(float(rng.uniform(0.6, 0.9)), 2)
        ans = round(float(beta_dist.cdf(hi, a, b) - beta_dist.cdf(lo, a, b)), 4)
        stmt = f"X ~ Beta(α = {a}, β = {b}). Find P({lo} < X < {hi})."
        wrongs = [round(1 - ans, 4), round(float(beta_dist.cdf(hi, a, b)), 4),
                  round(float(beta_dist.sf(lo, a, b)), 4)]
        extra = {"lo": lo, "hi": hi}
    else:
        raise ValueError(f"Unknown ask '{ask}' for beta")

    return Problem("beta", ask, stmt, ans, make_mc_choices(ans, wrongs, rng),
                   params={"alpha": a, "beta": b, **extra}, seed=seed)


@register("lognormal")
def gen_lognormal(ask: str, ranges: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    mu = round(float(rng.uniform(*ranges["mu"])), 2)
    sigma = round(float(rng.uniform(*ranges["sigma"])), 2)
    extra: dict = {}

    if ask == "mean":
        ans = round(float(np.exp(mu + sigma ** 2 / 2)), 4)
        stmt = f"ln X ~ N(μ = {mu}, σ = {sigma}). Find E[X]."
        wrongs = [round(float(np.exp(mu)), 4),
                  round(float(np.exp(mu + sigma ** 2)), 4),
                  round(float(np.exp(2 * mu + sigma ** 2) * (np.exp(sigma ** 2) - 1)), 4)]
    elif ask == "prob_interval":
        lo = round(float(np.exp(mu - sigma)), 2)
        hi = round(float(np.exp(mu + sigma)), 2)
        ans = round(float(lognorm.cdf(hi, s=sigma, scale=np.exp(mu))
                          - lognorm.cdf(lo, s=sigma, scale=np.exp(mu))), 4)
        stmt = f"ln X ~ N(μ = {mu}, σ = {sigma}). Find P({lo} < X < {hi})."
        wrongs = [round(1 - ans, 4), round(float(lognorm.cdf(hi, s=sigma, scale=np.exp(mu))), 4),
                  round(float(lognorm.sf(lo, s=sigma, scale=np.exp(mu))), 4)]
        extra = {"lo": lo, "hi": hi}
    else:
        raise ValueError(f"Unknown ask '{ask}' for lognormal")

    return Problem("lognormal", ask, stmt, ans, make_mc_choices(ans, wrongs, rng),
                   params={"mu": mu, "sigma": sigma, **extra}, seed=seed)


@register("chisquare")
def gen_chisquare(ask: str, ranges: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    k = int(rng.integers(ranges["k"][0], ranges["k"][1] + 1))

    if ask == "mean":
        ans = float(k)
        stmt = f"X ~ χ²(k = {k}). Find E[X]."
        wrongs = [float(2 * k), float(k / 2), float(k ** 0.5)]
    elif ask == "variance":
        ans = float(2 * k)
        stmt = f"X ~ χ²(k = {k}). Find Var(X)."
        wrongs = [float(k), float(4 * k), float(k ** 2)]
    else:
        raise ValueError(f"Unknown ask '{ask}' for chisquare")

    return Problem("chisquare", ask, stmt, ans, make_mc_choices(ans, wrongs, rng),
                   params={"k": k}, seed=seed)


@register("moments")
def gen_moments(ask: str, ranges: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    mu = round(float(rng.uniform(*ranges.get("mu", [1.0, 6.0]))), 1)
    sigma2 = round(float(rng.uniform(*ranges.get("sigma2", [0.5, 5.0]))), 1)
    m2 = round(sigma2 + mu ** 2, 4)

    if ask == "ex_squared":
        ans = m2
        stmt = (
            f"A random variable X has mean E[X] = {mu} and "
            f"Var(X) = {sigma2}. Find E[X²] = Var(X) + (E[X])²."
        )
        wrongs = [round(mu ** 2, 4), round(sigma2, 4),
                  round((mu + sigma2 ** 0.5) ** 2, 4)]
        params = {"mu": mu, "sigma2": sigma2}

    elif ask == "variance_from_moments":
        ans = round(sigma2, 4)
        stmt = (
            f"A random variable X has E[X] = {mu} and E[X²] = {m2}. "
            f"Find Var(X) = E[X²] − (E[X])²."
        )
        wrongs = [round(m2, 4), round(mu ** 2, 4),
                  round(sigma2 ** 0.5, 4)]
        params = {"mu": mu, "sigma2": sigma2, "m2": m2}

    else:
        raise ValueError(f"Unknown ask '{ask}' for moments")

    return Problem("moments", ask, stmt, ans,
                   make_mc_choices(ans, wrongs, rng),
                   params=params, seed=seed)


@register("pareto")
def gen_pareto(ask: str, ranges: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    # Ensure alpha > 1 so mean exists
    alpha = max(round(float(rng.uniform(*ranges["alpha"])), 1), 1.5)
    theta = round(float(rng.uniform(*ranges["theta"])), 1)
    extra: dict = {}

    if ask == "mean":
        ans = round(theta / (alpha - 1), 4)
        stmt = (
            f"X ~ Pareto(α = {alpha}, θ = {theta}) "
            f"with S(x) = (θ/(x+θ))^α. Find E[X] = θ/(α−1)."
        )
        wrongs = [round(theta / alpha, 4),
                  round(theta * (alpha - 1), 4),
                  round(alpha / theta, 4)]

    elif ask == "survival":
        x = round(float(rng.uniform(0.5 * theta, 3.0 * theta)), 2)
        ans = round(float((theta / (x + theta)) ** alpha), 4)
        stmt = (
            f"X ~ Pareto(α = {alpha}, θ = {theta}). "
            f"Find P(X > {x}) = (θ/(x+θ))^α."
        )
        wrongs = [round(1 - ans, 4),
                  round(float((theta / (x + theta)) ** (alpha + 1)), 4),
                  round(float((x / (x + theta)) ** alpha), 4)]
        extra = {"x": x}

    elif ask == "prob_interval":
        x1 = round(float(rng.uniform(0.2 * theta, theta)), 2)
        x2 = round(float(rng.uniform(2.0 * theta, 4.0 * theta)), 2)
        s1 = float((theta / (x1 + theta)) ** alpha)
        s2 = float((theta / (x2 + theta)) ** alpha)
        ans = round(s1 - s2, 4)
        stmt = (
            f"X ~ Pareto(α = {alpha}, θ = {theta}). "
            f"Find P({x1} < X < {x2}) = S({x1}) − S({x2})."
        )
        wrongs = [round(1 - ans, 4), round(s2, 4), round(s1, 4)]
        extra = {"x1": x1, "x2": x2}

    else:
        raise ValueError(f"Unknown ask '{ask}' for pareto")

    return Problem("pareto", ask, stmt, ans,
                   make_mc_choices(ans, wrongs, rng),
                   params={"alpha": alpha, "theta": theta, **extra},
                   seed=seed)


@register("weibull")
def gen_weibull(ask: str, ranges: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    alpha = round(float(rng.uniform(*ranges["alpha"])), 1)
    theta = round(float(rng.uniform(*ranges["theta"])), 1)
    extra: dict = {}

    if ask == "survival":
        x = round(float(rng.uniform(0.5 * theta, 2.0 * theta)), 2)
        ans = round(float(np.exp(-((x / theta) ** alpha))), 4)
        stmt = (
            f"X ~ Weibull(α = {alpha}, θ = {theta}) "
            f"with S(x) = exp(−(x/θ)^α). Find P(X > {x})."
        )
        wrongs = [round(1 - ans, 4),
                  round(float(np.exp(-x / theta)), 4),
                  round(float(np.exp(-((x / theta) ** (alpha + 1)))), 4)]
        extra = {"x": x}

    elif ask == "cdf":
        x = round(float(rng.uniform(0.5 * theta, 2.0 * theta)), 2)
        ans = round(float(1 - np.exp(-((x / theta) ** alpha))), 4)
        stmt = (
            f"X ~ Weibull(α = {alpha}, θ = {theta}). "
            f"Find P(X ≤ {x}) = 1 − exp(−(x/θ)^α)."
        )
        wrongs = [round(1 - ans, 4),
                  round(float(np.exp(-x / theta)), 4),
                  round(float(1 - np.exp(-x / theta)), 4)]
        extra = {"x": x}

    elif ask == "mean":
        g = float(gamma_fn(1 + 1 / alpha))
        ans = round(theta * g, 4)
        stmt = (
            f"X ~ Weibull(α = {alpha}, θ = {theta}). "
            f"Find E[X] = θ · Γ(1 + 1/α)."
        )
        wrongs = [round(theta / alpha, 4),
                  round(theta * float(gamma_fn(1 + 2 / alpha)), 4),
                  round(theta * alpha, 4)]

    else:
        raise ValueError(f"Unknown ask '{ask}' for weibull")

    return Problem("weibull", ask, stmt, ans,
                   make_mc_choices(ans, wrongs, rng),
                   params={"alpha": alpha, "theta": theta, **extra},
                   seed=seed)
