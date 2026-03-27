import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# --- 1. CONFIG ---
st.set_page_config(page_title="Industrial Heat Strategy Tool", layout="wide")
st.title("Industrial Heat: Financial and Strategic Suite")

# --- 2. DATA DEFAULTS ---
COUNTRY_DEFAULTS = {
    "Germany": {"gas": 0.055, "elec": 0.18, "tax": 80},
    "UK":      {"gas": 0.065, "elec": 0.22, "tax": 50},
    "USA":     {"gas": 0.020, "elec": 0.08, "tax": 0}
}

TECH_DEFAULTS = {
    "Gas Boiler":      {"capex": 55,   "opex": 1.16, "eff": 0.95, "life": 20, "util": 8000, "fuel": "Gas"},
    "Electric Boiler": {"capex": 120,  "opex": 0.58, "eff": 0.99, "life": 15, "util": 8000, "fuel": "Elec"},
    "High Heat HP":    {"capex": 1000, "opex": 0.50, "eff": 3.20, "life": 15, "util": 7500, "fuel": "Elec"},
    "Low Heat HP":     {"capex": 500,  "opex": 0.50, "eff": 4.00, "life": 15, "util": 7500, "fuel": "Elec"},
    "Microwave":       {"capex": 700,  "opex": 10.0, "eff": 0.85, "life": 12, "util": 4000, "fuel": "Elec"}
}

# --- 3. SIDEBAR: INCENTIVES AND GLOBAL SETTINGS ---
with st.sidebar:
    st.header("1. Scope")
    selected_countries = st.multiselect("Countries", options=list(COUNTRY_DEFAULTS.keys()), default=["Germany"])
    selected_techs = st.multiselect("Technologies", options=list(TECH_DEFAULTS.keys()), default=["Gas Boiler", "Electric Boiler", "High Heat HP"])
    
    st.divider()
    st.header("2. Market-Based Incentives")
    carbon_tax = st.number_input("Carbon Tax ($/tCO2)", 0, 500, 80, help="Applied to Natural Gas emissions only.")
    capex_subsidy = st.slider("CAPEX Subsidy (%)", 0, 100, 0, help="Direct grant reducing upfront investment for electric techs.")

    st.divider()
    st.header("3. Financial Foundation")
    discount_rate = st.slider("WACC / Discount Rate (%)", 1, 20, 7) / 100
    emission_factor = 0.202 # kgCO2/kWh gas

# --- 4. INPUTS ---
st.header("Input Parameters")
c_col1, c_col2 = st.columns(2)

with c_col1:
    st.subheader("Regional Energy Prices (Baseline)")
    country_params = {}
    for country in selected_countries:
        col_a, col_b = st.columns(2)
        with col_a: g_p = st.number_input(f"{country} Gas ($/kWh)", 0.01, 0.30, COUNTRY_DEFAULTS[country]['gas'], format="%.3f")
        with col_b: e_p = st.number_input(f"{country} Elec ($/kWh)", 0.01, 0.50, COUNTRY_DEFAULTS[country]['elec'], format="%.3f")
        country_params[country] = {"gas": g_p, "elec": e_p}

with c_col2:
    st.subheader("Technology Overrides")
    tech_params = {}
    for tech in selected_techs:
        with st.expander(f"Edit {tech}"):
            cap = st.number_input("CAPEX ($/kW)", 0, 5000, TECH_DEFAULTS[tech]['capex'], key=f"c_{tech}")
            eff = st.number_input("Efficiency (COP/%)", 0.1, 15.0, TECH_DEFAULTS[tech]['eff'], key=f"e_{tech}")
            life = st.number_input("Life (Years)", 1, 50, TECH_DEFAULTS[tech]['life'], key=f"l_{tech}")
            util = st.number_input("Annual Hours", 1, 8760, TECH_DEFAULTS[tech]['util'], key=f"u_{tech}")
            tech_params[tech] = {"capex": cap, "eff": eff, "life": life, "util": util, "opex": TECH_DEFAULTS[tech]['opex'], "fuel": TECH_DEFAULTS[tech]['fuel']}

# --- 5. CALCULATION ENGINE ---
results = []
for country, cp in country_params.items():
    # Baseline Gas Boiler Logic
    gb = tech_params.get("Gas Boiler", TECH_DEFAULTS["Gas Boiler"])
    crf_gb = (discount_rate * (1 + discount_rate)**gb['life']) / ((1 + discount_rate)**gb['life'] - 1)
    gas_fuel_cost = cp['gas'] + (carbon_tax * emission_factor / 1000)
    gas_lcoh = (((gb['capex'] * crf_gb) + gb['opex']) / gb['util'] * 100) + (gas_fuel_cost / gb['eff'] * 100)
    ann_gas_expenditure = (gas_lcoh / 100) * gb['util']

    for tech, tp in tech_params.items():
        # Apply Subsidy to Capex
        net_capex = tp['capex'] * (1 - capex_subsidy/100)
        crf_t = (discount_rate * (1 + discount_rate)**tp['life']) / ((1 + discount_rate)**tp['life'] - 1)
        
        # Levelized Cost of Heat
        f_price = gas_fuel_cost if tp['fuel'] == "Gas" else cp['elec']
        fixed_lcoh = ((net_capex * crf_t) + tp['opex']) / tp['util'] * 100
        var_lcoh = (f_price / tp['eff']) * 100
        total_lcoh = fixed_lcoh + var_lcoh
        
        # Comparative Financials
        ann_elec_expenditure = (total_lcoh / 100) * tp['util']
        ann_savings = ann_gas_expenditure - ann_elec_expenditure
        capex_gap = net_capex - (gb['capex'] if tech != "Gas Boiler" else net_capex)
        
        # Net Present Value and Payback
        pv_factor = ((1 + discount_rate)**tp['life'] - 1) / (discount_rate * (1 + discount_rate)**tp['life'])
        npv = (ann_savings * pv_factor) - capex_gap
        payback = capex_gap / ann_savings if ann_savings > 0 else np.inf
        
        results.append({
            "Country": country, "Technology": tech, "LCOH": total_lcoh, 
            "NPV ($/kW)": npv, "Payback": payback, "Savings/yr": ann_savings
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
    st.subheader("Project Financial Metrics (Relative to Gas Boiler)")
    df_fin = df_res[df_res['Technology'] != "Gas Boiler"].copy()
    
    st.dataframe(df_fin.style.format({
        "LCOH": "{:.2f} ct/kWh",
        "NPV ($/kW)": "${:,.2f}",
        "Payback": "{:.1f} Years",
        "Savings/yr": "${:,.2f}/kW"
    }), use_container_width=True)
    
    fig_npv, ax_npv = plt.subplots(figsize=(10, 4))
    sns.barplot(data=df_fin, x="Technology", y="NPV ($/kW)", hue="Country", ax=ax_npv)
    ax_npv.axhline(0, color='black', lw=1)
    ax_npv.set_title("Net Present Value per kW Capacity")
    st.pyplot(fig_npv)

with t3:
    st.subheader("Breakeven Electricity Price Analysis")
    st.markdown("This table calculates the maximum electricity price allowable for each technology to maintain parity with the Gas Boiler.")
    be_results = []
    for country in selected_countries:
        g_rows = df_res[(df_res['Country'] == country) & (df_res['Technology'] == "Gas Boiler")]
        if not g_rows.empty:
            g_lcoh = g_rows['LCOH'].values[0]
            for tech in selected_techs:
                if tech == "Gas Boiler": continue
                tp = tech_params[tech]
                net_c = tp['capex'] * (1 - capex_subsidy/100)
                crf_t = (discount_rate * (1 + discount_rate)**tp['life']) / ((1 + discount_rate)**tp['life'] - 1)
                fixed = ((net_c * crf_t) + tp['opex']) / tp['util'] * 100
                p_be = (g_lcoh - fixed) * tp['eff'] / 100
                be_results.append({"Country": country, "Technology": tech, "Breakeven Elec ($/kWh)": round(p_be, 3)})
    
    st.table(pd.DataFrame(be_results))

with t4:
    st.header("Methodology and Assumptions")
    st.markdown("### Levelized Cost of Heat (LCOH)")
    st.latex(r"LCOH = \frac{(CAPEX_{net} \cdot CRF) + OPEX_{fixed}}{Utilization} + \frac{Fuel Price}{Efficiency}")
    
    st.markdown("### Net Present Value (NPV)")
    st.latex(r"NPV = \sum_{t=1}^{n} \frac{Savings_{annual}}{(1+r)^t} - (CAPEX_{electrification} - CAPEX_{gas})")
    
    st.markdown("### Fixed Parameters")
    st.write(f"Natural Gas Emission Factor: {emission_factor} kgCO2 per kWh.")
    st.write("Calculations assume constant real energy prices over the project lifetime.")