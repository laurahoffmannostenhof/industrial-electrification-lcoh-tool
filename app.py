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
country_incentives = {}

for country in selected_countries:
    sym = COUNTRY_DEFAULTS[country]['currency']
    with st.container(border=True):
        st.subheader(f"{country} Policy Framework")
        
        # CATEGORY A: ELECTRICITY & BRIDGE PRICE (Peff)
        st.markdown("#### Electricity & Grid Policy")
        c1, c2 = st.columns([1, 1])
        with c1:
            if country == "Germany":
                comm_p = st.number_input("Wholesale/Commodity (€/kWh)", 0.01, 0.30, 0.095, format="%.3f", key=f"comm_{country}")
                bridge_active = st.checkbox("Apply Industriestrompreis (Bridge Price)", value=True, key=f"bridge_{country}")
                
                # Detailed Explanation of the mechanism
                st.markdown("""
                **Mechanism Explanation:**
                The Industriestrompreis reduces the commodity cost for energy-intensive firms. 
                It caps 50% of the volume at **5.0 ct/kWh**. The effective price ($P_{e\_eff}$) 
                is the weighted average of this cap and the current wholesale market price, 
                plus fixed non-commodity levies.
                """)
                
                non_comm_sum = sum(GERMANY_NON_COMMODITY.values()) / 100
                p_market_total = comm_p + non_comm_sum
                p_eff_comm = (max(min(comm_p, 0.050), 0.050) * 0.5 + comm_p * 0.5) if bridge_active else comm_p
                p_eff_total = p_eff_comm + non_comm_sum
            else:
                p_eff_total = st.number_input(f"Flat Elec Price ({sym}/kWh)", 0.01, 0.50, COUNTRY_DEFAULTS[country]['elec'], key=f"e_{country}")
                p_market_total, p_eff_comm, non_comm_sum = p_eff_total, p_eff_total, 0
        
        with c2:
            if country == "Germany":
                fig_e, ax_e = plt.subplots(figsize=(5, 1.8))
                ax_e.barh(["Pe_market", "Pe_eff"], [comm_p*100, p_eff_comm*100], color='#3498db', label="Commodity")
                ax_e.barh(["Pe_market", "Pe_eff"], [non_comm_sum*100, non_comm_sum*100], left=[comm_p*100, p_eff_comm*100], color='#95a5a6', label="Non-Commodity")
                ax_e.set_xlabel("ct/kWh", fontsize=8)
                ax_e.tick_params(labelsize=8)
                ax_e.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize='xx-small')
                st.pyplot(fig_e)

        # CATEGORY B: GAS & CARBON POLICY (Pg)
        st.markdown("#### Gas & Carbon Policy")
        c3, c4 = st.columns([1, 1])
        with c3:
            p_g_market = st.number_input(f"Base Gas Price ({sym}/kWh)", 0.01, 0.30, COUNTRY_DEFAULTS[country]['gas'], format="%.3f", key=f"gp_{country}")
            c_tax = st.number_input(f"Carbon Tax ({sym}/tCO2)", 0, 500, COUNTRY_DEFAULTS[country]['tax'], key=f"ctax_{country}")
            tax_impact = (c_tax * EMISSION_FACTOR / 1000)
            p_g_effective = p_g_market + tax_impact
        with c4:
            fig_g, ax_g = plt.subplots(figsize=(5, 1.2))
            ax_g.barh(["Pg_market", "Pg_effective"], [p_g_market*100, p_g_market*100], color='#e67e22', label="Base")
            ax_g.barh(["Pg_market", "Pg_effective"], [0, tax_impact*100], left=[p_g_market*100, p_g_market*100], color='#34495e', label="Carbon Surcharge")
            ax_g.set_xlabel("ct/kWh", fontsize=8)
            ax_g.tick_params(labelsize=8)
            ax_g.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize='xx-small')
            st.pyplot(fig_g)

        # CATEGORY C: CAPEX SUPPORT
        st.markdown("#### Investment Support")
        c5, c6 = st.columns([1, 1])
        with c5:
            subsidy = st.slider(f"CAPEX Subsidy (%)", 0, 100, COUNTRY_DEFAULTS[country]['subsidy'], key=f"sub_{country}")
        with c6:
            fig_c, ax_c = plt.subplots(figsize=(5, 1.2))
            ax_c.barh(["Investment"], [100 - subsidy], color='#2ecc71', label="Net Cost")
            ax_c.barh(["Investment"], [subsidy], left=[100 - subsidy], color='#f1c40f', label="Subsidy")
            ax_c.set_xlabel("%", fontsize=8)
            ax_c.tick_params(labelsize=8)
            ax_c.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize='xx-small')
            st.pyplot(fig_c)

        country_prices[country] = {"gas": p_g_effective, "elec": p_eff_total, "sym": sym}
        country_incentives[country] = {"tax": c_tax, "subsidy": subsidy, "bridge": bridge_active if country == "Germany" else False}

# --- 5. TECH SPECS (COLLAPSIBLE) ---
st.header("2. Technology Specifications")
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
        f_price = cp['gas'] if tp['fuel'] == "Gas" else cp['elec']
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
    st.header("Techno-Economic Methodology & Data Sources")
    
    m_col1, m_col2 = st.columns(2)
    
    with m_col1:
        st.subheader("Economic Equations")
        st.markdown("**1. Levelized Cost of Heat (LCOH)**")
        st.write("The LCOH represents the average total cost per unit of heat produced ($ct/kWh$). It accounts for the time-value of money via the Capital Recovery Factor.")
        st.latex(r"LCOH = \frac{(CAPEX_{net} \cdot CRF) + OPEX_{fixed}}{Utilization} + \frac{P_{fuel\_eff}}{Efficiency}")
        
        st.markdown("**2. Capital Recovery Factor (CRF)**")
        st.write("Used to annualize the investment costs over the asset's economic lifetime ($n$) at a specific discount rate ($i$).")
        st.latex(r"CRF = \frac{i(1+i)^n}{(1+i)^n - 1}")
        
        st.markdown("**3. Net Present Value (NPV)**")
        st.write("Determines the total value added compared to a Gas Boiler baseline over the technology's life.")
        st.latex(r"NPV = \sum_{t=1}^{n} \frac{S_t}{(1+i)^t} - \Delta CAPEX")
        st.caption("Where $S_t$ is annual operating savings and $\Delta CAPEX$ is the incremental upfront cost.")

    with m_col2:
        st.subheader("Carbon & Policy Logic")
        st.markdown("**Carbon Pricing ($P_{g\_effective}$)**")
        st.write("The effective gas price includes the market commodity price plus the carbon surcharge based on the technology-specific emission factor.")
        st.latex(r"P_{g\_eff} = P_{g\_market} + (\text{Carbon Tax} \cdot \epsilon)")
        st.write(f"Standard Natural Gas Emission Factor ($\epsilon$): **{EMISSION_FACTOR} kgCO2/kWh**")
        
        st.markdown("**German Industriestrompreis (Section 24c EnWG)**")
        st.write("The model implements the 2024-2028 German electricity price bridge. This involves two primary mechanisms:")
        st.markdown("""
        * **Commodity Cap:** A state-funded cap of 5.0 ct/kWh applied to 50% of reference consumption for eligible sectors.
        * **Levy Reductions:** The abolition of the EEG-Umlage and the stabilization of the 'Stromnebenkosten' (grid fees).
        """)

    st.divider()
    
    st.subheader("Data Sources & Literature")
    st.markdown("""
    * **Energy Prices:** [Eurostat - Energy price statistics](https://ec.europa.eu/eurostat/statistics-explained/index.php?title=Energy_price_statistics)
    * **German Policy Data:** [BMWK - Industriestrompreis Dokumentation](https://www.bundesregierung.de/breg-en/news/reduction-in-energy-prices-2358994)
    * **Emission Factors:** [IPCC - Emission Factor Database](https://www.ipcc-nggip.iges.or.jp/EFDB/main.php)
    """)
    
    # Methodology Download for PhD Appendix
    methodology_text = f"""
    IND-HEAT Framework Analysis
    Selected Countries: {', '.join(selected_countries)}
    WACC: {discount_rate*100}%
    Baseline Emission Factor: {EMISSION_FACTOR} kgCO2/kWh
    """
    st.download_button("Download Methodology Summary (TXT)", data=methodology_text, file_name="Methodology_Summary.txt")