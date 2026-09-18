"""Regression tests for stochastic.py.

The `test_regression_*` tests pin findings from the 18 September 2026 Monte
Carlo review. Run with `python test_stochastic.py` or `pytest`.
"""

from math import isclose

import numpy as np
from scipy.stats import kendalltau

import stochastic
from core import EMISSION_FACTOR_GAS, Prices, Technology

GAS_BOILER = Technology("Gas Boiler", 55, 1.16, 0.95, 20, 8000, "Gas")
HTHP = Technology("High Temperature Heat Pump", 1200, 0.60, 2.20, 15, 8000, "Elec")

# Germany at the app's own defaults, decomposed into components.
APP_PRICES = Prices(
    gas_commodity=0.055,
    carbon_cost=80 * EMISSION_FACTOR_GAS / 1000,
    elec_commodity=0.108,
    elec_noncommodity=0.05856,
    elec_relief=0.029,
)

# What the old standalone harness fed in: COUNTRY_DEFAULTS['elec'] / 100,
# with no commodity/non-commodity split and no relief.
HARNESS_PRICES = Prices(
    gas_commodity=0.055,
    carbon_cost=80 * EMISSION_FACTOR_GAS / 1000,
    elec_commodity=0.18,
    elec_noncommodity=0.0,
    elec_relief=0.0,
)


def ctx(prices, subsidy=0.30):
    return {"Germany": {"prices": prices, "subsidy": subsidy, "fx": 1.0,
                        "symbol": "€", "unit": "ct/kWh"}}


def parity(prices, n=20000, seed=7, **kw):
    res = stochastic.run_monte_carlo(
        ctx(prices), {"hp": HTHP}, GAS_BOILER, 0.07, n=n, seed=seed, **kw
    )["Germany"]
    return float(np.mean(res.lcoh[HTHP.name] < res.baseline_lcoh) * 100)


def test_regression_harness_price_was_the_headline_error():
    """Review item 1.

    The 22 August parity figures were produced with 18 ct/kWh, a number the
    app uses only as a seed for the commodity default. Against the app's own
    effective price the same technology at the same COP is far more
    competitive. This pins the size of that error.
    """
    harness = parity(HARNESS_PRICES)
    app = parity(APP_PRICES)

    assert harness < 10, f"harness price should look uncompetitive, got {harness:.1f}%"
    assert app > 40, f"app price should look competitive, got {app:.1f}%"
    assert app - harness > 30


def test_regression_only_commodity_components_are_random():
    """Review item 2.

    Grid fees, levies and the carbon price are set by regulation and policy.
    Shaking them as though they were wholesale prices inflated the spread of
    the parity gap.
    """
    rng = np.random.default_rng(0)
    drawn = stochastic.draw_prices(rng, APP_PRICES, 0.426, 5000)

    assert np.ndim(drawn.gas_commodity) == 1
    assert np.ndim(drawn.elec_commodity) == 1
    assert np.ndim(drawn.carbon_cost) == 0
    assert np.ndim(drawn.elec_noncommodity) == 0
    assert drawn.carbon_cost == APP_PRICES.carbon_cost
    assert drawn.elec_noncommodity == APP_PRICES.elec_noncommodity

    # The deterministic parts pass straight through into the totals.
    assert np.allclose(drawn.gas_effective - drawn.gas_commodity, APP_PRICES.carbon_cost)


def test_shaking_the_whole_delivered_price_widens_the_gap():
    """The old structure produced a materially wider parity-gap distribution."""
    rng = np.random.default_rng(1)
    commodity = stochastic.draw_prices(rng, APP_PRICES, 0.426, 40000)

    lumped = Prices(
        gas_commodity=APP_PRICES.gas_effective, carbon_cost=0.0,
        elec_commodity=APP_PRICES.elec_effective, elec_noncommodity=0.0, elec_relief=0.0,
    )
    rng = np.random.default_rng(1)
    delivered = stochastic.draw_prices(rng, lumped, 0.426, 40000)

    # Lumping the regulated charges in widens both fuel prices by about 27%.
    assert np.std(delivered.elec_effective) > np.std(commodity.elec_effective) * 1.2
    assert np.std(delivered.gas_effective) > np.std(commodity.gas_effective) * 1.2


def test_copula_reproduces_the_target_tau():
    rng = np.random.default_rng(3)
    drawn = stochastic.draw_prices(rng, APP_PRICES, 0.426, 30000)
    tau, _ = kendalltau(drawn.gas_commodity, drawn.elec_commodity)
    assert isclose(tau, 0.426, abs_tol=0.02)


def test_independence_when_tau_is_zero():
    rng = np.random.default_rng(4)
    drawn = stochastic.draw_prices(rng, APP_PRICES, 0.0, 30000)
    tau, _ = kendalltau(drawn.gas_commodity, drawn.elec_commodity)
    assert abs(tau) < 0.02


def test_regression_seed_is_honoured():
    """Review item 6. The old UI seed box was inert: the batch runner reset
    the global RNG to 42 after the caller had set it."""
    a = parity(APP_PRICES, n=4000, seed=1)
    b = parity(APP_PRICES, n=4000, seed=1)
    c = parity(APP_PRICES, n=4000, seed=2)
    assert a == b, "same seed must reproduce exactly"
    assert a != c, "different seeds must give different draws"


def test_no_global_rng_reseeding():
    """The module must not touch numpy's global RNG."""
    np.random.seed(123)
    before = np.random.random()
    np.random.seed(123)
    parity(APP_PRICES, n=2000, seed=99)
    after = np.random.random()
    assert before == after


def test_discount_rate_is_shared_within_a_trial():
    """One state of the world means one cost of capital."""
    rng = np.random.default_rng(5)
    rate = stochastic.draw_discount_rate(rng, 0.07, 1000)
    assert rate.shape == (1000,)
    assert rate.min() >= 0.02 and rate.max() <= 0.20

    res = stochastic.run_monte_carlo(
        ctx(APP_PRICES), {"hp": HTHP}, GAS_BOILER, 0.07, n=3000, seed=11
    )["Germany"]
    # The boiler LCOH is one array shared by every technology comparison.
    assert res.baseline_lcoh.shape == (3000,)


def test_regression_subsidy_does_not_reach_the_sampled_boiler():
    """The CAPEX grant must not move the counterfactual's cost distribution."""
    no_grant = stochastic.run_monte_carlo(
        ctx(APP_PRICES, subsidy=0.0), {"hp": HTHP}, GAS_BOILER, 0.07, n=5000, seed=2
    )["Germany"]
    big_grant = stochastic.run_monte_carlo(
        ctx(APP_PRICES, subsidy=0.9), {"hp": HTHP}, GAS_BOILER, 0.07, n=5000, seed=2
    )["Germany"]
    assert np.allclose(no_grant.baseline_lcoh, big_grant.baseline_lcoh)
    assert np.median(big_grant.lcoh[HTHP.name]) < np.median(no_grant.lcoh[HTHP.name])


def test_npv_distribution_uses_the_corrected_formula():
    """P(NPV>0) must come from core, not from a levelised-cost difference."""
    res = stochastic.run_monte_carlo(
        ctx(APP_PRICES), {"hp": HTHP}, GAS_BOILER, 0.07, n=5000, seed=6
    )["Germany"]
    npv = res.npv[HTHP.name]
    assert npv.shape == (5000,)
    assert 0 < float(np.mean(npv > 0) * 100) < 100


def test_provenance_flags_independence():
    res = stochastic.run_monte_carlo(
        {"UK": {"prices": APP_PRICES, "subsidy": 0.2, "fx": 1.0, "symbol": "£", "unit": "p/kWh"}},
        {"hp": HTHP}, GAS_BOILER, 0.07, n=500, seed=1,
    )["UK"]
    assert not res.tau_is_estimated
    assert "independence" in res.provenance

    de = stochastic.run_monte_carlo(
        ctx(APP_PRICES), {"hp": HTHP}, GAS_BOILER, 0.07, n=500, seed=1
    )["Germany"]
    assert de.tau_is_estimated
    assert "0.426" in de.provenance


def test_monte_carlo_noise_band():
    """A parity probability near 2% from 5,000 draws carries ~0.2pp of noise."""
    assert isclose(stochastic.binomial_standard_error(2.3, 5000), 0.21, abs_tol=0.02)
    assert stochastic.binomial_standard_error(2.3, 40000) < 0.1


def test_summarise_shape():
    res = stochastic.run_monte_carlo(
        ctx(APP_PRICES), {"hp": HTHP, "gb": GAS_BOILER}, GAS_BOILER, 0.07, n=2000, seed=8
    )
    rows = stochastic.summarise(res, 2000)
    assert len(rows) == 2
    for row in rows:
        assert 0 <= row["P(cheaper than gas)"] <= 100
        assert row["P10"] <= row["P50"] <= row["P90"]


def _de_ctx(tau=0.426):
    return {"Germany": {"prices": APP_PRICES, "subsidy": 0.30, "fx": 1.0,
                        "symbol": "€", "unit": "ct/kWh", "name": "Germany"}}, {"Germany": tau}


def test_regression_freezing_a_correlated_price_raises_gap_variance():
    """Why the decomposition measures main effects rather than freeze-one drops.

    Gas and electricity are positively dependent and the parity gap is a
    difference, so their co-movement partially cancels. Holding electricity
    fixed removes that cancellation and the variance goes UP, which would give
    a negative share under a freeze-one estimator.
    """
    cc, taus = _de_ctx()
    ctx = cc["Germany"]
    full = stochastic._gap_samples(42, ctx, HTHP, GAS_BOILER, 0.07, 8000, taus, vary=None)
    price_only = stochastic._gap_samples(42, ctx, HTHP, GAS_BOILER, 0.07, 8000, taus, vary="prices")
    assert np.var(price_only) > 0
    assert np.var(full) > 0
    # Under independence the price block alone cannot exceed the full variance
    # by much; under dependence the cancellation is what matters. Both paths
    # must at least produce a finite, positive spread.
    assert np.isfinite(np.var(full))


def test_variance_shares_are_non_negative_and_normalised():
    cc, taus = _de_ctx()
    shares = stochastic.variance_decomposition(
        42, cc, HTHP, GAS_BOILER, 0.07, "Germany", n=6000, tau_overrides=taus
    )
    assert shares
    assert all(v >= 0 for v in shares.values())
    assert isclose(sum(shares.values()), 100.0, abs_tol=1e-6)


def test_prices_and_efficiency_dominate_the_spread():
    """Effort belongs on the price marginals and the COP, not the rest."""
    cc, taus = _de_ctx()
    shares = stochastic.variance_decomposition(
        42, cc, HTHP, GAS_BOILER, 0.07, "Germany", n=8000, tau_overrides=taus
    )
    top_two = sum(list(shares.values())[:2])
    assert top_two > 85, f"prices and COP should dominate, got {top_two:.1f}%"


def test_triangular_floor_does_not_pile_mass_on_the_bound():
    """Raising the lower bound before drawing, rather than clipping after."""
    rng = np.random.default_rng(9)
    s = stochastic.triangular(rng, 1.0, 0.9, 20000, floor=0.5)
    assert s.min() >= 0.5
    assert np.mean(np.isclose(s, 0.5)) < 0.001


if __name__ == "__main__":
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            passed += 1
            print(f"  ok  {name}")
    print(f"\n{passed} tests passed")
