"""Generators for general probability topics: set operations, combinatorics,
conditional probability, independence, Bayes' theorem, density basics,
expectation, variance, MGFs, and univariate transformations."""
from __future__ import annotations

from math import comb, factorial, perm

import numpy as np

from engine.generation.base import Problem, make_mc_choices, register


@register("set_inclusion_exclusion")
def gen_set_inclusion_exclusion(ask: str, ranges: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    pa = round(float(rng.uniform(0.2, 0.7)), 2)
    pb = round(float(rng.uniform(0.2, 0.7)), 2)
    pab = round(float(rng.uniform(0.05, min(pa, pb) * 0.8)), 2)
    paub = round(pa + pb - pab, 4)

    if ask == "union_prob":
        ans = paub
        stmt = (
            f"P(A) = {pa}, P(B) = {pb}, P(A ∩ B) = {pab}. "
            f"Find P(A ∪ B)."
        )
        wrongs = [round(pa + pb, 4), round(pa + pb + pab, 4), round(1 - paub, 4)]
    elif ask == "complement_prob":
        ans = round(1 - paub, 4)
        stmt = (
            f"P(A) = {pa}, P(B) = {pb}, P(A ∩ B) = {pab}. "
            f"Find P((A ∪ B)ᶜ)."
        )
        wrongs = [paub, round(1 - pa - pb, 4), round(pab, 4)]
    else:
        raise ValueError(f"Unknown ask '{ask}' for set_inclusion_exclusion")

    return Problem("set_inclusion_exclusion", ask, stmt, ans,
                   make_mc_choices(ans, wrongs, rng),
                   params={"pa": pa, "pb": pb, "pab": pab}, seed=seed)


@register("combinatorics")
def gen_combinatorics(ask: str, ranges: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    n = int(rng.integers(ranges["n"][0], ranges["n"][1] + 1))
    r = int(rng.integers(ranges["r"][0], min(ranges["r"][1], n) + 1))

    if ask == "nCr":
        ans = float(comb(n, r))
        stmt = (
            f"How many ways to choose {r} items from {n} "
            f"(order doesn't matter)? Find C({n}, {r})."
        )
        wrongs = [float(perm(n, r)), float(comb(n, r - 1)), float(comb(n - 1, r))]
    elif ask == "nPr":
        ans = float(perm(n, r))
        stmt = f"How many ordered arrangements of {r} items from {n}? Find P({n}, {r})."
        wrongs = [float(comb(n, r)), float(perm(n, r - 1)), float(factorial(r) * comb(n, r))]
    elif ask == "multinomial":
        # Split n into 3 groups
        r1 = int(rng.integers(1, max(2, n // 3)))
        r2 = int(rng.integers(1, max(2, n - r1)))
        r3 = n - r1 - r2
        if r3 < 1:
            r3 = 1
            r2 = max(1, n - r1 - r3)
        if r1 + r2 + r3 != n:
            r3 = n - r1 - r2
        ans = float(factorial(n) // (factorial(r1) * factorial(r2) * factorial(r3)))
        stmt = (
            f"Arrange {n} objects in 3 groups of {r1}, {r2}, {r3}. "
            f"Find the multinomial coefficient."
        )
        wrongs = [float(comb(n, r1) * comb(n - r1, r2)),
                  float(factorial(n)), float(ans / r1)]
    else:
        raise ValueError(f"Unknown ask '{ask}' for combinatorics")

    extra = {"r1": r1, "r2": r2, "r3": r3} if ask == "multinomial" else {}
    return Problem("combinatorics", ask, stmt, ans, make_mc_choices(ans, wrongs, rng),
                   params={"n": n, "r": r, **extra}, seed=seed, tolerance=0.5)


@register("addition_rule")
def gen_addition_rule(ask: str, ranges: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    pa = round(float(rng.uniform(0.2, 0.6)), 2)
    pb = round(float(rng.uniform(0.2, 0.6)), 2)
    pab = round(float(rng.uniform(0.05, min(pa, pb) * 0.8)), 2)

    if ask == "union_prob":
        ans = round(pa + pb - pab, 4)
        stmt = f"P(A) = {pa}, P(B) = {pb}, P(A ∩ B) = {pab}. Find P(A ∪ B)."
        wrongs = [round(pa + pb, 4), round(pa + pb + pab, 4), round(1 - ans, 4)]
    elif ask == "either_or":
        # P(exactly one of A or B)
        ans = round(pa + pb - 2 * pab, 4)
        stmt = (
            f"P(A) = {pa}, P(B) = {pb}, P(A ∩ B) = {pab}. "
            f"Find P(exactly one of A or B occurs)."
        )
        wrongs = [round(pa + pb - pab, 4), round(pa + pb, 4), round(pab, 4)]
    else:
        raise ValueError(f"Unknown ask '{ask}' for addition_rule")

    return Problem("addition_rule", ask, stmt, ans, make_mc_choices(ans, wrongs, rng),
                   params={"pa": pa, "pb": pb, "pab": pab}, seed=seed)


@register("conditional")
def gen_conditional(ask: str, ranges: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    pb = round(float(rng.uniform(0.3, 0.7)), 2)
    pa_given_b = round(float(rng.uniform(0.2, 0.8)), 2)
    pab = round(pa_given_b * pb, 4)
    pa = round(float(rng.uniform(max(pab, 0.15), 0.85)), 2)

    if ask == "cond_prob":
        ans = pa_given_b
        stmt = f"P(B) = {pb}, P(A ∩ B) = {pab}. Find P(A | B)."
        wrongs = [round(pab / pa, 4) if pa > 0 else 0.5,
                  round(pb, 4), round(pa, 4)]
    elif ask == "joint_from_cond":
        ans = pab
        stmt = f"P(B) = {pb}, P(A | B) = {pa_given_b}. Find P(A ∩ B)."
        wrongs = [round(pa_given_b + pb, 4), round(pa_given_b / pb, 4),
                  round(pb * (1 - pa_given_b), 4)]
    else:
        raise ValueError(f"Unknown ask '{ask}' for conditional")

    return Problem("conditional", ask, stmt, ans, make_mc_choices(ans, wrongs, rng),
                   params={"pb": pb, "pa_given_b": pa_given_b, "pab": pab, "pa": pa},
                   seed=seed)


@register("independence")
def gen_independence(ask: str, ranges: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    pa = round(float(rng.uniform(0.2, 0.7)), 2)
    pb = round(float(rng.uniform(0.2, 0.7)), 2)

    if ask == "is_independent":
        # Make it independent with prob 0.5
        if rng.random() > 0.5:
            pab = round(pa * pb, 4)
            ans = round(pab, 4)  # correct joint under independence
            stmt = (
                f"A and B are independent. P(A) = {pa}, P(B) = {pb}. "
                f"Find P(A ∩ B)."
            )
            wrongs = [round(pa + pb, 4), round(pa + pb - pab, 4), round(pa * pb ** 2, 4)]
        else:
            pab = round(pa * pb, 4)
            ans = round(pa * pb, 4)
            stmt = (
                f"P(A) = {pa}, P(B) = {pb}. If A and B are independent, "
                f"find P(A ∩ B)."
            )
            wrongs = [round(pa + pb, 4), round(pa * pb + 0.05, 4), round(pa * pb / 2, 4)]
    elif ask == "joint_indep":
        pab = round(pa * pb, 4)
        ans = pab
        stmt = f"A and B are independent, P(A) = {pa}, P(B) = {pb}. Find P(A ∩ B)."
        wrongs = [round(pa + pb - pab, 4), round(pa * pb ** 2, 4), round(pa ** 2 * pb, 4)]
    else:
        raise ValueError(f"Unknown ask '{ask}' for independence")

    return Problem("independence", ask, stmt, ans, make_mc_choices(ans, wrongs, rng),
                   params={"pa": pa, "pb": pb}, seed=seed)


@register("bayes")
def gen_bayes(ask: str, ranges: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    n_hyp = int(rng.integers(ranges["n_hypotheses"][0], ranges["n_hypotheses"][1] + 1))

    # Sample priors summing to 1
    raw = rng.uniform(1, 5, size=n_hyp)
    priors = np.round(raw / raw.sum(), 3)
    priors[-1] = round(1 - priors[:-1].sum(), 3)

    # Sample likelihoods
    likelihoods = np.round(rng.uniform(0.1, 0.9, size=n_hyp), 2)

    # P(E) via total probability
    pe = float(np.dot(priors, likelihoods))
    # Posterior for H₁
    posterior = round(priors[0] * likelihoods[0] / pe, 4)

    if ask == "posterior":
        prior_str = ", ".join([f"P(H{i+1}) = {priors[i]}" for i in range(n_hyp)])
        like_str = ", ".join([f"P(E|H{i+1}) = {likelihoods[i]}" for i in range(n_hyp)])
        stmt = (
            f"{prior_str}. {like_str}. "
            f"Find P(H₁ | E) using Bayes' theorem."
        )
        wrongs = [
            round(priors[0] * likelihoods[0], 4),  # forgot normalization
            round(likelihoods[0] * priors[0] / priors[0], 4) if priors[0] > 0 else 0.5,
            round(1 - posterior, 4),
        ]
    else:
        raise ValueError(f"Unknown ask '{ask}' for bayes")

    return Problem("bayes", ask, stmt, posterior, make_mc_choices(posterior, wrongs, rng),
                   params={"priors": priors.tolist(), "likelihoods": likelihoods.tolist()},
                   seed=seed)


@register("counting_prob")
def gen_counting_prob(ask: str, ranges: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)

    if ask == "draw_prob":
        N = int(rng.integers(10, 25))
        K = int(rng.integers(2, N // 2))
        n = int(rng.integers(2, min(6, N // 3) + 1))
        k = int(rng.integers(1, min(n, K) + 1))
        # P(exactly k successes in n draws without replacement)
        from scipy.stats import hypergeom
        ans = round(float(hypergeom.pmf(k, N, K, n)), 4)
        stmt = (
            f"A box has {N} items, {K} are defective. Draw {n} at random "
            f"(without replacement). Find the probability of exactly {k} defective items."
        )
        from scipy.stats import binom
        binom_ans = round(float(binom.pmf(k, n, K / N)), 4)
        wrongs = [binom_ans, round(1 - ans, 4), round(comb(K, k) / comb(N, n), 4)]
        params = {"N": N, "K": K, "n": n, "k": k}
    elif ask == "arrangement_prob":
        n = int(rng.integers(5, 12))
        r = int(rng.integers(2, min(5, n) + 1))
        # P(specific arrangement) = 1 / P(n, r)
        favorable = int(rng.integers(1, 4))
        total = perm(n, r)
        ans = round(favorable / total, 4)
        stmt = (
            f"Arrange {r} items chosen from {n} in a row. "
            f"Find the probability of {favorable} specific arrangement(s)."
        )
        wrongs = [round(favorable / comb(n, r), 4), round(1 / comb(n, r), 4),
                  round(favorable / factorial(n), 4)]
        params = {"n": n, "r": r, "favorable": favorable}
    else:
        raise ValueError(f"Unknown ask '{ask}' for counting_prob")

    return Problem("counting_prob", ask, stmt, ans, make_mc_choices(ans, wrongs, rng),
                   params=params, seed=seed)


@register("density_basics")
def gen_density_basics(ask: str, ranges: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    k = int(rng.integers(1, 5))  # power: f(x) = c * x^k on [0,1]
    c = k + 1  # normalization constant

    extra: dict = {}
    if ask == "normalize_constant":
        ans = float(c)
        stmt = f"f(x) = c·x^{k} for 0 < x < 1 (0 otherwise). Find c so that f is a valid PDF."
        wrongs = [float(k), float(1 / c), float(c + 1)]
    elif ask == "cdf_from_pdf":
        t = round(float(rng.uniform(0.2, 0.9)), 2)
        extra = {"t": t}
        ans = round(t ** (k + 1), 4)
        stmt = f"f(x) = {c}·x^{k} for 0 < x < 1. Find P(X ≤ {t})."
        wrongs = [round(c * t ** k, 4), round(t ** k, 4), round(1 - t ** (k + 1), 4)]
    elif ask == "prob_interval":
        lo = round(float(rng.uniform(0.1, 0.4)), 2)
        hi = round(float(rng.uniform(0.6, 0.95)), 2)
        extra = {"lo": lo, "hi": hi}
        ans = round(hi ** (k + 1) - lo ** (k + 1), 4)
        stmt = f"f(x) = {c}·x^{k} for 0 < x < 1. Find P({lo} < X < {hi})."
        wrongs = [round(c * (hi - lo), 4), round(hi ** k - lo ** k, 4),
                  round(1 - ans, 4)]
    else:
        raise ValueError(f"Unknown ask '{ask}' for density_basics")

    return Problem("density_basics", ask, stmt, ans, make_mc_choices(ans, wrongs, rng),
                   params={"k": k, **extra}, seed=seed)


@register("expectation_generic")
def gen_expectation_generic(ask: str, ranges: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    # X takes values {1, 2, 3} with sampled probabilities
    raw = rng.uniform(1, 4, size=3)
    probs = np.round(raw / raw.sum(), 3)
    probs[-1] = round(1 - probs[:-1].sum(), 3)
    x_vals = np.array([1.0, 2.0, 3.0])
    ex = float(np.dot(x_vals, probs))

    if ask == "mean":
        ans = round(ex, 4)
        stmt = (
            f"X has PMF: P(X=1) = {probs[0]}, P(X=2) = {probs[1]}, P(X=3) = {probs[2]}. "
            f"Find E[X]."
        )
        ex2 = float(np.dot(x_vals ** 2, probs))
        wrongs = [round(ex2, 4), round(ex2 - ex ** 2, 4), round(2.0, 4)]
    elif ask == "lotus":
        ans = round(float(np.dot(x_vals ** 2, probs)), 4)
        stmt = (
            f"X has PMF: P(X=1) = {probs[0]}, P(X=2) = {probs[1]}, P(X=3) = {probs[2]}. "
            f"Find E[X²]."
        )
        var_x = round(float(np.dot(x_vals ** 2, probs)) - ex ** 2, 4)
        wrongs = [round(ex ** 2, 4), round(ex, 4), var_x]
    else:
        raise ValueError(f"Unknown ask '{ask}' for expectation_generic")

    return Problem("expectation_generic", ask, stmt, ans, make_mc_choices(ans, wrongs, rng),
                   params={"probs": probs.tolist()}, seed=seed)


@register("variance_generic")
def gen_variance_generic(ask: str, ranges: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    raw = rng.uniform(1, 4, size=3)
    probs = np.round(raw / raw.sum(), 3)
    probs[-1] = round(1 - probs[:-1].sum(), 3)
    x_vals = np.array([1.0, 2.0, 3.0])
    ex = float(np.dot(x_vals, probs))
    ex2 = float(np.dot(x_vals ** 2, probs))
    var = ex2 - ex ** 2
    sd = var ** 0.5

    if ask == "variance":
        ans = round(var, 4)
        stmt = (
            f"X has PMF: P(X=1) = {probs[0]}, P(X=2) = {probs[1]}, P(X=3) = {probs[2]}. "
            f"Find Var(X)."
        )
        wrongs = [round(sd, 4), round(ex2, 4), round(ex, 4)]
    elif ask == "sd":
        ans = round(sd, 4)
        stmt = (
            f"X has PMF: P(X=1) = {probs[0]}, P(X=2) = {probs[1]}, P(X=3) = {probs[2]}. "
            f"Find SD(X)."
        )
        wrongs = [round(var, 4), round(ex, 4), round(var ** 2, 4)]
    else:
        raise ValueError(f"Unknown ask '{ask}' for variance_generic")

    return Problem("variance_generic", ask, stmt, ans, make_mc_choices(ans, wrongs, rng),
                   params={"probs": probs.tolist()}, seed=seed)


@register("mgf")
def gen_mgf(ask: str, ranges: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    # Use binomial MGF: M(t) = (q + p*e^t)^n
    n = int(rng.integers(3, 12))
    p = round(float(rng.uniform(0.2, 0.8)), 2)
    q = round(1 - p, 2)

    if ask == "moment_from_mgf":
        # E[X] = M'(0) = np for Binomial(n,p)
        ans = round(n * p, 4)
        stmt = (
            f"X has MGF M(t) = ({q} + {p}·eᵗ)^{n}. "
            f"Find E[X] using M'(0)."
        )
        wrongs = [round(n * q, 4), round(n * p * q, 4), round(n * p ** 2, 4)]
    elif ask == "identify_dist_from_mgf":
        # Find E[X²] = M''(0)
        ex = n * p
        ex2 = n * p * q + (n * p) ** 2
        ans = round(ex2, 4)
        stmt = (
            f"X has MGF M(t) = ({q} + {p}·eᵗ)^{n}. "
            f"Find E[X²] = M''(0)."
        )
        wrongs = [round(ex ** 2, 4), round(n * p * q, 4), round(ex, 4)]
    else:
        raise ValueError(f"Unknown ask '{ask}' for mgf")

    return Problem("mgf", ask, stmt, ans, make_mc_choices(ans, wrongs, rng),
                   params={"n": n, "p": p}, seed=seed)


@register("transformation_univariate")
def gen_transformation_univariate(ask: str, ranges: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    lam = round(float(rng.uniform(0.5, 3.0)), 2)

    extra: dict = {}
    if ask == "cdf_method":
        # X ~ Exp(λ), Y = X². Find P(Y ≤ y₀) = P(X ≤ √y₀) = 1 - e^{-λ√y₀}
        y0 = round(float(rng.uniform(0.5, 4.0)), 2)
        extra = {"y0": y0}
        ans = round(float(1 - np.exp(-lam * y0 ** 0.5)), 4)
        stmt = (
            f"X ~ Exponential(λ = {lam}). Let Y = X². "
            f"Find P(Y ≤ {y0}) using the CDF method."
        )
        wrongs = [round(1 - float(np.exp(-lam * y0)), 4),
                  round(float(np.exp(-lam * y0 ** 0.5)), 4),
                  round(1 - float(np.exp(-lam ** 2 * y0)), 4)]
    elif ask == "pdf_of_transform":
        # X ~ U(0,1), Y = X², f_Y(y) = 1/(2√y) for 0 < y < 1
        # Evaluate at y₀: f_Y(y₀) = 1/(2√y₀)
        y0 = round(float(rng.uniform(0.1, 0.9)), 2)
        extra = {"y0": y0}
        ans = round(1 / (2 * y0 ** 0.5), 4)
        stmt = (
            f"X ~ Uniform(0, 1). Let Y = X². "
            f"Find f_Y({y0}) using the change-of-variables formula."
        )
        wrongs = [round(2 * y0 ** 0.5, 4), round(y0 ** 0.5, 4),
                  round(1 / (y0 ** 0.5), 4)]
    else:
        raise ValueError(f"Unknown ask '{ask}' for transformation_univariate")

    return Problem("transformation_univariate", ask, stmt, ans,
                   make_mc_choices(ans, wrongs, rng),
                   params={"lam": lam, **extra}, seed=seed)


@register("percentile")
def gen_percentile(ask: str, ranges: dict, seed: int) -> Problem:
    rng = np.random.default_rng(seed)
    lam = round(float(rng.uniform(0.5, 3.0)), 2)

    extra: dict = {}
    if ask == "percentile":
        p = int(rng.choice([25, 75, 90]))
        extra = {"p": p / 100}
        ans = round(float(-np.log(1 - p / 100) / lam), 4)
        stmt = (
            f"X ~ Exponential(λ = {lam}). Find the {p}th percentile "
            f"(the value x such that P(X ≤ x) = {p/100})."
        )
        wrongs = [round((p / 100) / lam, 4), round(float(-np.log(p / 100) / lam), 4),
                  round(float(-np.log(1 - p / 100) * lam), 4)]
    elif ask == "median":
        ans = round(float(np.log(2) / lam), 4)
        stmt = f"X ~ Exponential(λ = {lam}). Find the median."
        wrongs = [round(1 / lam, 4), round(float(np.log(2) * lam), 4),
                  round(2 / lam, 4)]
    else:
        raise ValueError(f"Unknown ask '{ask}' for percentile")

    return Problem("percentile", ask, stmt, ans, make_mc_choices(ans, wrongs, rng),
                   params={"lam": lam, **extra}, seed=seed)
