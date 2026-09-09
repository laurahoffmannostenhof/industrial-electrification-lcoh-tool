"""Regression tests for core.py.

Each test named `test_regression_*` pins a bug found in the 9 September 2026
review. Run with `python test_core.py` or `pytest test_core.py`.
"""

from math import isclose, isnan

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

GAS_BOILER = Technology("Gas Boiler", 55, 1.16, 0.95, 20, 8000, "Gas")
HTHP = Technology("High Temperature Heat Pump", 1200, 0.60, 2.20, 15, 8000, "Elec")
MICROWAVE = Technology("Microwave", 700, 1.0, 0.85, 12, 4000, "Elec")

# Germany, app defaults: 10.8 ct commodity, 5.856 ct non-commodity,
# Industriestrompreis relief of 2.9 ct, 5.5 ct gas, EUR 80/t carbon.
GERMANY = Prices(
    gas_effective=0.055 + 80 * EMISSION_FACTOR_GAS / 1000,
    elec_effective=0.108 - 0.029 + 0.05856,
    gas_base=0.055,
    elec_raw=0.108 + 0.05856,
)
RATE = 0.07
SUBSIDY = 0.30


def test_crf_and_annuity_are_inverses():
    for life in (5, 15, 20):
        crf = capital_recovery_factor(RATE, life)
        assert isclose(crf * annuity_factor(RATE, life), 1.0, rel_tol=1e-12)


def test_crf_zero_rate():
    assert isclose(capital_recovery_factor(0.0, 10), 0.1)


def test_regression_npv_does_not_double_count_capital():
    """Review item 1.

    The old code took the difference of two levelised costs, which already
    amortise capital, and then subtracted incremental capital again. At the
    German defaults that turned a positive NPV into a large negative one.
    """
    econ = switching_economics(HTHP, GAS_BOILER, GERMANY, RATE, SUBSIDY)

    # The old, wrong construction, reproduced for contrast.
    heat = GAS_BOILER.util
    old_savings = (econ["baseline_lcoh"] / 100 * heat) - (econ["lcoh"] / 100 * heat)
    old_npv = old_savings * annuity_factor(RATE, HTHP.life) - econ["incremental_capex"]

    assert econ["npv"] > 0, "heat pump should clear at these defaults"
    assert old_npv < 0, "the old construction gave the opposite sign"
    assert isclose(econ["npv"], 122.0, abs_tol=1.0)
    assert isclose(old_npv, -670.7, abs_tol=1.0)


def test_npv_equals_operating_savings_less_incremental_capex():
    econ = switching_economics(HTHP, GAS_BOILER, GERMANY, RATE, SUBSIDY)
    expected = (
        econ["annual_operating_saving"] * annuity_factor(RATE, HTHP.life)
        - econ["incremental_capex"]
    )
    assert isclose(econ["npv"], expected, rel_tol=1e-12)


def test_operating_saving_excludes_capital():
    """The saving term must be fuel plus fixed O&M only."""
    econ = switching_economics(HTHP, GAS_BOILER, GERMANY, RATE, SUBSIDY)
    heat = GAS_BOILER.util
    fuel = heat * (GERMANY.gas_effective / GAS_BOILER.eff
                   - GERMANY.elec_effective / HTHP.eff)
    om = GAS_BOILER.opex - HTHP.opex
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
    capacity. Its capital and fixed O&M scale up; its LCOH per kWh does not
    change.
    """
    econ = switching_economics(MICROWAVE, GAS_BOILER, GERMANY, RATE, SUBSIDY)
    assert isclose(econ["capacity_scaling"], 2.0)

    grant = 1 - SUBSIDY
    expected_capex = MICROWAVE.capex * grant * 2.0 - GAS_BOILER.capex
    assert isclose(econ["incremental_capex"], expected_capex, rel_tol=1e-12)

    # LCOH is per kWh delivered, so oversizing must leave it untouched.
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
    """Each lever, applied alone, should land the residual gap on zero."""
    decomp = policy_decomposition(
        HTHP, GAS_BOILER, GERMANY, RATE, carbon_price=80, subsidy=SUBSIDY
    )
    gap = decomp["residual_gap"]
    if gap <= 0:
        return  # already at parity under these defaults

    levers = interventions_to_close(gap, HTHP, GAS_BOILER, RATE)

    # Carbon price lever.
    extra_carbon = levers["carbon_price"] * EMISSION_FACTOR_GAS / 1000 / GAS_BOILER.eff * 100
    assert isclose(extra_carbon, gap, rel_tol=1e-9)

    # CAPEX grant lever.
    crf = capital_recovery_factor(RATE, HTHP.life)
    extra_grant = (HTHP.capex * levers["capex_grant_pp"] / 100 * crf) / HTHP.util * 100
    assert isclose(extra_grant, gap, rel_tol=1e-9)

    # Electricity price lever.
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
    # Cheaper than gas means a negative cost of abatement.
    assert (econ["abatement_cost"] < 0) == (econ["lcoh_gap"] < 0)


def test_om_share_flags_implausible_values():
    assert HTHP.fixed_om_share_of_capex() < 0.001  # 0.05%, the review's item 6
    assert GAS_BOILER.fixed_om_share_of_capex() > 0.02


if __name__ == "__main__":
    passed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            passed += 1
            print(f"  ok  {name}")
    print(f"\n{passed} tests passed")
