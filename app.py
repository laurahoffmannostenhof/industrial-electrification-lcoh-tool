import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# --- 1. CONFIG & STYLE ---
st.set_page_config(page_title="Industrial Heat Strategy Tool", layout="wide")
st.title("🛡️ Industrial Heat: Techno-Economic Strategy Tool")
st.markdown("---")

# --- 2. GLOBAL DEFAULTS & DATA ---
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

# --- 3. SIDEBAR: SCOPE & GLOBAL SETTINGS ---
with st.sidebar:
    st.header("🔍 1. Define Scope")
    selected_countries = st.multiselect("Select Countries", options=list(COUNTRY_DEFAULTS.keys()), default=["Germany"])
    selected_techs = st.multiselect("Select Technologies", options=list(TECH_DEFAULTS.keys()), default=["Gas Boiler", "Electric Boiler", "High Heat HP"])
    
    st.divider()
    st.header("💰 2. Market-Based Incentives")
    st.info("Policy-driven levers affecting the business case.")
    # Carbon tax is now centralized here or can be handled per country below
    global_carbon_tax_mode = st.checkbox("Use Global Carbon Tax for all countries?", value=False)
    if global_carbon_tax_mode:
        universal_tax = st.number_input("Universal Carbon Tax ($/tCO2)", 0, 500, 80)

    st.divider()
    st.header("⚖️ 3. Financial Foundation")
    discount_rate = st.slider("WACC / Discount Rate (%)", 1, 15, 7) / 100
    emission_factor = 0.202 # kgCO2/kWh gas (Fixed assumption)

# --- 4. MAIN INTERFACE: USER OVERRIDES ---
st.header("📥 Scenario Customization")

# --- Country-Specific Overrides ---
st.subheader("📍 Regional Energy Prices")
country_params = {}
c_cols = st.columns(len(selected_countries) if selected_countries else 1)

for i, country in enumerate(selected_countries):
    with c_cols[i]:
        st.markdown(f"**{country}**")
        g_p = st.number_input(f"Gas Price ($/kWh)", 0.01, 0.30, COUNTRY_DEFAULTS[country]['gas'], format="%.3f", key=f"g_{country}")
        e_p = st.number_input(f"Elec Price ($/kWh)", 0.01, 0.50, COUNTRY_DEFAULTS[country]['elec'], format="%.3f", key=f"e_{country}")
        
        if global_carbon_tax_mode:
            tax = universal_tax
            st.caption(f"Carbon Tax: ${tax}/t (Global)")
        else:
            tax = st.number_input(f"Carbon Tax ($/t)", 0, 500, COUNTRY_DEFAULTS[country]['tax'], key=f"t_{country}")
        
        country_params[country] = {"gas": g_p, "elec": e_p, "tax": tax}

st.divider()

# --- Technology-Specific Overrides ---
st.subheader("🏗️ Technology Specifications")
st.caption("Adjust hardware performance, lifespan, and annual runtime per technology.")
tech_params = {}
t_cols = st.columns(len(selected_techs) if selected_techs else 1)

for i, tech in enumerate(selected_techs):
    with t_cols[i]:
        st.markdown(f"**{tech}**")
        cap = st.number_input("CAPEX ($/kW)", 0, 3000, TECH_DEFAULTS[tech]['capex'], key=f"c_{tech}")
        eff = st.number_input("Efficiency (COP/%)", 0.1, 10.0, TECH_DEFAULTS[tech]['eff'], key=f"ef_{tech}")
        life = st.number_input("Life (Years)", 1, 50, TECH_DEFAULTS[tech]['life'], key=f"l_{tech}")
        util = st.number_input("Annual Hours", 1, 8760, TECH_DEFAULTS[tech]['util'], key=f"u_{tech}")
        
        tech_params[tech] = {
            "capex": cap, "eff": eff, "life": life, "util": util, 
            "opex": TECH_DEFAULTS[tech]['opex'], "fuel": TECH_DEFAULTS[tech]['fuel']
        }

# --- 5. CALCULATION ENGINE ---
results = []
for country, cp in country_params.items():
    for tech, tp in tech_params.items():
        # Capital Recovery Factor (CRF) per technology
        crf_tech = (discount_rate * (1 + discount_rate)**tp['life']) / ((1 + discount_rate)**tp['life'] - 1)
        
        # LCOH Components
        fuel_price = (cp['gas'] + (cp['tax'] * emission_factor / 1000)) if tp['fuel'] == "Gas" else cp['elec']
        
        annualized_cap_opex = (tp['capex'] * crf_tech) + tp['opex']
        fixed_lcoh = (annualized_cap_opex / tp['util']) * 100 # Convert to ct/kWh
        variable_lcoh = (fuel_price / tp['eff']) * 100
        
        total_lcoh = fixed_lcoh + variable_lcoh
        
        results.append({
            "Country": country, "Technology": tech, "LCOH (ct/kWh)": round(total_lcoh, 2),
            "Annual Cost ($/kW)": round((total_lcoh/100) * tp['util'], 2),
            "Capex Contribution": round(fixed_lcoh, 2),
            "Fuel Contribution": round(variable_lcoh, 2)
        })

df_res = pd.DataFrame(results)

# --- 6. OUTPUTS & METHODOLOGY ---
st.divider()
tab1, tab2, tab3, tab4 = st.tabs(["📊 LCOH Comparison", "📈 Price Sensitivity", "📄 Detailed Results", "📖 Methodology"])

with tab1:
    if not df_res.empty:
        fig, ax = plt.subplots(figsize=(10, 5))
        sns.barplot(data=df_res, x="Technology", y="LCOH (ct/kWh)", hue="Country", ax=ax)
        ax.set_title("Total Levelized Cost of Heat")
        st.pyplot(fig)
    else:
        st.info("Select items to see charts.")

with tab2:
    st.subheader("Electricity Price Thresholds")
    if selected_countries and any(tp['fuel'] == "Elec" for tp in tech_params.values()):
        focus_c = selected_countries[0]
        st.write(f"Showing sensitivity for **{focus_c}**")
        e_range = np.linspace(0.01, 0.40, 100)
        fig2, ax2 = plt.subplots(figsize=(10, 5))
        
        for tech, tp in tech_params.items():
            crf_t = (discount_rate * (1 + discount_rate)**tp['life']) / ((1 + discount_rate)**tp['life'] - 1)
            fixed = ((tp['capex'] * crf_t) + tp['opex']) / tp['util'] * 100
            
            if tp['fuel'] == "Elec":
                y = [fixed + (p / tp['eff'] * 100) for p in e_range]
                ax2.plot(e_range, y, label=tech)
            else:
                gas_lcoh = fixed + ((country_params[focus_c]['gas'] + (country_params[focus_c]['tax'] * emission_factor / 1000)) / tp['eff'] * 100)
                ax2.axhline(gas_lcoh, color="black", linestyle="--", label=f"{tech} Baseline")
        
        ax2.set_xlabel("Electricity Price ($/kWh)")
        ax2.set_ylabel("LCOH (ct/kWh)")
        ax2.legend()
        st.pyplot(fig2)

with tab3:
    st.dataframe(df_res, use_container_width=True)

with tab4:
    st.header("Methodology & Assumptions")
    st.markdown("""
    ### 1. Levelized Cost of Heat (LCOH) Equation
    The tool calculates the total cost of heat generation over the project lifetime, expressed in **ct/kWh**.
    """)
    
    st.latex(r"LCOH = \frac{(CAPEX \cdot CRF) + OPEX_{fixed}}{Utilization} + \frac{Fuel Price_{adjusted}}{Efficiency}")
    
    st.markdown("""
    ### 2. Capital Recovery Factor (CRF)
    Each technology is annualized based on its specific lifetime using the WACC (Discount Rate) provided in the sidebar.
    """)
    
    st.latex(r"CRF = \frac{r(1+r)^n}{(1+r)^n - 1}")
    
    st.markdown(f"""
    ### 3. Fixed Assumptions
    - **Natural Gas Emission Factor:** {emission_factor} kg $CO_2$ per kWh.
    - **Currency:** All values are in USD ($).
    - **Carbon Tax Adjustment:** Applied directly to the Natural Gas fuel price.
    """)