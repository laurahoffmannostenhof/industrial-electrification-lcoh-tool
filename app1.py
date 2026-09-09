import io

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import streamlit as st

import core
from core import Prices, Technology

# --- 1. CONFIG & STYLE ---
st.set_page_config(page_title="Industrial Heat Strategy Tool", layout="wide")
plt.style.use("seaborn-v0_8-whitegrid")

# --- 2. DATA DEFAULTS ---
# `fx` is local currency units per USD, applied to CAPEX and fixed O&M, which
# are quoted in USD. Left at 1.0 by default: the tool has never converted, and
# setting a real rate changes published numbers, so that is a deliberate act.
COUNTRY_DEFAULTS = {
    "Germany":          {"gas": 5.5, "elec": 18, "tax": 80, "subsidy": 30, "currency": "€", "unit": "ct/kWh", "fx": 1.0},
    "UK":               {"gas": 6.5, "elec": 22, "tax": 50, "subsidy": 20, "currency": "£", "unit": "p/kWh",  "fx": 1.0},
    "USA - California": {"gas": 4.8, "elec": 26, "tax": 10, "subsidy": 40, "currency": "$", "unit": "ct/kWh", "fx": 1.0},
    "USA - Texas":      {"gas": 2.2, "elec": 9,  "tax": 0,  "subsidy": 0,  "currency": "$", "unit": "ct/kWh", "fx": 1.0},
}

# The gas boiler is the counterfactual, not one option among many. It is
# configured separately and always present, so nothing can silently fall back
# to a hardcoded baseline when it is deselected.
BASELINE_DEFAULT = {"capex": 55, "opex": 1.16, "eff": 0.95, "life": 20, "util": 8000, "fuel": "Gas"}

TECH_DEFAULTS = {
    "Electric Boiler":               {"capex": 120,  "opex": 0.58, "eff": 0.99, "life": 15, "util": 8000, "fuel": "Elec"},
    "High Temperature Heat Pump":    {"capex": 1200, "opex": 0.60, "eff": 2.20, "life": 15, "util": 8000, "fuel": "Elec"},
    "Mechanical Vapor Reconversion": {"capex": 1500, "opex": 0.40, "eff": 4.50, "life": 20, "util": 8000, "fuel": "Elec"},
    "Low Temperature Heat Pump":     {"capex": 500,  "opex": 0.50, "eff": 4.00, "life": 15, "util": 7500, "fuel": "Elec"},
    "Microwave":                     {"capex": 700,  "opex": 10.0, "eff": 0.85, "life": 12, "util": 4000, "fuel": "Elec"},
}

GERMANY_NON_COMMODITY = {"grid_fee": 2.860, "offshore": 0.941, "kwkg": 0.446, "stromnev": 1.559, "tax": 0.050}
GERMANY_LEVIES = GERMANY_NON_COMMODITY["offshore"] + GERMANY_NON_COMMODITY["kwkg"] + GERMANY_NON_COMMODITY["stromnev"]

# Fixed O&M below this share of CAPEX per year is flagged. Industrial plant is
# normally 2-4%; anything near zero means O&M is effectively absent for the
# capital-intensive options, which is where it matters most.
OM_SHARE_FLOOR = 0.015

# --- 3. SIDEBAR ---
with st.sidebar:
    st.header("Scope & Global Financials")
    selected_countries = st.multiselect(
        "Select Jurisdictions", options=list(COUNTRY_DEFAULTS.keys()), default=["Germany", "USA - Texas"]
    )
    selected_techs = st.multiselect(
        "Select Electrification Options",
        options=list(TECH_DEFAULTS.keys()),
        default=["Electric Boiler", "High Temperature Heat Pump"],
    )
    discount_rate = st.slider("WACC / Discount Rate (%)", 1, 20, 7) / 100

    st.divider()
    st.subheader("Gas Boiler Baseline")
    st.caption("The counterfactual. Always applied, whatever is selected above.")
    b_cap = st.number_input("CAPEX (USD/kW)", 0, 5000, BASELINE_DEFAULT["capex"], key="b_cap")
    b_opex = st.number_input("Fixed O&M (USD/kW/yr)", 0.0, 100.0, BASELINE_DEFAULT["opex"], step=0.1, key="b_opex")
    b_eff = st.number_input("Thermal efficiency", 0.1, 1.2, BASELINE_DEFAULT["eff"], step=0.01, key="b_eff")
    b_life = st.number_input("Life (years)", 1, 50, BASELINE_DEFAULT["life"], key="b_life")
    b_util = st.number_input("Annual hours", 1, 8760, BASELINE_DEFAULT["util"], key="b_util")

baseline = Technology("Gas Boiler", b_cap, b_opex, b_eff, int(b_life), b_util, "Gas")

# --- 4. CATEGORICAL INPUT DASHBOARD ---
st.title("Techno-Economic Platform for Evaluating Thermal Decarbonization and Switching Price Dynamics")
st.markdown(
    "Assess industrial heat electrification across Germany, UK, California, and Texas. "
    "By Laura Hoffmann-Ostenhof. Work in Progress. Feedback welcome!"
)

if not selected_countries:
    st.info("Select at least one jurisdiction in the sidebar.")
    st.stop()

country_ctx = {}

for country in selected_countries:
    cfg = COUNTRY_DEFAULTS[country]
    sym, unit = cfg["currency"], cfg["unit"]

    with st.container(border=True):
        st.subheader(f"{country} Policy Framework")

        # CATEGORY A: ELECTRICITY & BRIDGE PRICE
        st.markdown("#### Electricity & Grid Policy")
        c1, c2 = st.columns([1, 1])
        with c1:
            comm_p = st.number_input(
                f"Wholesale/Commodity ({unit})", 0.5, 40.0, float(cfg["elec"]) * 0.6,
                format="%.1f", key=f"comm_{country}",
            ) / 100

            with st.expander("Advanced Bill & Policy Relief Settings"):
                if country == "Germany":
                    grid = st.number_input("Grid Fees (ct/kWh)", 0.0, 10.0, GERMANY_NON_COMMODITY["grid_fee"], key=f"grid_{country}")
                    levies = st.number_input("Statutory Levies (ct/kWh)", 0.0, 10.0, GERMANY_LEVIES, key=f"levy_{country}")
                    e_tax = st.number_input("Electricity Tax (ct/kWh)", 0.0, 5.0, GERMANY_NON_COMMODITY["tax"], key=f"etax_{country}")
                    relief = 0.0
                    if st.checkbox("Apply Industriestrompreis (Section 24c EnWG)", value=True, key=f"bridge_{country}"):
                        relief = max(0.0, (comm_p * 100) - 5.0) * 0.5
                    non_comm_sum = (grid + levies + e_tax) / 100

                elif country == "UK":
                    grid = st.number_input("T&D Charges (p/kWh)", 0.0, 15.0, 4.5, key=f"grid_{country}")
                    levies = st.number_input("Policy Levies (p/kWh)", 0.0, 15.0, 3.2, key=f"levy_{country}")
                    relief = 0.0
                    if st.checkbox("IETF Phase 3 Levy Exemption", value=True, key=f"ietf_{country}"):
                        relief = 2.8
                    non_comm_sum = (grid + levies) / 100

                elif country == "USA - California":
                    grid = st.number_input("Public Purpose & T&D", 0.0, 20.0, 10.5, key=f"grid_{country}")
                    relief = 0.0
                    if st.checkbox("SGIP / Load Shifting Credit", value=True, key=f"sgip_{country}"):
                        relief = 3.5
                    non_comm_sum = grid / 100

                else:  # USA - Texas
                    grid = st.number_input("Transmission (TCOS) & Distribution", 0.0, 10.0, 3.8, key=f"grid_{country}")
                    relief = 0.0
                    if st.checkbox("ERCOT 4CP Avoidance Logic", value=True, key=f"tcp_{country}"):
                        relief = grid * 0.75
                    non_comm_sum = grid / 100

                st.caption(
                    "Relief magnitudes are indicative and not yet sourced to the enacted schemes. "
                    "See the Methodology tab."
                )

            p_market_total = comm_p + non_comm_sum
            p_eff_comm = comm_p - (relief / 100)
            p_eff_total = p_eff_comm + non_comm_sum

        with c2:
            fig_e, ax_e = plt.subplots(figsize=(5, 1.8))
            ax_e.barh(["Pe_market", "Pe_eff"], [comm_p * 100, p_eff_comm * 100], color="#3498db", label="Commodity")
            ax_e.barh(["Pe_market", "Pe_eff"], [non_comm_sum * 100, non_comm_sum * 100],
                      left=[comm_p * 100, p_eff_comm * 100], color="#95a5a6", label="Non-Commodity")
            ax_e.set_xlabel(f"{unit}", fontsize=8)
            ax_e.tick_params(labelsize=8)
            ax_e.legend(bbox_to_anchor=(1.05, 1), loc="upper left", fontsize="xx-small")
            st.pyplot(fig_e)
            plt.close(fig_e)

        # CATEGORY B: GAS & CARBON
        st.markdown("#### Gas & Carbon Policy")
        c3, c4 = st.columns([1, 1])
        with c3:
            p_g_market = st.number_input(
                f"Base Gas Price ({unit})", 0.5, 30.0, float(cfg["gas"]), format="%.1f", key=f"gp_{country}"
            ) / 100
            c_tax = st.number_input(f"Carbon Tax ({sym}/tCO2)", 0, 500, cfg["tax"], key=f"ctax_{country}")
            tax_impact = c_tax * core.EMISSION_FACTOR_GAS / 1000
            p_g_effective = p_g_market + tax_impact
        with c4:
            fig_g, ax_g = plt.subplots(figsize=(5, 1.2))
            ax_g.barh(["Pg_market", "Pg_effective"], [p_g_market * 100, p_g_market * 100], color="#e67e22", label="Base")
            ax_g.barh(["Pg_market", "Pg_effective"], [0, tax_impact * 100],
                      left=[p_g_market * 100, p_g_market * 100], color="#34495e", label="Carbon")
            ax_g.set_xlabel(f"{unit}", fontsize=8)
            ax_g.legend(bbox_to_anchor=(1.05, 1), loc="upper left", fontsize="xx-small")
            st.pyplot(fig_g)
            plt.close(fig_g)

        # CATEGORY C: CAPEX & CURRENCY
        st.markdown("#### Investment Support")
        c5, c6 = st.columns([1, 1])
        with c5:
            subsidy = st.slider("CAPEX Subsidy (%)", 0, 100, cfg["subsidy"], key=f"sub_{country}")
            st.caption("Applied to electrification options only, not to the gas boiler counterfactual.")
            fx = st.number_input(
                f"FX rate ({sym} per USD)", 0.1, 5.0, float(cfg["fx"]), step=0.01, key=f"fx_{country}",
                help="CAPEX and fixed O&M are quoted in USD. Energy prices are local. "
                     "At 1.00 no conversion is applied and the two are mixed.",
            )
            if abs(fx - 1.0) < 1e-9 and sym != "$":
                st.warning(f"No FX applied: USD capital is being added to {sym} energy prices.", icon="⚠️")
        with c6:
            fig_c, ax_c = plt.subplots(figsize=(5, 1.2))
            ax_c.barh(["Investment"], [100 - subsidy], color="#2ecc71", label="Net")
            ax_c.barh(["Investment"], [subsidy], left=[100 - subsidy], color="#f1c40f", label="Subsidy")
            ax_c.set_xlabel("%", fontsize=8)
            ax_c.legend(bbox_to_anchor=(1.05, 1), loc="upper left", fontsize="xx-small")
            st.pyplot(fig_c)
            plt.close(fig_c)

        country_ctx[country] = {
            "prices": Prices(
                gas_effective=p_g_effective,
                elec_effective=p_eff_total,
                gas_base=p_g_market,
                elec_raw=p_market_total,
            ),
            "subsidy": subsidy / 100,
            "carbon_price": c_tax,
            "fx": fx,
            "symbol": sym,
            "unit": unit,
        }

# --- 5. TECH SPECS ---
st.header("2. Technology Specifications")
if not selected_techs:
    st.info("Select at least one electrification option in the sidebar.")
    st.stop()

technologies = {}
for name in selected_techs:
    d = TECH_DEFAULTS[name]
    with st.expander(f"{name} Configuration", expanded=False):
        t_cols = st.columns(5)
        with t_cols[0]:
            cap = st.number_input("CAPEX (USD/kW)", 0, 5000, d["capex"], key=f"cap_{name}")
        with t_cols[1]:
            opex = st.number_input(
                "Fixed O&M (USD/kW/yr)", 0.0, 100.0, float(d["opex"]), step=0.1, key=f"opx_{name}"
            )
        with t_cols[2]:
            eff = st.number_input(
                "COP / efficiency", 0.1, 15.0, float(d["eff"]), key=f"eff_{name}",
                help="A coefficient of performance for heat pumps and MVR (e.g. 2.2), "
                     "or a thermal fraction for resistive and combustion plant (e.g. 0.99). "
                     "Do not enter a percentage.",
            )
        with t_cols[3]:
            life = st.number_input("Life (Years)", 1, 50, d["life"], key=f"lif_{name}")
        with t_cols[4]:
            util = st.number_input("Annual Hours", 1, 8760, d["util"], key=f"uti_{name}")

        tech = Technology(name, cap, opex, eff, int(life), util, d["fuel"])
        share = tech.fixed_om_share_of_capex()
        if share < OM_SHARE_FLOOR:
            st.warning(
                f"Fixed O&M is {share:.2%} of CAPEX per year. Industrial plant is typically 2-4%. "
                f"At 3% this option's O&M would be {tech.capex * 0.03:.0f} USD/kW/yr, "
                f"adding roughly {(tech.capex * 0.03 - tech.opex) / tech.util * 100:.2f} {unit} to its LCOH.",
                icon="⚠️",
            )
        if util < baseline.util:
            st.info(
                f"Runs {util} h against the baseline's {baseline.util} h. To deliver the same annual heat "
                f"it is sized {baseline.util / util:.2f}x larger, and its capital scales accordingly.",
                icon="ℹ️",
            )
        technologies[name] = tech

# --- 6. CALCULATION ---
all_techs = {baseline.name: baseline, **technologies}
df_res = pd.DataFrame(core.build_results(country_ctx, all_techs, baseline, discount_rate))

# --- 7. STRATEGIC RESULTS ---
st.header("3. Strategic Results")
t1, t2, t3, t4, t5, t6 = st.tabs(
    ["LCOH Comparison", "Financials", "Sensitivity", "Policy Gap Solver", "Methodology", "Data Sources & Policy Frameworks (2026)"]
)

with t1:
    fig_main, ax_main = plt.subplots(figsize=(10, 4))
    sns.barplot(data=df_res, x="Technology", y="LCOH", hue="Country", ax=ax_main, palette="viridis", edgecolor="0.2")
    ax_main.set_ylabel("LCOH (ct/p per kWh delivered heat)", fontweight="bold")
    ax_main.legend(bbox_to_anchor=(1.05, 1), loc="upper left")
    plt.setp(ax_main.get_xticklabels(), rotation=15, ha="right")
    st.pyplot(fig_main)
    plt.close(fig_main)
    st.caption(
        "The Gas Boiler bar is the counterfactual used for every NPV in the Financials tab. "
        "The CAPEX subsidy is not applied to it."
    )

with t2:
    show = df_res[[
        "Country", "Technology", "LCOH", "Gap vs gas", "Incremental CAPEX",
        "Annual saving", "NPV", "Payback", "Abatement cost",
    ]].copy()
    show["Payback"] = show["Payback"].replace(np.inf, np.nan)
    st.dataframe(
        show.style.format({
            "LCOH": "{:.2f}",
            "Gap vs gas": "{:+.2f}",
            "Incremental CAPEX": "{:,.0f}",
            "Annual saving": "{:,.1f}",
            "NPV": "{:,.0f}",
            "Payback": "{:.1f}",
            "Abatement cost": "{:,.0f}",
        }, na_rep="n/a"),
        width="stretch",
    )
    st.caption(
        "LCOH and gap in minor currency units per kWh. CAPEX, saving and NPV per kW of gas boiler capacity. "
        "Payback and NPV are incremental: the present value of **operating** savings less incremental capital. "
        "Capital is counted once, up front. Abatement cost is currency per tCO2 of **direct combustion** "
        "emissions displaced; grid emissions are not modelled, so it is gross of electricity supply carbon."
    )
    buf = io.StringIO()
    df_res.to_csv(buf, index=False)
    st.download_button(
        "Download results (CSV)", buf.getvalue(), file_name="lcoh_results.csv", mime="text/csv"
    )

with t3:
    focus = st.selectbox("Select Jurisdiction for Sensitivity", selected_countries)
    ctx = country_ctx[focus]
    unit = ctx["unit"]
    e_range_ct = np.linspace(1.0, 45.0, 100)  # minor currency units per kWh

    fig_s, ax_s = plt.subplots(figsize=(10, 5))
    g_base = core.levelised_cost(baseline, ctx["prices"].gas_effective, discount_rate, fx=ctx["fx"])
    ax_s.axhline(g_base, color="black", linestyle="-", alpha=0.4, label="Gas baseline")

    for tech in technologies.values():
        curve = [
            core.levelised_cost(tech, p / 100, discount_rate, ctx["subsidy"], ctx["fx"])
            for p in e_range_ct
        ]
        ax_s.plot(e_range_ct, curve, label=tech.name, lw=2)

    ax_s.axvline(ctx["prices"].elec_effective * 100, color="grey", linestyle=":", label="Current effective price")
    ax_s.set_xlabel(f"Electricity Price ({unit})")
    ax_s.set_ylabel(f"LCOH ({unit})")
    ax_s.legend()
    st.pyplot(fig_s)
    plt.close(fig_s)
    st.caption(
        "Gas is held fixed while electricity varies. That is an independence assumption, and the estimated "
        "gas-electricity dependence is positive (Kendall tau approx. 0.43 for Germany), which removes exactly "
        "the scenarios where a gas spike lets electrification win. This chart therefore reads more favourably "
        "than a correlated model. Treat it as a one-way sensitivity, not a scenario."
    )

with t4:
    st.header("Policy Stack & Gap Solver")
    s_tech_name = st.selectbox(
        "Select Technology for Cross-Jurisdiction Analysis", list(technologies.keys()), key="poster_tech_sel"
    )
    s_tech = technologies[s_tech_name]

    plot_data = []
    for country, ctx in country_ctx.items():
        d = core.policy_decomposition(
            s_tech, baseline, ctx["prices"], discount_rate, ctx["carbon_price"], ctx["subsidy"], ctx["fx"]
        )
        d["Jurisdiction"] = country
        plot_data.append(d)

    df_plot = pd.DataFrame(plot_data)

    fig_p, ax_p = plt.subplots(figsize=(12, 6))
    x = np.arange(len(df_plot))
    width = 0.35
    ax_p.bar(x - width / 2, df_plot["market_gap"], width, label="Raw Market Gap (No Policy)",
             color="#bdc3c7", edgecolor="black")
    ax_p.bar(x + width / 2, df_plot["residual_gap"], width, label="Residual Gap (With 2026 Policy)",
             color="#3498db", edgecolor="black")
    ax_p.axhline(0, color="black", lw=1.5)
    ax_p.set_xticks(x)
    ax_p.set_xticklabels(df_plot["Jurisdiction"], fontweight="bold")
    ax_p.set_ylabel("Cost Gap vs. Gas Boiler (ct/p per kWh)", fontweight="bold")
    ax_p.set_title(f"Economic Parity Gap for {s_tech_name}: Market vs. Policy Support", fontsize=14, fontweight="bold")
    ax_p.legend()
    for i, val in enumerate(df_plot["residual_gap"]):
        offset = 0.2 if val >= 0 else -0.4
        ax_p.text(i + width / 2, val + offset, f"{val:.2f}", ha="center", fontweight="bold", color="#2980b9")
    st.pyplot(fig_p)
    plt.close(fig_p)

    with st.expander("Policy support, decomposed"):
        st.dataframe(
            df_plot[[
                "Jurisdiction", "market_gap", "carbon_price_effect", "capex_grant_effect",
                "price_relief_effect", "policy_support", "residual_gap",
            ]].style.format({c: "{:+.2f}" for c in df_plot.columns if c != "Jurisdiction"}),
            width="stretch",
        )
        st.caption("Market gap plus policy support equals the residual gap, by construction.")

    st.divider()
    st.subheader("Strategic Gap Closing: Intervention Menu")
    st.write("What further shifts are required to eliminate the **Residual Gap**?")

    for country, ctx in country_ctx.items():
        row = df_plot[df_plot["Jurisdiction"] == country].iloc[0]
        gap = row["residual_gap"]
        if gap <= 0:
            st.success(f"{country}: {s_tech_name} has reached LCOH parity. Check the Financials tab for NPV.")
            continue

        with st.expander(f"Close the Gap in {country} (+{gap:.2f} {ctx['unit']} needed)"):
            levers = core.interventions_to_close(gap, s_tech, baseline, discount_rate, ctx["fx"])
            c1, c2, c3 = st.columns(3)
            c1.metric("Add Carbon Tax", f"+{levers['carbon_price']:.1f} {ctx['symbol']}/t")
            c2.metric("Add CAPEX Grant", f"+{levers['capex_grant_pp']:.1f} pp")
            c3.metric("Reduce Elec Price", f"-{levers['elec_price']:.2f} {ctx['unit']}")

            total_grant = ctx["subsidy"] * 100 + levers["capex_grant_pp"]
            if total_grant > 100:
                st.warning(
                    f"That grant would take total CAPEX support to {total_grant:.0f}%, above full funding. "
                    "This lever cannot close the gap alone.",
                    icon="⚠️",
                )
            if levers["elec_price"] > ctx["prices"].elec_effective * 100:
                st.warning(
                    "The required cut exceeds the whole delivered electricity price. "
                    "This lever cannot close the gap alone.",
                    icon="⚠️",
                )
            st.caption(f"Targeting LCOH parity at {row['adjusted_gas_lcoh']:.2f} {ctx['unit']}.")

with t5:
    st.header("Techno-Economic Methodology & Data Sources")
    m1, m2 = st.columns(2)
    with m1:
        st.subheader("Economic Equations")
        st.latex(r"LCOH = \frac{(CAPEX_{net} \cdot CRF) + OPEX_{fixed}}{Utilisation} + \frac{P_{fuel}}{\eta}")
        st.latex(r"CRF = \frac{i(1+i)^n}{(1+i)^n - 1}")
        st.latex(r"NPV = \left(\sum_{t=1}^{n} \frac{S^{op}_t}{(1+i)^t}\right) - \Delta CAPEX")
        st.markdown(
            "$S^{op}$ is the **operating** saving, fuel plus fixed O&M. It excludes capital. "
            "Levelised costs already amortise capital, so an NPV built from the LCOH difference "
            "would charge the same capital twice and can invert the sign of the result."
        )
        st.latex(r"\Delta CAPEX = CAPEX_{elec}\cdot\frac{h_{base}}{h_{elec}} - CAPEX_{gas}")
        st.markdown(
            "Options with lower annual utilisation are oversized so that both deliver the same annual heat."
        )
    with m2:
        st.subheader("German Policy Framework: Bridge Price Mechanism")
        st.write("The model implements the **Industriestrompreis** (Section 24c EnWG) logic: a 5.0 ct/kWh commodity cap on 50% of volume.")
        st.table(pd.DataFrame({
            "Component": ["Grid Fees", "Offshore Levy", "KWKG Levy", "StromNEV (§19)", "Electricity Tax"],
            "Value [ct/kWh]": [
                GERMANY_NON_COMMODITY["grid_fee"], GERMANY_NON_COMMODITY["offshore"],
                GERMANY_NON_COMMODITY["kwkg"], GERMANY_NON_COMMODITY["stromnev"],
                GERMANY_NON_COMMODITY["tax"],
            ],
        }))

    st.divider()
    st.subheader("Known gaps and unverified assumptions")
    st.warning(
        "**Not sourced.** IETF exemption 2.8 p/kWh, SGIP credit 3.5 ct/kWh, ERCOT 4CP relief at 75% of the "
        "grid fee, and the €80/tCO2 nEHS default are indicative magnitudes. The mechanisms are real; "
        "these numbers are not yet traced to the enacted schemes.",
        icon="⚠️",
    )
    st.warning(
        "**No time dimension.** Single-point prices, no load profile, no time-of-use. Flexibility value, "
        "thermal storage and dispatch against time-varying prices cannot be represented in this data model.",
        icon="⚠️",
    )
    st.warning(
        "**No grid emissions.** The abatement cost reflects displaced direct combustion only.",
        icon="⚠️",
    )
    st.warning(
        "**Fixed O&M convention is unresolved.** Several options sit far below the 2-4% of CAPEX typical of "
        "industrial plant. Flagged inline in the Technology Specifications section.",
        icon="⚠️",
    )

    # Surface, rather than silently ignore, the disagreement with tech_inputs.csv.
    try:
        csv_df = pd.read_csv("tech_inputs.csv")
        st.subheader("tech_inputs.csv is not loaded by the model")
        st.write(
            "This file is not wired into the calculation and its technology names do not match the live "
            "defaults. Where they correspond, the numbers disagree. Efficiency drives the conclusion, so "
            "two uncommunicating sources of it need resolving before anything is published."
        )
        st.dataframe(csv_df, width="stretch")
        st.dataframe(
            pd.DataFrame([
                {"Parameter": "High-temp HP CAPEX", "tech_inputs.csv": "700-1100", "Live default": str(TECH_DEFAULTS["High Temperature Heat Pump"]["capex"])},
                {"Parameter": "High-temp HP efficiency", "tech_inputs.csv": "2.8-3.5", "Live default": str(TECH_DEFAULTS["High Temperature Heat Pump"]["eff"])},
                {"Parameter": "MVR/MVC efficiency", "tech_inputs.csv": "7.0-10.0", "Live default": str(TECH_DEFAULTS["Mechanical Vapor Reconversion"]["eff"])},
                {"Parameter": "MVC fixed O&M", "tech_inputs.csv": "10.0", "Live default": f"{TECH_DEFAULTS['Microwave']['opex']} (on Microwave)"},
            ]),
            width="stretch",
        )
    except FileNotFoundError:
        pass

    st.divider()
    st.markdown(
        "* **Bridge Price Policy:** [BMWK](https://www.bundesregierung.de/breg-en/news/reduction-in-energy-prices-2358994)\n"
        "* **Energy Prices:** [Eurostat](https://ec.europa.eu/eurostat/statistics-explained/index.php?title=Energy_price_statistics)"
    )

with t6:
    st.header("Data Sources & Policy Frameworks (2026)")
    st.markdown(
        "This section provides the evidentiary basis for the tool's default assumptions. "
        "Links are to the governing scheme; the specific magnitudes used are flagged as unverified "
        "in the Methodology tab."
    )

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Operational & Price Relief (P_eff)")
        st.info("**Wholesale & Commodity Caps**")
        st.write(
            "* **Germany (Section 24c EnWG):** [BMWK Energy Laws Portal](https://www.bmwk.de/Navigation/DE/Service/Gesetze/Gesetze-und-Verordnungen/gesetze-und-verordnungen.html)  \n"
            "  *Backs the 5.0 ct/kWh commodity cap for 50% volume.*\n"
            "* **UK (EII Exemption Scheme):** [GOV.UK British Industry Supercharger](https://www.gov.uk/government/publications/british-industry-supercharger)  \n"
            "  *Backs the exemption from RO, FIT, and CFD costs for energy-intensive sectors.*"
        )
        st.info("**Grid Fee & T&D Optimization**")
        st.write(
            "* **USA - Texas (4CP Mechanism):** [ERCOT 4CP](https://www.ercot.com/mktinfo/data_agg/4cp)  \n"
            "  *Backs TCOS reduction via peak load management. The 75% figure is an assumption.*\n"
            "* **Germany (StromNEV §19):** [BNetzA Grid Fee Regulation](https://www.bundesnetzagentur.de/EN/Areas/Energy/Companies/GridFees/GridFees_node.html)  \n"
            "  *Backs grid fee relief for consistent Bandlast profiles.*\n"
            "* **USA - California (ACC Multipliers):** [CPUC Avoided Cost Calculator](https://www.cpuc.ca.gov/industries-and-topics/electrical-energy/demand-side-management/acc)  \n"
            "  *Backs hourly value multipliers for electrification load-shifting.*"
        )

    with col_b:
        st.subheader("Capital Incentives & Grants (Subsidy)")
        st.info("**Direct CAPEX Grants**")
        st.write(
            "* **UK (IETF Phase 3):** [Industrial Energy Transformation Fund](https://www.gov.uk/government/collections/industrial-energy-transformation-fund)  \n"
            "  *Backs the default 20% grant assumption.*\n"
            "* **Germany (EEW Modules):** [BAFA Energy Efficiency in Economy](https://www.bafa.de/EN/Energy/Energy_Efficiency/Energy_Efficiency_in_Economy/energy_efficiency_in_economy_node.html)  \n"
            "  *Backs the 30% default subsidy for heat pumps and MVR.*\n"
            "* **USA - California (SGIP):** [CPUC Self-Generation Incentive Program](https://www.cpuc.ca.gov/sgip/)  \n"
            "  *Backs the capital rebate structure for thermal storage and load shifting.*"
        )
        st.info("**Carbon Pricing & Tax Benchmarks**")
        st.write(
            "* **EU/Germany (nEHS Pricing):** [DEHSt National Emissions Trading](https://www.dehst.de/EN/National-Emissions-Trading/national-emissions-trading_node.html)  \n"
            "  *Backs the €80/tCO2 default carbon surcharge logic.*\n"
            "* **USA (Inflation Reduction Act):** [IRS Clean Energy Tax Credits](https://www.irs.gov/clean-energy-tax-credits)  \n"
            "  *Federal credit eligibility. Not currently implemented in the model.*"
        )

    st.divider()
    st.markdown("### Technical Calculation Standards")
    st.table(pd.DataFrame({
        "Mechanism": ["Emission Factors (Natural Gas)", "Industrial Gas Benchmarks", "Electricity Cost Statistics", "LCOH Calculation Standard"],
        "Source Agency": ["IPCC / DEFRA", "EIA (US) & Eurostat (EU)", "IEA Energy Prices", "NREL / Fraunhofer ISE"],
        "Verified Link": [
            "https://www.ipcc.ch/data/",
            "https://www.eia.gov/outlooks/aeo/",
            "https://www.iea.org/reports/energy-prices-and-taxes-for-oecd-countries",
            "https://www.nrel.gov/analysis/tech-lcoe.html",
        ],
    }))
