"""Generators for discrete distributions: Bernoulli, Binomial, Geometric,
Negative Binomial, Hypergeometric, Poisson, and Discrete Uniform."""
from __future__ import annotations

import numpy as np
from scipy.stats import binom, geom, hypergeom, nbinom, poisson

from engine.generation.base import Problem, make_mc_choices, register


@register("bernoulli")
def gen_bernoulli(ask: str, ranges: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    p = round(float(rng.uniform(*ranges["p"])), 2)
    q = round(1 - p, 2)

    if ask == "mean":
        ans = p
        stmt = f"X ~ Bernoulli(p = {p}). Find E[X]."
        wrongs = [q, p * q, p ** 2]
    elif ask == "variance":
        ans = round(p * q, 4)
        stmt = f"X ~ Bernoulli(p = {p}). Find Var(X)."
        wrongs = [p, q, round(p * q) ** 0.5]
    else:
        raise ValueError(f"Unknown ask '{ask}' for bernoulli")

    return Problem("bernoulli", ask, stmt, ans, make_mc_choices(ans, wrongs, rng),
                   params={"p": p}, seed=seed)


@register("binomial")
def gen_binomial(ask: str, ranges: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    n = int(rng.integers(ranges["n"][0], ranges["n"][1] + 1))
    p = round(float(rng.uniform(*ranges["p"])), 2)
    q = round(1 - p, 2)
    k = int(rng.integers(0, n + 1))

    if ask == "pmf_eq":
        ans = round(float(binom.pmf(k, n, p)), 4)
        stmt = f"X ~ Binomial(n = {n}, p = {p}). Find P(X = {k})."
        wrongs = [
            round(1 - ans, 4),
            round(float(binom.cdf(k, n, p)), 4),
            round(float(binom.pmf(k + 1 if k < n else k - 1, n, p)), 4),
        ]
    elif ask == "cdf_le":
        ans = round(float(binom.cdf(k, n, p)), 4)
        stmt = f"X ~ Binomial(n = {n}, p = {p}). Find P(X ≤ {k})."
        wrongs = [
            round(float(binom.sf(k - 1, n, p)), 4),
            round(float(binom.pmf(k, n, p)), 4),
            round(1 - ans, 4),
        ]
    elif ask == "cdf_ge":
        ans = round(float(binom.sf(k - 1, n, p)), 4)
        stmt = f"X ~ Binomial(n = {n}, p = {p}). Find P(X ≥ {k})."
        wrongs = [
            round(float(binom.cdf(k, n, p)), 4),
            round(float(binom.sf(k, n, p)), 4),
            round(1 - ans, 4),
        ]
    elif ask == "mean":
        ans = round(n * p, 4)
        stmt = f"X ~ Binomial(n = {n}, p = {p}). Find E[X]."
        wrongs = [round(n * p * q, 4), round(p, 4), round((n * p * q) ** 0.5, 4)]
    elif ask == "variance":
        ans = round(n * p * q, 4)
        stmt = f"X ~ Binomial(n = {n}, p = {p}). Find Var(X)."
        wrongs = [round(n * p, 4), round((n * p * q) ** 0.5, 4), round(n * p ** 2, 4)]
    else:
        raise ValueError(f"Unknown ask '{ask}' for binomial")

    return Problem("binomial", ask, stmt, ans, make_mc_choices(ans, wrongs, rng),
                   params={"n": n, "p": p, "k": k}, seed=seed)


@register("geometric")
def gen_geometric(ask: str, ranges: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    p = round(float(rng.uniform(*ranges["p"])), 2)
    q = round(1 - p, 2)
    k = int(rng.integers(1, max(2, int(4 / p)) + 1))

    if ask == "pmf_eq":
        ans = round(float(geom.pmf(k, p)), 4)
        stmt = f"X ~ Geometric(p = {p}), trials until first success. Find P(X = {k})."
        wrongs = [round(1 - ans, 4), round(q ** (k - 1), 4), round(p ** k, 4)]
    elif ask == "cdf_ge":
        ans = round(float(geom.sf(k - 1, p)), 4)
        stmt = f"X ~ Geometric(p = {p}). Find P(X ≥ {k})."
        wrongs = [round(float(geom.cdf(k, p)), 4), round(q ** k, 4), round(1 - ans, 4)]
    elif ask == "mean":
        ans = round(1 / p, 4)
        stmt = f"X ~ Geometric(p = {p}). Find E[X]."
        wrongs = [round(q / p, 4), round(q / p ** 2, 4), round(p, 4)]
    elif ask == "variance":
        ans = round(q / p ** 2, 4)
        stmt = f"X ~ Geometric(p = {p}). Find Var(X)."
        wrongs = [round(1 / p, 4), round(q / p, 4), round(1 / p ** 2, 4)]
    else:
        raise ValueError(f"Unknown ask '{ask}' for geometric")

    return Problem("geometric", ask, stmt, ans, make_mc_choices(ans, wrongs, rng),
                   params={"p": p, "k": k}, seed=seed)


@register("negbinomial")
def gen_negbinomial(ask: str, ranges: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    r = int(rng.integers(ranges["r"][0], ranges["r"][1] + 1))
    p = round(float(rng.uniform(*ranges["p"])), 2)
    q = round(1 - p, 2)
    k = int(rng.integers(r, r + int(3 * q / p) + 2))

    if ask == "pmf_eq":
        ans = round(float(nbinom.pmf(k - r, r, p)), 4)
        stmt = (
            f"X = trials until the {r}-th success, p = {p}. Find P(X = {k})."
        )
        wrongs = [round(1 - ans, 4), round(float(nbinom.pmf(k - r + 1, r, p)), 4),
                  round(float(nbinom.cdf(k - r, r, p)), 4)]
    elif ask == "mean":
        ans = round(r / p, 4)
        stmt = f"X = trials until {r}-th success, p = {p}. Find E[X]."
        wrongs = [round(r * q / p ** 2, 4), round(r / p ** 2, 4), round(r * q / p, 4)]
    elif ask == "variance":
        ans = round(r * q / p ** 2, 4)
        stmt = f"X = trials until {r}-th success, p = {p}. Find Var(X)."
        wrongs = [round(r / p, 4), round(r * q / p, 4), round(r / p ** 2, 4)]
    else:
        raise ValueError(f"Unknown ask '{ask}' for negbinomial")

    return Problem("negbinomial", ask, stmt, ans, make_mc_choices(ans, wrongs, rng),
                   params={"r": r, "p": p, "k": k}, seed=seed)


@register("hypergeometric")
def gen_hypergeometric(ask: str, ranges: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    N = int(rng.integers(ranges["N"][0], ranges["N"][1] + 1))
    K = int(rng.integers(ranges["K"][0], min(ranges["K"][1], N - 1) + 1))
    n = int(rng.integers(ranges["n"][0], min(ranges["n"][1], N) + 1))
    k = int(rng.integers(max(0, n - (N - K)), min(n, K) + 1))

    if ask == "pmf_eq":
        ans = round(float(hypergeom.pmf(k, N, K, n)), 4)
        stmt = (
            f"Urn has {N} items: {K} successes, {N - K} failures. "
            f"Draw {n} without replacement. Find P(X = {k} successes)."
        )
        # Key distractor: binomial answer (forgot no-replacement)
        binom_ans = round(float(binom.pmf(k, n, K / N)), 4)
        wrongs = [binom_ans, round(1 - ans, 4), round(float(hypergeom.pmf(k + 1, N, K, n)), 4)]
    elif ask == "mean":
        ans = round(n * K / N, 4)
        stmt = (
            f"Draw {n} from {N} items ({K} successes). Find E[X]."
        )
        wrongs = [round(n * K / N * (1 - K / N), 4), round(K / N, 4), round(n * K / N ** 2, 4)]
    else:
        raise ValueError(f"Unknown ask '{ask}' for hypergeometric")

    return Problem("hypergeometric", ask, stmt, ans, make_mc_choices(ans, wrongs, rng),
                   params={"N": N, "K": K, "n": n, "k": k}, seed=seed)


@register("poisson")
def gen_poisson(ask: str, ranges: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    lam = round(float(rng.uniform(*ranges["lam"])), 2)
    k = int(rng.integers(0, max(1, int(2 * lam)) + 1))

    if ask == "pmf_eq":
        ans = round(float(poisson.pmf(k, lam)), 4)
        stmt = f"X ~ Poisson(λ = {lam}). Find P(X = {k})."
        wrongs = [round(1 - ans, 4), round(float(poisson.cdf(k, lam)), 4),
                  round(float(poisson.pmf(k + 1, lam)), 4)]
    elif ask == "cdf_le":
        ans = round(float(poisson.cdf(k, lam)), 4)
        stmt = f"X ~ Poisson(λ = {lam}). Find P(X ≤ {k})."
        wrongs = [round(float(poisson.sf(k, lam)), 4), round(float(poisson.pmf(k, lam)), 4),
                  round(1 - ans, 4)]
    elif ask == "cdf_ge":
        ans = round(float(poisson.sf(k - 1, lam)), 4)
        stmt = f"X ~ Poisson(λ = {lam}). Find P(X ≥ {k})."
        wrongs = [round(float(poisson.cdf(k, lam)), 4), round(float(poisson.sf(k, lam)), 4),
                  round(1 - ans, 4)]
    elif ask == "mean":
        ans = lam
        stmt = f"X ~ Poisson(λ = {lam}). Find E[X]."
        wrongs = [round(lam ** 0.5, 4), round(lam ** 2, 4), round(1 / lam, 4)]
    else:
        raise ValueError(f"Unknown ask '{ask}' for poisson")

    return Problem("poisson", ask, stmt, ans, make_mc_choices(ans, wrongs, rng),
                   params={"lam": lam, "k": k}, seed=seed)


@register("discrete_uniform")
def gen_discrete_uniform(ask: str, ranges: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    n = int(rng.integers(ranges["n"][0], ranges["n"][1] + 1))
    k = int(rng.integers(1, n + 1))

    if ask == "mean":
        ans = round((n + 1) / 2, 4)
        stmt = f"X ~ DiscreteUniform on {{1, 2, …, {n}}}. Find E[X]."
        wrongs = [round(n / 2, 4), round((n + 1) / 4, 4), round(n, 4)]
    elif ask == "variance":
        ans = round((n ** 2 - 1) / 12, 4)
        stmt = f"X ~ DiscreteUniform on {{1, 2, …, {n}}}. Find Var(X)."
        wrongs = [round((n + 1) / 2, 4), round((n ** 2 - 1) / 6, 4), round(n / 12, 4)]
    elif ask == "pmf_eq":
        ans = round(1 / n, 4)
        stmt = f"X ~ DiscreteUniform on {{1, 2, …, {n}}}. Find P(X = {k})."
        wrongs = [round(k / n, 4), round(1 / (n - 1), 4), round(2 / n, 4)]
    else:
        raise ValueError(f"Unknown ask '{ask}' for discrete_uniform")

    return Problem("discrete_uniform", ask, stmt, ans, make_mc_choices(ans, wrongs, rng),
                   params={"n": n, "k": k}, seed=seed)
