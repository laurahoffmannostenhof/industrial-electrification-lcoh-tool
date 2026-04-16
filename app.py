import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import io

# --- 1. CONFIG & STYLE ---
st.set_page_config(page_title="Industrial Heat Strategy Tool", layout="wide")
plt.style.use('seaborn-v0_8-whitegrid')

# --- 2. DATA DEFAULTS ---
COUNTRY_DEFAULTS = {
    "Germany": {"gas": 0.055, "elec": 0.18, "tax": 80, "subsidy": 30, "currency": "€"},
    "UK":      {"gas": 0.065, "elec": 0.22, "tax": 50, "subsidy": 20, "currency": "£"},
    "USA":     {"gas": 0.020, "elec": 0.08, "tax": 0,  "subsidy": 0,  "currency": "$"}
}

TECH_DEFAULTS = {
    "Gas Boiler":      {"capex": 55,   "opex": 1.16, "eff": 0.95, "life": 20, "util": 8000, "fuel": "Gas"},
    "Electric Boiler": {"capex": 120,  "opex": 0.58, "eff": 0.99, "life": 15, "util": 8000, "fuel": "Elec"},
    "High Heat Heat Pump":    {"capex": 1000, "opex": 0.50, "eff": 3.20, "life": 15, "util": 7500, "fuel": "Elec"},
    "Low Heat Heat Pump":     {"capex": 500,  "opex": 0.50, "eff": 4.00, "life": 15, "util": 7500, "fuel": "Elec"},
    "Microwave":       {"capex": 700,  "opex": 10.0, "eff": 0.85, "life": 12, "util": 4000, "fuel": "Elec"}
}

# 2026 Statutory Defaults for Germany (ct/kWh) - Source: Netztransparenz.de / BMWK
GERMANY_NON_COMMODITY = {
    "grid_fee": 2.860, 
    "offshore": 0.941,
    "kwkg": 0.446,
    "stromnev": 1.559,
    "tax": 0.050
}

GERMANY_NON_COMMODITY = {"grid_fee": 2.860, "offshore": 0.941, "kwkg": 0.446, "stromnev": 1.559, "tax": 0.050}
EMISSION_FACTOR = 0.202 # kgCO2/kWh gas

# --- 3. SIDEBAR ---
with st.sidebar:
    st.header("Scope & Global Financials")
    selected_countries = st.multiselect("Select Countries", options=list(COUNTRY_DEFAULTS.keys()), default=["Germany"])
    selected_techs = st.multiselect("Select Technologies", options=list(TECH_DEFAULTS.keys()), default=["Gas Boiler", "Electric Boiler", "High Heat Heat Pump"])
    discount_rate = st.slider("WACC / Discount Rate (%)", 1, 20, 7) / 100
    st.divider()
    st.info("Tip: Use the Strategic Results tabs at the bottom to compare Net Present Value (NPV) and Payback periods.")

# --- 4. CATEGORICAL INPUT DASHBOARD ---
st.title("IND-HEAT: Policy Impact Dashboard")
st.markdown("Assess the competitiveness of industrial heat electrification across jurisdictions.")

country_prices = {}
price_cols = st.columns(len(selected_countries) if selected_countries else 1)
for i, country in enumerate(selected_countries):
    with price_cols[i]:
        st.markdown(f"**{country} Prices**")
        g_p = st.number_input(f"Gas ($/kWh)", 0.01, 0.30, COUNTRY_DEFAULTS[country]['gas'], format="%.3f", key=f"g_p_{country}")
        e_p = st.number_input(f"Elec ($/kWh)", 0.01, 0.50, COUNTRY_DEFAULTS[country]['elec'], format="%.3f", key=f"e_p_{country}")
        country_prices[country] = {"gas": g_p, "elec": e_p}

st.divider()

# Category 2: Market-Based Incentives
st.subheader("Market-Based Incentives")
country_incentives = {}
incentive_cols = st.columns(len(selected_countries) if selected_countries else 1)
for i, country in enumerate(selected_countries):
    with incentive_cols[i]:
        st.markdown(f"**{country} Policy**")
        c_tax = st.number_input(f"Carbon Tax ($/tCO2)", 0, 500, COUNTRY_DEFAULTS[country]['tax'], key=f"tax_{country}")
        subsidy = st.slider(f"CAPEX Subsidy (%)", 0, 100, COUNTRY_DEFAULTS[country]['subsidy'], key=f"sub_{country}")
        country_incentives[country] = {"tax": c_tax, "subsidy": subsidy}

st.divider()

# Category 3: Technology Specifications
st.subheader("Technology Specifications")
tech_params = {}
for tech in selected_techs:
    with st.expander(f"{tech} Configuration", expanded=False):
        t_cols = st.columns(4)
        with t_cols[0]: cap = st.number_input("CAPEX ($/kW)", 0, 5000, TECH_DEFAULTS[tech]['capex'], key=f"cap_{tech}")
        with t_cols[1]: eff = st.number_input("Efficiency (COP/%)", 0.1, 15.0, TECH_DEFAULTS[tech]['eff'], key=f"eff_{tech}")
        with t_cols[2]: life = st.number_input("Life (Years)", 1, 50, TECH_DEFAULTS[tech]['life'], key=f"lif_{tech}")
        with t_cols[3]: util = st.number_input("Annual Hours", 1, 8760, TECH_DEFAULTS[tech]['util'], key=f"uti_{tech}")
        tech_params[tech] = {"capex": cap, "eff": eff, "life": life, "util": util, "opex": TECH_DEFAULTS[tech]['opex'], "fuel": TECH_DEFAULTS[tech]['fuel']}

# --- 6. CALCULATION & RESULTS ---
results = []
for country in selected_countries:
    cp, ci = country_prices[country], country_incentives[country]
    gb = tech_params.get("Gas Boiler", TECH_DEFAULTS["Gas Boiler"])
    crf_gb = (discount_rate * (1 + discount_rate)**gb['life']) / ((1 + discount_rate)**gb['life'] - 1)
    gas_lcoh = (((gb['capex'] * crf_gb) + gb['opex']) / gb['util'] * 100) + (cp['gas'] / gb['eff'] * 100)
    
    for tech, tp in tech_params.items():
        net_capex = tp['capex'] * (1 - ci['subsidy']/100)
        crf_t = (discount_rate * (1 + discount_rate)**tp['life']) / ((1 + discount_rate)**tp['life'] - 1)
        
        f_price = effective_gas_price if tp['fuel'] == "Gas" else cp['elec']
        total_lcoh = (((net_capex * crf_t) + tp['opex']) / tp['util'] * 100) + (f_price / tp['eff'] * 100)
        ann_savings = ((gas_lcoh / 100) * gb['util']) - (total_lcoh / 100 * tp['util'])
        capex_gap = net_capex - (gb['capex'] if tech != "Gas Boiler" else net_capex)
        pv_f = ((1 + discount_rate)**tp['life'] - 1) / (discount_rate * (1 + discount_rate)**tp['life'])
        results.append({
            "Country": country, "Symbol": cp['sym'], "Technology": tech, "LCOH": total_lcoh, 
            "NPV": (ann_savings * pv_f) - capex_gap, "Payback": capex_gap / ann_savings if ann_savings > 0 else np.inf
        })

df_res = pd.DataFrame(results)

st.header("3. Strategic Results")
t1, t2, t3, t4 = st.tabs(["LCOH Comparison", "Financials", "Sensitivity", "Methodology"])

with t1:
    fig_main, ax_main = plt.subplots(figsize=(10, 4))
    sns.barplot(data=df_res, x="Technology", y="LCOH", hue="Country", ax=ax_main, palette="viridis", edgecolor="0.2")
    ax_main.set_ylabel("LCOH (ct or p / kWh)", fontweight='bold')
    ax_main.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    sns.despine(left=True)
    st.pyplot(fig_main)

with t2:
    st.dataframe(df_res[["Country", "Technology", "LCOH", "NPV", "Payback"]], use_container_width=True)

with t3:
    if selected_countries:
        focus = st.selectbox("Select Country for Sensitivity", selected_countries)
        e_range = np.linspace(0.01, 0.45, 100)
        fig_s, ax_s = plt.subplots(figsize=(10, 5))
        g_base = df_res[(df_res['Country'] == focus) & (df_res['Technology'] == "Gas Boiler")]['LCOH'].values[0]
        ax_s.axhline(g_base, color='black', linestyle='--', label="Gas Boiler (Baseline)")
        for tech in selected_techs:
            tp = tech_params[tech]
            if tp['fuel'] == "Elec":
                crf = (discount_rate * (1 + discount_rate)**tp['life']) / ((1 + discount_rate)**tp['life'] - 1)
                fixed = (((tp['capex'] * (1 - country_incentives[focus]['subsidy']/100)) * crf) + tp['opex']) / tp['util'] * 100
                y_vals = [fixed + (p / tp['eff'] * 100) for p in e_range]
                ax_s.plot(e_range, y_vals, label=tech, lw=2)
        ax_s.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        st.pyplot(fig_s)

# --- REPLACING THE METHODOLOGY TAB (T4) ---

with t4:
    st.header("Methodology and Assumptions")
    st.markdown("### Levelized Cost of Heat (LCOH)")
    st.latex(r"LCOH = \frac{(CAPEX_{net} \cdot CRF) + OPEX_{fixed}}{Utilization} + \frac{Fuel Price}{Efficiency}")
    
    st.markdown("### Net Present Value (NPV)")
    st.latex(r"NPV = \sum_{t=1}^{n} \frac{Savings_{annual}}{(1+r)^t} - (CAPEX_{electrification} - CAPEX_{gas})")
    
    st.markdown("### Fixed Parameters")
    st.write(f"Natural Gas Emission Factor: {emission_factor} kgCO2 per kWh.")
    st.write("Calculations assume constant real energy prices over the project lifetime.")