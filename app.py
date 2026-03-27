import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# --- 1. CONFIG ---
st.set_page_config(page_title="Industrial Heat Strategy Tool", layout="wide")
st.title("Industrial Heat: Financial and Strategic Suite")

# --- TOOL DESCRIPTION ---
st.markdown("""
This tool evaluates the economic viability of electrifying industrial process heat. 
It compares various electric heating technologies against a **Natural Gas Boiler** baseline. 
The analysis separates raw market energy prices from policy-driven incentives—such as **Carbon Taxes** and **CAPEX Subsidies**—to help stakeholders identify the "tipping point" for decarbonization investment.
""")

# --- 2. DATA DEFAULTS ---
COUNTRY_DEFAULTS = {
    "Germany": {"gas": 0.055, "elec": 0.18, "tax": 80, "subsidy": 30},
    "UK":      {"gas": 0.065, "elec": 0.22, "tax": 50, "subsidy": 20},
    "USA":     {"gas": 0.020, "elec": 0.08, "tax": 0,  "subsidy": 0}
}

TECH_DEFAULTS = {
    "Gas Boiler":      {"capex": 55,   "opex": 1.16, "eff": 0.95, "life": 20, "util": 8000, "fuel": "Gas"},
    "Electric Boiler": {"capex": 120,  "opex": 0.58, "eff": 0.99, "life": 15, "util": 8000, "fuel": "Elec"},
    "High Heat HP":    {"capex": 1000, "opex": 0.50, "eff": 3.20, "life": 15, "util": 7500, "fuel": "Elec"},
    "Low Heat HP":     {"capex": 500,  "opex": 0.50, "eff": 4.00, "life": 15, "util": 7500, "fuel": "Elec"},
    "Microwave":       {"capex": 700,  "opex": 10.0, "eff": 0.85, "life": 12, "util": 4000, "fuel": "Elec"}
}

# --- 3. SIDEBAR: GLOBAL SETTINGS ---
with st.sidebar:
    st.header("1. Scope")
    selected_countries = st.multiselect("Countries", options=list(COUNTRY_DEFAULTS.keys()), default=["Germany"])
    selected_techs = st.multiselect("Technologies", options=list(TECH_DEFAULTS.keys()), default=["Gas Boiler", "Electric Boiler", "High Heat HP"])
    
    st.divider()
    st.header("2. Financial Foundation")
    discount_rate = st.slider("WACC / Discount Rate (%)", 1, 20, 7) / 100
    emission_factor = 0.202 # kgCO2/kWh gas

# --- 4. INPUTS (STACKED LAYOUT) ---
st.header("Input Parameters")

# Category 1: Regional Energy Prices
st.subheader("Regional Energy Prices")
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
tech_cols = st.columns(len(selected_techs) if selected_techs else 1)
for i, tech in enumerate(selected_techs):
    with tech_cols[i]:
        st.markdown(f"**{tech}**")
        cap = st.number_input("CAPEX ($/kW)", 0, 5000, TECH_DEFAULTS[tech]['capex'], key=f"c_{tech}")
        eff = st.number_input("Efficiency (COP/%)", 0.1, 15.0, TECH_DEFAULTS[tech]['eff'], key=f"e_{tech}")
        life = st.number_input("Life (Years)", 1, 50, TECH_DEFAULTS[tech]['life'], key=f"l_{tech}")
        util = st.number_input("Annual Hours", 1, 8760, TECH_DEFAULTS[tech]['util'], key=f"u_{tech}")
        tech_params[tech] = {"capex": cap, "eff": eff, "life": life, "util": util, "opex": TECH_DEFAULTS[tech]['opex'], "fuel": TECH_DEFAULTS[tech]['fuel']}

# --- 5. CALCULATION ENGINE ---
results = []
for country in selected_countries:
    cp = country_prices[country]
    ci = country_incentives[country]
    
    gb = tech_params.get("Gas Boiler", TECH_DEFAULTS["Gas Boiler"])
    crf_gb = (discount_rate * (1 + discount_rate)**gb['life']) / ((1 + discount_rate)**gb['life'] - 1)
    effective_gas_price = cp['gas'] + (ci['tax'] * emission_factor / 1000)
    
    gas_lcoh = (((gb['capex'] * crf_gb) + gb['opex']) / gb['util'] * 100) + (effective_gas_price / gb['eff'] * 100)
    ann_gas_expenditure = (gas_lcoh / 100) * gb['util']

    for tech, tp in tech_params.items():
        net_capex = tp['capex'] * (1 - ci['subsidy']/100)
        crf_t = (discount_rate * (1 + discount_rate)**tp['life']) / ((1 + discount_rate)**tp['life'] - 1)
        
        f_price = effective_gas_price if tp['fuel'] == "Gas" else cp['elec']
        total_lcoh = (((net_capex * crf_t) + tp['opex']) / tp['util'] * 100) + (f_price / tp['eff'] * 100)
        
        ann_savings = ann_gas_expenditure - (total_lcoh / 100 * tp['util'])
        capex_gap = net_capex - (gb['capex'] if tech != "Gas Boiler" else net_capex)
        
        pv_factor = ((1 + discount_rate)**tp['life'] - 1) / (discount_rate * (1 + discount_rate)**tp['life'])
        npv = (ann_savings * pv_factor) - capex_gap
        payback = capex_gap / ann_savings if ann_savings > 0 else np.inf
        
        results.append({
            "Country": country, "Technology": tech, "LCOH": total_lcoh, 
            "NPV ($/kW)": npv, "Payback": payback
        })

df_res = pd.DataFrame(results)

# --- 6. OUTPUT TABS ---
t1, t2, t3, t4 = st.tabs(["LCOH Comparison", "Financial Viability", "Price Sensitivity", "Methodology"])

with t1:
    fig, ax = plt.subplots(figsize=(10, 4))
    sns.barplot(data=df_res, x="Technology", y="LCOH", hue="Country", ax=ax)
    ax.set_ylabel("ct / kWh")
    st.pyplot(fig)

with t2:
    df_fin = df_res[df_res['Technology'] != "Gas Boiler"].copy()
    st.dataframe(df_fin.style.format({"LCOH": "{:.2f}", "NPV ($/kW)": "{:,.2f}", "Payback": "{:.1f}"}), use_container_width=True)
    fig_npv, ax_npv = plt.subplots(figsize=(10, 4))
    sns.barplot(data=df_fin, x="Technology", y="NPV ($/kW)", hue="Country", ax=ax_npv)
    ax_npv.axhline(0, color='black', lw=1)
    st.pyplot(fig_npv)

with t3:
    if selected_countries:
        focus_country = st.selectbox("Focus Country for Graph", options=selected_countries)
        e_range = np.linspace(0.01, 0.45, 100)
        fig_sens, ax_sens = plt.subplots(figsize=(10, 5))
        g_baseline = df_res[(df_res['Country'] == focus_country) & (df_res['Technology'] == "Gas Boiler")]['LCOH'].values[0]
        ax_sens.axhline(g_baseline, color='black', linestyle='--', label=f"Gas Boiler ({focus_country})")
        ci_focus = country_incentives[focus_country]
        for tech in selected_techs:
            tp = tech_params[tech]
            if tp['fuel'] == "Elec":
                net_c = tp['capex'] * (1 - ci_focus['subsidy']/100)
                crf_t = (discount_rate * (1 + discount_rate)**tp['life']) / ((1 + discount_rate)**tp['life'] - 1)
                fixed = ((net_c * crf_t) + tp['opex']) / tp['util'] * 100
                y_vals = [fixed + (p / tp['eff'] * 100) for p in e_range]
                ax_sens.plot(e_range, y_vals, label=tech, lw=2)
        ax_sens.set_xlabel("Electricity Price ($/kWh)")
        ax_sens.set_ylabel("LCOH (ct/kWh)")
        ax_sens.legend()
        st.pyplot(fig_sens)

with t4:
    st.header("Methodology and Assumptions")
    st.markdown("### Levelized Cost of Heat (LCOH)")
    st.latex(r"LCOH = \frac{(CAPEX_{net} \cdot CRF) + OPEX_{fixed}}{Utilization} + \frac{Fuel Price}{Efficiency}")
    
    st.markdown("### Net Present Value (NPV)")
    st.latex(r"NPV = \sum_{t=1}^{n} \frac{Savings_{annual}}{(1+r)^t} - (CAPEX_{electrification} - CAPEX_{gas})")
    
    st.markdown("### Fixed Parameters")
    st.write(f"Natural Gas Emission Factor: {emission_factor} kgCO2 per kWh.")
    st.write("Calculations assume constant real energy prices over the project lifetime.")