"""Sourced default parameters, with each number next to its citation.

The app reads its defaults from here and renders the Methodology and Sources
tabs from the same structures, so a figure and its provenance cannot drift
apart. Anything without a source carries `UNSOURCED` explicitly rather than
being left to look authoritative.

Every URL in SOURCES was checked to resolve on 18 September 2026.

UNITS
-----
Electricity and gas price components  minor currency units per kWh (ct, p)
Carbon price                          major currency units per tCO2
CAPEX                                 major currency units per kW thermal
Fixed O&M                             major currency units per MWh of heat
                                      delivered, following the convention of
                                      the ECCO dataset these figures come from
Efficiency                            COP, or thermal fraction
"""

from __future__ import annotations

from dataclasses import dataclass, field

UNSOURCED = "unsourced"


@dataclass(frozen=True)
class Source:
    title: str
    publisher: str
    url: str
    period: str
    note: str = ""


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

SOURCES: dict[str, Source] = {
    # --- Germany -----------------------------------------------------------
    "bdew_strom": Source(
        "Strompreisanalyse", "BDEW",
        "https://www.bdew.de/service/daten-und-grafiken/bdew-strompreisanalyse/",
        "August 2026",
        "17.2 ct/kWh total for the 160 MWh to 20 GWh medium-voltage band. BDEW "
        "merges procurement, retail margin and network charges into one block "
        "for industry, so no official commodity/network split exists.",
    ),
    "netztransparenz_offshore": Source(
        "Offshore-Netzumlage", "Übertragungsnetzbetreiber (netztransparenz.de)",
        "https://www.netztransparenz.de/de-de/Erneuerbare-Energien-und-Umlagen/Sonstige-Umlagen/Offshore-Netzumlage",
        "2026, published 24 October 2025",
        "Single rate for all non-privileged consumers. Reduction only on "
        "application under the EnFG for electricity-cost-intensive firms.",
    ),
    "netztransparenz_kwkg": Source(
        "KWKG-Umlage", "Übertragungsnetzbetreiber (netztransparenz.de)",
        "https://www.netztransparenz.de/de-de/Erneuerbare-Energien-und-Umlagen/Sonstige-Umlagen/KWKG-Umlage",
        "2026, published 24 October 2025",
        "Up 61% on 2025. Same EnFG reduction route as the Offshore levy.",
    ),
    "netztransparenz_19": Source(
        "Aufschlag für besondere Netznutzung (§19 StromNEV-Umlage)",
        "Übertragungsnetzbetreiber (netztransparenz.de)",
        "https://www.netztransparenz.de/de-de/Erneuerbare-Energien-und-Umlagen/Sonstige-Umlagen/Aufschlag-fuer-besondere-Netznutzung-19-StromNEV-Umlage",
        "2026, published 24 October 2025",
        "Carries the rate bands. 1.559 ct/kWh on the first 1 GWh per site per "
        "year, then 0.050 above it, automatically.",
    ),
    "kav": Source(
        "Konzessionsabgabenverordnung (KAV)", "Gesetze im Internet (Bundesamt für Justiz)",
        "https://www.gesetze-im-internet.de/kav/",
        "current consolidated text",
        "Sets the concession fee ceilings. Sondervertragskunden, which is what "
        "industrial sites are, pay the 0.11 ct/kWh rate rather than the much "
        "higher tariff-customer rates.",
    ),
    "amprion_19": Source(
        "Aufschlag für besondere Netznutzung seit 2012", "Amprion",
        "https://www.amprion.net/Strommarkt/Abgaben-und-Umlagen/Aufschlag-f%C3%BCr-besondere-Netznutzung/Aufschlag-f%C3%BCr-besondere-Netznutzung-seit-2012.html",
        "2012 to 2026",
        "Rate history, and the degression bands above 1 GWh per site per year.",
    ),
    "stromnev_19": Source(
        "§19 StromNEV", "Gesetze im Internet (Bundesamt für Justiz)",
        "https://www.gesetze-im-internet.de/stromnev/__19.html",
        "current consolidated text",
        "Individual network charges for atypical and intensive network use.",
    ),
    "stromstg_9b": Source(
        "§9b StromStG", "Gesetze im Internet (Bundesamt für Justiz)",
        "https://www.gesetze-im-internet.de/stromstg/__9b.html",
        "current consolidated text",
        "Electricity tax relief for manufacturing, permanent from 2026: "
        "2.00 of the 2.05 ct/kWh standard rate, leaving 0.05.",
    ),
    "enwg_24c": Source(
        "§24c EnWG", "Gesetze im Internet (Bundesamt für Justiz)",
        "https://www.gesetze-im-internet.de/enwg_2005/__24c.html",
        "in force 2026",
        "Federal subsidy to transmission network charges, about EUR 6.5 bn, "
        "which cut transmission charges by roughly 57% in 2026. This is NOT "
        "the Industriestrompreis, contrary to how earlier versions of this "
        "tool labelled it.",
    ),
    "bafa_ist": Source(
        "Industriestrompreis", "BAFA",
        "https://www.bafa.de/DE/Energie/Indurstriestrompreis/industriestrompreis.html",
        "billing years 2026 to 2028",
        "EU state-aid approval 16 April 2026, Billigkeitsrichtlinie 6 May 2026, "
        "under the Clean Industrial Deal State Aid Framework. An ex-post "
        "payment of (reference price minus target price) on 50% of eligible "
        "volume, not a price cap. Sectoral eligibility by relocation risk.",
    ),
    "bafa_eew": Source(
        "Bundesförderung für Energie- und Ressourceneffizienz, Modul 2",
        "BAFA",
        "https://www.bafa.de/DE/Energie/Energieeffizienz/Energieeffizienz_und_Prozesswaerme/Modul2_Prozesswaerme/modul2_prozesswaerme.html",
        "open to 31 December 2028",
        "Process heat from renewables, the route for industrial heat pumps. "
        "40% for large enterprises, 50 to 60% for SMEs, capped at EUR 20 m.",
    ),
    "dehst_nehs": Source(
        "nEHS Versteigerung ab 2026", "DEHSt",
        "https://www.dehst.de/SharedDocs/FAQ/DE/nehs/063-nEHS-versteigerung-ab-2026.html",
        "2026",
        "Auction within a statutory EUR 55 to 65 per tCO2 corridor. The 2026 "
        "auction cleared at the EUR 65 ceiling. EU ETS2 is postponed to 2028.",
    ),
    "eurostat_gas": Source(
        "Natural gas price statistics", "Eurostat",
        "https://ec.europa.eu/eurostat/statistics-explained/index.php?title=Natural_gas_price_statistics",
        "H2 2025, the latest published",
        "Non-household band I3 (2,778 to 27,778 MWh/yr): 7.13 ct/kWh delivered, "
        "excluding VAT but including the carbon and energy tax components.",
    ),
    "smard": Source(
        "Großhandelspreise (day-ahead)", "SMARD / Bundesnetzagentur",
        "https://www.smard.de/home",
        "Q2 2026",
        "Day-ahead average EUR 95.21/MWh. The Industriestrompreis reference "
        "price for 2026 is a one-year forward at EUR 87.44/MWh.",
    ),
    "bnetza_netze": Source(
        "Individuelle Netzentgelte für Industriekunden", "Bundesnetzagentur",
        "https://www.bundesnetzagentur.de/DE/Beschlusskammern/BK04/BK4_71_NetzE/BK4_71_Ind_NetzE_Strom/BK4_Ind_NetzEntg_Strom.html",
        "2026",
        "Band-load network charge reductions under §19(2) StromNEV require at "
        "least 7,000 utilisation hours AND at least 10 GWh/yr at the site.",
    ),
    # --- United Kingdom ----------------------------------------------------
    "desnz_qep": Source(
        "Gas and electricity prices in the non-domestic sector (QEP 3.4.1/3.4.2)",
        "DESNZ",
        "https://www.gov.uk/government/statistical-data-sets/gas-and-electricity-prices-in-the-non-domestic-sector",
        "2026 Q1, released 30 June 2026",
        "Medium band (2,000 to 19,999 MWh/yr): electricity 24.458 p/kWh and "
        "gas 4.123 p/kWh, both excluding CCL and VAT. Delivered totals only; "
        "DESNZ publishes no component breakdown.",
    ),
    "desnz_qep_collection": Source(
        "Quarterly Energy Prices", "DESNZ",
        "https://www.gov.uk/government/collections/quarterly-energy-prices",
        "quarterly",
        "Parent collection for the tables above.",
    ),
    "ccl_rates": Source(
        "Climate Change Levy rates", "HMRC",
        "https://www.gov.uk/guidance/climate-change-levy-rates",
        "from 1 April 2026",
        "0.801 p/kWh on both electricity and gas. Climate Change Agreement "
        "holders pay 8% of the main rate on electricity and 11% on gas.",
    ),
    "cca": Source(
        "Climate change agreements", "Environment Agency",
        "https://www.gov.uk/guidance/climate-change-agreements--2",
        "scheme runs to 31 March 2030",
        "Cuts the gas CCL by 89%, which reduces the levy-driven incentive to "
        "switch away from gas.",
    ),
    "bics": Source(
        "British Industrial Competitiveness Scheme: business guidance",
        "DESNZ / DBT",
        "https://www.gov.uk/government/publications/british-industrial-competitiveness-scheme-business-guidance",
        "exemptions from April 2027",
        "Exempts RO and FiT from April 2027 and the Capacity Market from "
        "October 2027, but not CfD. Site threshold 33 MWh/yr. Government "
        "estimate GBP 35 to 40/MWh. Applications 1 October to 30 November 2026.",
    ),
    "bics_collection": Source(
        "British Industrial Competitiveness Scheme", "DESNZ / DBT",
        "https://www.gov.uk/government/collections/british-industrial-competitiveness-scheme",
        "2026 onwards", "Parent collection.",
    ),
    "supercharger_ncc": Source(
        "British Industry Supercharger: Network Charging Compensation Scheme",
        "DBT",
        "https://www.gov.uk/government/consultations/british-industry-supercharger-network-charging-compensation-scheme",
        "90% compensation from 1 April 2026",
        "Raised from 60%. Combined Supercharger package worth GBP 65 to 87/MWh "
        "to roughly 550 certificated businesses.",
    ),
    "eii_exemption": Source(
        "CfD, Renewables Obligation and small-scale FiT: apply for an exemption",
        "DESNZ",
        "https://www.gov.uk/government/publications/renewables-obligation-and-small-scale-feed-in-tariffs-apply-for-compensation",
        "current",
        "The actual levy exemption for energy-intensive industries. Requires "
        "electricity costs of at least 20% of GVA plus sector tests, so a "
        "typical industrial heat site does not qualify.",
    ),
    "ietf": Source(
        "Industrial Energy Transformation Fund", "DESNZ",
        "https://www.gov.uk/government/collections/industrial-energy-transformation-fund",
        "closed",
        "A capital grant fund, never a levy exemption. Closed at the June 2025 "
        "Spending Review; the second Phase 3 window never ran and there is no "
        "successor. Historic Phase 3 rates were 50 to 65% of eligible costs "
        "for large enterprises on decarbonisation deployment.",
    ),
    "ofgem_ro": Source(
        "Renewables Obligation", "Ofgem",
        "https://www.ofgem.gov.uk/environmental-and-social-schemes/renewables-obligation-ro",
        "2026/27",
        "0.472 ROCs/MWh at a buy-out price of GBP 69.34.",
    ),
    "emrs": Source(
        "Key figures for payments", "EMR Settlement",
        "https://www.emrsettlement.co.uk/",
        "2026/27",
        "CfD interim levy rate, which moved by a factor of three within "
        "2026/27, plus the Capacity Market supplier charge and the Nuclear RAB "
        "levy.",
    ),
    "neso_tnuos": Source(
        "Transmission Network Use of System charges", "NESO",
        "https://www.neso.energy/industry-information/charging/transmission-network-use-system-tnuos-charges",
        "2026/27",
        "The demand residual is a fixed daily site charge by capacity band, "
        "not a p/kWh rate, and rose a volume-weighted 64% from April 2026.",
    ),
    "uk_ets_price": Source(
        "Determinations of the UK ETS carbon price", "DESNZ",
        "https://www.gov.uk/government/publications/determinations-of-the-uk-ets-carbon-price",
        "2026",
        "GBP 49.41/tCO2e for civil penalties in 2026, a backward-looking "
        "administrative price. The market price in September 2026 was closer "
        "to GBP 59.",
    ),
    "icap_ukets": Source(
        "UK Emissions Trading Scheme", "ICAP",
        "https://icapcarbonaction.com/en/ets/uk-emissions-trading-scheme-uk-ets",
        "2026",
        "Scope threshold is 20 MW total rated thermal input, so a site burning "
        "3 to 25 GWh/yr of gas is usually out of scope entirely.",
    ),
    "desnz_policy_impacts": Source(
        "Policy impacts on prices and bills", "DESNZ",
        "https://www.gov.uk/guidance/policy-impacts-on-prices-and-bills",
        "current",
        "Background on how policy costs reach bills. Does not currently give a "
        "component breakdown for industrial users.",
    ),
    # --- Technology and cross-cutting --------------------------------------
    "ecco": Source(
        "Electrification of industrial heat, technology dataset", "ECCO",
        "https://eccoclimate.org/",
        "March 2025",
        "CAPEX for 2021 and 2050, fixed O&M in EUR per MWh of heat delivered, "
        "lifetime, and COP by technology. The O&M unit matters: it is per MWh "
        "of output, not per kW of capacity per year.",
    ),
    "eurostat_elec": Source(
        "Electricity price statistics", "Eurostat",
        "https://ec.europa.eu/eurostat/statistics-explained/index.php?title=Electricity_price_statistics",
        "H2 2025",
        "Non-household electricity prices by consumption band.",
    ),
    "destatis": Source(
        "Erdgas- und Strom-Durchschnittspreise", "Destatis",
        "https://www.destatis.de/DE/Themen/Wirtschaft/Preise/Erdgas-Strom-DurchschnittsPreise/_inhalt.html",
        "H2 2025",
        "German non-household gas and electricity prices by band.",
    ),
    "ipcc": Source(
        "Emission factor data", "IPCC",
        "https://www.ipcc.ch/",
        "current",
        "Natural gas combustion emission factor, 0.202 kgCO2 per kWh of gas "
        "input. DEHSt uses 0.20088 for nEHS purposes.",
    ),
    "eia_aeo": Source(
        "Annual Energy Outlook", "EIA",
        "https://www.eia.gov/outlooks/aeo/",
        "current",
        "US gas price benchmarks. Not used for the US defaults in this tool, "
        "which remain unsourced.",
    ),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Figure:
    value: float
    source: str = UNSOURCED
    note: str = ""

    @property
    def is_sourced(self) -> bool:
        return self.source != UNSOURCED


@dataclass(frozen=True)
class Levy:
    name: str
    value: float
    source: str = UNSOURCED
    note: str = ""


@dataclass(frozen=True)
class Relief:
    """A policy lever the user can switch on.

    kind:
      "reference_topup" - pays (reference - target) on `coverage` of volume.
                          The German Industriestrompreis.
      "exemption"       - removes named levies, and `network_share` of the
                          network charge. The UK EII Supercharger.
      "flat"            - a flat reduction in minor units per kWh, used where
                          the government publishes an estimated value rather
                          than a component rule.
    """
    id: str
    label: str
    kind: str
    source: str
    default_on: bool = False
    params: dict = field(default_factory=dict)
    note: str = ""
    caveat: str = ""


# ---------------------------------------------------------------------------
# Jurisdictions
# ---------------------------------------------------------------------------

COUNTRIES: dict[str, dict] = {
    "Germany": {
        "currency": "€",
        "unit": "ct/kWh",
        "fx": Figure(1.0, UNSOURCED, "CAPEX is quoted in EUR from the ECCO dataset, so no conversion is applied."),
        "sourced": True,
        "band": "medium voltage, 2,000 to 20,000 MWh/yr",
        "elec_commodity": Figure(
            9.50, "smard",
            "Day-ahead average for Q2 2026. The Industriestrompreis reference "
            "price for the same year is 8.744 ct/kWh, a one-year forward.",
        ),
        "elec_network": Figure(
            6.10, "bdew_strom",
            "Derived as a residual: BDEW's 17.2 ct/kWh total for this band, "
            "less the commodity price above and the itemised levies below. It "
            "therefore includes retail margin as well as transmission and "
            "distribution. Transmission alone fell to about 2.86 ct/kWh in "
            "2026 after the §24c EnWG subsidy.",
        ),
        "elec_levies": [
            Levy("Offshore-Netzumlage", 0.941, "netztransparenz_offshore"),
            Levy("KWKG-Umlage", 0.446, "netztransparenz_kwkg"),
            Levy("Aufschlag für besondere Netznutzung (§19 StromNEV)", 0.050, "netztransparenz_19",
                 "1.559 ct/kWh applies to the first 1 GWh per site per year only. "
                 "Above that the rate drops to 0.050 automatically, with no "
                 "application and no eligibility test. For this consumption band "
                 "almost all volume pays 0.050."),
            Levy("Konzessionsabgabe", 0.110, "kav",
                 "Sondervertragskunden rate, which is what industrial sites pay."),
            Levy("Stromsteuer, manufacturing rate", 0.050, "stromstg_9b",
                 "2.05 ct/kWh standard, less the 2.00 ct/kWh §9b relief, which "
                 "became permanent in 2026."),
        ],
        "gas_commodity": Figure(
            5.82, "eurostat_gas",
            "Eurostat band I3 delivered price of 7.13 ct/kWh for H2 2025, less "
            "the 1.31 ct/kWh carbon component at EUR 65/tCO2, to avoid counting "
            "carbon twice when the carbon price is added below.",
        ),
        "carbon_price": Figure(
            65.0, "dehst_nehs",
            "The 2026 nEHS auction cleared at the EUR 65 ceiling of the "
            "statutory EUR 55 to 65 corridor. EU ETS2 starts in 2028.",
        ),
        "capex_grant": Figure(
            40.0, "bafa_eew",
            "BAFA EEW Modul 2 for a large enterprise. SMEs get 50 to 60%.",
        ),
        "reliefs": [
            Relief(
                "industriestrompreis",
                "Industriestrompreis (BAFA, billing years 2026 to 2028)",
                "reference_topup", "bafa_ist", False,
                {"reference": 8.744, "target": 5.0, "coverage": 0.5},
                "Pays (reference price minus EUR 50/MWh target) on 50% of "
                "eligible volume. At the 2026 reference price of 8.744 ct/kWh "
                "that is 1.87 ct/kWh off the average price.",
                "Off by default. Eligibility is sectoral, restricted to "
                "relocation-risk sectors, so a typical industrial heat user "
                "does not qualify. The scheme also expires after billing year "
                "2028, carries a reinvestment obligation, and cannot be "
                "combined with Strompreiskompensation.",
            ),
        ],
    },
    "UK": {
        "currency": "£",
        "unit": "p/kWh",
        "fx": Figure(0.86, UNSOURCED,
                     "Indicative GBP per EUR, applied to the EUR-denominated "
                     "CAPEX figures. Set to 1.00 to disable conversion."),
        "sourced": True,
        "band": "DESNZ Medium band, 2,000 to 19,999 MWh/yr",
        "elec_commodity": Figure(
            14.16, "desnz_qep",
            "Derived as a residual from the DESNZ delivered price of 24.458 "
            "p/kWh less the network and policy components below. DESNZ "
            "publishes no official split, so this is a reconstruction.",
        ),
        "elec_network": Figure(
            4.40, "neso_tnuos",
            "TNUoS, DUoS, BSUoS and AAHEDC combined. Indicative: the TNUoS "
            "residual is a fixed daily site charge rather than a p/kWh rate, "
            "and DUoS is specific to the distribution network operator.",
        ),
        "elec_levies": [
            Levy("Renewables Obligation", 3.27, "ofgem_ro",
                 "0.472 ROCs/MWh at a GBP 69.34 buy-out price. Actual "
                 "pass-through is nearer 3.4 to 3.6 once recycling is included."),
            Levy("Contracts for Difference", 0.63, "emrs",
                 "Time-weighted across 2026/27. The interim levy rate moved "
                 "from GBP 10.26 to GBP 2.07/MWh within the year, so a single "
                 "value here is a poor approximation."),
            Levy("Feed-in Tariff", 0.70, "emrs",
                 "Derived from total scheme payments divided by supplied "
                 "volume. Not published as a unit rate."),
            Levy("Capacity Market", 0.90, "emrs",
                 "Levied only on 16:00 to 19:00 working-day demand from "
                 "November to February. This value assumes a flat load; a "
                 "daytime-only process pays considerably more."),
            Levy("Nuclear RAB (Sizewell C)", 0.43, "emrs",
                 "A newer supplier obligation, now comparable in size to the "
                 "CfD levy."),
            Levy("Climate Change Levy", 0.801, "ccl_rates",
                 "From 1 April 2026, the same rate on electricity and gas. "
                 "Climate Change Agreement holders pay 8% of this on "
                 "electricity."),
        ],
        "gas_commodity": Figure(
            4.123, "desnz_qep",
            "DESNZ Medium band, 2026 Q1, excluding CCL and VAT. Earlier "
            "versions of this tool used 6.5 p/kWh, overstating it by 58%.",
        ),
        "carbon_price": Figure(
            0.0, "icap_ukets",
            "Zero by default. The UK ETS stationary threshold is 20 MW total "
            "rated thermal input, and a site burning 3 to 25 GWh/yr of gas "
            "rarely reaches it. For a site in scope, use GBP 49.41 (the "
            "official 2026 administrative price) or about GBP 59 (market).",
        ),
        "capex_grant": Figure(
            0.0, "ietf",
            "Zero because no UK capital grant scheme for industrial heat "
            "electrification is currently open. The IETF closed at the June "
            "2025 Spending Review with no successor. Its historic Phase 3 "
            "rate of 50 to 65% can be entered as a counterfactual.",
        ),
        "reliefs": [
            Relief(
                "eii_supercharger",
                "EII Exemption Scheme (British Industry Supercharger)",
                "exemption", "eii_exemption", False,
                {"levies": ["Renewables Obligation", "Contracts for Difference",
                            "Feed-in Tariff", "Capacity Market"],
                 "network_share": 0.90},
                "Removes the four named levies in full and compensates 90% of "
                "network charges, the latter raised from 60% in April 2026. "
                "Worth GBP 65 to 87/MWh on the government's own figure.",
                "Off by default. Requires electricity costs of at least 20% of "
                "GVA plus sector trade and electricity intensity tests, so a "
                "typical industrial heat site of this size will not qualify.",
            ),
            Relief(
                "bics",
                "British Industrial Competitiveness Scheme (from April 2027)",
                "flat", "bics", False,
                {"value": 3.75},
                "The government's own estimate of GBP 35 to 40/MWh. Implemented "
                "as a flat value rather than a component sum because the "
                "published estimate and the sum of the individual levy rates "
                "do not reconcile.",
                "Off by default, and it does not begin until April 2027. Site "
                "threshold is 33 MWh/yr, far below the Supercharger's, so this "
                "is the more likely route for a typical heat user. Does not "
                "cover CfD. Applications ran 1 October to 30 November 2026.",
            ),
        ],
    },
    "USA - California": {
        "currency": "$", "unit": "ct/kWh", "fx": Figure(1.08, UNSOURCED, "Indicative USD per EUR."),
        "sourced": False,
        "band": "not specified",
        "elec_commodity": Figure(15.60, UNSOURCED),
        "elec_network": Figure(10.50, UNSOURCED),
        "elec_levies": [],
        "gas_commodity": Figure(4.80, UNSOURCED),
        "carbon_price": Figure(10.0, UNSOURCED),
        "capex_grant": Figure(40.0, UNSOURCED),
        "reliefs": [
            Relief("sgip", "SGIP / load-shifting credit", "flat", UNSOURCED, False,
                   {"value": 3.5}, "", "Magnitude assumed, not sourced."),
        ],
    },
    "USA - Texas": {
        "currency": "$", "unit": "ct/kWh", "fx": Figure(1.08, UNSOURCED, "Indicative USD per EUR."),
        "sourced": False,
        "band": "not specified",
        "elec_commodity": Figure(5.40, UNSOURCED),
        "elec_network": Figure(3.80, UNSOURCED),
        "elec_levies": [],
        "gas_commodity": Figure(2.20, UNSOURCED),
        "carbon_price": Figure(0.0, UNSOURCED),
        "capex_grant": Figure(0.0, UNSOURCED),
        "reliefs": [
            Relief("ercot_4cp", "ERCOT 4CP peak avoidance", "exemption", UNSOURCED, False,
                   {"levies": [], "network_share": 0.75}, "",
                   "Mechanism is real, the 75% is assumed."),
        ],
    },
}


# ---------------------------------------------------------------------------
# Technologies
# ---------------------------------------------------------------------------
# CAPEX in EUR/kW thermal, O&M in EUR/MWh of heat delivered, following ECCO.
# Each entry pairs a CAPEX with the efficiency from the SAME source row, which
# earlier versions did not: CAPEX 1200 (a medium-heat cost) was paired with
# COP 2.20 (a high-heat machine), flattering capital and penalising efficiency
# at the same time.

BASELINE = {
    "name": "Gas Boiler",
    "capex": Figure(61.7, "ecco", "Steam boiler. The hot-water variant is 50.1."),
    "opex_per_mwh": Figure(1.16, "ecco"),
    "eff": Figure(0.95, "ecco", "Some UK sources give 0.80 to 0.90 for older plant."),
    "life": Figure(25, "ecco"),
    "util": Figure(8000, UNSOURCED, "Assumed continuous process operation."),
    "fuel": "Gas",
}

TECHNOLOGIES = {
    "Electric Boiler": {
        "capex": Figure(156.2, "ecco", "Steam. Hot water is 137."),
        "opex_per_mwh": Figure(0.58, "ecco"),
        "eff": Figure(0.99, "ecco"),
        "life": Figure(25, "ecco"),
        "util": Figure(8000, UNSOURCED),
        "fuel": "Elec",
        "temperature": "steam, to about 200 °C",
    },
    "Heat Pump (medium heat, to 150 °C)": {
        "capex": Figure(1220, "ecco"),
        "opex_per_mwh": Figure(0.554, "ecco"),
        "eff": Figure(4.0, "ecco", "The wider EU range for 100 to 200 °C is COP 2.5 to 4.0."),
        "life": Figure(20, "ecco"),
        "util": Figure(8000, UNSOURCED),
        "fuel": "Elec",
        "temperature": "100 to 150 °C",
    },
    "Booster Heat Pump (steam, above 150 °C)": {
        "capex": Figure(1888, "ecco"),
        "opex_per_mwh": Figure(0.579, "ecco"),
        "eff": Figure(2.1, "ecco", "The wider EU range above 200 °C is COP 1.7 to 2.7."),
        "life": Figure(20, "ecco"),
        "util": Figure(8000, UNSOURCED),
        "fuel": "Elec",
        "temperature": "above 150 °C",
    },
    "Mechanical Vapour Recompression": {
        "capex": Figure(1400, UNSOURCED, "Midpoint of a 1,000 to 1,875 USD/kWth range in the project workbook."),
        "opex_per_mwh": Figure(0.60, UNSOURCED, "Assumed by analogy with heat pumps. No source."),
        "eff": Figure(5.0, UNSOURCED, "Sources give COP of at least 5, with IEA/EATSP at 8.1. This is the conservative end."),
        "life": Figure(20, UNSOURCED),
        "util": Figure(8000, UNSOURCED),
        "fuel": "Elec",
        "temperature": "steam recompression",
    },
    "Microwave": {
        "capex": Figure(833, "ecco"),
        "opex_per_mwh": Figure(10.0, "ecco", "Ten times the heat pump figure, and correct: ECCO gives 10 EUR/MWh for the electric oven, microwave and CHP alike."),
        "eff": Figure(0.90, "ecco"),
        "life": Figure(30, "ecco"),
        "util": Figure(4000, UNSOURCED, "Assumed batch operation."),
        "fuel": "Elec",
        "temperature": "process-specific",
    },
}

EMISSION_FACTOR_SOURCE = "ipcc"


# ---------------------------------------------------------------------------
# Convenience
# ---------------------------------------------------------------------------

def levy_total(country: str) -> float:
    return sum(l.value for l in COUNTRIES[country]["elec_levies"])


def market_delivered_elec(country: str) -> float:
    c = COUNTRIES[country]
    return c["elec_commodity"].value + c["elec_network"].value + levy_total(country)


def unsourced_figures() -> list[tuple[str, str]]:
    """Every default that carries no citation, for the Methodology tab."""
    out = []
    for cname, c in COUNTRIES.items():
        for key in ("elec_commodity", "elec_network", "gas_commodity", "carbon_price", "capex_grant", "fx"):
            if not c[key].is_sourced:
                out.append((cname, key))
        for lv in c["elec_levies"]:
            if lv.source == UNSOURCED:
                out.append((cname, lv.name))
    for tname, t in TECHNOLOGIES.items():
        for key in ("capex", "opex_per_mwh", "eff", "life", "util"):
            if not t[key].is_sourced:
                out.append((tname, key))
    for key in ("capex", "opex_per_mwh", "eff", "life", "util"):
        if not BASELINE[key].is_sourced:
            out.append((BASELINE["name"], key))
    return out
