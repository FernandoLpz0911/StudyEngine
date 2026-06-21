"""
Worked-solution generator — one source of truth with the answer generators.
Every solve_* function reuses the same math as its corresponding gen_* function
and returns intermediate values alongside step-by-step solution text.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from math import comb, factorial, perm

import numpy as np
from scipy.stats import beta as beta_dist
from scipy.stats import binom as binom_dist
from scipy.stats import gamma as gamma_dist
from scipy.stats import geom, hypergeom, lognorm, nbinom, norm, poisson


@dataclass
class Solved:
    answer: float
    steps: list[str]
    intermediates: dict = field(default_factory=dict)


_solvers: dict[str, object] = {}


def _reg(kind: str):
    def decorator(fn):
        _solvers[kind] = fn
        return fn
    return decorator


def solve(kind: str, ask: str, params: dict) -> Solved:
    """Dispatch to the right solver. Returns Solved with answer, steps, intermediates."""
    fn = _solvers.get(kind)
    if fn is None:
        return Solved(float("nan"), [f"No worked solution available for '{kind}'."], {})
    return fn(ask, params)


def _unknown(ask: str) -> Solved:
    return Solved(float("nan"), [f"Unknown ask variant: '{ask}'."], {})



@_reg("bernoulli")
def _s_bernoulli(ask: str, params: dict) -> Solved:
    p = params["p"]
    q = round(1 - p, 2)
    if ask == "mean":
        return Solved(p, [
            f"X ~ Bernoulli(p = {p})",
            f"E[X] = p = {p}",
        ], {"p": p})
    if ask == "variance":
        ans = round(p * q, 4)
        return Solved(ans, [
            f"X ~ Bernoulli(p = {p}),  q = 1 - p = {q}",
            f"Var(X) = p·q = {p} × {q} = {ans}",
        ], {"q": q})
    return _unknown(ask)


@_reg("binomial")
def _s_binomial(ask: str, params: dict) -> Solved:
    n, p = params["n"], params["p"]
    k = params.get("k", 0)
    q = round(1 - p, 2)
    if ask == "pmf_eq":
        nCk = comb(n, k)
        pk = round(p ** k, 6)
        qnk = round(q ** (n - k), 6)
        ans = round(float(binom_dist.pmf(k, n, p)), 4)
        return Solved(ans, [
            f"X ~ Binomial(n={n}, p={p})",
            f"P(X = {k}) = C({n},{k}) · p^{k} · (1-p)^{n-k}",
            f"            = {nCk} · {p}^{k} · {q}^{n-k}",
            f"            = {nCk} × {pk} × {qnk}",
            f"            = {ans}",
        ], {"nCk": nCk, "pk": pk, "qnk": qnk})
    if ask == "cdf_le":
        ans = round(float(binom_dist.cdf(k, n, p)), 4)
        return Solved(ans, [
            f"X ~ Binomial(n={n}, p={p})",
            f"P(X ≤ {k}) = Σ_{{i=0}}^{{{k}}} C({n},i)·p^i·(1-p)^{{{n}-i}}",
            f"           = {ans}  (binomial CDF)",
        ], {})
    if ask == "cdf_ge":
        k1 = k - 1
        cdf_k1 = round(float(binom_dist.cdf(k1, n, p)), 4)
        ans = round(float(binom_dist.sf(k1, n, p)), 4)
        return Solved(ans, [
            f"X ~ Binomial(n={n}, p={p})",
            f"P(X ≥ {k}) = 1 - P(X ≤ {k1})",
            f"P(X ≤ {k1}) = {cdf_k1}",
            f"P(X ≥ {k})  = 1 - {cdf_k1} = {ans}",
        ], {"cdf_k1": cdf_k1})
    if ask == "mean":
        ans = round(n * p, 4)
        return Solved(ans, [
            f"X ~ Binomial(n={n}, p={p})",
            f"E[X] = n·p = {n} × {p} = {ans}",
        ], {})
    if ask == "variance":
        ans = round(n * p * q, 4)
        return Solved(ans, [
            f"X ~ Binomial(n={n}, p={p}),  q = 1-p = {q}",
            f"Var(X) = n·p·q = {n} × {p} × {q} = {ans}",
        ], {"q": q})
    return _unknown(ask)


@_reg("geometric")
def _s_geometric(ask: str, params: dict) -> Solved:
    p = params["p"]
    k = params.get("k", 1)
    q = round(1 - p, 2)
    if ask == "pmf_eq":
        qk1 = round(q ** (k - 1), 6)
        ans = round(float(geom.pmf(k, p)), 4)
        return Solved(ans, [
            f"X ~ Geometric(p={p})  (trials until first success, support k=1,2,...)",
            f"P(X = {k}) = (1-p)^{{k-1}} · p = {q}^{{{k-1}}} · {p}",
            f"           = {qk1} × {p} = {ans}",
        ], {"qk1": qk1})
    if ask == "cdf_ge":
        ans = round(float(geom.sf(k - 1, p)), 4)
        return Solved(ans, [
            f"X ~ Geometric(p={p})",
            f"P(X ≥ {k}) = (1-p)^{{k-1}} = {q}^{{{k-1}}} = {ans}",
            "(Geometric tail: probability of needing ≥k trials = q^(k-1))",
        ], {})
    if ask == "mean":
        ans = round(1 / p, 4)
        return Solved(ans, [
            f"X ~ Geometric(p={p})",
            f"E[X] = 1/p = 1/{p} = {ans}",
        ], {})
    if ask == "variance":
        ans = round(q / p ** 2, 4)
        return Solved(ans, [
            f"X ~ Geometric(p={p}),  q = {q}",
            f"Var(X) = q/p² = {q}/{p**2:.4f} = {ans}",
        ], {"q": q})
    return _unknown(ask)


@_reg("negbinomial")
def _s_negbinomial(ask: str, params: dict) -> Solved:
    r, p = params["r"], params["p"]
    k = params.get("k", 0)
    q = round(1 - p, 2)
    if ask == "pmf_eq":
        ans = round(float(nbinom.pmf(k - r, r, p)), 4)
        nCk = comb(k - 1, r - 1)
        pr = round(p ** r, 6)
        qkr = round(q ** (k - r), 6)
        return Solved(ans, [
            f"X = trials until {r}-th success, p = {p}",
            f"P(X = {k}) = C({k-1},{r-1}) · p^{r} · q^{{{k-r}}}",
            f"           = {nCk} · {pr} · {qkr}",
            f"           = {ans}",
        ], {"nCk": nCk})
    if ask == "mean":
        ans = round(r / p, 4)
        return Solved(ans, [
            f"NegBinomial: r={r} successes, p={p}",
            f"E[X] = r/p = {r}/{p} = {ans}",
        ], {})
    if ask == "variance":
        ans = round(r * q / p ** 2, 4)
        return Solved(ans, [
            f"NegBinomial: r={r}, p={p},  q={q}",
            f"Var(X) = r·q/p² = {r}×{q}/{p**2:.4f} = {ans}",
        ], {"q": q})
    return _unknown(ask)


@_reg("hypergeometric")
def _s_hypergeometric(ask: str, params: dict) -> Solved:
    N, K, n = params["N"], params["K"], params["n"]
    k = params.get("k", 0)
    if ask == "pmf_eq":
        cKk = comb(K, k)
        cNKnk = comb(N - K, n - k)
        cNn = comb(N, n)
        ans = round(float(hypergeom.pmf(k, N, K, n)), 4)
        return Solved(ans, [
            f"Hypergeometric: N={N} items, K={K} successes, draw n={n} without replacement",
            f"P(X = {k}) = C({K},{k}) · C({N-K},{n-k}) / C({N},{n})",
            f"           = {cKk} × {cNKnk} / {cNn}",
            f"           = {cKk * cNKnk} / {cNn} = {ans}",
        ], {"cKk": cKk, "cNKnk": cNKnk, "cNn": cNn})
    if ask == "mean":
        ans = round(n * K / N, 4)
        return Solved(ans, [
            f"Hypergeometric: N={N}, K={K}, n={n}",
            f"E[X] = n·K/N = {n}×{K}/{N} = {ans}",
        ], {})
    return _unknown(ask)


@_reg("poisson")
def _s_poisson(ask: str, params: dict) -> Solved:
    lam = params["lam"]
    k = params.get("k", 0)
    if ask == "pmf_eq":
        e_lam = round(float(np.exp(-lam)), 6)
        lam_k = round(float(lam ** k), 6)
        k_fact = factorial(k)
        ans = round(float(poisson.pmf(k, lam)), 4)
        return Solved(ans, [
            f"X ~ Poisson(λ = {lam})",
            f"P(X = {k}) = e^{{-λ}} · λ^k / k! = e^{{-{lam}}} · {lam}^{k} / {k}!",
            f"           = {e_lam} × {lam_k} / {k_fact}",
            f"           = {ans}",
        ], {"e_lam": e_lam, "lam_k": lam_k, "k_fact": k_fact})
    if ask == "cdf_le":
        ans = round(float(poisson.cdf(k, lam)), 4)
        return Solved(ans, [
            f"X ~ Poisson(λ = {lam})",
            f"P(X ≤ {k}) = Σ_{{i=0}}^{{{k}}} e^{{-{lam}}}·{lam}^i / i! = {ans}",
        ], {})
    if ask == "cdf_ge":
        k1 = k - 1
        cdf_k1 = round(float(poisson.cdf(k1, lam)), 4)
        ans = round(float(poisson.sf(k1, lam)), 4)
        return Solved(ans, [
            f"X ~ Poisson(λ = {lam})",
            f"P(X ≥ {k}) = 1 - P(X ≤ {k1}) = 1 - {cdf_k1} = {ans}",
        ], {})
    if ask == "mean":
        return Solved(lam, [
            f"X ~ Poisson(λ = {lam})",
            f"E[X] = λ = {lam}  (mean equals the rate parameter)",
        ], {})
    return _unknown(ask)


@_reg("discrete_uniform")
def _s_discrete_uniform(ask: str, params: dict) -> Solved:
    n = params["n"]
    k = params.get("k", 1)
    if ask == "mean":
        ans = round((n + 1) / 2, 4)
        return Solved(ans, [
            f"X ~ DiscreteUniform on {{1, 2, …, {n}}}",
            f"E[X] = (n+1)/2 = ({n}+1)/2 = {ans}",
        ], {})
    if ask == "variance":
        ans = round((n ** 2 - 1) / 12, 4)
        return Solved(ans, [
            f"X ~ DiscreteUniform on {{1, …, {n}}}",
            f"Var(X) = (n²-1)/12 = ({n}²-1)/12 = {n**2-1}/12 = {ans}",
        ], {})
    if ask == "pmf_eq":
        ans = round(1 / n, 4)
        return Solved(ans, [
            f"X ~ DiscreteUniform on {{1, …, {n}}}",
            f"P(X = {k}) = 1/n = 1/{n} = {ans}  (all n values equally likely)",
        ], {})
    return _unknown(ask)


@_reg("continuous_uniform")
def _s_continuous_uniform(ask: str, params: dict) -> Solved:
    a, b = params["a"], params["b"]
    width = round(b - a, 4)
    if ask == "prob_interval":
        lo, hi = params["lo"], params["hi"]
        span = round(hi - lo, 4)
        ans = round(span / width, 4)
        return Solved(ans, [
            f"X ~ Uniform({a}, {b}),  f(x) = 1/(b-a) = 1/{width}",
            f"P({lo} < X < {hi}) = (hi - lo) / (b - a)",
            f"                   = ({hi} - {lo}) / {width}",
            f"                   = {span} / {width} = {ans}",
        ], {"width": width, "span": span})
    if ask == "mean":
        ans = round((a + b) / 2, 4)
        return Solved(ans, [
            f"X ~ Uniform({a}, {b})",
            f"E[X] = (a + b) / 2 = ({a} + {b}) / 2 = {ans}",
        ], {})
    if ask == "variance":
        ans = round(width ** 2 / 12, 4)
        return Solved(ans, [
            f"X ~ Uniform({a}, {b}),  b-a = {width}",
            f"Var(X) = (b-a)² / 12 = {width}² / 12 = {round(width**2, 4)} / 12 = {ans}",
        ], {"width": width})
    if ask == "percentile":
        p = params["p"]
        ans = round(a + p * width, 4)
        return Solved(ans, [
            f"X ~ Uniform({a}, {b})",
            "p-th percentile: x_p = a + p·(b-a)",
            f"x_{{{int(p*100)}%}} = {a} + {p} × {width} = {ans}",
        ], {"width": width, "p": p})
    return _unknown(ask)


@_reg("exponential")
def _s_exponential(ask: str, params: dict) -> Solved:
    lam = params["lam"]
    if ask == "survival":
        t = params["t"]
        exp_val = round(float(np.exp(-lam * t)), 6)
        ans = round(exp_val, 4)
        return Solved(ans, [
            f"X ~ Exponential(λ = {lam})",
            "Survival: P(X > t) = e^{-λt}",
            f"P(X > {t}) = e^{{-{lam}·{t}}} = e^{{-{round(lam*t, 4)}}} = {ans}",
        ], {"lam_t": round(lam * t, 4)})
    if ask == "prob_interval":
        lo, hi = params["lo"], params["hi"]
        s_lo = round(float(np.exp(-lam * lo)), 6)
        s_hi = round(float(np.exp(-lam * hi)), 6)
        ans = round(s_lo - s_hi, 4)
        return Solved(ans, [
            f"X ~ Exponential(λ = {lam})",
            f"P({lo} < X < {hi}) = e^{{-λ·lo}} - e^{{-λ·hi}}",
            f"                   = e^{{-{round(lam*lo,4)}}} - e^{{-{round(lam*hi,4)}}}",
            f"                   = {s_lo} - {s_hi} = {ans}",
        ], {"s_lo": s_lo, "s_hi": s_hi})
    if ask == "mean":
        ans = round(1 / lam, 4)
        return Solved(ans, [
            f"X ~ Exponential(λ = {lam})",
            f"E[X] = 1/λ = 1/{lam} = {ans}",
        ], {})
    if ask == "percentile":
        p = params["p"]
        neg_log = round(float(-np.log(1 - p)), 6)
        ans = round(float(-np.log(1 - p) / lam), 4)
        return Solved(ans, [
            f"X ~ Exponential(λ = {lam}),  CDF: F(x) = 1 - e^{{-λx}}",
            f"Solve 1 - e^{{-λx}} = {p}  →  e^{{-λx}} = {round(1-p,4)}",
            f"-λx = ln({round(1-p,4)})  →  x = -ln({round(1-p,4)}) / {lam}",
            f"    = {neg_log} / {lam} = {ans}",
        ], {"p": p, "neg_log": neg_log})
    if ask == "memoryless":
        s, t = params["s"], params["t"]
        ans = round(float(np.exp(-lam * t)), 4)
        return Solved(ans, [
            f"X ~ Exponential(λ = {lam}) — memoryless property",
            "P(X > s+t | X > s) = P(X > t)  [exponential has no memory]",
            f"P(X > {t}) = e^{{-{lam}·{t}}} = {ans}",
        ], {"s": s, "t": t})
    return _unknown(ask)


@_reg("gamma")
def _s_gamma(ask: str, params: dict) -> Solved:
    alpha, theta = params["alpha"], params["theta"]
    if ask == "mean":
        ans = round(alpha * theta, 4)
        return Solved(ans, [
            f"X ~ Gamma(α={alpha}, θ={theta})  [scale parameterization: mean=αθ, Var=αθ²]",
            f"E[X] = α·θ = {alpha} × {theta} = {ans}",
        ], {})
    if ask == "variance":
        ans = round(alpha * theta ** 2, 4)
        return Solved(ans, [
            f"X ~ Gamma(α={alpha}, θ={theta})",
            f"Var(X) = α·θ² = {alpha} × {theta}² = {alpha} × {round(theta**2,4)} = {ans}",
        ], {})
    if ask == "prob_interval":
        lo, hi = params["lo"], params["hi"]
        cdf_hi = round(float(gamma_dist.cdf(hi, a=alpha, scale=theta)), 4)
        cdf_lo = round(float(gamma_dist.cdf(lo, a=alpha, scale=theta)), 4)
        ans = round(cdf_hi - cdf_lo, 4)
        return Solved(ans, [
            f"X ~ Gamma(α={alpha}, θ={theta})",
            f"P({lo} < X < {hi}) = F({hi}) - F({lo})",
            f"F({hi}) = {cdf_hi},  F({lo}) = {cdf_lo}",
            f"        = {cdf_hi} - {cdf_lo} = {ans}",
        ], {"cdf_hi": cdf_hi, "cdf_lo": cdf_lo})
    return _unknown(ask)


@_reg("normal")
def _s_normal(ask: str, params: dict) -> Solved:
    mu, sigma = params["mu"], params["sigma"]
    if ask == "prob_interval":
        lo, hi = params["lo"], params["hi"]
        z_lo = round((lo - mu) / sigma, 4)
        z_hi = round((hi - mu) / sigma, 4)
        phi_lo = round(float(norm.cdf(lo, mu, sigma)), 4)
        phi_hi = round(float(norm.cdf(hi, mu, sigma)), 4)
        ans = round(phi_hi - phi_lo, 4)
        return Solved(ans, [
            f"X ~ N(μ={mu}, σ={sigma})",
            f"Standardize:  z₁ = ({lo}-{mu})/{sigma} = {z_lo}",
            f"              z₂ = ({hi}-{mu})/{sigma} = {z_hi}",
            f"P({lo} < X < {hi}) = Φ({z_hi}) - Φ({z_lo}) = {phi_hi} - {phi_lo} = {ans}",
        ], {"z_lo": z_lo, "z_hi": z_hi})
    if ask == "survival":
        x = params["x"]
        z = round((x - mu) / sigma, 4)
        phi_z = round(float(norm.cdf(x, mu, sigma)), 4)
        ans = round(float(norm.sf(x, mu, sigma)), 4)
        return Solved(ans, [
            f"X ~ N(μ={mu}, σ={sigma})",
            f"z = ({x} - {mu}) / {sigma} = {z}",
            f"P(X > {x}) = 1 - Φ({z}) = 1 - {phi_z} = {ans}",
        ], {"z": z, "phi_z": phi_z})
    if ask == "percentile":
        p = params["p"]
        z_p = round(float(norm.ppf(p)), 4)
        ans = round(float(norm.ppf(p, mu, sigma)), 4)
        return Solved(ans, [
            f"X ~ N(μ={mu}, σ={sigma})",
            f"Find x: Φ((x-μ)/σ) = {p}",
            f"z_p = Φ⁻¹({p}) = {z_p}",
            f"x = μ + z_p·σ = {mu} + {z_p}×{sigma} = {ans}",
        ], {"z_p": z_p, "p": p})
    if ask == "standardize":
        x = params["x"]
        z = params["z"]
        ans = round(float(norm.cdf(z)), 4)
        return Solved(ans, [
            f"X ~ N(μ={mu}, σ={sigma})",
            f"Standardize: Z = (X-μ)/σ = ({x}-{mu})/{sigma} = {z}",
            f"P(X ≤ {x}) = P(Z ≤ {z}) = Φ({z}) = {ans}",
        ], {"z": z})
    return _unknown(ask)


@_reg("beta")
def _s_beta(ask: str, params: dict) -> Solved:
    a, b = params["alpha"], params["beta"]
    if ask == "mean":
        ans = round(a / (a + b), 4)
        return Solved(ans, [
            f"X ~ Beta(α={a}, β={b}),  support (0, 1)",
            f"E[X] = α/(α+β) = {a}/({a}+{b}) = {a}/{a+b} = {ans}",
        ], {})
    if ask == "prob_interval":
        lo, hi = params["lo"], params["hi"]
        cdf_hi = round(float(beta_dist.cdf(hi, a, b)), 4)
        cdf_lo = round(float(beta_dist.cdf(lo, a, b)), 4)
        ans = round(cdf_hi - cdf_lo, 4)
        return Solved(ans, [
            f"X ~ Beta(α={a}, β={b}),  support (0, 1)",
            f"P({lo} < X < {hi}) = F({hi}) - F({lo}) = {cdf_hi} - {cdf_lo} = {ans}",
        ], {"cdf_hi": cdf_hi, "cdf_lo": cdf_lo})
    return _unknown(ask)


@_reg("lognormal")
def _s_lognormal(ask: str, params: dict) -> Solved:
    mu, sigma = params["mu"], params["sigma"]
    if ask == "mean":
        exp_arg = round(mu + sigma ** 2 / 2, 4)
        ans = round(float(np.exp(mu + sigma ** 2 / 2)), 4)
        return Solved(ans, [
            f"ln X ~ N(μ={mu}, σ={sigma})  →  X ~ LogNormal(μ={mu}, σ={sigma})",
            f"E[X] = e^{{μ + σ²/2}} = e^{{{mu} + {sigma}²/2}} = e^{{{exp_arg}}} = {ans}",
        ], {"exp_arg": exp_arg})
    if ask == "prob_interval":
        lo, hi = params["lo"], params["hi"]
        cdf_hi = round(float(lognorm.cdf(hi, s=sigma, scale=np.exp(mu))), 4)
        cdf_lo = round(float(lognorm.cdf(lo, s=sigma, scale=np.exp(mu))), 4)
        ans = round(cdf_hi - cdf_lo, 4)
        return Solved(ans, [
            f"ln X ~ N(μ={mu}, σ={sigma})",
            f"Transform: P({lo} < X < {hi}) = P(ln {lo} < lnX < ln {hi})",
            f"P({lo} < X < {hi}) = F_LN({hi}) - F_LN({lo}) = {cdf_hi} - {cdf_lo} = {ans}",
        ], {"cdf_hi": cdf_hi, "cdf_lo": cdf_lo})
    return _unknown(ask)


@_reg("chisquare")
def _s_chisquare(ask: str, params: dict) -> Solved:
    k = params["k"]
    if ask == "mean":
        return Solved(float(k), [
            f"X ~ χ²(k={k})  (Chi-square: sum of k squared standard normals)",
            f"E[X] = k = {k}",
        ], {})
    if ask == "variance":
        ans = float(2 * k)
        return Solved(ans, [
            f"X ~ χ²(k={k})",
            f"Var(X) = 2k = 2×{k} = {ans}",
        ], {})
    return _unknown(ask)


@_reg("set_inclusion_exclusion")
def _s_set_ie(ask: str, params: dict) -> Solved:
    pa, pb, pab = params["pa"], params["pb"], params["pab"]
    paub = round(pa + pb - pab, 4)
    if ask == "union_prob":
        return Solved(paub, [
            "Inclusion-Exclusion: P(A∪B) = P(A) + P(B) - P(A∩B)",
            f"= {pa} + {pb} - {pab} = {paub}",
        ], {"paub": paub})
    if ask == "complement_prob":
        ans = round(1 - paub, 4)
        return Solved(ans, [
            f"P(A∪B) = P(A) + P(B) - P(A∩B) = {pa} + {pb} - {pab} = {paub}",
            f"P((A∪B)ᶜ) = 1 - P(A∪B) = 1 - {paub} = {ans}",
        ], {"paub": paub})
    return _unknown(ask)


@_reg("combinatorics")
def _s_combinatorics(ask: str, params: dict) -> Solved:
    n, r = params["n"], params["r"]
    if ask == "nCr":
        ans = float(comb(n, r))
        return Solved(ans, [
            f"Combinations (order doesn't matter): C({n},{r}) = {n}! / ({r}!·({n-r})!)",
            f"= {factorial(n)} / ({factorial(r)} × {factorial(n-r)}) = {int(ans)}",
        ], {})
    if ask == "nPr":
        ans = float(perm(n, r))
        return Solved(ans, [
            f"Permutations (order matters): P({n},{r}) = {n}! / ({n-r})!",
            f"= {factorial(n)} / {factorial(n-r)} = {int(ans)}",
        ], {})
    if ask == "multinomial":
        r1 = params.get("r1", 1)
        r2 = params.get("r2", 1)
        r3 = params.get("r3", n - r1 - r2)
        ans = float(factorial(n) // (factorial(r1) * factorial(r2) * factorial(r3)))
        return Solved(ans, [
            f"Multinomial coefficient: {n}! / ({r1}!·{r2}!·{r3}!)",
            f"= {factorial(n)} / ({factorial(r1)}×{factorial(r2)}×{factorial(r3)})",
            f"= {int(ans)}",
        ], {"r1": r1, "r2": r2, "r3": r3})
    return _unknown(ask)


@_reg("addition_rule")
def _s_addition_rule(ask: str, params: dict) -> Solved:
    pa, pb, pab = params["pa"], params["pb"], params["pab"]
    if ask == "union_prob":
        ans = round(pa + pb - pab, 4)
        return Solved(ans, [
            "Addition rule: P(A∪B) = P(A) + P(B) - P(A∩B)",
            f"= {pa} + {pb} - {pab} = {ans}",
        ], {})
    if ask == "either_or":
        ans = round(pa + pb - 2 * pab, 4)
        return Solved(ans, [
            "P(exactly one of A or B) = P(A) + P(B) - 2·P(A∩B)",
            f"= {pa} + {pb} - 2×{pab} = {ans}",
            "(P(A∪B) minus the cases where both occur = subtract P(A∩B) twice)",
        ], {})
    return _unknown(ask)


@_reg("conditional")
def _s_conditional(ask: str, params: dict) -> Solved:
    pb = params["pb"]
    pa_given_b = params["pa_given_b"]
    pab = params["pab"]
    if ask == "cond_prob":
        return Solved(pa_given_b, [
            "Conditional probability: P(A|B) = P(A∩B) / P(B)",
            f"= {pab} / {pb} = {pa_given_b}",
        ], {})
    if ask == "joint_from_cond":
        return Solved(pab, [
            "Multiplication rule: P(A∩B) = P(A|B) · P(B)",
            f"= {pa_given_b} × {pb} = {pab}",
        ], {})
    return _unknown(ask)


@_reg("independence")
def _s_independence(ask: str, params: dict) -> Solved:
    pa, pb = params["pa"], params["pb"]
    pab = round(pa * pb, 4)
    if ask in ("is_independent", "joint_indep"):
        return Solved(pab, [
            "Independence: P(A∩B) = P(A)·P(B)",
            f"= {pa} × {pb} = {pab}",
        ], {})
    return _unknown(ask)


@_reg("bayes")
def _s_bayes(ask: str, params: dict) -> Solved:
    priors = params["priors"]
    likes = params["likelihoods"]
    n = len(priors)
    pe = float(np.dot(priors, likes))
    posterior = round(priors[0] * likes[0] / pe, 4)
    if ask == "posterior":
        pe_terms = " + ".join(
            f"P(H{i+1})·P(E|H{i+1})={round(priors[i]*likes[i],4)}"
            for i in range(n)
        )
        return Solved(posterior, [
            "Bayes' theorem: P(H₁|E) = P(H₁)·P(E|H₁) / P(E)",
            f"P(E) = Σ P(Hᵢ)·P(E|Hᵢ) = {pe_terms}",
            f"     = {round(pe, 4)}",
            f"P(H₁|E) = {priors[0]}×{likes[0]} / {round(pe,4)}",
            f"        = {round(priors[0]*likes[0],4)} / {round(pe,4)} = {posterior}",
        ], {"pe": round(pe, 4)})
    return _unknown(ask)


@_reg("counting_prob")
def _s_counting_prob(ask: str, params: dict) -> Solved:
    if ask == "draw_prob":
        N, K, n, k = params["N"], params["K"], params["n"], params["k"]
        cKk = comb(K, k)
        cNKnk = comb(N - K, n - k)
        cNn = comb(N, n)
        ans = round(float(hypergeom.pmf(k, N, K, n)), 4)
        return Solved(ans, [
            f"Equally-likely sampling without replacement from N={N}, K={K} defective",
            f"P(exactly {k} defective in draw of {n}) = C({K},{k})·C({N-K},{n-k}) / C({N},{n})",
            f"= {cKk}×{cNKnk} / {cNn} = {cKk*cNKnk}/{cNn} = {ans}",
        ], {"cKk": cKk, "cNKnk": cNKnk, "cNn": cNn})
    if ask == "arrangement_prob":
        n, r, favorable = params["n"], params["r"], params["favorable"]
        total = perm(n, r)
        ans = round(favorable / total, 4)
        return Solved(ans, [
            f"Ordered arrangements of {r} from {n}: P({n},{r}) = {total}",
            f"P({favorable} specific arrangement(s)) = {favorable} / {total} = {ans}",
        ], {"total": total})
    return _unknown(ask)


@_reg("density_basics")
def _s_density_basics(ask: str, params: dict) -> Solved:
    k = params["k"]
    c = k + 1
    if ask == "normalize_constant":
        return Solved(float(c), [
            f"f(x) = c·x^{k} on (0,1).  Require ∫₀¹ c·x^{k} dx = 1",
            f"∫₀¹ x^{k} dx = 1/(k+1) = 1/{c}",
            f"c·(1/{c}) = 1  →  c = {c}",
        ], {})
    if ask == "cdf_from_pdf":
        t = params["t"]
        ans = round(t ** (k + 1), 4)
        return Solved(ans, [
            f"f(x) = {c}·x^{k} on (0,1)",
            f"F(t) = ∫₀ᵗ {c}·x^{k} dx = {c}·[x^{{{k+1}}}/{k+1}]₀ᵗ",
            f"     = {c}·t^{{{k+1}}}/{c} = t^{{{k+1}}}",
            f"F({t}) = {t}^{{{k+1}}} = {ans}",
        ], {})
    if ask == "prob_interval":
        lo, hi = params["lo"], params["hi"]
        ans = round(hi ** (k + 1) - lo ** (k + 1), 4)
        return Solved(ans, [
            f"f(x) = {c}·x^{k} on (0,1),  CDF: F(x) = x^{{{k+1}}}",
            f"P({lo} < X < {hi}) = F({hi}) - F({lo})",
            f"= {hi}^{{{k+1}}} - {lo}^{{{k+1}}}",
            f"= {round(hi**(k+1),6)} - {round(lo**(k+1),6)} = {ans}",
        ], {})
    return _unknown(ask)


@_reg("expectation_generic")
def _s_expectation_generic(ask: str, params: dict) -> Solved:
    probs = params["probs"]
    p1, p2, p3 = probs[0], probs[1], probs[2]
    ex = round(1 * p1 + 2 * p2 + 3 * p3, 4)
    ex2 = round(1 * p1 + 4 * p2 + 9 * p3, 4)
    if ask == "mean":
        return Solved(ex, [
            "E[X] = Σ x·P(X=x)",
            f"     = 1·{p1} + 2·{p2} + 3·{p3}",
            f"     = {round(p1,4)} + {round(2*p2,4)} + {round(3*p3,4)} = {ex}",
        ], {"ex": ex})
    if ask == "lotus":
        return Solved(ex2, [
            "E[X²] = Σ x²·P(X=x)  (Law of the Unconscious Statistician)",
            f"      = 1²·{p1} + 2²·{p2} + 3²·{p3}",
            f"      = {round(p1,4)} + {round(4*p2,4)} + {round(9*p3,4)} = {ex2}",
        ], {"ex": ex})
    return _unknown(ask)


@_reg("variance_generic")
def _s_variance_generic(ask: str, params: dict) -> Solved:
    probs = params["probs"]
    p1, p2, p3 = probs[0], probs[1], probs[2]
    ex = 1 * p1 + 2 * p2 + 3 * p3
    ex2 = 1 * p1 + 4 * p2 + 9 * p3
    var = round(ex2 - ex ** 2, 4)
    sd = round(var ** 0.5, 4)
    if ask == "variance":
        return Solved(var, [
            "Var(X) = E[X²] - (E[X])²",
            f"E[X]  = 1·{p1} + 2·{p2} + 3·{p3} = {round(ex,4)}",
            f"E[X²] = 1·{p1} + 4·{p2} + 9·{p3} = {round(ex2,4)}",
            f"Var(X) = {round(ex2,4)} - {round(ex,4)}² = {round(ex2,4)} - {round(ex**2,4)} = {var}",
        ], {"ex": round(ex, 4), "ex2": round(ex2, 4)})
    if ask == "sd":
        return Solved(sd, [
            f"Var(X) = E[X²] - (E[X])² = {var}",
            f"SD(X)  = √Var(X) = √{var} = {sd}",
        ], {"var": var})
    return _unknown(ask)


@_reg("mgf")
def _s_mgf(ask: str, params: dict) -> Solved:
    n, p = params["n"], params["p"]
    q = round(1 - p, 2)
    if ask == "moment_from_mgf":
        ans = round(n * p, 4)
        return Solved(ans, [
            f"M(t) = ({q} + {p}·eᵗ)^{n}  →  X ~ Binomial(n={n}, p={p})",
            f"E[X] = M'(0) = n·p = {n} × {p} = {ans}",
        ], {})
    if ask == "identify_dist_from_mgf":
        ex = n * p
        ans = round(n * p * q + (n * p) ** 2, 4)
        return Solved(ans, [
            f"M(t) = ({q} + {p}·eᵗ)^{n}  →  X ~ Binomial(n={n}, p={p})",
            "E[X²] = M''(0) = Var(X) + (E[X])² = n·p·q + (n·p)²",
            f"      = {n}·{p}·{q} + ({n}·{p})²",
            f"      = {round(n*p*q,4)} + {round((n*p)**2,4)} = {ans}",
        ], {"ex": ex})
    return _unknown(ask)


@_reg("transformation_univariate")
def _s_transformation_univariate(ask: str, params: dict) -> Solved:
    lam = params["lam"]
    if ask == "cdf_method":
        y0 = params["y0"]
        sqrt_y0 = round(y0 ** 0.5, 4)
        ans = round(float(1 - np.exp(-lam * y0 ** 0.5)), 4)
        return Solved(ans, [
            f"X ~ Exp(λ={lam}),  Y = X²",
            "CDF method: P(Y ≤ y₀) = P(X² ≤ y₀) = P(X ≤ √y₀)",
            f"P(X ≤ √{y0}) = P(X ≤ {sqrt_y0}) = 1 - e^{{-{lam}·{sqrt_y0}}}",
            f"= 1 - e^{{-{round(lam*sqrt_y0,4)}}} = {ans}",
        ], {"sqrt_y0": sqrt_y0})
    if ask == "pdf_of_transform":
        y0 = params["y0"]
        ans = round(1 / (2 * y0 ** 0.5), 4)
        return Solved(ans, [
            "X ~ Uniform(0,1),  Y = X²",
            "Change of variables: f_Y(y) = f_X(g⁻¹(y)) · |dg⁻¹/dy|",
            "g⁻¹(y) = √y,  |dg⁻¹/dy| = 1/(2√y)",
            "f_X(√y) = 1 (uniform),  so f_Y(y) = 1/(2√y)",
            f"f_Y({y0}) = 1/(2√{y0}) = 1/{round(2*y0**0.5,4)} = {ans}",
        ], {})
    return _unknown(ask)


@_reg("percentile")
def _s_percentile(ask: str, params: dict) -> Solved:
    lam = params["lam"]
    if ask == "percentile":
        p = params["p"]
        neg_log = round(float(-np.log(1 - p)), 6)
        ans = round(float(-np.log(1 - p) / lam), 4)
        return Solved(ans, [
            f"X ~ Exp(λ={lam}),  CDF: F(x) = 1 - e^{{-λx}}",
            f"Solve F(x) = {p}:  1 - e^{{-λx}} = {p}  →  e^{{-λx}} = {round(1-p,4)}",
            f"x = -ln({round(1-p,4)}) / {lam} = {neg_log}/{lam} = {ans}",
        ], {"p": p, "neg_log": neg_log})
    if ask == "median":
        ans = round(float(np.log(2) / lam), 4)
        return Solved(ans, [
            f"X ~ Exp(λ={lam}),  median: solve F(x) = 0.5",
            "1 - e^{-λx} = 0.5  →  e^{-λx} = 0.5  →  x = ln(2)/λ",
            f"= {round(float(np.log(2)),6)} / {lam} = {ans}",
        ], {})
    return _unknown(ask)


@_reg("joint_basics")
def _s_joint_basics(ask: str, params: dict) -> Solved:
    k = params["k"]
    c = 2 * (k + 1)
    if ask == "normalize_constant":
        return Solved(float(c), [
            f"f(x,y) = c·x^{k}·y on (0,1)×(0,1)",
            f"∫₀¹∫₀¹ c·x^{k}·y dx dy = c · [1/(k+1)] · [1/2] = c/{c} = 1  →  c = {c}",
        ], {})
    if ask == "joint_prob_region":
        x0 = params.get("x0", 0.5)
        y0 = params.get("y0", 0.5)
        ans = round(c * x0 ** (k + 1) / (k + 1) * y0 ** 2 / 2, 4)
        return Solved(ans, [
            f"f(x,y) = {c}·x^{k}·y on (0,1)×(0,1)",
            f"P(X<{x0}, Y<{y0}) = ∫₀^{{{x0}}} ∫₀^{{{y0}}} {c}·x^{k}·y dy dx",
            f"= {c} · [x^{{{k+1}}}/{k+1}]₀^{{{x0}}} · [y²/2]₀^{{{y0}}}",
            f"= {c} · {round(x0**(k+1)/(k+1),6)} · {round(y0**2/2,6)} = {ans}",
        ], {"x0": x0, "y0": y0})
    return _unknown(ask)


@_reg("marginal")
def _s_marginal(ask: str, params: dict) -> Solved:
    table = np.array(params["table"])
    px = table.sum(axis=1)
    py = table.sum(axis=0)
    if ask == "marginal_pdf":
        ans = round(float(px[1]), 4)
        row_vals = " + ".join(f"{v:.4f}" for v in table[1, :])
        return Solved(ans, [
            "Marginalize by summing over Y: P(X=1) = Σ_y P(X=1, Y=y)",
            f"= {row_vals} = {ans}",
        ], {})
    if ask == "marginal_prob":
        ans = round(float(py[0] + py[1]), 4)
        return Solved(ans, [
            "P(Y ≤ 1) = P(Y=0) + P(Y=1)",
            f"P(Y=0) = {round(float(py[0]),4)},  P(Y=1) = {round(float(py[1]),4)}",
            f"P(Y ≤ 1) = {round(float(py[0]),4)} + {round(float(py[1]),4)} = {ans}",
        ], {})
    return _unknown(ask)


@_reg("conditional_dist")
def _s_conditional_dist(ask: str, params: dict) -> Solved:
    table = np.array(params["table"])
    px = table.sum(axis=1)
    if ask == "cond_pdf":
        # j is not stored — reconstruct: problem shows P(Y=j|X=1)
        # The generator picks j from rng, but we don't store j.
        # We compute all conditional probs and return the formula.
        px1 = round(float(px[1]), 4)
        cond = [round(float(table[1, j] / px[1]), 4) for j in range(3)]
        return Solved(cond[0], [
            "P(Y=j | X=1) = P(X=1, Y=j) / P(X=1)",
            f"P(X=1) = {px1}",
            f"P(Y=0|X=1) = {table[1,0]:.4f}/{px1} = {cond[0]}",
            f"P(Y=1|X=1) = {table[1,1]:.4f}/{px1} = {cond[1]}",
            f"P(Y=2|X=1) = {table[1,2]:.4f}/{px1} = {cond[2]}",
            "(Match to the j asked in the problem statement)",
        ], {"cond": cond, "px1": px1})
    if ask == "cond_prob":
        px0 = round(float(px[0]), 4)
        c0 = round(float(table[0, 0] / px[0]), 4)
        c1 = round(float(table[0, 1] / px[0]), 4)
        ans = round(c0 + c1, 4)
        return Solved(ans, [
            "P(Y ≤ 1 | X=0) = [P(X=0,Y=0) + P(X=0,Y=1)] / P(X=0)",
            f"P(X=0) = {px0}",
            f"Numerator = {table[0,0]:.4f} + {table[0,1]:.4f}"
            f" = {round(float(table[0,0]+table[0,1]),4)}",
            f"P(Y ≤ 1 | X=0) = "
            f"{round(float(table[0,0]+table[0,1]),4)} / {px0} = {ans}",
        ], {})
    return _unknown(ask)


@_reg("independence_rv")
def _s_independence_rv(ask: str, params: dict) -> Solved:
    table = np.array(params["table"])
    px = table.sum(axis=1)
    py = table.sum(axis=0)
    if ask == "is_independent":
        px0 = round(float(px[0]), 4)
        py0 = round(float(py[0]), 4)
        prod = round(px0 * py0, 4)
        joint = round(float(table[0, 0]), 4)
        return Solved(joint, [
            "Check independence: P(X=0,Y=0) should equal P(X=0)·P(Y=0)",
            f"P(X=0) = {px0},  P(Y=0) = {py0}",
            f"P(X=0)·P(Y=0) = {px0}×{py0} = {prod}",
            f"P(X=0,Y=0) = {joint}",
            f"{'Equal → independent' if abs(prod-joint)<1e-4 else 'Not equal → not independent'}",
        ], {"prod": prod, "joint": joint})
    return _unknown(ask)


@_reg("covariance")
def _s_covariance(ask: str, params: dict) -> Solved:
    table = np.array(params["table"])
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
        return Solved(cov, [
            "Cov(X,Y) = E[XY] - E[X]·E[Y]",
            f"E[X] = {round(ex,4)},  E[Y] = {round(ey,4)}",
            f"E[XY] = Σᵢⱼ xᵢ·yⱼ·P(X=xᵢ,Y=yⱼ) = {round(exy,4)}",
            f"Cov(X,Y) = {round(exy,4)} - {round(ex,4)}×{round(ey,4)} = {cov}",
        ], {"ex": round(ex, 4), "ey": round(ey, 4), "exy": round(exy, 4)})
    if ask == "var_of_sum":
        ans = round(vx + vy + 2 * cov, 4)
        return Solved(ans, [
            "Var(X+Y) = Var(X) + Var(Y) + 2·Cov(X,Y)",
            f"Var(X) = {round(vx,4)},  Var(Y) = {round(vy,4)},  Cov(X,Y) = {cov}",
            f"= {round(vx,4)} + {round(vy,4)} + 2×{cov} = {ans}",
        ], {"vx": round(vx, 4), "vy": round(vy, 4), "cov": cov})
    return _unknown(ask)


@_reg("correlation")
def _s_correlation(ask: str, params: dict) -> Solved:
    table = np.array(params["table"])
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
    denom = sx * sy
    ans = round(cov / denom, 4) if denom > 1e-9 else 0.0
    if ask == "correlation":
        return Solved(ans, [
            "ρ(X,Y) = Cov(X,Y) / (σ_X · σ_Y)",
            f"Cov(X,Y) = E[XY] - E[X]·E[Y]"
            f" = {round(exy,4)} - {round(ex,4)}×{round(ey,4)} = {round(cov,4)}",
            f"σ_X = √Var(X) = √{round(vx,4)} = {round(sx,4)},  σ_Y = {round(sy,4)}",
            f"ρ = {round(cov,4)} / ({round(sx,4)}×{round(sy,4)})"
            f" = {round(cov,4)}/{round(denom,4)} = {ans}",
        ], {"cov": round(cov, 4), "sx": round(sx, 4), "sy": round(sy, 4)})
    return _unknown(ask)


@_reg("expectation_joint")
def _s_expectation_joint(ask: str, params: dict) -> Solved:
    table = np.array(params["table"])
    x_vals = np.array([1.0, 2.0])
    y_vals = np.array([1.0, 2.0])
    ex = float(np.dot(x_vals, table.sum(axis=1)))
    ey = float(np.dot(y_vals, table.sum(axis=0)))
    exy = float(sum(x_vals[i] * y_vals[j] * table[i, j] for i in range(2) for j in range(2)))
    if ask == "E_XY":
        ans = round(exy, 4)
        return Solved(ans, [
            "E[XY] = ΣΣ x·y·P(X=x, Y=y)",
            f"= 1·1·{table[0,0]:.4f} + 1·2·{table[0,1]:.4f}"
            f" + 2·1·{table[1,0]:.4f} + 2·2·{table[1,1]:.4f}",
            f"= {ans}",
        ], {})
    if ask == "E_sum":
        ans = round(ex + ey, 4)
        return Solved(ans, [
            "Linearity: E[X+Y] = E[X] + E[Y]",
            f"E[X] = {round(ex,4)},  E[Y] = {round(ey,4)}",
            f"E[X+Y] = {round(ex,4)} + {round(ey,4)} = {ans}",
        ], {"ex": round(ex, 4), "ey": round(ey, 4)})
    return _unknown(ask)


@_reg("conditional_expectation")
def _s_conditional_expectation(ask: str, params: dict) -> Solved:
    table = np.array(params["table"])
    y_vals = np.array([0.0, 1.0, 2.0])
    px = table.sum(axis=1)
    ey_x0 = float(np.dot(y_vals, table[0, :] / px[0]))
    ey_x1 = float(np.dot(y_vals, table[1, :] / px[1]))
    px0 = round(float(px[0]), 4)
    px1 = round(float(px[1]), 4)
    row0 = [round(float(table[0, j]), 4) for j in range(3)]
    row1 = [round(float(table[1, j]), 4) for j in range(3)]
    cond0 = [round(float(table[0, j] / px[0]), 4) for j in range(3)]
    cond1 = [round(float(table[1, j] / px[1]), 4) for j in range(3)]

    if ask == "cond_expectation":
        ans = round(ey_x1, 4)
        return Solved(ans, [
            "Goal: E[Y|X=1] = Σ_y  y · P(Y=y | X=1)",
            f"Step 1 — marginal P(X=1) = {row1[0]} + {row1[1]} + {row1[2]} = {px1}",
            "Step 2 — conditional probs P(Y=j|X=1) = P(X=1,Y=j) / P(X=1):",
            f"  P(Y=0|X=1) = {row1[0]} / {px1} = {cond1[0]}",
            f"  P(Y=1|X=1) = {row1[1]} / {px1} = {cond1[1]}",
            f"  P(Y=2|X=1) = {row1[2]} / {px1} = {cond1[2]}",
            "Step 3 — weighted sum:",
            f"  E[Y|X=1] = 0·{cond1[0]} + 1·{cond1[1]} + 2·{cond1[2]}",
            f"           = 0 + {cond1[1]} + {round(2*cond1[2], 4)} = {ans}",
        ], {})
    if ask == "double_expectation":
        ey_x0_r = round(ey_x0, 4)
        ey_x1_r = round(ey_x1, 4)
        tower = ey_x0 * px[0] + ey_x1 * px[1]
        ans = round(float(tower), 4)
        return Solved(ans, [
            "Tower property: E[Y] = E[E[Y|X]] = E[Y|X=0]·P(X=0) + E[Y|X=1]·P(X=1)",
            f"Marginals: P(X=0) = {px0},  P(X=1) = {px1}",
            "Compute E[Y|X=0] — divide row 0 by P(X=0):",
            f"  P(Y=0|X=0) = {row0[0]}/{px0} = {cond0[0]}",
            f"  P(Y=1|X=0) = {row0[1]}/{px0} = {cond0[1]}",
            f"  P(Y=2|X=0) = {row0[2]}/{px0} = {cond0[2]}",
            f"  E[Y|X=0] = 0·{cond0[0]} + 1·{cond0[1]} + 2·{cond0[2]} = {ey_x0_r}",
            "Compute E[Y|X=1] — divide row 1 by P(X=1):",
            f"  P(Y=0|X=1) = {row1[0]}/{px1} = {cond1[0]}",
            f"  P(Y=1|X=1) = {row1[1]}/{px1} = {cond1[1]}",
            f"  P(Y=2|X=1) = {row1[2]}/{px1} = {cond1[2]}",
            f"  E[Y|X=1] = 0·{cond1[0]} + 1·{cond1[1]} + 2·{cond1[2]} = {ey_x1_r}",
            "Apply tower property:",
            f"  E[Y] = {ey_x0_r}×{px0} + {ey_x1_r}×{px1}",
            f"       = {round(ey_x0_r*px0,4)} + {round(ey_x1_r*px1,4)} = {ans}",
        ], {})
    return _unknown(ask)


@_reg("total_variance")
def _s_total_variance(ask: str, params: dict) -> Solved:
    table = np.array(params["table"])
    y_vals = np.array([0.0, 1.0, 2.0])
    px = table.sum(axis=1)
    ey_given_x = [float(np.dot(y_vals, table[i, :] / px[i])) for i in range(2)]
    e2y_given_x = [float(np.dot(y_vals ** 2, table[i, :] / px[i])) for i in range(2)]
    var_y_given_x = [e2y_given_x[i] - ey_given_x[i] ** 2 for i in range(2)]
    e_var = float(np.dot(var_y_given_x, px))
    e_ey = float(np.dot(ey_given_x, px))
    var_ey = float(np.dot(np.array(ey_given_x) ** 2, px)) - e_ey ** 2
    ans = round(e_var + var_ey, 4)
    if ask == "total_variance":
        return Solved(ans, [
            "Law of Total Variance: Var(Y) = E[Var(Y|X)] + Var(E[Y|X])",
            f"E[Y|X=0] = {round(ey_given_x[0],4)},  Var(Y|X=0) = {round(var_y_given_x[0],4)}",
            f"E[Y|X=1] = {round(ey_given_x[1],4)},  Var(Y|X=1) = {round(var_y_given_x[1],4)}",
            f"E[Var(Y|X)] = {round(e_var,4)}",
            f"Var(E[Y|X]) = {round(var_ey,4)}",
            f"Var(Y) = {round(e_var,4)} + {round(var_ey,4)} = {ans}",
        ], {"e_var": round(e_var, 4), "var_ey": round(var_ey, 4)})
    return _unknown(ask)


@_reg("sum_distribution")
def _s_sum_distribution(ask: str, params: dict) -> Solved:
    n, lam = params["n"], params["lam"]
    mean_s = round(n / lam, 4)
    var_s = round(n / lam ** 2, 4)
    if ask == "sum_mean_var":
        return Solved(mean_s, [
            f"Xᵢ ~ Exp(λ={lam}) iid,  S = X₁+…+X_{n}",
            f"E[Xᵢ] = 1/λ = {round(1/lam,4)}",
            f"E[S] = n·E[X] = {n} × {round(1/lam,4)} = {mean_s}",
            f"(S ~ Gamma(α={n}, θ=1/λ={round(1/lam,4)}))",
        ], {})
    if ask == "identify_sum_dist":
        return Solved(var_s, [
            f"S = X₁+…+X_{n},  Xᵢ ~ Exp(λ={lam}) iid  →  S ~ Gamma({n}, 1/{lam})",
            f"Var(Xᵢ) = 1/λ² = {round(1/lam**2,4)}",
            f"Var(S) = n·Var(X) = {n} × {round(1/lam**2,4)} = {var_s}",
        ], {})
    return _unknown(ask)


@_reg("order_statistics")
def _s_order_statistics(ask: str, params: dict) -> Solved:
    n, lam, t = params["n"], params["lam"], params["t"]
    ft = round(float(1 - np.exp(-lam * t)), 4)
    sf = round(1 - ft, 4)
    if ask == "max_cdf":
        ans = round(ft ** n, 4)
        return Solved(ans, [
            f"X₁,…,X_{n} iid Exp(λ={lam}),  M = max",
            f"F(t) = P(Xᵢ ≤ t) = 1 - e^{{-{lam}·{t}}} = {ft}",
            f"F_max(t) = P(M ≤ t) = [F(t)]^n = {ft}^{n} = {ans}",
        ], {"ft": ft})
    if ask == "min_cdf":
        ans = round(1 - (1 - ft) ** n, 4)
        return Solved(ans, [
            f"X₁,…,X_{n} iid Exp(λ={lam}),  m = min",
            f"F(t) = {ft},  1-F(t) = {sf}",
            f"F_min(t) = P(m ≤ t) = 1 - [1-F(t)]^n = 1 - {sf}^{n}",
            f"= 1 - {round(sf**n,6)} = {ans}",
        ], {"ft": ft, "sf": sf})
    if ask == "min_max_prob":
        ans = round((1 - ft) ** n, 4)
        return Solved(ans, [
            f"X₁,…,X_{n} iid Exp(λ={lam})",
            "P(min > t) = P(all Xᵢ > t) = [P(X > t)]^n = [1-F(t)]^n",
            f"= {sf}^{n} = {ans}",
        ], {"sf": sf})
    return _unknown(ask)


@_reg("clt")
def _s_clt(ask: str, params: dict) -> Solved:
    n, lam = params["n"], params["lam"]
    mu = params["mu"]
    sigma2 = params["sigma2"]
    if ask == "clt_prob":
        c, z = params["c"], params["z"]
        ans = round(float(norm.cdf(z)), 4)
        sigma_xbar = round((sigma2 / n) ** 0.5, 4)
        return Solved(ans, [
            f"Xᵢ ~ Exp(λ={lam}) iid,  n={n},  μ={mu}, σ²={sigma2}",
            "CLT: X̄ ≈ N(μ, σ²/n)",
            f"σ_{{X̄}} = √(σ²/n) = √({sigma2}/{n}) = {sigma_xbar}",
            f"z = (c-μ)/σ_{{X̄}} = ({c}-{mu})/{sigma_xbar} = {z}",
            f"P(X̄ ≤ {c}) ≈ Φ({z}) = {ans}",
        ], {"sigma_xbar": sigma_xbar, "z": z})
    if ask == "clt_sum_prob":
        c, z = params["c"], params["z"]
        ans = round(float(norm.sf(z)), 4)
        sigma_s = round((n * sigma2) ** 0.5, 4)
        return Solved(ans, [
            f"S = X₁+…+X_{n},  Xᵢ ~ Exp(λ={lam}) iid",
            f"CLT: S ≈ N(n·μ, n·σ²) = N({n*mu:.2f}, {round(n*sigma2,4)})",
            f"σ_S = √(n·σ²) = {sigma_s}",
            f"z = (c - n·μ)/σ_S = ({c} - {round(n*mu,4)})/{sigma_s} = {z}",
            f"P(S > {c}) ≈ 1 - Φ({z}) = {ans}",
        ], {"sigma_s": sigma_s, "z": z})
    return _unknown(ask)


@_reg("chebyshev")
def _s_chebyshev(ask: str, params: dict) -> Solved:
    mu, sigma2, k = params["mu"], params["sigma2"], params["k"]
    sigma = round(sigma2 ** 0.5, 4)
    if ask == "chebyshev_bound":
        ans = round(1 / k ** 2, 4)
        return Solved(ans, [
            "Chebyshev: P(|X-μ| ≥ k·σ) ≤ 1/k²",
            f"μ={mu}, σ²={sigma2}, σ={sigma}, k={k}",
            f"P(|X-{mu}| ≥ {k}·{sigma}) ≤ 1/{k}² = 1/{round(k**2,4)} = {ans}",
        ], {"sigma": sigma})
    if ask == "markov_bound":
        t = params["t"]
        ans = round(mu / t, 4)
        return Solved(ans, [
            "Markov's inequality: P(X ≥ t) ≤ E[X]/t  (requires X ≥ 0)",
            f"E[X] = {mu},  t = {t}",
            f"P(X ≥ {t}) ≤ {mu}/{t} = {ans}",
        ], {"t": t})
    return _unknown(ask)



@_reg("moments")
def _s_moments(ask: str, params: dict) -> Solved:
    mu = params["mu"]
    sigma2 = params["sigma2"]
    if ask == "ex_squared":
        m2 = round(sigma2 + mu ** 2, 4)
        return Solved(m2, [
            "Key identity: E[X²] = Var(X) + (E[X])²",
            f"E[X] = {mu},  Var(X) = {sigma2}",
            f"E[X²] = {sigma2} + {mu}² = {sigma2} + {round(mu**2, 4)} = {m2}",
        ], {"m2": m2})
    if ask == "variance_from_moments":
        m2 = params["m2"]
        ans = round(m2 - mu ** 2, 4)
        return Solved(ans, [
            "Computational formula: Var(X) = E[X²] − (E[X])²",
            f"E[X] = {mu},  E[X²] = {m2}",
            f"Var(X) = {m2} − {mu}² = {m2} − {round(mu**2, 4)} = {ans}",
        ], {})
    return _unknown(ask)


@_reg("pareto")
def _s_pareto(ask: str, params: dict) -> Solved:
    alpha = params["alpha"]
    theta = params["theta"]
    if ask == "mean":
        ans = round(theta / (alpha - 1), 4)
        return Solved(ans, [
            f"X ~ Pareto(α={alpha}, θ={theta}),  S(x) = (θ/(x+θ))^α",
            "E[X] = θ / (α−1)  [requires α > 1]",
            f"     = {theta} / ({alpha}−1) = {theta} / {round(alpha-1,1)} = {ans}",
        ], {})
    if ask == "survival":
        x = params["x"]
        ratio = round(theta / (x + theta), 6)
        ans = round(ratio ** alpha, 4)
        return Solved(ans, [
            f"X ~ Pareto(α={alpha}, θ={theta})",
            "S(x) = P(X > x) = (θ/(x+θ))^α",
            f"S({x}) = ({theta}/({x}+{theta}))^{alpha}",
            f"      = ({theta}/{round(x+theta,4)})^{alpha}",
            f"      = {round(ratio,4)}^{alpha} = {ans}",
        ], {"ratio": ratio})
    if ask == "prob_interval":
        x1, x2 = params["x1"], params["x2"]
        s1 = round((theta / (x1 + theta)) ** alpha, 4)
        s2 = round((theta / (x2 + theta)) ** alpha, 4)
        ans = round(s1 - s2, 4)
        return Solved(ans, [
            f"X ~ Pareto(α={alpha}, θ={theta})",
            "P(a < X < b) = S(a) − S(b) where S(x) = (θ/(x+θ))^α",
            f"S({x1}) = ({theta}/{round(x1+theta,4)})^{alpha} = {s1}",
            f"S({x2}) = ({theta}/{round(x2+theta,4)})^{alpha} = {s2}",
            f"P({x1} < X < {x2}) = {s1} − {s2} = {ans}",
        ], {"s1": s1, "s2": s2})
    return _unknown(ask)


@_reg("weibull")
def _s_weibull(ask: str, params: dict) -> Solved:
    import math
    from math import gamma as gamma_fn
    alpha = params["alpha"]
    theta = params["theta"]
    if ask == "survival":
        x = params["x"]
        exponent = round((x / theta) ** alpha, 6)
        ans = round(math.exp(-exponent), 4)
        return Solved(ans, [
            f"X ~ Weibull(α={alpha}, θ={theta})",
            "S(x) = P(X > x) = exp(−(x/θ)^α)",
            f"S({x}) = exp(−({x}/{theta})^{alpha})",
            f"      = exp(−{exponent}) = {ans}",
        ], {"exponent": exponent})
    if ask == "cdf":
        x = params["x"]
        exponent = round((x / theta) ** alpha, 6)
        ans = round(1 - math.exp(-exponent), 4)
        return Solved(ans, [
            f"X ~ Weibull(α={alpha}, θ={theta})",
            "F(x) = 1 − exp(−(x/θ)^α)",
            f"F({x}) = 1 − exp(−({x}/{theta})^{alpha})",
            f"      = 1 − exp(−{exponent}) = {ans}",
        ], {"exponent": exponent})
    if ask == "mean":
        g = round(gamma_fn(1 + 1 / alpha), 6)
        ans = round(theta * g, 4)
        return Solved(ans, [
            f"X ~ Weibull(α={alpha}, θ={theta})",
            "E[X] = θ · Γ(1 + 1/α)",
            f"     = {theta} · Γ(1 + 1/{alpha})",
            f"     = {theta} · Γ({round(1 + 1/alpha, 4)})",
            f"     = {theta} · {g} = {ans}",
        ], {"gamma_val": g})
    return _unknown(ask)


@_reg("transformations_multi")
def _s_transformations_multi(ask: str, params: dict) -> Solved:
    import math
    if ask == "min_of_exp":
        n, lam, t = params["n"], params["lam"], params["t"]
        nlam = round(n * lam, 4)
        ans = round(math.exp(-nlam * t), 4)
        return Solved(ans, [
            "Key result: min of n iid Exp(λ) ~ Exp(nλ)",
            f"n={n}, λ={lam}  →  M = min ~ Exp({n}×{lam}) = Exp({nlam})",
            f"P(M > {t}) = exp(−{nlam}×{t}) = exp(−{round(nlam*t,4)}) = {ans}",
        ], {"n_lam": nlam})
    if ask == "sum_uniform_prob":
        z = params["z"]
        ans = round(z ** 2 / 2, 4)
        return Solved(ans, [
            "Z = X+Y with X,Y ~ U(0,1). PDF of Z is triangular.",
            "For 0 < z ≤ 1: f_Z(z) = z  →  F_Z(z) = z²/2",
            f"P(Z ≤ {z}) = {z}²/2 = {round(z**2, 4)}/2 = {ans}",
        ], {})
    if ask == "jacobian_abs":
        a, b = params["a"], params["b"]
        det = a * b - 1
        ans = round(1 / abs(det), 4)
        return Solved(ans, [
            f"Forward map: U = {a}X + Y,  V = X + {b}Y",
            f"Jacobian of forward map: det([{a},1; 1,{b}]) = {a}×{b} − 1×1 = {det}",
            f"|Jacobian of inverse| = 1/|det| = 1/{abs(det)} = {ans}",
            "f(u,v) = f(x,y) × |J_inverse| — multiply joint PDF by this factor.",
        ], {"det": det})
    return _unknown(ask)


# Bridge the ported solver registry into StudyEngine's central one, so
# engine.feedback.worked_solution returns these steps for every Exam P kind.
from engine.feedback.solve import register_solver as _register_solver  # noqa: E402


def _examp_steps(kind: str, ask: str, params: dict) -> list[str]:
    return solve(kind, ask, params).steps


for _kind in list(_solvers):
    _register_solver(_kind)(_examp_steps)

