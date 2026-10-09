"""Techno-economic core for the industrial heat electrification tool.

Pure numerics. No Streamlit import, so this module can be reused by
stochastic.py and exercised directly by tests. The app is a thin UI over it.

Every function here is array-safe: pass floats and you get floats back, pass
numpy arrays for the uncertain quantities and you get distributions back. The
Monte Carlo therefore runs the *same* formulas as the deterministic view
rather than a second implementation of them.

UNITS
-----
Prices          major currency units per kWh (e.g. 0.055 EUR/kWh)
CAPEX           major currency units per kW of rated capacity, via `fx`
OPEX            major currency units per MWh of heat DELIVERED (fixed O&M),
                following the ECCO dataset the technology figures come from.
                Converting this per-output figure as though it were per kW per
                year understates it by a factor of utilisation/1000.
LCOH            minor currency units per kWh of delivered heat (ct/kWh, p/kWh)
NPV             major currency units per kW of *baseline* capacity
Efficiency      COP for heat pumps / MVR, thermal fraction for combustion and
                resistive technologies. Fuel cost is price / efficiency either
                way.

CONVENTIONS
-----------
Everything is expressed per kW of the *baseline* (gas boiler) capacity, and
per the annual delivered heat that baseline provides. A technology with lower
annual utilisation must be oversized to deliver the same heat, so its CAPITAL
is scaled by baseline.util / tech.util. Without that scaling a low-utilisation
technology looks cheap because it is quietly delivering less heat. Fixed O&M
is not scaled, because it is already expressed per MWh of heat delivered and
both options deliver the same heat.

The NPV is incremental: the present value of *operating* savings against the
incremental capital cost of switching. Levelised costs already amortise
capital, so they must not be used as the savings term in an NPV that also
subtracts capital up front.

Prices are held as COMPONENTS, not totals. The commodity part of each fuel
price is the part that moves with the market; carbon pricing, grid fees and
levies are set by policy and regulation. Keeping them separate lets the
Monte Carlo apply volatility and the estimated gas-electricity dependence to
the commodity components alone, which is where both were measured.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import inf

import numpy as np

# kgCO2 per kWh of natural gas input (higher heating value basis).
EMISSION_FACTOR_GAS = 0.202


def _unwrap(x):
    """Return a plain float for 0-d results so scalar callers see scalars."""
    arr = np.asarray(x)
    return float(arr) if arr.ndim == 0 else arr


# --------------------------------------------------------------------------
# Financial primitives
# --------------------------------------------------------------------------

def capital_recovery_factor(rate, life: int):
    """Annualise a capital sum over `life` years at `rate`.

    `rate` may be a scalar or an array of sampled discount rates.
    """
    if life <= 0:
        raise ValueError("life must be positive")
    r = np.asarray(rate, dtype=float)
    growth = (1.0 + r) ** life
    with np.errstate(divide="ignore", invalid="ignore"):
        crf = np.where(r == 0, 1.0 / life, r * growth / (growth - 1.0))
    return _unwrap(crf)


def annuity_factor(rate, life: int):
    """Present value of 1 per year for `life` years. Inverse of the CRF."""
    return _unwrap(1.0 / np.asarray(capital_recovery_factor(rate, life)))


# --------------------------------------------------------------------------
# Data carriers
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Technology:
    name: str
    capex: float           # major currency units per kW thermal
    opex_per_mwh: float    # major currency units per MWh of heat DELIVERED
    eff: float             # COP or thermal fraction
    life: int         # years
    util: float       # full-load hours per year
    fuel: str         # "Gas" or "Elec"

    @property
    def is_electric(self) -> bool:
        return self.fuel != "Gas"

    def annual_om_per_kw(self):
        """Fixed O&M per kW of capacity per year, from the per-MWh figure."""
        return _unwrap(np.asarray(self.opex_per_mwh) * np.asarray(self.util) / 1000.0)

    def fixed_om_share_of_capex(self):
        """Annual fixed O&M as a fraction of CAPEX.

        Not a unit conversion but a cross-check. The project workbook holds
        O&M in two incompatible conventions: EUR per MWh of heat delivered
        (the ECCO dataset) and 2 to 3% of CAPEX per year (the LCOH input
        sheet). This expresses the first in terms of the second so the
        disagreement is visible.
        """
        return _unwrap(np.asarray(self.annual_om_per_kw()) / np.asarray(self.capex))

    def with_samples(self, **fields) -> "Technology":
        """Copy with sampled (array-valued) parameters substituted."""
        return replace(self, **fields)


@dataclass(frozen=True)
class Prices:
    """Fuel price components, in major currency units per kWh.

    gas_commodity      wholesale / contracted gas, per kWh of gas input
    carbon_cost        carbon price expressed per kWh of gas input
    elec_commodity     wholesale electricity, per kWh delivered
    elec_noncommodity  grid fees, levies and electricity tax
    elec_relief        policy relief applied to the commodity component
    """
    gas_commodity: float
    carbon_cost: float
    elec_commodity: float
    elec_noncommodity: float
    elec_relief: float = 0.0

    @property
    def gas_effective(self):
        return self.gas_commodity + self.carbon_cost

    @property
    def gas_base(self):
        return self.gas_commodity

    @property
    def elec_effective(self):
        return self.elec_commodity - self.elec_relief + self.elec_noncommodity

    @property
    def elec_raw(self):
        return self.elec_commodity + self.elec_noncommodity


# --------------------------------------------------------------------------
# Levelised cost
# --------------------------------------------------------------------------

def levelised_cost(tech: Technology, fuel_price, discount_rate, subsidy=0.0, fx=1.0):
    """LCOH in minor currency units per kWh of delivered heat.

    `subsidy` is a CAPEX grant as a fraction (0-1). It is applied only to
    electric technologies: a decarbonisation grant does not reduce the cost of
    the counterfactual gas boiler, and applying it to both makes the baseline
    used for NPV differ from the baseline shown in the charts.
    """
    grant = subsidy if tech.is_electric else 0.0
    capex_local = np.asarray(tech.capex) * fx * (1.0 - np.asarray(grant))
    crf = np.asarray(capital_recovery_factor(discount_rate, tech.life))
    capital = capex_local * crf / np.asarray(tech.util) * 100.0
    # O&M is per MWh of heat delivered, so it converts straight to minor
    # units per kWh. It is NOT divided by utilisation: doing that treats a
    # per-output figure as a per-capacity-per-year one and understates it by
    # a factor of utilisation/1000.
    om = np.asarray(tech.opex_per_mwh) * fx / 10.0
    variable = np.asarray(fuel_price) / np.asarray(tech.eff) * 100.0
    return _unwrap(capital + om + variable)


def fuel_price_for(tech: Technology, prices: Prices, market_only: bool = False):
    if tech.is_electric:
        return prices.elec_raw if market_only else prices.elec_effective
    return prices.gas_base if market_only else prices.gas_effective


# --------------------------------------------------------------------------
# Switching economics
# --------------------------------------------------------------------------

def switching_economics(
    tech: Technology,
    baseline: Technology,
    prices: Prices,
    discount_rate,
    subsidy=0.0,
    fx: float = 1.0,
) -> dict:
    """Incremental economics of replacing `baseline` with `tech`.

    Returns LCOH for both, the annual operating saving, the incremental
    capital cost, NPV, simple payback, and the implied cost of abatement.

    The NPV term is operating savings only. Capital appears once, up front,
    as `incremental_capex`. Using the LCOH difference as the savings term
    would amortise the same capital a second time and can flip the sign.
    """
    heat = np.asarray(baseline.util, dtype=float)

    tech_lcoh = np.asarray(
        levelised_cost(tech, fuel_price_for(tech, prices), discount_rate, subsidy, fx)
    )
    base_lcoh = np.asarray(
        levelised_cost(baseline, fuel_price_for(baseline, prices), discount_rate, subsidy, fx)
    )

    if tech.name == baseline.name:
        zero = np.zeros_like(tech_lcoh)
        nan = np.full_like(tech_lcoh, np.nan)
        return {
            "lcoh": _unwrap(tech_lcoh),
            "baseline_lcoh": _unwrap(base_lcoh),
            "lcoh_gap": _unwrap(zero),
            "annual_operating_saving": _unwrap(zero),
            "incremental_capex": _unwrap(zero),
            "npv": _unwrap(zero),
            "payback": _unwrap(nan),
            "co2_avoided_kg_per_kwh": _unwrap(zero),
            "abatement_cost": _unwrap(nan),
            "capacity_scaling": _unwrap(np.ones_like(tech_lcoh)),
        }

    # Oversize to deliver the same annual heat if utilisation differs.
    scale = heat / np.asarray(tech.util, dtype=float)

    grant = subsidy if tech.is_electric else 0.0
    capex_tech = np.asarray(tech.capex) * fx * (1.0 - np.asarray(grant)) * scale
    capex_base = np.asarray(baseline.capex) * fx
    incremental_capex = capex_tech - capex_base

    base_fuel = heat * np.asarray(prices.gas_effective) / np.asarray(baseline.eff)
    tech_fuel = heat * np.asarray(fuel_price_for(tech, prices)) / np.asarray(tech.eff)
    # O&M is per MWh of heat delivered and both options deliver the same heat,
    # so neither term carries the capacity scaling factor.
    base_opex = np.asarray(baseline.opex_per_mwh) * fx * heat / 1000.0
    tech_opex = np.asarray(tech.opex_per_mwh) * fx * heat / 1000.0

    annual_saving = (base_fuel + base_opex) - (tech_fuel + tech_opex)

    npv = annual_saving * np.asarray(annuity_factor(discount_rate, tech.life)) - incremental_capex

    with np.errstate(divide="ignore", invalid="ignore"):
        payback = np.where(annual_saving > 0, incremental_capex / annual_saving, inf)

    # Direct combustion emissions displaced. Grid emissions are NOT modelled,
    # so this is gross of the electricity supply's carbon intensity.
    lcoh_gap = tech_lcoh - base_lcoh
    if tech.is_electric:
        co2_per_kwh = EMISSION_FACTOR_GAS / np.asarray(baseline.eff)
        abatement = (lcoh_gap / 100.0) / co2_per_kwh * 1000.0
    else:
        co2_per_kwh = np.zeros_like(lcoh_gap)
        abatement = np.full_like(lcoh_gap, np.nan)

    return {
        "lcoh": _unwrap(tech_lcoh),
        "baseline_lcoh": _unwrap(base_lcoh),
        "lcoh_gap": _unwrap(lcoh_gap),
        "annual_operating_saving": _unwrap(annual_saving),
        "incremental_capex": _unwrap(incremental_capex),
        "npv": _unwrap(npv),
        "payback": _unwrap(payback),
        "co2_avoided_kg_per_kwh": _unwrap(co2_per_kwh),
        "abatement_cost": _unwrap(abatement),
        "capacity_scaling": _unwrap(scale),
    }


# --------------------------------------------------------------------------
# Policy decomposition (drives the gap solver)
# --------------------------------------------------------------------------

def policy_decomposition(
    tech: Technology,
    baseline: Technology,
    prices: Prices,
    discount_rate,
    carbon_price: float,
    subsidy: float,
    fx: float = 1.0,
) -> dict:
    """Split the parity gap into the market gap and each policy contribution.

    All terms in minor currency units per kWh of delivered heat, so that
    market_gap + policy_support == residual_gap by construction.
    """
    crf_tech = capital_recovery_factor(discount_rate, tech.life)

    market_gas = levelised_cost(baseline, prices.gas_base, discount_rate, subsidy=0.0, fx=fx)
    market_elec = levelised_cost(tech, prices.elec_raw, discount_rate, subsidy=0.0, fx=fx)

    carbon = carbon_price * EMISSION_FACTOR_GAS / 1000.0 / baseline.eff * 100.0
    grant = (tech.capex * fx * subsidy * crf_tech) / tech.util * 100.0
    relief = (prices.elec_raw - prices.elec_effective) / tech.eff * 100.0

    market_gap = market_elec - market_gas
    support = carbon + grant + relief

    return {
        "market_gas_lcoh": market_gas,
        "market_elec_lcoh": market_elec,
        "market_gap": market_gap,
        "carbon_price_effect": carbon,
        "capex_grant_effect": grant,
        "price_relief_effect": relief,
        "policy_support": -support,
        "residual_gap": market_gap - support,
        "adjusted_gas_lcoh": market_gas + carbon,
        "adjusted_elec_lcoh": market_elec - grant - relief,
    }


def interventions_to_close(gap, tech, baseline, discount_rate, fx: float = 1.0) -> dict:
    """Additional policy needed to close `gap` (minor units/kWh), one lever at
    a time. Each is the exact inverse of the corresponding term in
    `policy_decomposition`.

    The electricity figure is returned in minor units per kWh, matching the
    gap. Returning it in major units while labelling it as minor understates
    the required cut by a factor of 100.
    """
    if gap <= 0:
        return {"carbon_price": 0.0, "capex_grant_pp": 0.0, "elec_price": 0.0}

    crf_tech = capital_recovery_factor(discount_rate, tech.life)
    return {
        "carbon_price": gap * baseline.eff / 100.0 / (EMISSION_FACTOR_GAS / 1000.0),
        "capex_grant_pp": (gap * tech.util / 100.0) / (tech.capex * fx * crf_tech) * 100.0,
        "elec_price": gap * tech.eff,
    }


# --------------------------------------------------------------------------
# Table builder
# --------------------------------------------------------------------------

def build_results(countries: dict, technologies: dict, baseline: Technology, discount_rate) -> list:
    """Assemble one row per (country, technology).

    `countries` maps a name to a dict with keys: prices (Prices), subsidy
    (fraction), fx (float), symbol (str), unit (str).
    """
    rows = []
    for country, ctx in countries.items():
        for tech in technologies.values():
            econ = switching_economics(
                tech, baseline, ctx["prices"], discount_rate,
                subsidy=ctx["subsidy"], fx=ctx["fx"],
            )
            rows.append({
                "Country": country,
                "Symbol": ctx["symbol"],
                "Unit": ctx["unit"],
                "Technology": tech.name,
                "LCOH": econ["lcoh"],
                "Gap vs gas": econ["lcoh_gap"],
                "NPV": econ["npv"],
                "Payback": econ["payback"],
                "Incremental CAPEX": econ["incremental_capex"],
                "Annual saving": econ["annual_operating_saving"],
                "Abatement cost": econ["abatement_cost"],
            })
    return rows
