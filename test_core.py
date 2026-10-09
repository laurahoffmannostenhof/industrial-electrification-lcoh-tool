"""Regression tests for core.py.

Each test named `test_regression_*` pins a bug found in the 9 September 2026
review. Run with `python test_core.py` or `pytest test_core.py`.
"""

from math import isclose, isnan

import numpy as np

from core import (
    EMISSION_FACTOR_GAS,
    Prices,
    Technology,
    annuity_factor,
    capital_recovery_factor,
    interventions_to_close,
    levelised_cost,
    policy_decomposition,
    switching_economics,
)

GAS_BOILER = Technology("Gas Boiler", 61.7, 1.16, 0.95, 25, 8000, "Gas")
HTHP = Technology("High Temperature Heat Pump", 1200, 0.60, 2.20, 15, 8000, "Elec")
MICROWAVE = Technology("Microwave", 700, 1.0, 0.85, 12, 4000, "Elec")

# Germany, app defaults: 10.8 ct commodity, 5.856 ct non-commodity,
# Industriestrompreis relief of 2.9 ct, 5.5 ct gas, EUR 80/t carbon.
GERMANY = Prices(
    gas_commodity=0.055,
    carbon_cost=80 * EMISSION_FACTOR_GAS / 1000,
    elec_commodity=0.108,
    elec_noncommodity=0.05856,
    elec_relief=0.029,
)
RATE = 0.07
SUBSIDY = 0.30


def test_price_components_compose_to_the_totals():
    assert isclose(GERMANY.gas_effective, 0.055 + 0.01616, rel_tol=1e-9)
    assert isclose(GERMANY.gas_base, 0.055)
    assert isclose(GERMANY.elec_effective, 0.108 - 0.029 + 0.05856, rel_tol=1e-12)
    assert isclose(GERMANY.elec_raw, 0.108 + 0.05856, rel_tol=1e-12)


def test_crf_and_annuity_are_inverses():
    for life in (5, 15, 20):
        crf = capital_recovery_factor(RATE, life)
        assert isclose(crf * annuity_factor(RATE, life), 1.0, rel_tol=1e-12)


def test_crf_zero_rate():
    assert isclose(capital_recovery_factor(0.0, 10), 0.1)


def test_crf_is_array_safe():
    rates = np.array([0.0, 0.05, 0.07])
    out = capital_recovery_factor(rates, 15)
    assert out.shape == (3,)
    assert isclose(out[0], 1 / 15)
    assert isclose(out[2], capital_recovery_factor(0.07, 15))


def test_scalars_in_scalars_out():
    assert isinstance(levelised_cost(HTHP, 0.1, RATE), float)
    assert isinstance(capital_recovery_factor(RATE, 15), float)


def test_regression_npv_does_not_double_count_capital():
    """Review item 1.

    The old code took the difference of two levelised costs, which already
    amortise capital, and then subtracted incremental capital again. At the
    German defaults that turned a positive NPV into a large negative one.
    """
    econ = switching_economics(HTHP, GAS_BOILER, GERMANY, RATE, SUBSIDY)

    heat = GAS_BOILER.util
    old_savings = (econ["baseline_lcoh"] / 100 * heat) - (econ["lcoh"] / 100 * heat)
    old_npv = old_savings * annuity_factor(RATE, HTHP.life) - econ["incremental_capex"]

    assert econ["npv"] > 0, "heat pump should clear at these defaults"
    assert old_npv < 0, "the old construction gave the opposite sign"
    assert isclose(econ["npv"], 164.4, abs_tol=1.0)
    assert isclose(old_npv, -627.4, abs_tol=1.0)


def test_npv_equals_operating_savings_less_incremental_capex():
    econ = switching_economics(HTHP, GAS_BOILER, GERMANY, RATE, SUBSIDY)
    expected = (
        econ["annual_operating_saving"] * annuity_factor(RATE, HTHP.life)
        - econ["incremental_capex"]
    )
    assert isclose(econ["npv"], expected, rel_tol=1e-12)


def test_operating_saving_excludes_capital():
    econ = switching_economics(HTHP, GAS_BOILER, GERMANY, RATE, SUBSIDY)
    heat = GAS_BOILER.util
    fuel = heat * (GERMANY.gas_effective / GAS_BOILER.eff
                   - GERMANY.elec_effective / HTHP.eff)
    # O&M is per MWh of heat delivered and both deliver the same heat.
    om = (GAS_BOILER.opex_per_mwh - HTHP.opex_per_mwh) * heat / 1000
    assert isclose(econ["annual_operating_saving"], fuel + om, rel_tol=1e-12)


def test_regression_subsidy_does_not_reach_the_gas_boiler():
    """Review item 5.

    A decarbonisation CAPEX grant must not cut the cost of the counterfactual.
    The gas boiler's own LCOH has to equal the baseline used for every NPV.
    """
    with_grant = levelised_cost(GAS_BOILER, GERMANY.gas_effective, RATE, subsidy=0.9)
    without = levelised_cost(GAS_BOILER, GERMANY.gas_effective, RATE, subsidy=0.0)
    assert isclose(with_grant, without, rel_tol=1e-12)

    econ = switching_economics(GAS_BOILER, GAS_BOILER, GERMANY, RATE, SUBSIDY)
    assert isclose(econ["lcoh"], econ["baseline_lcoh"], rel_tol=1e-12)
    assert econ["npv"] == 0.0
    assert isnan(econ["payback"])


def test_regression_low_utilisation_is_oversized_not_rewarded():
    """Review item 4.

    A technology running 4000 h cannot serve an 8000 h duty at the same rated
    capacity. Its CAPITAL scales up; its LCOH per kWh does not change, and its
    O&M does not scale because that figure is already per MWh delivered.
    """
    econ = switching_economics(MICROWAVE, GAS_BOILER, GERMANY, RATE, SUBSIDY)
    assert isclose(econ["capacity_scaling"], 2.0)

    expected_capex = MICROWAVE.capex * (1 - SUBSIDY) * 2.0 - GAS_BOILER.capex
    assert isclose(econ["incremental_capex"], expected_capex, rel_tol=1e-12)

    direct = levelised_cost(MICROWAVE, GERMANY.elec_effective, RATE, SUBSIDY)
    assert isclose(econ["lcoh"], direct, rel_tol=1e-12)


def test_regression_required_electricity_cut_is_in_minor_units():
    """Review item 3.

    The gap solver returned major currency units while labelling them as
    minor, understating the required cut by a factor of 100.
    """
    levers = interventions_to_close(1.0, HTHP, GAS_BOILER, RATE)
    assert isclose(levers["elec_price"], 2.20, rel_tol=1e-12)


def test_interventions_actually_close_the_gap():
    decomp = policy_decomposition(
        HTHP, GAS_BOILER, GERMANY, RATE, carbon_price=80, subsidy=SUBSIDY
    )
    gap = decomp["residual_gap"]
    if gap <= 0:
        return

    levers = interventions_to_close(gap, HTHP, GAS_BOILER, RATE)
    extra_carbon = levers["carbon_price"] * EMISSION_FACTOR_GAS / 1000 / GAS_BOILER.eff * 100
    assert isclose(extra_carbon, gap, rel_tol=1e-9)

    crf = capital_recovery_factor(RATE, HTHP.life)
    extra_grant = (HTHP.capex * levers["capex_grant_pp"] / 100 * crf) / HTHP.util * 100
    assert isclose(extra_grant, gap, rel_tol=1e-9)

    assert isclose(levers["elec_price"] / HTHP.eff, gap, rel_tol=1e-9)


def test_policy_decomposition_is_additive():
    decomp = policy_decomposition(
        HTHP, GAS_BOILER, GERMANY, RATE, carbon_price=80, subsidy=SUBSIDY
    )
    assert isclose(
        decomp["market_gap"] + decomp["policy_support"],
        decomp["residual_gap"],
        rel_tol=1e-12,
    )


def test_fx_scales_capital_not_fuel():
    base = levelised_cost(HTHP, GERMANY.elec_effective, RATE, SUBSIDY, fx=1.0)
    doubled = levelised_cost(HTHP, GERMANY.elec_effective, RATE, SUBSIDY, fx=2.0)
    fuel = GERMANY.elec_effective / HTHP.eff * 100
    assert isclose(doubled - fuel, 2 * (base - fuel), rel_tol=1e-12)


def test_abatement_cost_sign_follows_the_gap():
    econ = switching_economics(HTHP, GAS_BOILER, GERMANY, RATE, SUBSIDY)
    assert isclose(
        econ["abatement_cost"],
        econ["lcoh_gap"] / 100 / (EMISSION_FACTOR_GAS / GAS_BOILER.eff) * 1000,
        rel_tol=1e-12,
    )
    assert (econ["abatement_cost"] < 0) == (econ["lcoh_gap"] < 0)


def test_om_is_per_mwh_delivered_not_per_kw_year():
    """Review correction of 18 September.

    The project workbook gives O&M in EUR per MWh of heat delivered. Dividing
    that by annual hours, as the app once did, understates it by a factor of
    utilisation/1000 - eightfold at 8,000 hours.
    """
    lcoh = levelised_cost(GAS_BOILER, GERMANY.gas_effective, RATE)
    capital = GAS_BOILER.capex * capital_recovery_factor(RATE, GAS_BOILER.life) / GAS_BOILER.util * 100
    fuel = GERMANY.gas_effective / GAS_BOILER.eff * 100
    om_component = lcoh - capital - fuel
    assert isclose(om_component, GAS_BOILER.opex_per_mwh / 10, rel_tol=1e-12)

    wrong = GAS_BOILER.opex_per_mwh / GAS_BOILER.util * 100
    assert isclose(om_component / wrong, GAS_BOILER.util / 1000, rel_tol=1e-9)


def test_om_conventions_in_the_workbook_disagree():
    """Flagged, not fixed: the two source conventions differ by an order of
    magnitude for heat pumps. ECCO's per-MWh figure implies 0.4% of CAPEX a
    year; the LCOH input sheet states 2 to 3% for the same technology."""
    assert HTHP.fixed_om_share_of_capex() < 0.01
    assert GAS_BOILER.fixed_om_share_of_capex() > 0.10


def test_switching_economics_vectorises_consistently():
    """The array path must reproduce the scalar path element by element."""
    rates = np.array([0.05, 0.07, 0.09])
    sampled = HTHP.with_samples(capex=np.array([1100.0, 1200.0, 1300.0]))
    econ = switching_economics(sampled, GAS_BOILER, GERMANY, rates, SUBSIDY)

    for i, (r, cx) in enumerate(zip(rates, [1100.0, 1200.0, 1300.0])):
        one = switching_economics(
            HTHP.with_samples(capex=cx), GAS_BOILER, GERMANY, r, SUBSIDY
        )
        assert isclose(econ["npv"][i], one["npv"], rel_tol=1e-12)
        assert isclose(econ["lcoh"][i], one["lcoh"], rel_tol=1e-12)


if __name__ == "__main__":
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            passed += 1
            print(f"  ok  {name}")
    print(f"\n{passed} tests passed")
