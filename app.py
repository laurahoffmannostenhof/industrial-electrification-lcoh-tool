import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# --- 1. CONFIG & STYLE ---
st.set_page_config(page_title="Industrial Heat Decarbonization Tool", layout="wide")
st.title("🏭 Industrial Heat: Techno-Economic Strategy Tool")
st.markdown("---")

# --- 2. GLOBAL DEFAULTS & DATA ---
# This dictionary holds the "Suggested Defaults"
COUNTRY_DEFAULTS = {
    "Germany": {"gas": 0.055, "elec": 0.18, "tax": 80, "color": "#3498db"},
    "UK":      {"gas": 0.065, "elec": 0.22, "tax": 50, "color": "#e74c3c"},
    "USA":     {"gas": 0.020, "elec": 0.08, "tax": 0,  "color": "#2ecc71"}
}

TECH_DEFAULTS = {
    "Gas Boiler":      {"capex": 55,   "opex": 1.16, "eff": 0.95, "fuel": "Gas"},
    "Electric Boiler": {"capex": 120,  "opex": 0.58, "eff": 0.99, "fuel": "Elec"},
    "High Heat HP":    {"capex": 1000, "opex": 0.50, "eff": 3.20, "fuel": "Elec"},
    "Low Heat HP":     {"capex": 500,  "opex": 0.50, "eff": 4.00, "fuel": "Elec"},
    "Microwave":       {"capex": 700,  "opex": 10.0, "eff": 0.85, "fuel": "Elec"}
}

# --- 3. SIDEBAR: SELECTIONS ---
with st.sidebar:
    st.header("🔍 1. Define Scope")
    selected_countries = st.multiselect("Select Countries", options=list(COUNTRY_DEFAULTS.keys()), default=["Germany"])
    selected_techs = st.multiselect("Select Technologies", options=list(TECH_DEFAULTS.keys()), default=["Gas Boiler", "Electric Boiler", "High Heat HP"])
    
    st.divider()
    st.header("⚙️ 2. Global Assumptions")
    discount_rate = st.slider("Discount Rate (%)", 1, 15, 7) / 100
    lifetime = st.number_input("Lifetime (Years)", 5, 40, 20)
    utilization = st.number_input("Annual Hours (Utilization)", 1000, 8760, 8000)
    emission_factor = 0.202 # kgCO2/kWh gas

# Calculation for Capital Recovery Factor
crf = (discount_rate * (1 + discount_rate)**lifetime) / ((1 + discount_rate)**lifetime - 1)

# --- 4. MAIN INTERFACE: OVERRIDE DEFAULTS ---
st.header("📥 User Inputs & Overrides")
st.info("Edit the values below to customize the scenarios for your specific project.")

# Create dynamic input columns for each selected country
country_data = {}
cols = st.columns(len(selected_countries) if selected_countries else 1)

for i, country in enumerate(selected_countries):
    with cols[i]:
        st.subheader(f"📍 {country}")
        g_price = st.slider(f"Gas Price ($/kWh) - {country}", 0.01, 0.20, COUNTRY_DEFAULTS[country]['gas'], key=f"g_{country}")
        e_price = st.slider(f"Elec Price ($/kWh) - {country}", 0.01, 0.40, COUNTRY_DEFAULTS[country]['elec'], key=f"e_{country}")
        c_tax = st.number_input(f"Carbon Tax ($/t) - {country}", 0, 500, COUNTRY_DEFAULTS[country]['tax'], key=f"t_{country}")
        country_data[country] = {"gas": g_price, "elec": e_price, "tax": c_tax}

st.divider()

# Create dynamic input columns for each technology
tech_overrides = {}
t_cols = st.columns(len(selected_techs) if selected_techs else 1)
for i, tech in enumerate(selected_techs):
    with t_cols[i]:
        st.write(f"**{tech}**")
        cap = st.number_input("CAPEX ($/kW)", 0, 3000, TECH_DEFAULTS[tech]['capex'], key=f"cap_{tech}")
        eff = st.number_input("Efficiency (COP/%)", 0.1, 10.0, TECH_DEFAULTS[tech]['eff'], key=f"eff_{tech}")
        tech_overrides[tech] = {"capex": cap, "eff": eff, "opex": TECH_DEFAULTS[tech]['opex'], "fuel_type": TECH_DEFAULTS[tech]['fuel']}

# --- 5. CALCULATION ENGINE ---
results = []
for country, c_vals in country_data.items():
    for tech, t_vals in tech_overrides.items():
        # LCOH Math
        fuel_price = (c_vals['gas'] + (c_vals['tax'] * emission_factor / 1000)) if t_vals['fuel_type'] == "Gas" else c_vals['elec']
        fixed_cost = ((t_vals['capex'] * crf) + t_vals['opex']) / utilization * 100 # ct/kWh
        variable_cost = (fuel_price / t_vals['eff']) * 100 # ct/kWh
        lcoh = fixed_cost + variable_cost
        
        results.append({
            "Country": country,
            "Technology": tech,
            "LCOH (ct/kWh)": round(lcoh, 2),
            "Annual Cost ($/kW)": round((lcoh/100) * utilization, 2)
        })

df_res = pd.DataFrame(results)

# --- 6. OUTPUTS ---
if not df_res.empty:
    tab1, tab2, tab3 = st.tabs(["📊 LCOH Comparison", "📈 Sensitivity (Elec Price)", "📄 Data Table"])

    with tab1:
        st.subheader("Levelized Cost of Heat Comparison")
        fig, ax = plt.subplots(figsize=(10, 5))
        sns.barplot(data=df_res, x="Technology", y="LCOH (ct/kWh)", hue="Country", ax=ax)
        ax.set_ylabel("ct / kWh")
        st.pyplot(fig)
        st.caption("LCOH includes Annualized CAPEX, Fixed OPEX, and Fuel Costs (including Carbon Taxes).")

    with tab2:
        st.subheader("Electricity Price Sensitivity")
        # Generate lines for LCOH vs Elec Price
        e_prices = np.linspace(0.01, 0.40, 50)
        fig2, ax2 = plt.subplots(figsize=(10, 5))
        
        # We focus on the first selected country for this sensitivity for clarity
        focus_country = selected_countries[0]
        c_vals = country_data[focus_country]
        
        for tech in selected_techs:
            t_vals = tech_overrides[tech]
            if t_vals['fuel_type'] == "Elec":
                y = [(((t_vals['capex'] * crf) + t_vals['opex']) / utilization * 100) + (p / t_vals['eff'] * 100) for p in e_prices]
                ax2.plot(e_prices, y, label=tech)
            else:
                # Gas is a flat line relative to elec price
                gas_lcoh = (((t_vals['capex'] * crf) + t_vals['opex']) / utilization * 100) + ((c_vals['gas'] + (c_vals['tax'] * emission_factor / 1000)) / t_vals['eff'] * 100)
                ax2.axhline(gas_lcoh, label=f"{tech} (Baseline)", linestyle="--", color="black")

        ax2.set_xlabel("Electricity Price ($/kWh)")
        ax2.set_ylabel("LCOH (ct/kWh)")
        ax2.set_title(f"Impact of Electricity Price in {focus_country}")
        ax2.legend()
        st.pyplot(fig2)

    with tab3:
        st.dataframe(df_res, use_container_width=True)
        st.download_button("Download Results", df_res.to_csv(), "lcoh_results.csv")
else:
    st.warning("Please select at least one Country and one Technology in the sidebar.")