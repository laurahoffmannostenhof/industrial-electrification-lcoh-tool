"""Techno-economic core for the industrial heat electrification tool.

Pure numerics. No Streamlit import, so this module can be reused by
stochastic.py and exercised directly by tests. The app is a thin UI over it.

UNITS
-----
Prices          major currency units per kWh (e.g. 0.055 EUR/kWh)
CAPEX           USD per kW of rated capacity, converted with `fx`
OPEX            USD per kW per year (fixed O&M), converted with `fx`
LCOH            minor currency units per kWh of delivered heat (ct/kWh, p/kWh)
NPV             major currency units per kW of *baseline* capacity
Efficiency      COP for heat pumps / MVR, thermal fraction for combustion and
                resistive technologies. Fuel cost is price / efficiency either
                way.

CONVENTIONS
-----------
Everything is expressed per kW of the *baseline* (gas boiler) capacity, and
per the annual delivered heat that baseline provides. A technology with lower
annual utilisation must be oversized to deliver the same heat, so its capital
and fixed O&M are scaled by baseline.util / tech.util. Without that scaling a
low-utilisation technology looks cheap because it is quietly delivering less
heat.

The NPV is incremental: the present value of *operating* savings against the
incremental capital cost of switching. Levelised costs already amortise
capital, so they must not be used as the savings term in an NPV that also
subtracts capital up front.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import inf, isfinite, nan

# kgCO2 per kWh of natural gas input (higher heating value basis).
EMISSION_FACTOR_GAS = 0.202


# --------------------------------------------------------------------------
# Financial primitives
# --------------------------------------------------------------------------

def capital_recovery_factor(rate: float, life: int) -> float:
    """Annualise a capital sum over `life` years at `rate`."""
    if life <= 0:
        raise ValueError("life must be positive")
    if rate == 0:
        return 1.0 / life
    return (rate * (1 + rate) ** life) / ((1 + rate) ** life - 1)


def annuity_factor(rate: float, life: int) -> float:
    """Present value of 1 per year for `life` years. Inverse of the CRF."""
    return 1.0 / capital_recovery_factor(rate, life)


# --------------------------------------------------------------------------
# Data carriers
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Technology:
    name: str
    capex: float      # USD/kW
    opex: float       # USD/kW/yr, fixed O&M
    eff: float        # COP or thermal fraction
    life: int         # years
    util: float       # full-load hours per year
    fuel: str         # "Gas" or "Elec"

    @property
    def is_electric(self) -> bool:
        return self.fuel != "Gas"

    def fixed_om_share_of_capex(self) -> float:
        """Fixed O&M as a fraction of CAPEX per year.

        Industrial plant typically sits at 2-4%. Values far below that mean
        O&M is effectively absent for capital-intensive options, which is
        where it matters most. Surfaced in the UI as a data-quality flag.
        """
        return self.opex / self.capex if self.capex else nan


@dataclass(frozen=True)
class Prices:
    """All in major currency units per kWh."""
    gas_effective: float   # incl. carbon price
    elec_effective: float  # incl. non-commodity, net of relief
    gas_base: float        # excl. carbon price
    elec_raw: float        # incl. non-commodity, gross of relief


# --------------------------------------------------------------------------
# Levelised cost
# --------------------------------------------------------------------------

def levelised_cost(
    tech: Technology,
    fuel_price: float,
    discount_rate: float,
    subsidy: float = 0.0,
    fx: float = 1.0,
) -> float:
    """LCOH in minor currency units per kWh of delivered heat.

    `subsidy` is a CAPEX grant as a fraction (0-1). It is applied only to
    electric technologies: a decarbonisation grant does not reduce the cost of
    the counterfactual gas boiler, and applying it to both makes the baseline
    used for NPV differ from the baseline shown in the charts.
    """
    grant = subsidy if tech.is_electric else 0.0
    capex_local = tech.capex * fx * (1.0 - grant)
    opex_local = tech.opex * fx
    crf = capital_recovery_factor(discount_rate, tech.life)
    fixed = (capex_local * crf + opex_local) / tech.util * 100.0
    variable = fuel_price / tech.eff * 100.0
    return fixed + variable


def fuel_price_for(tech: Technology, prices: Prices, market_only: bool = False) -> float:
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
    discount_rate: float,
    subsidy: float = 0.0,
    fx: float = 1.0,
) -> dict:
    """Incremental economics of replacing `baseline` with `tech`.

    Returns LCOH for both, the annual operating saving, the incremental
    capital cost, NPV, simple payback, and the implied cost of abatement.

    The NPV term is operating savings only. Capital appears once, up front,
    as `incremental_capex`. Using the LCOH difference as the savings term
    would amortise the same capital a second time and can flip the sign.
    """
    heat = baseline.util  # kWh delivered per year, per kW of baseline capacity

    tech_lcoh = levelised_cost(
        tech, fuel_price_for(tech, prices), discount_rate, subsidy, fx
    )
    base_lcoh = levelised_cost(
        baseline, fuel_price_for(baseline, prices), discount_rate, subsidy, fx
    )

    if tech.name == baseline.name:
        return {
            "lcoh": tech_lcoh,
            "baseline_lcoh": base_lcoh,
            "lcoh_gap": 0.0,
            "annual_operating_saving": 0.0,
            "incremental_capex": 0.0,
            "npv": 0.0,
            "payback": nan,
            "co2_avoided_kg_per_kwh": 0.0,
            "abatement_cost": nan,
            "capacity_scaling": 1.0,
        }

    # Oversize to deliver the same annual heat if utilisation differs.
    scale = heat / tech.util

    grant = subsidy if tech.is_electric else 0.0
    capex_tech = tech.capex * fx * (1.0 - grant) * scale
    capex_base = baseline.capex * fx
    incremental_capex = capex_tech - capex_base

    base_fuel = heat * prices.gas_effective / baseline.eff
    base_opex = baseline.opex * fx
    tech_fuel = heat * fuel_price_for(tech, prices) / tech.eff
    tech_opex = tech.opex * fx * scale

    annual_saving = (base_fuel + base_opex) - (tech_fuel + tech_opex)

    npv = annual_saving * annuity_factor(discount_rate, tech.life) - incremental_capex
    payback = incremental_capex / annual_saving if annual_saving > 0 else inf

    # Direct combustion emissions displaced. Grid emissions are NOT modelled,
    # so this is gross of the electricity supply's carbon intensity.
    co2_per_kwh = EMISSION_FACTOR_GAS / baseline.eff if tech.is_electric else 0.0
    lcoh_gap = tech_lcoh - base_lcoh
    if co2_per_kwh > 0:
        # minor units/kWh -> major/kWh -> major/kg -> major/tonne
        abatement = (lcoh_gap / 100.0) / co2_per_kwh * 1000.0
    else:
        abatement = nan

    return {
        "lcoh": tech_lcoh,
        "baseline_lcoh": base_lcoh,
        "lcoh_gap": lcoh_gap,
        "annual_operating_saving": annual_saving,
        "incremental_capex": incremental_capex,
        "npv": npv,
        "payback": payback,
        "co2_avoided_kg_per_kwh": co2_per_kwh,
        "abatement_cost": abatement,
        "capacity_scaling": scale,
    }


# --------------------------------------------------------------------------
# Policy decomposition (drives the gap solver)
# --------------------------------------------------------------------------

def policy_decomposition(
    tech: Technology,
    baseline: Technology,
    prices: Prices,
    discount_rate: float,
    carbon_price: float,
    subsidy: float,
    fx: float = 1.0,
) -> dict:
    """Split the parity gap into the market gap and each policy contribution.

    All terms in minor currency units per kWh of delivered heat, so that
    market_gap + policy_support == residual_gap by construction.
    """
    crf_tech = capital_recovery_factor(discount_rate, tech.life)

    market_gas = levelised_cost(
        baseline, prices.gas_base, discount_rate, subsidy=0.0, fx=fx
    )
    market_elec = levelised_cost(
        tech, prices.elec_raw, discount_rate, subsidy=0.0, fx=fx
    )

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


def interventions_to_close(
    gap: float,
    tech: Technology,
    baseline: Technology,
    discount_rate: float,
    fx: float = 1.0,
) -> dict:
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
    carbon_price = gap * baseline.eff / 100.0 / (EMISSION_FACTOR_GAS / 1000.0)
    grant_pp = (gap * tech.util / 100.0) / (tech.capex * fx * crf_tech) * 100.0
    elec_cut = gap * tech.eff  # minor units/kWh

    return {
        "carbon_price": carbon_price,
        "capex_grant_pp": grant_pp,
        "elec_price": elec_cut,
    }


# --------------------------------------------------------------------------
# Table builder
# --------------------------------------------------------------------------

def build_results(
    countries: dict,
    technologies: dict,
    baseline: Technology,
    discount_rate: float,
) -> list:
    """Assemble one row per (country, technology).

    `countries` maps a name to a dict with keys: prices (Prices), subsidy
    (fraction), fx (float), symbol (str), unit (str).
    """
    rows = []
    for country, ctx in countries.items():
        for tech in technologies.values():
            econ = switching_economics(
                tech,
                baseline,
                ctx["prices"],
                discount_rate,
                subsidy=ctx["subsidy"],
                fx=ctx["fx"],
            )
            rows.append(
                {
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
                }
            )
    return rows
