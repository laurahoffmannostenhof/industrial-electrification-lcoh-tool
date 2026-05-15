import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import io

# --- 1. CONFIG & STYLE ---
st.set_page_config(page_title="Industrial Heat Strategy Tool", layout="wide")
plt.style.use('seaborn-v0_8-whitegrid')

# --- 2. DATA DEFAULTS (SPLIT USA) ---
COUNTRY_DEFAULTS = {
    "Germany": {"gas": 5.5, "elec": 18, "tax": 80, "subsidy": 30, "currency": "€", "unit": "ct/kWh"},
    "UK":      {"gas": 6.5, "elec": 22, "tax": 50, "subsidy": 20, "currency": "£", "unit": "p/kWh"},
    "USA - California": {"gas": 4.8, "elec": 26, "tax": 10, "subsidy": 40, "currency": "$", "unit": "ct/kWh"},
    "USA - Texas":      {"gas": 2.2, "elec": 9, "tax": 0, "subsidy": 0, "currency": "$", "unit": "ct/kWh"}
}

TECH_DEFAULTS = {
    "Gas Boiler":      {"capex": 55,   "opex": 1.16, "eff": 0.95, "life": 20, "util": 8000, "fuel": "Gas"},
    "Electric Boiler": {"capex": 120,  "opex": 0.58, "eff": 0.99, "life": 15, "util": 8000, "fuel": "Elec"},
    "High Temperature Heat Pump":    {"capex": 1200, "opex": 0.60, "eff": 2.20, "life": 15, "util": 8000, "fuel": "Elec"},
    "Mechanical Vapor Reconversion": {"capex": 1500, "opex": 0.40, "eff": 4.50, "life": 20, "util": 8000, "fuel": "Elec"},
    "Low Temperature Heat Pump":     {"capex": 500,  "opex": 0.50, "eff": 4.00, "life": 15, "util": 7500, "fuel": "Elec"},
    "Microwave":       {"capex": 700,  "opex": 10.0, "eff": 0.85, "life": 12, "util": 4000, "fuel": "Elec"}
}

GERMANY_NON_COMMODITY = {"grid_fee": 2.860, "offshore": 0.941, "kwkg": 0.446, "stromnev": 1.559, "tax": 0.050}
EMISSION_FACTOR = 0.202 # kgCO2/kWh gas

# --- 3. SIDEBAR ---
with st.sidebar:
    st.header("Scope & Global Financials")
    selected_countries = st.multiselect("Select Jurisdictions", options=list(COUNTRY_DEFAULTS.keys()), default=["Germany", "USA - Texas"])
    selected_techs = st.multiselect("Select Technologies", options=list(TECH_DEFAULTS.keys()), default=["Gas Boiler", "Electric Boiler", "High Temperature Heat Pump"])
    discount_rate = st.slider("WACC / Discount Rate (%)", 1, 20, 7) / 100

# --- 4. CATEGORICAL INPUT DASHBOARD ---
st.title("Techno-Economic Platform for Evaluating Thermal Decarbonization and Switching Price Dynamics")
st.markdown("Assess industrial heat electrification across Germany, UK, California, and Texas. By Laura Hoffmann-Ostenhof. Work in Progress. Feedback welcome!")

country_prices = {}
country_incentives = {}

for country in selected_countries:
    sym = COUNTRY_DEFAULTS[country]['currency']
    unit = COUNTRY_DEFAULTS[country]['unit']
    
    with st.container(border=True):
        st.subheader(f"{country} Policy Framework")
        
        # CATEGORY A: ELECTRICITY & BRIDGE PRICE
        st.markdown("#### Electricity & Grid Policy")
        c1, c2 = st.columns([1, 1])
        with c1:
            comm_p = st.number_input(f"Wholesale/Commodity ({unit})", 0.5, 40.0, float(COUNTRY_DEFAULTS[country]['elec']) * 0.6, format="%.1f", key=f"comm_{country}") / 100
            
            with st.expander("Advanced Bill & Policy Relief Settings"):
                if country == "Germany":
                    grid = st.number_input("Grid Fees (ct/kWh)", 0.0, 10.0, GERMANY_NON_COMMODITY['grid_fee'], key=f"grid_{country}")
                    levies = st.number_input("Statutory Levies (ct/kWh)", 0.0, 10.0, 2.946, key=f"levy_{country}")
                    e_tax = st.number_input("Electricity Tax (ct/kWh)", 0.0, 5.0, 0.05, key=f"etax_{country}")
                    relief = 0
                    if st.checkbox("Apply Industriestrompreis (Section 24c EnWG)", value=True, key=f"bridge_{country}"):
                        relief = max(0, (comm_p * 100) - 5.0) * 0.5
                    non_comm_sum = (grid + levies + e_tax) / 100
                
                elif country == "UK":
                    grid = st.number_input("T&D Charges (p/kWh)", 0.0, 15.0, 4.5, key=f"grid_{country}")
                    levies = st.number_input("Policy Levies (p/kWh)", 0.0, 15.0, 3.2, key=f"levy_{country}")
                    relief = 0
                    if st.checkbox("IETF Phase 3 Levy Exemption", value=True, key=f"ietf_{country}"):
                        relief = 2.8
                    non_comm_sum = (grid + levies) / 100
                
                elif country == "USA - California":
                    grid = st.number_input("Public Purpose & T&D", 0.0, 20.0, 10.5, key=f"grid_{country}")
                    relief = 0
                    if st.checkbox("SGIP / Load Shifting Credit", value=True, key=f"sgip_{country}"):
                        relief = 3.5
                    non_comm_sum = grid / 100

                else: # USA - Texas
                    grid = st.number_input("Transmission (TCOS) & Distribution", 0.0, 10.0, 3.8, key=f"grid_{country}")
                    relief = 0
                    if st.checkbox("ERCOT 4CP Avoidance Logic", value=True, key=f"tcp_{country}"):
                        relief = grid * 0.75
                    non_comm_sum = grid / 100

            p_market_total = comm_p + non_comm_sum
            p_eff_comm = comm_p - (relief/100)
            p_eff_total = p_eff_comm + non_comm_sum

        with c2:
            fig_e, ax_e = plt.subplots(figsize=(5, 1.8))
            ax_e.barh(["Pe_market", "Pe_eff"], [comm_p*100, p_eff_comm*100], color='#3498db', label="Commodity")
            ax_e.barh(["Pe_market", "Pe_eff"], [non_comm_sum*100, non_comm_sum*100], left=[comm_p*100, p_eff_comm*100], color='#95a5a6', label="Non-Commodity")
            ax_e.set_xlabel(f"{unit}", fontsize=8)
            ax_e.tick_params(labelsize=8); ax_e.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize='xx-small')
            st.pyplot(fig_e)

        # CATEGORY B: GAS & CARBON
        st.markdown("#### Gas & Carbon Policy")
        c3, c4 = st.columns([1, 1])
        with c3:
            p_g_market = st.number_input(f"Base Gas Price ({unit})", 0.5, 30.0, COUNTRY_DEFAULTS[country]['gas'], format="%.1f", key=f"gp_{country}") / 100
            c_tax = st.number_input(f"Carbon Tax ({sym}/tCO2)", 0, 500, COUNTRY_DEFAULTS[country]['tax'], key=f"ctax_{country}")
            tax_impact = (c_tax * EMISSION_FACTOR / 1000)
            p_g_effective = p_g_market + tax_impact
        with c4:
            fig_g, ax_g = plt.subplots(figsize=(5, 1.2))
            ax_g.barh(["Pg_market", "Pg_effective"], [p_g_market*100, p_g_market*100], color='#e67e22', label="Base")
            ax_g.barh(["Pg_market", "Pg_effective"], [0, tax_impact*100], left=[p_g_market*100, p_g_market*100], color='#34495e', label="Carbon")
            ax_g.set_xlabel(f"{unit}", fontsize=8); ax_g.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize='xx-small')
            st.pyplot(fig_g)

        # CATEGORY C: CAPEX
        st.markdown("#### Investment Support")
        c5, c6 = st.columns([1, 1])
        with c5:
            subsidy = st.slider(f"CAPEX Subsidy (%)", 0, 100, COUNTRY_DEFAULTS[country]['subsidy'], key=f"sub_{country}")
        with c6:
            fig_c, ax_c = plt.subplots(figsize=(5, 1.2))
            ax_c.barh(["Investment"], [100 - subsidy], color='#2ecc71', label="Net")
            ax_c.barh(["Investment"], [subsidy], left=[100 - subsidy], color='#f1c40f', label="Subsidy")
            ax_c.set_xlabel("%", fontsize=8); ax_c.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize='xx-small')
            st.pyplot(fig_c)

        country_prices[country] = {"gas": p_g_effective, "elec": p_eff_total, "gas_base": p_g_market, "elec_raw": p_market_total, "sym": sym, "unit": unit}
        country_incentives[country] = {"tax": c_tax, "subsidy": subsidy}

# --- 5. TECH SPECS ---
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

# --- 6. CALCULATION ---
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
        lcoh = (((net_capex * crf_t) + tp['opex']) / tp['util'] * 100) + (f_price / tp['eff'] * 100)
        ann_savings = ((gas_lcoh / 100) * gb['util']) - (lcoh / 100 * tp['util'])
        capex_gap = net_capex - (gb['capex'] if tech != "Gas Boiler" else net_capex)
        pv_f = ((1 + discount_rate)**tp['life'] - 1) / (discount_rate * (1 + discount_rate)**tp['life'])
        results.append({"Country": country, "Symbol": cp['sym'], "Technology": tech, "LCOH": lcoh, "NPV": (ann_savings * pv_f) - capex_gap, "Payback": capex_gap / ann_savings if ann_savings > 0 else np.inf})

df_res = pd.DataFrame(results)

# --- 7. STRATEGIC RESULTS ---
st.header("3. Strategic Results")
t1, t2, t3, t4, t5, t6 = st.tabs(["LCOH Comparison", "Financials", "Sensitivity", "Policy Gap Solver", "Methodology", "Data Sources & Policy Frameworks (2026)"])

with t1:
    fig_main, ax_main = plt.subplots(figsize=(10, 4))
    sns.barplot(data=df_res, x="Technology", y="LCOH", hue="Country", ax=ax_main, palette="viridis", edgecolor="0.2")
    ax_main.set_ylabel("LCOH (ct/p / kWh)", fontweight='bold'); ax_main.legend(bbox_to_anchor=(1.05, 1), loc='upper left'); st.pyplot(fig_main)

with t2:
    st.dataframe(df_res[["Country", "Technology", "LCOH", "NPV", "Payback"]], width='stretch')

with t3:
    if selected_countries:
        focus = st.selectbox("Select Jurisdiction for Sensitivity", selected_countries)
        unit = country_prices[focus]['unit']; e_range = np.linspace(0.01, 0.45, 100); fig_s, ax_s = plt.subplots(figsize=(10, 5))
        g_base = df_res[(df_res['Country'] == focus) & (df_res['Technology'] == "Gas Boiler")]['LCOH'].values[0]
        ax_s.axhline(g_base, color='black', linestyle='-', alpha=0.3, label="Gas Baseline")
        for tech in selected_techs:
            tp = tech_params[tech]
            if tp['fuel'] == "Elec":
                crf = (discount_rate * (1 + discount_rate)**tp['life']) / ((1 + discount_rate)**tp['life'] - 1)
                fixed = (((tp['capex'] * (1 - country_incentives[focus]['subsidy']/100)) * crf) + tp['opex']) / tp['util'] * 100
                ax_s.plot(e_range, [fixed + (p / tp['eff'] * 100) for p in e_range], label=tech, lw=2)
        ax_s.set_xlabel(f"Electricity Price ({unit})"); ax_s.legend(); st.pyplot(fig_s)

with t4:
    st.header("Policy Stack & Gap Solver")
    
    # 1. TECHNOLOGY SELECTOR (Pick one to compare across all countries)
    s_tech = st.selectbox("Select Technology for Cross-Jurisdiction Analysis", 
                          [t for t in selected_techs if t != "Gas Boiler"], key="poster_tech_sel")
    
    # 2. DATA PREP FOR PLOTTING
    plot_data = []
    for country in selected_countries:
        cp, ci = country_prices[country], country_incentives[country]
        tp = tech_params[s_tech]
        gb = tech_params.get("Gas Boiler", TECH_DEFAULTS["Gas Boiler"])
        
        # Financial Constants
        crf_gb = (discount_rate * (1 + discount_rate)**gb['life']) / ((1 + discount_rate)**gb['life'] - 1)
        crf_t = (discount_rate * (1 + discount_rate)**tp['life']) / ((1 + discount_rate)**tp['life'] - 1)

        # MARKET BASELINE (No Policy)
        m_gas_lcoh = (((gb['capex'] * crf_gb) + gb['opex']) / gb['util'] * 100) + (cp['gas_base'] / gb['eff'] * 100)
        m_elec_lcoh = ((tp['capex'] * crf_t) + tp['opex']) / tp['util'] * 100 + (cp['elec_raw'] / tp['eff'] * 100)
        
        # POLICY IMPACTS
        tax_impact = (ci['tax'] * EMISSION_FACTOR / 1000 / gb['eff'] * 100) # Gas gets pricier
        subsidy_savings = ((tp['capex'] * (ci['subsidy']/100)) * crf_t) / tp['util'] * 100 # Elec gets cheaper
        bridge_savings = ((cp['elec_raw'] - cp['elec']) / tp['eff'] * 100) # Elec gets cheaper
        
        adj_gas_lcoh = m_gas_lcoh + tax_impact
        adj_elec_lcoh = m_elec_lcoh - subsidy_savings - bridge_savings
        
        plot_data.append({
            "Jurisdiction": country,
            "Market Gap": m_elec_lcoh - m_gas_lcoh,
            "Policy Support": -(tax_impact + subsidy_savings + bridge_savings),
            "Residual Gap": adj_elec_lcoh - adj_gas_lcoh,
            "Gas_Baseline": adj_gas_lcoh,
            "Elec_LCOH": adj_elec_lcoh
        })

    df_plot = pd.DataFrame(plot_data)

    # 3. THE "POSTER GRAPH"
    fig_p, ax_p = plt.subplots(figsize=(12, 6))
    x = np.arange(len(df_plot))
    width = 0.35

    # Plotting Market vs Policy Adjusted
    ax_p.bar(x - width/2, df_plot['Market Gap'], width, label='Raw Market Gap (No Policy)', color='#bdc3c7', edgecolor='black')
    ax_p.bar(x + width/2, df_plot['Residual Gap'], width, label='Residual Gap (With 2026 Policy)', color='#3498db', edgecolor='black')

    # Formatting for Academic Poster
    ax_p.axhline(0, color='black', lw=1.5)
    ax_p.set_xticks(x)
    ax_p.set_xticklabels(df_plot['Jurisdiction'], fontweight='bold')
    ax_p.set_ylabel("Cost Gap vs. Gas Boiler (ct/kWh)", fontweight='bold')
    ax_p.set_title(f"Economic Parity Gap for {s_tech}: Market vs. Policy Support", fontsize=14, fontweight='bold')
    ax_p.legend()
    
    # Annotate values for direct use in poster
    for i, val in enumerate(df_plot['Residual Gap']):
        ax_p.text(i + width/2, val + 0.2, f"{val:.2f}", ha='center', fontweight='bold', color='#2980b9')

    st.pyplot(fig_p)
    st.divider()

    # 4. POLICY INTERVENTION SIMULATOR
    st.subheader("Strategic Gap Closing: Intervention Menu")
    st.write("What further shifts are required to eliminate the **Residual Gap**?")
    
    for country in selected_countries:
        row = df_plot[df_plot['Jurisdiction'] == country].iloc[0]
        if row['Residual Gap'] > 0:
            with st.expander(f"Close the Gap in {country} (+{row['Residual Gap']:.2f} ct needed)"):
                # Back-calculating the shift required
                tp = tech_params[s_tech]
                crf_t = (discount_rate * (1 + discount_rate)**tp['life']) / ((1 + discount_rate)**tp['life'] - 1)
                
                req_tax = row['Residual Gap'] * (gb['eff'] / 100) / (EMISSION_FACTOR / 1000)
                req_sub = (row['Residual Gap'] * tp['util'] / 100) / (tp['capex'] * crf_t) * 100
                req_elec = row['Residual Gap'] * tp['eff'] / 100
                
                c1, c2, c3 = st.columns(3)
                c1.metric("Add Carbon Tax", f"+{req_tax:.1f} {country_prices[country]['sym']}/t")
                c2.metric("Add CAPEX Grant", f"+{req_sub:.1f}%")
                c3.metric("Reduce Elec Price", f"-{req_elec:.2f} ct")
                
                st.caption(f"Targeting LCOH Parity at {row['Gas_Baseline']:.2f} {country_prices[country]['unit']}")
        else:
            st.success(f"✅ {country}: {s_tech} has reached economic parity.")
with t5:
    st.header("Techno-Economic Methodology & Data Sources")
    m_col1, m_col2 = st.columns(2)
    with m_col1:
        st.subheader("Economic Equations")
        st.latex(r"LCOH = \frac{(CAPEX_{net} \cdot CRF) + OPEX_{fixed}}{Utilization} + \frac{P_{fuel\_eff}}{Efficiency}")
        st.latex(r"CRF = \frac{i(1+i)^n}{(1+i)^n - 1}")
        st.latex(r"NPV = \sum_{t=1}^{n} \frac{S_t}{(1+i)^t} - \Delta CAPEX")
    with m_col2:
        st.subheader("German Policy Framework: Bridge Price Mechanism")
        st.write("The model implements the **Industriestrompreis** (Section 24c EnWG) logic.")
        st.table(pd.DataFrame({"Component": ["Grid Fees", "Offshore Levy", "KWKG Levy", "StromNEV (§19)", "Electricity Tax"], "Value [ct/kWh]": [2.860, 0.941, 0.446, 1.559, 0.050]}))
    st.divider()
    st.markdown("* **Bridge Price Policy:** [BMWK](https://www.bundesregierung.de/breg-en/news/reduction-in-energy-prices-2358994)\n* **Energy Prices:** [Eurostat](https://ec.europa.eu/eurostat/statistics-explained/index.php?title=Energy_price_statistics)")

# --- ADDING TAB 6: DATA SOURCES & POLICY BACKING ---
# --- ADDING TAB 6: DATA SOURCES & POLICY BACKING ---
with t6:
    st.header("Data Sources & Policy Frameworks (2026)")
    st.markdown("""
    This section provides the evidentiary basis for the tool's default assumptions. 
    All calculations are mapped to specific 2026 regulatory updates and official government portals.
    """)
    
    col_a, col_b = st.columns(2)
    
    with col_a:
        st.subheader("📊 Operational & Price Relief (P_eff)")
        
        st.info("**Wholesale & Commodity Caps**")
        st.write("""
        * **Germany (Section 24c EnWG):** [BMWK Energy Laws Portal](https://www.bmwk.de/Navigation/DE/Service/Gesetze/Gesetze-und-Verordnungen/gesetze-und-verordnungen.html)  
          *Backs the 5.0 ct/kWh commodity cap for 50% volume.*
        * **UK (EII Exemption Scheme):** [GOV.UK British Industry Supercharger](https://www.gov.uk/government/publications/british-industry-supercharger)  
          *Backs the exemption from RO, FIT, and CFD costs for energy-intensive sectors.*
        """)
        
        st.info("**Grid Fee & T&D Optimization**")
        st.write("""
        * **USA - Texas (4CP Mechanism):** [ERCOT 4CP Financial Impacts](https://www.ercot.com/mktinfo/data_agg/4cp)  
          *Backs the ~75% TCOS reduction via peak load management.*
        * **Germany (StromNEV §19):** [BNetzA Grid Fee Regulation](https://www.bundesnetzagentur.de/EN/Areas/Energy/Companies/GridFees/GridFees_node.html)  
          *Backs the specific grid fee relief for consistent 'Bandlast' profiles.*
        * **USA - California (ACC Multipliers):** [CPUC Avoided Cost Calculator](https://www.cpuc.ca.gov/industries-and-topics/electrical-energy/demand-side-management/acc)  
          *Backs the hourly value multipliers for electrification load-shifting.*
        """)

    with col_b:
        st.subheader("🏗️ Capital Incentives & Grants (Subsidy)")
        
        st.info("**Direct CAPEX Grants**")
        st.write("""
        * **UK (IETF Phase 3):** [IETF Industrial Energy Transformation Fund](https://www.gov.uk/government/collections/industrial-energy-transformation-fund)  
          *Backs the default 20% grant assumption for deep decarbonization.*
        * **Germany (EEW Modules):** [BAFA Energy Efficiency in Economy](https://www.bafa.de/EN/Energy/Energy_Efficiency/Energy_Efficiency_in_Economy/energy_efficiency_in_economy_node.html)  
          *Backs the 30% default subsidy for Heat Pumps and MVR systems.*
        * **USA - California (SGIP):** [CPUC Self-Generation Incentive Program](https://www.cpuc.ca.gov/sgip/)  
          *Backs the capital rebate structure for thermal storage and load shifting.*
        """)
        
        st.info("**Carbon Pricing & Tax Benchmarks**")
        st.write("""
        * **EU/Germany (nEHS Pricing):** [DEHSt National Emissions Trading](https://www.dehst.de/EN/National-Emissions-Trading/national-emissions-trading_node.html)  
          *Backs the €80/tCO2 default carbon surcharge logic.*
        * **USA (Inflation Reduction Act 45V):** [IRS Clean Energy Tax Credits](https://www.irs.gov/clean-energy-tax-credits)  
          *Backs the federal tax credit eligibility for hydrogen and electrification.*
        """)

    st.divider()
    st.markdown("### Technical Calculation Standards")
    st.table(pd.DataFrame({
        "Mechanism": ["Emission Factors (Natural Gas)", "Industrial Gas Benchmarks", "Electricity Cost Statistics", "LCOH Calculation Standard"],
        "Source Agency": ["IPCC / DEFRA", "EIA (US) & Eurostat (EU)", "IEA Energy Prices", "NREL / Fraunhofer ISE"],
        "Verified Link": [
            "https://www.ipcc.ch/data/",
            "https://www.eia.gov/outlooks/aeo/",
            "https://www.iea.org/reports/energy-prices-and-taxes-for-oecd-countries",
            "https://www.nrel.gov/analysis/tech-lcoe.html"
        ]
    }))