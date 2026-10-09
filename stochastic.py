"""Monte Carlo uncertainty analysis, built on core.py.

Every LCOH and NPV here comes from the same `core` functions the deterministic
tabs use, called with arrays instead of scalars. There is no second copy of the
formulas, so the stochastic and deterministic views cannot drift apart.

Three things this module does differently from the earlier standalone version,
each of which changed a published number:

1. Prices come from the app's own `core.Prices`, not from a test harness.
   The old `__main__` block fed `COUNTRY_DEFAULTS['elec']` (18 ct/kWh for
   Germany) straight in as a delivered price. That figure is only a seed the
   app multiplies by 0.6 to get the commodity default, and it is roughly 31%
   above the app's effective delivered price. Every parity probability
   computed that way was far too pessimistic about electrification.

2. Volatility and the gas-electricity dependence are applied to the COMMODITY
   components only. Grid fees, levies and the carbon price are set by
   regulation and policy; shaking them as though they were wholesale prices
   inflated the spread of the parity gap by about a quarter. The estimated
   Kendall's tau was also measured on wholesale series, so applying it to a
   delivered price that is a third regulated charges was a mismatch.

3. The random seed is honoured, one discount rate is drawn per trial and
   shared across technologies, one gas boiler is sampled per country, and the
   CAPEX subsidy reaches electrification options only. Each of these makes a
   trial a coherent scenario rather than a bundle of unrelated draws.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.stats import norm, triang

import core
from core import Prices, Technology

# ---------------------------------------------------------------------------
# Uncertainty definitions
# ---------------------------------------------------------------------------

# Half-width of the +/- range around each point estimate, as a fraction.
# (capex, eff, opex_per_mwh, util). The efficiency half-widths are symmetric
# while the published COP bands are not, so they approximate the source
# ranges rather than reproducing them. Documented in the Methodology tab.
UNCERTAINTY_RANGES = {
    "Gas Boiler":                                 (0.10, 0.03, 0.15, 0.05),
    "Electric Boiler":                            (0.15, 0.02, 0.15, 0.05),
    "Heat Pump (medium heat, to 150 \u00b0C)":      (0.25, 0.20, 0.20, 0.10),
    "Booster Heat Pump (steam, above 150 \u00b0C)": (0.25, 0.20, 0.20, 0.10),
    "Mechanical Vapour Recompression":            (0.30, 0.20, 0.25, 0.10),
    "Microwave":                                  (0.35, 0.15, 0.30, 0.15),
    # Legacy names, kept so older saved configurations still resolve.
    "High Temperature Heat Pump":                 (0.25, 0.15, 0.20, 0.10),
    "Low Temperature Heat Pump":                  (0.20, 0.10, 0.20, 0.08),
}
DEFAULT_RANGE = (0.15, 0.10, 0.15, 0.08)

# Volatility of the COMMODITY component of each fuel price. These are
# placeholders, not estimates: the 22 August variance work showed the parity
# probability moves more with these than with the copula, so they are the
# first thing to derive empirically from the series already loaded in
# estimate_tau.py.
COMMODITY_VOLATILITY = {"Gas": 0.25, "Elec": 0.30}

# Discount rate spread, as multipliers on the user's central WACC.
DISCOUNT_RATE_SPREAD = (0.6, 1.6)
DISCOUNT_RATE_BOUNDS = (0.02, 0.20)

# Kendall's tau between gas and electricity commodity LOG-RETURNS, estimated
# per jurisdiction at monthly frequency. Germany is empirical from 2015-2026
# TTF gas and EPEX day-ahead power. None falls back to independence, and the
# UI says so rather than hiding it.
PRICE_TAU_GAS_ELEC = {
    "Germany": 0.426,
    "UK": None,
    "USA - California": None,
    "USA - Texas": None,
}


def tau_to_rho(tau: float) -> float:
    """Gaussian-copula parameter from Kendall's tau: rho = sin(pi*tau/2)."""
    return float(np.sin(np.pi * tau / 2.0))


# ---------------------------------------------------------------------------
# Sampling primitives
# ---------------------------------------------------------------------------

def _triangular_bounds(mode, half_width, floor=None):
    low = mode * (1.0 - half_width)
    high = mode * (1.0 + half_width)
    if floor is not None:
        low = max(low, floor)
    return low, high


def triangular(rng, mode, half_width, n, floor=None):
    """Triangular draw centred on `mode`.

    The lower bound is raised to `floor` before drawing rather than clipped
    afterwards. Clipping a drawn sample piles probability mass onto the floor
    and shifts the mean; raising the bound keeps a proper density.
    """
    low, high = _triangular_bounds(mode, half_width, floor)
    if high <= low:
        return np.full(n, float(mode))
    return rng.triangular(low, mode, high, size=n)


def triangular_ppf(u, mode, half_width, floor=None):
    """Inverse CDF of the same triangular marginal, for the copula path."""
    low, high = _triangular_bounds(mode, half_width, floor)
    scale = high - low
    if scale <= 0:
        return np.full_like(np.asarray(u, dtype=float), float(mode))
    c = (mode - low) / scale
    return triang.ppf(u, c, loc=low, scale=scale)


def nearest_correlation(R):
    """Nearest positive semi-definite correlation matrix (eigenvalue clip).

    A no-op for a valid 2x2. It matters once a carbon price is added as a
    third correlated variable.
    """
    R = np.asarray(R, dtype=float)
    vals, vecs = np.linalg.eigh(R)
    if (vals > 0).all():
        return R
    vals = np.clip(vals, 1e-8, None)
    A = (vecs * vals) @ vecs.T
    d = np.sqrt(np.diag(A))
    return A / np.outer(d, d)


# ---------------------------------------------------------------------------
# Drawing a price world
# ---------------------------------------------------------------------------

def draw_prices(rng, prices: Prices, tau: float, n: int, volatility=None) -> Prices:
    """One correlated (gas, electricity) commodity world of `n` trials.

    Only the commodity components are drawn. Carbon pricing, grid fees,
    levies and policy relief are carried through deterministically, because
    they are set by policy rather than by the market and because the tau was
    estimated on wholesale series.

    The Gaussian copula is invariant under the monotone marginal transform, so
    passing rho = sin(pi*tau/2) reproduces the target Kendall's tau exactly.
    """
    vol = volatility or COMMODITY_VOLATILITY
    rho = tau_to_rho(tau)
    R = nearest_correlation([[1.0, rho], [rho, 1.0]])
    Z = rng.multivariate_normal(np.zeros(2), R, size=n)
    U = norm.cdf(Z)

    gas = triangular_ppf(U[:, 0], prices.gas_commodity, vol["Gas"], floor=1e-5)
    elec = triangular_ppf(U[:, 1], prices.elec_commodity, vol["Elec"], floor=1e-5)

    return Prices(
        gas_commodity=gas,
        carbon_cost=prices.carbon_cost,
        elec_commodity=elec,
        elec_noncommodity=prices.elec_noncommodity,
        elec_relief=prices.elec_relief,
    )


def draw_technology(rng, tech: Technology, n: int) -> Technology:
    """Sample a technology's uncertain parameters. Life stays deterministic."""
    cap_hw, eff_hw, opex_hw, util_hw = UNCERTAINTY_RANGES.get(tech.name, DEFAULT_RANGE)
    return tech.with_samples(
        capex=triangular(rng, tech.capex, cap_hw, n, floor=1.0),
        eff=triangular(rng, tech.eff, eff_hw, n, floor=0.1),
        opex_per_mwh=triangular(rng, tech.opex_per_mwh, opex_hw, n, floor=0.0),
        util=triangular(rng, tech.util, util_hw, n, floor=500.0),
    )


def draw_discount_rate(rng, central: float, n: int):
    """One discount rate per trial, shared by every technology in that trial.

    A trial is a state of the world. The cost of capital cannot be 5% for the
    boiler and 11% for the heat pump in the same state of the world.
    """
    lo_mult, hi_mult = DISCOUNT_RATE_SPREAD
    lo_bound, hi_bound = DISCOUNT_RATE_BOUNDS
    return rng.triangular(
        max(lo_bound, central * lo_mult), central, min(hi_bound, central * hi_mult), size=n
    )


# ---------------------------------------------------------------------------
# The run
# ---------------------------------------------------------------------------

@dataclass
class CountryResult:
    country: str
    unit: str
    symbol: str
    tau: float
    tau_is_estimated: bool
    baseline_lcoh: np.ndarray
    lcoh: dict          # tech name -> array
    npv: dict           # tech name -> array
    gap: dict           # tech name -> array, LCOH vs the sampled boiler
    prices: Prices      # the sampled price world

    @property
    def provenance(self) -> str:
        if self.tau_is_estimated:
            return f"gas-electricity dependence: Kendall's tau = {self.tau:.3f} (estimated)"
        return "gas-electricity dependence: independence assumed (tau not yet estimated)"


def run_monte_carlo(
    country_ctx: dict,
    technologies: dict,
    baseline: Technology,
    discount_rate: float,
    n: int = 5000,
    seed: int = 42,
    tau_overrides: dict | None = None,
    correlated: bool = True,
    volatility: dict | None = None,
) -> dict:
    """Run the Monte Carlo for every (country, technology) pair.

    `country_ctx` is the same structure `core.build_results` takes: name ->
    {prices, subsidy, fx, symbol, unit}.

    Returns {country: CountryResult}. The generator is explicit and seeded
    once here; nothing reseeds the global numpy RNG, so the seed the caller
    passes is the seed that is used.
    """
    rng = np.random.default_rng(seed)
    tau_map = {**PRICE_TAU_GAS_ELEC, **(tau_overrides or {})}
    results = {}

    for country, ctx in country_ctx.items():
        raw_tau = tau_map.get(country)
        estimated = raw_tau is not None
        tau = float(raw_tau) if (estimated and correlated) else 0.0

        prices = draw_prices(rng, ctx["prices"], tau, n, volatility)
        rate = draw_discount_rate(rng, discount_rate, n)

        # One boiler per country per trial. Every technology is compared
        # against the same sampled counterfactual.
        base_s = draw_technology(rng, baseline, n)

        lcoh, npv, gap = {}, {}, {}
        base_lcoh = None

        for tech in technologies.values():
            tech_s = draw_technology(rng, tech, n)
            econ = core.switching_economics(
                tech_s, base_s, prices, rate, subsidy=ctx["subsidy"], fx=ctx["fx"]
            )
            lcoh[tech.name] = np.asarray(econ["lcoh"])
            npv[tech.name] = np.asarray(econ["npv"])
            gap[tech.name] = np.asarray(econ["lcoh_gap"])
            base_lcoh = np.asarray(econ["baseline_lcoh"])

        if base_lcoh is None:
            base_lcoh = np.asarray(
                core.levelised_cost(base_s, prices.gas_effective, rate, fx=ctx["fx"])
            )

        results[country] = CountryResult(
            country=country, unit=ctx["unit"], symbol=ctx["symbol"],
            tau=tau, tau_is_estimated=estimated and correlated,
            baseline_lcoh=base_lcoh, lcoh=lcoh, npv=npv, gap=gap, prices=prices,
        )

    return results


# ---------------------------------------------------------------------------
# Summaries
# ---------------------------------------------------------------------------

def binomial_standard_error(p_percent: float, n: int) -> float:
    """Standard error of a probability estimated from `n` draws, in points.

    A parity probability near 2% from 5,000 draws carries about 0.2 points of
    Monte Carlo noise, so quoting it to a decimal place without the draw count
    overstates the precision.
    """
    p = p_percent / 100.0
    return float(np.sqrt(max(p * (1 - p), 0.0) / n) * 100.0)


def summarise(results: dict, n: int) -> list:
    """One row per (country, technology), with distribution statistics."""
    rows = []
    for country, res in results.items():
        for tech_name, samples in res.lcoh.items():
            gap = res.gap[tech_name]
            npv = res.npv[tech_name]
            cheaper = float(np.mean(samples < res.baseline_lcoh) * 100)
            positive = float(np.mean(npv > 0) * 100)
            rows.append({
                "Country": country,
                "Technology": tech_name,
                "P10": float(np.percentile(samples, 10)),
                "P50": float(np.percentile(samples, 50)),
                "P90": float(np.percentile(samples, 90)),
                "Mean": float(np.mean(samples)),
                "Std": float(np.std(samples)),
                "Median gap": float(np.median(gap)),
                "P(cheaper than gas)": cheaper,
                "+/- (MC noise)": binomial_standard_error(cheaper, n) * 1.96,
                "P(NPV > 0)": positive,
                "Median NPV": float(np.median(npv)),
            })
    return rows


VARIANCE_KNOBS = ("prices", "eff", "capex", "opex_per_mwh", "util", "discount_rate")

KNOB_LABELS = {
    "prices": "commodity prices (gas and electricity jointly)",
    "eff": "efficiency / COP",
    "capex": "CAPEX",
    "opex_per_mwh": "fixed O&M",
    "util": "utilisation",
    "discount_rate": "discount rate",
}


def variance_decomposition(rng_seed, country_ctx, tech, baseline, discount_rate,
                           country, n=4000, tau_overrides=None):
    """Share of parity-gap variance attributable to each input, as MAIN EFFECTS.

    Each knob is measured by varying it alone with every other input held at
    its point value. The obvious alternative, freezing one input at a time and
    attributing the drop in variance, is not usable here: gas and electricity
    are deliberately correlated, and the parity gap is a difference, so their
    co-movement partially cancels. Freezing one of them then makes the variance
    go UP, and the implied share is negative. Measured at the German defaults,
    total variance rises from 0.47 to 0.54 when electricity is held fixed.

    Gas and electricity are treated as a single block for the same reason:
    splitting correlated inputs into individual shares is not meaningful.

    Shares are normalised to sum to 100 and are indicative. Interactions are
    not attributed, so they will not reproduce an exact Sobol decomposition.
    """
    ctx = country_ctx[country]
    effects = {}
    for knob in VARIANCE_KNOBS:
        gap = _gap_samples(rng_seed, ctx, tech, baseline, discount_rate, n,
                           tau_overrides, vary=knob)
        effects[knob] = float(np.var(gap))

    scale = sum(effects.values())
    if scale <= 0:
        return {}
    return {KNOB_LABELS[k]: v / scale * 100.0
            for k, v in sorted(effects.items(), key=lambda kv: -kv[1])}


def _gap_samples(seed, ctx, tech, baseline, discount_rate, n, tau_overrides, vary=None):
    """Parity-gap draws with only `vary` random and everything else at its
    point value. `vary=None` leaves every input random."""
    rng = np.random.default_rng(seed)
    tau_map = {**PRICE_TAU_GAS_ELEC, **(tau_overrides or {})}
    raw = tau_map.get(ctx.get("name"))
    tau = float(raw) if raw is not None else 0.0

    # Draw everything first so the random stream is identical across variants,
    # then substitute point values for whatever is not being varied.
    prices = draw_prices(rng, ctx["prices"], tau, n)
    rate = draw_discount_rate(rng, discount_rate, n)
    base_s = draw_technology(rng, baseline, n)
    tech_s = draw_technology(rng, tech, n)

    if vary is not None:
        if vary != "prices":
            prices = ctx["prices"]
        if vary != "discount_rate":
            rate = discount_rate
        for field in ("eff", "capex", "opex_per_mwh", "util"):
            if vary != field:
                tech_s = tech_s.with_samples(**{field: getattr(tech, field)})
                base_s = base_s.with_samples(**{field: getattr(baseline, field)})

    econ = core.switching_economics(tech_s, base_s, prices, rate,
                                    subsidy=ctx["subsidy"], fx=ctx["fx"])
    return np.asarray(econ["lcoh_gap"])
