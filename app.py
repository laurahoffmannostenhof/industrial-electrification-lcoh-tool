import io

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import streamlit as st

import core
import defaults
import stochastic
from core import Prices, Technology
from defaults import COUNTRIES, SOURCES, TECHNOLOGIES, UNSOURCED

st.set_page_config(page_title="Industrial Heat Strategy Tool", layout="wide")
plt.style.use("seaborn-v0_8-whitegrid")


def cite(source_id: str) -> str:
    """Inline markdown citation for a source id."""
    if source_id == UNSOURCED:
        return "_no source_"
    s = SOURCES[source_id]
    return f"[{s.publisher}]({s.url})"


def figure_help(fig) -> str:
    bits = [f"Source: {SOURCES[fig.source].publisher}, {SOURCES[fig.source].period}"
            if fig.is_sourced else "No source. Assumed value."]
    if fig.note:
        bits.append(fig.note)
    return "\n\n".join(bits)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("Scope & Global Financials")
    selected_countries = st.multiselect(
        "Select Jurisdictions", options=list(COUNTRIES.keys()), default=["Germany", "UK"]
    )
    selected_techs = st.multiselect(
        "Select Electrification Options",
        options=list(TECHNOLOGIES.keys()),
        default=["Electric Boiler", "Heat Pump (medium heat, to 150 °C)"],
    )
    discount_rate = st.slider("WACC / Discount Rate (%)", 1, 20, 7) / 100

    st.divider()
    st.subheader("Gas Boiler Baseline")
    st.caption("The counterfactual. Always applied, whatever is selected above.")
    B = defaults.BASELINE
    b_cap = st.number_input("CAPEX (currency/kW)", 0.0, 5000.0, float(B["capex"].value),
                            help=figure_help(B["capex"]), key="b_cap")
    b_opex = st.number_input("Fixed O&M (currency/MWh heat)", 0.0, 100.0,
                             float(B["opex_per_mwh"].value), step=0.01,
                             help=figure_help(B["opex_per_mwh"]), key="b_opex")
    b_eff = st.number_input("Thermal efficiency", 0.1, 1.2, float(B["eff"].value), step=0.01,
                            help=figure_help(B["eff"]), key="b_eff")
    b_life = st.number_input("Life (years)", 1, 50, int(B["life"].value),
                             help=figure_help(B["life"]), key="b_life")
    b_util = st.number_input("Annual hours", 1, 8760, int(B["util"].value),
                             help=figure_help(B["util"]), key="b_util")

baseline = Technology("Gas Boiler", b_cap, b_opex, b_eff, int(b_life), b_util, "Gas")

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.title("Techno-Economic Platform for Evaluating Thermal Decarbonization and Switching Price Dynamics")
st.markdown(
    "Assess industrial heat electrification across Germany, the UK, California and Texas. "
    "By Laura Hoffmann-Ostenhof. Work in Progress. Feedback welcome!"
)

if not selected_countries:
    st.info("Select at least one jurisdiction in the sidebar.")
    st.stop()

country_ctx = {}

for country in selected_countries:
    cfg = COUNTRIES[country]
    sym, unit = cfg["currency"], cfg["unit"]

    with st.container(border=True):
        head = f"{country} Policy Framework"
        st.subheader(head)
        if cfg["sourced"]:
            st.caption(f"Defaults sourced for {cfg['band']}. Hover any field for its source.")
        else:
            st.caption("Defaults for this jurisdiction are assumed, not sourced. See the Methodology tab.")

        # --- Electricity ---------------------------------------------------
        st.markdown("#### Electricity")
        c1, c2 = st.columns([1, 1])
        with c1:
            comm_p = st.number_input(
                f"Wholesale / commodity ({unit})", 0.0, 60.0,
                float(cfg["elec_commodity"].value), step=0.01, format="%.3f",
                help=figure_help(cfg["elec_commodity"]), key=f"comm_{country}",
            ) / 100

            with st.expander("Network charges, levies and policy relief"):
                net_p = st.number_input(
                    f"Network charges and retail margin ({unit})", 0.0, 30.0,
                    float(cfg["elec_network"].value), step=0.01, format="%.3f",
                    help=figure_help(cfg["elec_network"]), key=f"net_{country}",
                )

                levy_values = {}
                if cfg["elec_levies"]:
                    st.markdown("**Levies and taxes**")
                for lv in cfg["elec_levies"]:
                    levy_values[lv.name] = st.number_input(
                        f"{lv.name} ({unit})", 0.0, 20.0, float(lv.value), step=0.001, format="%.3f",
                        help=(f"Source: {SOURCES[lv.source].publisher}" if lv.source != UNSOURCED
                              else "No source. Assumed value.") + (f"\n\n{lv.note}" if lv.note else ""),
                        key=f"levy_{country}_{lv.name}",
                    )

                relief_ct = 0.0
                relief_detail = []
                if cfg["reliefs"]:
                    st.markdown("**Policy relief**")
                for r in cfg["reliefs"]:
                    on = st.checkbox(r.label, value=r.default_on, key=f"relief_{country}_{r.id}")
                    if r.caveat:
                        st.caption(r.caveat)
                    if not on:
                        continue
                    if r.kind == "reference_topup":
                        v = max(0.0, r.params["reference"] - r.params["target"]) * r.params["coverage"]
                    elif r.kind == "flat":
                        v = r.params["value"]
                    elif r.kind == "exemption":
                        v = sum(levy_values.get(n, 0.0) for n in r.params.get("levies", []))
                        v += net_p * r.params.get("network_share", 0.0)
                    else:
                        v = 0.0
                    relief_ct += v
                    relief_detail.append((r.label, v))

                non_comm_sum = (net_p + sum(levy_values.values())) / 100
                if relief_detail:
                    st.caption(" · ".join(f"{lab}: −{v:.2f} {unit}" for lab, v in relief_detail))

            p_market_total = comm_p + non_comm_sum
            p_eff_total = p_market_total - relief_ct / 100

        with c2:
            fig_e, ax_e = plt.subplots(figsize=(5, 1.9))
            ax_e.barh(["Market", "After relief"],
                      [comm_p * 100, comm_p * 100 - relief_ct], color="#3498db", label="Commodity")
            ax_e.barh(["Market", "After relief"],
                      [non_comm_sum * 100, non_comm_sum * 100],
                      left=[comm_p * 100, comm_p * 100 - relief_ct],
                      color="#95a5a6", label="Network, levies and tax")
            ax_e.set_xlabel(unit, fontsize=8)
            ax_e.tick_params(labelsize=8)
            ax_e.legend(bbox_to_anchor=(1.05, 1), loc="upper left", fontsize="xx-small")
            st.pyplot(fig_e)
            plt.close(fig_e)
            st.caption(f"Delivered {p_market_total*100:.2f} {unit}, after relief {p_eff_total*100:.2f} {unit}.")

        # --- Gas and carbon ------------------------------------------------
        st.markdown("#### Gas and carbon")
        c3, c4 = st.columns([1, 1])
        with c3:
            p_g_market = st.number_input(
                f"Delivered gas price, excluding carbon ({unit})", 0.0, 30.0,
                float(cfg["gas_commodity"].value), step=0.01, format="%.3f",
                help=figure_help(cfg["gas_commodity"]), key=f"gp_{country}",
            ) / 100
            c_tax = st.number_input(
                f"Carbon price ({sym}/tCO2)", 0.0, 500.0, float(cfg["carbon_price"].value), step=1.0,
                help=figure_help(cfg["carbon_price"]), key=f"ctax_{country}",
            )
            tax_impact = c_tax * core.EMISSION_FACTOR_GAS / 1000
            p_g_effective = p_g_market + tax_impact
        with c4:
            fig_g, ax_g = plt.subplots(figsize=(5, 1.3))
            ax_g.barh(["Delivered", "With carbon"], [p_g_market * 100, p_g_market * 100],
                      color="#e67e22", label="Gas")
            ax_g.barh(["Delivered", "With carbon"], [0, tax_impact * 100],
                      left=[p_g_market * 100, p_g_market * 100], color="#34495e", label="Carbon")
            ax_g.set_xlabel(unit, fontsize=8)
            ax_g.legend(bbox_to_anchor=(1.05, 1), loc="upper left", fontsize="xx-small")
            st.pyplot(fig_g)
            plt.close(fig_g)

        # --- Capital support -----------------------------------------------
        st.markdown("#### Capital support")
        c5, c6 = st.columns([1, 1])
        with c5:
            subsidy = st.slider("CAPEX grant (%)", 0, 100, int(cfg["capex_grant"].value),
                                help=figure_help(cfg["capex_grant"]), key=f"sub_{country}")
            st.caption("Applied to electrification options only, never to the gas boiler counterfactual.")
            fx = st.number_input(
                f"FX rate ({sym} per unit of the CAPEX currency)", 0.1, 5.0,
                float(cfg["fx"].value), step=0.01, help=figure_help(cfg["fx"]), key=f"fx_{country}",
            )
        with c6:
            fig_c, ax_c = plt.subplots(figsize=(5, 1.3))
            ax_c.barh(["Investment"], [100 - subsidy], color="#2ecc71", label="Net")
            ax_c.barh(["Investment"], [subsidy], left=[100 - subsidy], color="#f1c40f", label="Grant")
            ax_c.set_xlabel("%", fontsize=8)
            ax_c.legend(bbox_to_anchor=(1.05, 1), loc="upper left", fontsize="xx-small")
            st.pyplot(fig_c)
            plt.close(fig_c)

        country_ctx[country] = {
            "prices": Prices(
                gas_commodity=p_g_market,
                carbon_cost=tax_impact,
                elec_commodity=comm_p,
                elec_noncommodity=non_comm_sum,
                elec_relief=relief_ct / 100,
            ),
            "subsidy": subsidy / 100,
            "carbon_price": c_tax,
            "fx": fx,
            "symbol": sym,
            "unit": unit,
        }

# ---------------------------------------------------------------------------
# Technologies
# ---------------------------------------------------------------------------
st.header("2. Technology Specifications")
if not selected_techs:
    st.info("Select at least one electrification option in the sidebar.")
    st.stop()

technologies = {}
for name in selected_techs:
    d = TECHNOLOGIES[name]
    with st.expander(f"{name} — {d['temperature']}", expanded=False):
        t_cols = st.columns(5)
        with t_cols[0]:
            cap = st.number_input("CAPEX (currency/kW)", 0.0, 6000.0, float(d["capex"].value),
                                  help=figure_help(d["capex"]), key=f"cap_{name}")
        with t_cols[1]:
            opex = st.number_input("Fixed O&M (currency/MWh heat)", 0.0, 100.0,
                                   float(d["opex_per_mwh"].value), step=0.01,
                                   help=figure_help(d["opex_per_mwh"]), key=f"opx_{name}")
        with t_cols[2]:
            eff = st.number_input("COP / efficiency", 0.1, 20.0, float(d["eff"].value), step=0.01,
                                  help=figure_help(d["eff"]), key=f"eff_{name}")
        with t_cols[3]:
            life = st.number_input("Life (years)", 1, 50, int(d["life"].value),
                                   help=figure_help(d["life"]), key=f"lif_{name}")
        with t_cols[4]:
            util = st.number_input("Annual hours", 1, 8760, int(d["util"].value),
                                   help=figure_help(d["util"]), key=f"uti_{name}")

        tech = Technology(name, cap, opex, eff, int(life), util, d["fuel"])
        st.caption(
            f"O&M is per MWh of heat delivered, so {opex:.3f} is "
            f"{opex/10:.3f} {COUNTRIES[selected_countries[0]]['unit']} on the LCOH and "
            f"{tech.annual_om_per_kw():.1f} per kW per year at {util:,} hours, "
            f"which is {tech.fixed_om_share_of_capex():.1%} of CAPEX."
        )
        if util < baseline.util:
            st.info(
                f"Runs {util:,} h against the baseline's {baseline.util:,} h, so it is sized "
                f"{baseline.util/util:.2f}x larger to deliver the same annual heat. Capital scales; "
                "O&M does not, because it is already per MWh delivered.",
                icon="ℹ️",
            )
        technologies[name] = tech

# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
all_techs = {baseline.name: baseline, **technologies}
df_res = pd.DataFrame(core.build_results(country_ctx, all_techs, baseline, discount_rate))

st.header("3. Strategic Results")
t1, t2, t3, t7, t4, t5, t6 = st.tabs(
    ["LCOH Comparison", "Financials", "Sensitivity", "Uncertainty", "Policy Gap Solver",
     "Methodology", "Data Sources"]
)

with t1:
    fig_main, ax_main = plt.subplots(figsize=(10, 4))
    sns.barplot(data=df_res, x="Technology", y="LCOH", hue="Country", ax=ax_main,
                palette="viridis", edgecolor="0.2")
    ax_main.set_ylabel("LCOH (minor currency units per kWh heat)", fontweight="bold")
    ax_main.legend(bbox_to_anchor=(1.05, 1), loc="upper left")
    plt.setp(ax_main.get_xticklabels(), rotation=15, ha="right")
    st.pyplot(fig_main)
    plt.close(fig_main)
    st.caption(
        "The Gas Boiler bar is the counterfactual behind every NPV in the Financials tab, and the "
        "CAPEX grant is not applied to it. Units are per jurisdiction and are not comparable across bars "
        "of different currencies."
    )

with t2:
    show = df_res[["Country", "Technology", "LCOH", "Gap vs gas", "Incremental CAPEX",
                   "Annual saving", "NPV", "Payback", "Abatement cost"]].copy()
    show["Payback"] = show["Payback"].replace(np.inf, np.nan)
    st.dataframe(
        show.style.format({
            "LCOH": "{:.2f}", "Gap vs gas": "{:+.2f}", "Incremental CAPEX": "{:,.0f}",
            "Annual saving": "{:,.1f}", "NPV": "{:,.0f}", "Payback": "{:.1f}",
            "Abatement cost": "{:,.0f}",
        }, na_rep="n/a"),
        width="stretch",
    )
    st.caption(
        "LCOH and gap in minor currency units per kWh. CAPEX, saving and NPV per kW of gas boiler "
        "capacity. NPV and payback are incremental: the present value of **operating** savings less "
        "incremental capital, so capital is counted once. Abatement cost is currency per tCO2 of "
        "**direct combustion** emissions displaced; grid emissions are not modelled."
    )
    buf = io.StringIO()
    df_res.to_csv(buf, index=False)
    st.download_button("Download results (CSV)", buf.getvalue(),
                       file_name="lcoh_results.csv", mime="text/csv")

with t3:
    focus = st.selectbox("Jurisdiction", selected_countries, key="sens_c")
    ctx = country_ctx[focus]
    unit = ctx["unit"]
    e_range_ct = np.linspace(1.0, 45.0, 100)

    fig_s, ax_s = plt.subplots(figsize=(10, 5))
    g_base = core.levelised_cost(baseline, ctx["prices"].gas_effective, discount_rate, fx=ctx["fx"])
    ax_s.axhline(g_base, color="black", linestyle="-", alpha=0.4, label="Gas baseline")
    for tech in technologies.values():
        ax_s.plot(e_range_ct,
                  [core.levelised_cost(tech, p / 100, discount_rate, ctx["subsidy"], ctx["fx"])
                   for p in e_range_ct], label=tech.name, lw=2)
    ax_s.axvline(ctx["prices"].elec_effective * 100, color="grey", linestyle=":",
                 label="Current effective price")
    ax_s.set_xlabel(f"Electricity price ({unit})")
    ax_s.set_ylabel(f"LCOH ({unit})")
    ax_s.legend()
    st.pyplot(fig_s)
    plt.close(fig_s)
    st.caption(
        "Gas is held fixed while electricity varies, which is an independence assumption. The estimated "
        "gas-electricity dependence is positive, so this reads more favourably than the correlated model "
        "in the Uncertainty tab. Treat it as a one-way sensitivity, not a scenario."
    )


@st.cache_data(show_spinner=False)
def run_uncertainty(country_items, tech_items, base, rate, n, seed, tau_items, correlated):
    ctx = {c: {"prices": p, "subsidy": s, "fx": f, "symbol": sy, "unit": u}
           for c, p, s, f, sy, u in country_items}
    return stochastic.run_monte_carlo(
        ctx, dict(tech_items), base, rate, n=n, seed=seed,
        tau_overrides=dict(tau_items), correlated=correlated,
    )


with t7:
    st.header("Monte Carlo Uncertainty Analysis")
    st.markdown(
        "Each trial is one coherent state of the world: a single drawn gas and electricity "
        "**commodity** price, correlated where a dependence has been estimated, a single cost of "
        "capital, and a single gas boiler, against which every electrification option is compared. "
        "The full method is in the Methodology tab."
    )

    u1, u2, u3 = st.columns(3)
    with u1:
        n_sims = st.select_slider("Simulations", options=[1000, 2000, 5000, 10000, 40000],
                                  value=5000, key="mc_n")
    with u2:
        mc_seed = st.number_input("Random seed", value=42, step=1, key="mc_seed")
    with u3:
        use_corr = st.checkbox("Apply estimated price dependence", value=True, key="mc_corr")
        st.caption("Unticked forces independence, the comparison baseline.")

    with st.expander("Kendall's tau by jurisdiction"):
        st.write(
            "Germany is empirical, from monthly log-returns of TTF gas against EPEX day-ahead power. "
            "The others have no estimate and fall back to independence. The sampling interval on the "
            "German estimate is roughly 0.31 to 0.54, so it is worth sweeping."
        )
        tau_overrides = {}
        tcols = st.columns(max(len(selected_countries), 1))
        for col, country in zip(tcols, selected_countries):
            with col:
                dflt = stochastic.PRICE_TAU_GAS_ELEC.get(country)
                val = st.number_input(f"{country}", -0.95, 0.95,
                                      float(dflt) if dflt is not None else 0.0,
                                      step=0.01, key=f"tau_{country}")
                if dflt is not None or abs(val) > 1e-9:
                    tau_overrides[country] = val

    country_items = tuple((c, x["prices"], x["subsidy"], x["fx"], x["symbol"], x["unit"])
                          for c, x in country_ctx.items())
    with st.spinner(f"Running {n_sims:,} simulations..."):
        mc = run_uncertainty(country_items, tuple(technologies.items()), baseline, discount_rate,
                             int(n_sims), int(mc_seed), tuple(sorted(tau_overrides.items())),
                             bool(use_corr))

    st.subheader("LCOH distribution")
    fig_u, axes = plt.subplots(1, len(mc), figsize=(5 * len(mc), 5), squeeze=False)
    for ax, (country, res) in zip(axes.flatten(), mc.items()):
        names = list(res.lcoh.keys())
        x = np.arange(len(names))
        p10 = [np.percentile(res.lcoh[t], 10) for t in names]
        p50 = [np.percentile(res.lcoh[t], 50) for t in names]
        p90 = [np.percentile(res.lcoh[t], 90) for t in names]
        ax.bar(x, np.array(p90) - np.array(p10), bottom=p10, width=0.6,
               color="#3498db", alpha=0.75, edgecolor="white")
        for i, m in enumerate(p50):
            ax.hlines(m, i - 0.3, i + 0.3, color="black", linewidth=2, zorder=5)
        b10, b50, b90 = np.percentile(res.baseline_lcoh, [10, 50, 90])
        ax.axhspan(b10, b90, color="#e67e22", alpha=0.15, zorder=0)
        ax.axhline(b50, color="#e67e22", linestyle="--", linewidth=1.5, zorder=1)
        ax.set_xticks(x)
        ax.set_xticklabels([n.split("(")[0].strip().replace(" ", "\n", 1) for n in names], fontsize=8)
        ax.set_title(country, fontweight="bold")
        ax.set_ylabel(f"LCOH ({res.unit})", fontweight="bold")
        ax.set_ylim(bottom=0)
    fig_u.suptitle(f"N = {n_sims:,} simulations", fontsize=11, y=1.02)
    fig_u.tight_layout()
    st.pyplot(fig_u)
    plt.close(fig_u)
    st.caption("Bars span P10 to P90, black line is the median, shaded band is the gas counterfactual "
               "over the same draws. Axis units differ by jurisdiction.")
    for country, res in mc.items():
        st.caption(f"**{country}** — {res.provenance}")

    st.subheader("Parity gap and NPV")
    fc = st.selectbox("Jurisdiction", list(mc.keys()), key="mc_focus_c")
    ft = st.selectbox("Technology", list(technologies.keys()), key="mc_focus_t")
    res = mc[fc]
    gap, npv = res.gap[ft], res.npv[ft]

    g1, g2 = st.columns(2)
    with g1:
        fig_g, ax_g = plt.subplots(figsize=(5, 3.2))
        ax_g.hist(gap, bins=60, color="#3498db", alpha=0.8)
        ax_g.axvline(0, color="black", lw=1.5)
        ax_g.set_xlabel(f"LCOH gap vs gas ({res.unit})")
        ax_g.set_ylabel("Trials")
        st.pyplot(fig_g)
        plt.close(fig_g)
        prob = float(np.mean(gap < 0) * 100)
        st.metric("Cheaper than gas", f"{prob:.1f}%",
                  delta=f"±{stochastic.binomial_standard_error(prob, int(n_sims))*1.96:.1f} pp (MC noise)",
                  delta_color="off")
    with g2:
        fig_n, ax_n = plt.subplots(figsize=(5, 3.2))
        ax_n.hist(npv, bins=60, color="#2ecc71", alpha=0.8)
        ax_n.axvline(0, color="black", lw=1.5)
        ax_n.set_xlabel(f"NPV ({res.symbol}/kW of boiler capacity)")
        ax_n.set_ylabel("Trials")
        st.pyplot(fig_n)
        plt.close(fig_n)
        pn = float(np.mean(npv > 0) * 100)
        st.metric("NPV positive", f"{pn:.1f}%",
                  delta=f"±{stochastic.binomial_standard_error(pn, int(n_sims))*1.96:.1f} pp (MC noise)",
                  delta_color="off")
    st.caption("The gap is the paired difference within each trial, not the difference of two "
               "independent distributions.")

    with st.expander("What drives the spread?"):
        shares = stochastic.variance_decomposition(
            int(mc_seed), {fc: {**country_ctx[fc], "name": fc}},
            technologies[ft], baseline, discount_rate, fc,
            n=min(int(n_sims), 8000), tau_overrides=tau_overrides,
        )
        if shares:
            fig_v, ax_v = plt.subplots(figsize=(7, 3))
            keys = list(shares.keys())
            ax_v.barh(keys[::-1], [shares[k] for k in keys][::-1], color="#8e44ad", alpha=0.8)
            ax_v.set_xlabel("Share of parity-gap variance (%)")
            st.pyplot(fig_v)
            plt.close(fig_v)
            st.caption("Main effects: each input varied alone. See the Methodology tab for why this is "
                       "not a freeze-one decomposition.")

    st.subheader("Summary statistics")
    df_mc = pd.DataFrame(stochastic.summarise(mc, int(n_sims)))
    st.dataframe(
        df_mc.style.format({
            "P10": "{:.2f}", "P50": "{:.2f}", "P90": "{:.2f}", "Mean": "{:.2f}", "Std": "{:.2f}",
            "Median gap": "{:+.2f}", "P(cheaper than gas)": "{:.1f}%", "+/- (MC noise)": "±{:.1f}",
            "P(NPV > 0)": "{:.1f}%", "Median NPV": "{:,.0f}",
        }),
        width="stretch",
    )
    buf_mc = io.StringIO()
    df_mc.to_csv(buf_mc, index=False)
    st.download_button("Download Monte Carlo results (CSV)", buf_mc.getvalue(),
                       file_name="monte_carlo_results.csv", mime="text/csv")

with t4:
    st.header("Policy Stack & Gap Solver")
    s_tech_name = st.selectbox("Technology", list(technologies.keys()), key="poster_tech_sel")
    s_tech = technologies[s_tech_name]

    plot_data = []
    for country, ctx in country_ctx.items():
        d = core.policy_decomposition(s_tech, baseline, ctx["prices"], discount_rate,
                                      ctx["carbon_price"], ctx["subsidy"], ctx["fx"])
        d["Jurisdiction"] = country
        plot_data.append(d)
    df_plot = pd.DataFrame(plot_data)

    fig_p, ax_p = plt.subplots(figsize=(12, 6))
    x = np.arange(len(df_plot))
    w = 0.35
    ax_p.bar(x - w / 2, df_plot["market_gap"], w, label="Raw market gap (no policy)",
             color="#bdc3c7", edgecolor="black")
    ax_p.bar(x + w / 2, df_plot["residual_gap"], w, label="Residual gap (with selected policy)",
             color="#3498db", edgecolor="black")
    ax_p.axhline(0, color="black", lw=1.5)
    ax_p.set_xticks(x)
    ax_p.set_xticklabels(df_plot["Jurisdiction"], fontweight="bold")
    ax_p.set_ylabel("Cost gap vs gas boiler (minor units per kWh)", fontweight="bold")
    ax_p.set_title(f"Economic parity gap for {s_tech_name}", fontsize=14, fontweight="bold")
    ax_p.legend()
    for i, v in enumerate(df_plot["residual_gap"]):
        ax_p.text(i + w / 2, v + (0.2 if v >= 0 else -0.4), f"{v:.2f}",
                  ha="center", fontweight="bold", color="#2980b9")
    st.pyplot(fig_p)
    plt.close(fig_p)

    with st.expander("Policy support, decomposed"):
        st.dataframe(
            df_plot[["Jurisdiction", "market_gap", "carbon_price_effect", "capex_grant_effect",
                     "price_relief_effect", "policy_support", "residual_gap"]].style.format(
                {c: "{:+.2f}" for c in df_plot.columns if c != "Jurisdiction"}),
            width="stretch",
        )
        st.caption("Market gap plus policy support equals the residual gap, by construction.")

    st.divider()
    st.subheader("Closing the residual gap")
    for country, ctx in country_ctx.items():
        row = df_plot[df_plot["Jurisdiction"] == country].iloc[0]
        gap = row["residual_gap"]
        if gap <= 0:
            st.success(f"{country}: {s_tech_name} reaches LCOH parity. Check the Financials tab for NPV.")
            continue
        with st.expander(f"{country}: +{gap:.2f} {ctx['unit']} to close"):
            levers = core.interventions_to_close(gap, s_tech, baseline, discount_rate, ctx["fx"])
            c1, c2, c3 = st.columns(3)
            c1.metric("Add carbon price", f"+{levers['carbon_price']:.1f} {ctx['symbol']}/t")
            c2.metric("Add CAPEX grant", f"+{levers['capex_grant_pp']:.1f} pp")
            c3.metric("Cut electricity price", f"-{levers['elec_price']:.2f} {ctx['unit']}")
            if ctx["subsidy"] * 100 + levers["capex_grant_pp"] > 100:
                st.warning("That grant exceeds full funding. This lever cannot close the gap alone.", icon="⚠️")
            if levers["elec_price"] > ctx["prices"].elec_effective * 100:
                st.warning("The required cut exceeds the whole delivered electricity price. "
                           "This lever cannot close the gap alone.", icon="⚠️")

# ---------------------------------------------------------------------------
# Methodology
# ---------------------------------------------------------------------------
with t5:
    st.header("Methodology")

    st.subheader("Levelised cost of heat")
    st.latex(r"LCOH = \underbrace{\frac{CAPEX_{net}\cdot CRF}{h}}_{\text{capital}}"
             r" + \underbrace{\frac{OPEX}{10}}_{\text{fixed O\&M}}"
             r" + \underbrace{\frac{P_{fuel}}{\eta}}_{\text{fuel}}")
    st.latex(r"CRF = \frac{i(1+i)^n}{(1+i)^n - 1}")
    st.markdown(
        "All three terms are in minor currency units per kWh of heat delivered. "
        "$h$ is annual full-load hours and $\\eta$ is a COP or a thermal fraction.\n\n"
        "**Fixed O&M is per MWh of heat delivered**, following the ECCO dataset the technology "
        "figures come from, so it converts straight to minor units per kWh by dividing by ten. It is "
        "not divided by annual hours. Doing that treats a per-output figure as a per-capacity-per-year "
        "one and understates it by a factor of $h/1000$, which is eightfold at 8,000 hours."
    )

    st.subheader("Net present value")
    st.latex(r"NPV = S^{op}\cdot\frac{(1+i)^n - 1}{i(1+i)^n} - \Delta CAPEX")
    st.latex(r"\Delta CAPEX = CAPEX_{elec}\cdot\frac{h_{base}}{h_{elec}} - CAPEX_{gas}")
    st.markdown(
        "$S^{op}$ is the annual **operating** saving: fuel plus fixed O&M, excluding capital. "
        "Levelised costs already amortise capital, so an NPV built from the difference of two LCOH "
        "figures charges the same capital twice and can invert the sign of the result.\n\n"
        "Options with lower annual utilisation are oversized so both deliver the same annual heat. "
        "Capital scales with that factor; O&M does not, because it is already per MWh delivered."
    )

    st.subheader("Price structure")
    st.markdown(
        "Each fuel price is held as components rather than a single delivered figure:\n\n"
        "- **Commodity** — the part set by the market, and the part that moves.\n"
        "- **Network charges and retail margin**, and each **levy and tax** separately.\n"
        "- **Policy relief**, applied as a reduction to the delivered price.\n"
        "- **Carbon**, priced per kWh of gas input via the emission factor.\n\n"
        "This matters for the Monte Carlo below, and it makes the relief mechanisms auditable: each "
        "one states what it removes rather than applying an undifferentiated discount."
    )

    st.subheader("Policy relief mechanisms")
    st.markdown(
        "Three mechanism types are implemented, matching how the schemes actually work:\n\n"
        "- **Reference top-up** — pays (reference price − target price) on a share of volume. The "
        "German Industriestrompreis. The reference is the scheme's own fixed forward price, not the "
        "user's commodity assumption.\n"
        "- **Exemption** — removes named levies in full and a share of network charges. The UK EII "
        "Exemption Scheme under the British Industry Supercharger.\n"
        "- **Flat** — a stated value per kWh, used where the government publishes an estimate rather "
        "than a component rule. The British Industrial Competitiveness Scheme.\n\n"
        "**Every relief is off by default.** Each carries eligibility conditions that a typical "
        "industrial heat site of this size does not meet, and switching them on silently was how "
        "earlier versions of this tool produced its most optimistic numbers."
    )

    st.subheader("Monte Carlo method")
    st.markdown(
        "**A trial is one state of the world.** Within a trial there is one gas commodity price, one "
        "electricity commodity price, one cost of capital, one sampled gas boiler, and one sample of "
        "each technology. Every comparison is made inside that trial, so the parity probability is the "
        "frequency of a **paired** difference, not the overlap of two independently drawn "
        "distributions."
    )
    st.markdown(
        "**Marginals.** Each uncertain parameter is drawn from a triangular distribution centred on "
        "its point estimate, with the half-widths listed below. The lower bound is raised to any "
        "physical floor before drawing rather than clipping afterwards, because clipping piles "
        "probability mass on the floor and shifts the mean."
    )
    st.markdown(
        "**Dependence.** Gas and electricity commodity prices are drawn jointly through a Gaussian "
        "copula (NORTA): correlated standard normals, mapped to uniforms by the normal CDF, then "
        "through each marginal's inverse CDF. The copula is invariant under that monotone transform, "
        "so the target Kendall's tau is reproduced exactly."
    )
    st.latex(r"\rho = \sin\!\left(\frac{\pi\tau}{2}\right)")
    st.markdown(
        "$\\tau$ is estimated from **monthly log-returns**: daily series aligned in levels first, then "
        "aggregated, then differenced, so every return spans the same interval on both sides. Monthly "
        "is the horizon-appropriate frequency for a levelised metric; daily understates the dependence. "
        "Germany is empirical at $\\tau = 0.426$ from TTF gas against EPEX day-ahead power. The other "
        "jurisdictions have no estimate and run at independence, which the Uncertainty tab states "
        "explicitly for each one rather than leaving it implicit."
    )
    st.markdown(
        "**Volatility applies to commodity components only.** Grid fees, levies and the carbon price "
        "are set by regulation and policy, not by the market, and the dependence above was estimated "
        "on wholesale series. Applying wholesale volatility to a delivered price that is roughly a "
        "third regulated charges widens the parity-gap distribution by about a quarter and roughly "
        "doubles the parity probability, without moving the median."
    )
    st.markdown(
        "**Variance decomposition** reports **main effects**: each input is varied alone with "
        "everything else held at its point value. The alternative, freezing one input at a time and "
        "attributing the drop in variance, is not usable here. Gas and electricity are deliberately "
        "correlated and the parity gap is a difference, so their co-movement partially cancels; "
        "freezing one of them makes the variance rise rather than fall, and the implied share is "
        "negative. For the same reason the two prices are treated as a single block. Shares are "
        "normalised to sum to 100 and do not attribute interactions."
    )
    st.markdown(
        "**Sampling error.** Each parity probability carries a binomial standard error of "
        "$\\sqrt{p(1-p)/N}$, reported as a 95% band. At 5,000 draws a probability near 2% carries "
        "about ±0.4 points, so quoting one decimal place without the draw count overstates the "
        "precision. The seed is honoured: the generator is explicit and nothing reseeds numpy's "
        "global state."
    )

    st.markdown("**Parameter half-widths**")
    st.dataframe(pd.DataFrame(
        [{"Technology": k, "CAPEX": f"±{v[0]:.0%}", "Efficiency": f"±{v[1]:.0%}",
          "Fixed O&M": f"±{v[2]:.0%}", "Utilisation": f"±{v[3]:.0%}"}
         for k, v in stochastic.UNCERTAINTY_RANGES.items() if k in all_techs]
        + [{"Technology": "Gas commodity price", "CAPEX": "", "Efficiency": "",
            "Fixed O&M": "", "Utilisation": f"±{stochastic.COMMODITY_VOLATILITY['Gas']:.0%}"},
           {"Technology": "Electricity commodity price", "CAPEX": "", "Efficiency": "",
            "Fixed O&M": "", "Utilisation": f"±{stochastic.COMMODITY_VOLATILITY['Elec']:.0%}"}],
    ), width="stretch", hide_index=True)

# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------
with t6:
    st.header("Data Sources")
    st.markdown(
        "Every default in this tool is either traced to a source below or listed as unsourced in the "
        "Methodology tab. Hovering any input field shows its source and period. All links were checked "
        "on 18 September 2026."
    )

    groups = {
        "Germany": ["bdew_strom", "netztransparenz_offshore", "netztransparenz_kwkg",
                    "netztransparenz_19", "amprion_19", "stromnev_19", "kav", "stromstg_9b",
                    "enwg_24c", "bafa_ist", "bafa_eew", "dehst_nehs", "eurostat_gas", "smard",
                    "bnetza_netze", "destatis"],
        "United Kingdom": ["desnz_qep", "desnz_qep_collection", "ccl_rates", "cca", "bics",
                           "bics_collection", "supercharger_ncc", "eii_exemption", "ietf",
                           "ofgem_ro", "emrs", "neso_tnuos", "uk_ets_price", "icap_ukets",
                           "desnz_policy_impacts"],
        "Technology and cross-cutting": ["ecco", "eurostat_elec", "ipcc", "eia_aeo"],
    }

    for group, ids in groups.items():
        st.subheader(group)
        for sid in ids:
            s = SOURCES[sid]
            st.markdown(f"**[{s.title}]({s.url})** — {s.publisher}, {s.period}")
            if s.note:
                st.caption(s.note)
