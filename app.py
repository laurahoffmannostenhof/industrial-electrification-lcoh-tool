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
    "Germany": {"gas": 5.5, "elec": 18, "tax": 80, "subsidy": 30, "currency": "€", "unit": "ct/kWh"},
    "UK":      {"gas": 6.5, "elec": 22, "tax": 50, "subsidy": 20, "currency": "£", "unit": "p/kWh"},
    "USA":     {"gas": 2.0, "elec": 8, "tax": 0,  "subsidy": 0,  "currency": "$", "unit": "ct/kWh"}
}

TECH_DEFAULTS = {
    "Gas Boiler":      {"capex": 55,   "opex": 1.16, "eff": 0.95, "life": 20, "util": 8000, "fuel": "Gas"},
    "Electric Boiler": {"capex": 120,  "opex": 0.58, "eff": 0.99, "life": 15, "util": 8000, "fuel": "Elec"},
    "High Temperature Heat Pump":    {"capex": 1200, "opex": 0.60, "eff": 2.20, "life": 15, "util": 8000, "fuel": "Elec"},
    "Mechanical Vapor Recompression": {"capex": 1500, "opex": 0.40, "eff": 4.50, "life": 20, "util": 8000, "fuel": "Elec"},
    "Low Temperature Heat Pump":     {"capex": 500,  "opex": 0.50, "eff": 4.00, "life": 15, "util": 7500, "fuel": "Elec"},
    "Microwave":       {"capex": 700,  "opex": 10.0, "eff": 0.85, "life": 12, "util": 4000, "fuel": "Elec"}
}

GERMANY_NON_COMMODITY = {"grid_fee": 2.860, "offshore": 0.941, "kwkg": 0.446, "stromnev": 1.559, "tax": 0.050}
EMISSION_FACTOR = 0.202 # kgCO2/kWh gas

# --- 3. SIDEBAR ---
with st.sidebar:
    st.header("Scope & Global Financials")
    selected_countries = st.multiselect("Select Countries", options=list(COUNTRY_DEFAULTS.keys()), default=["Germany"])
    selected_techs = st.multiselect("Select Technologies", options=list(TECH_DEFAULTS.keys()), default=["Gas Boiler", "Electric Boiler", "High Temperature Heat Pump"])
    discount_rate = st.slider("WACC / Discount Rate (%)", 1, 20, 7) / 100
    st.divider()
    st.info("Tip: Use the Strategic Results tabs at the bottom to compare Net Present Value (NPV) and Payback periods.")

# --- 4. CATEGORICAL INPUT DASHBOARD ---
st.title("Industrial Heat Electrification Parity Engine")
st.markdown("A Multi-Level Analytical System for Economics, Markets, and Policy by Laura Hoffmann-Ostenhof. Work in Progress - Feedback Welcome!")

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
            unit = COUNTRY_DEFAULTS[country]['unit']
            if country == "Germany":
                comm_p = st.number_input(f"Wholesale/Commodity ({unit})", 1.0, 30.0, 9.5, format="%.1f", key=f"comm_{country}") / 100
                bridge_active = st.checkbox("Apply Industriestrompreis (Bridge Price)", value=True, key=f"bridge_{country}")
                
                # Detailed Explanation of the mechanism
                non_comm_val = sum(GERMANY_NON_COMMODITY.values())
                st.markdown(f"""
                **Mechanism Explanation:**
                The Industriestrompreis reduces the commodity cost for energy-intensive firms. 
                It caps 50% of the volume at **5.0 ct/kWh**. The effective price ($P_{{e\\\_eff}}$) 
                is the weighted average of this cap and the current wholesale market price, 
                plus fixed non-commodity levies. 
                
                These non-commodity charges (grid fees, statutory levies, and electricity tax) 
                currently total approximately **{non_comm_val:.3f} ct/kWh**. Please refer to the 
                **Methodology** tab for a detailed breakdown and references.
                """)
                
                non_comm_sum = non_comm_val / 100
                p_market_total = comm_p + non_comm_sum
                p_eff_comm = (max(min(comm_p, 0.050), 0.050) * 0.5 + comm_p * 0.5) if bridge_active else comm_p
                p_eff_total = p_eff_comm + non_comm_sum
            else:
                p_eff_total = st.number_input(f"Flat Elec Price ({unit})", 1.0, 50.0, float(COUNTRY_DEFAULTS[country]['elec']), key=f"e_{country}") / 100
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
            p_g_market = st.number_input(f"Base Gas Price ({unit})", 1.0, 30.0, COUNTRY_DEFAULTS[country]['gas'], format="%.1f", key=f"gp_{country}") / 100
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

        country_prices[country] = {"gas": p_g_effective, "elec": p_eff_total, "gas_base": p_g_market, "elec_raw": p_market_total, "sym": sym, "unit": unit}
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
t1, t2, t3, t4, t5 = st.tabs(["LCOH Comparison", "Financials", "Sensitivity", "Policy Gap Solver", "Methodology"])

with t1:
    fig_main, ax_main = plt.subplots(figsize=(10, 4))
    sns.barplot(data=df_res, x="Technology", y="LCOH", hue="Country", ax=ax_main, palette="viridis", edgecolor="0.2")
    ax_main.set_ylabel("LCOH (ct/p / kWh)", fontweight='bold')
    ax_main.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    sns.despine(left=True)
    st.pyplot(fig_main)

with t2:
    st.dataframe(df_res[["Country", "Technology", "LCOH", "NPV", "Payback"]], width='stretch')

with t3:
    if selected_countries:
        focus = st.selectbox("Select Country for Sensitivity", selected_countries)
        unit = country_prices[focus]['unit']
        e_range = np.linspace(0.01, 0.45, 100)
        fig_s, ax_s = plt.subplots(figsize=(10, 5))
        
        g_base = df_res[(df_res['Country'] == focus) & (df_res['Technology'] == "Gas Boiler")]['LCOH'].values[0]
        ax_s.axhline(g_base, color='black', linestyle='-', alpha=0.3, label="Gas Boiler (Baseline)")
        
        break_evens = []

        for tech in selected_techs:
            tp = tech_params[tech]
            if tp['fuel'] == "Elec":
                crf = (discount_rate * (1 + discount_rate)**tp['life']) / ((1 + discount_rate)**tp['life'] - 1)
                fixed_costs = (((tp['capex'] * (1 - country_incentives[focus]['subsidy']/100)) * crf) + tp['opex']) / tp['util'] * 100
                y_vals = [fixed_costs + (p / tp['eff'] * 100) for p in e_range]
                line, = ax_s.plot(e_range, y_vals, label=tech, lw=2)
                
                be_price = (g_base - fixed_costs) * tp['eff'] / 100
                
                if 0.01 <= be_price <= 0.45:
                    break_evens.append((tech, be_price, line.get_color()))

        for tech, price, color in break_evens:
            ax_s.axvline(price, color=color, linestyle='--', alpha=0.6)
            ax_s.text(price + 0.005, ax_s.get_ylim()[1]*0.9, f"{price:.3f}", 
                      color=color, rotation=90, fontweight='bold', fontsize=9)

        ax_s.set_title(f"Break-even Sensitivity: {focus}", fontweight='bold')
        ax_s.set_xlabel(f"Electricity Price ({unit})", fontweight='bold')
        ax_s.set_ylabel(f"LCOH ({unit})", fontweight='bold')
        ax_s.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        st.pyplot(fig_s)

        st.markdown("### How to Interpret this Graph")
        cols = st.columns(len(break_evens) if break_evens else 1)
        for i, (tech, price, color) in enumerate(break_evens):
            with cols[i]:
                st.metric(f"Switching Price: {tech}", f"{price:.3f} {unit}")
                st.write(f"If electricity is **below** this price, {tech} is the cheaper strategic choice.")

with t4:
    st.header("Policy Stack & Gap Solver")
    
    if selected_countries:
        # 1. SETUP
        s_country = st.selectbox("Select Country", selected_countries, key="stack_country_v6")
        s_tech = st.selectbox("Select Tech", [t for t in selected_techs if t != "Gas Boiler"], key="stack_tech_v6")
        
        cp, ci, tp = country_prices[s_country], country_incentives[s_country], tech_params[s_tech]
        gb = tech_params.get("Gas Boiler", TECH_DEFAULTS["Gas Boiler"])
        
        # Financial Constants
        crf_gb = (discount_rate * (1 + discount_rate)**gb['life']) / ((1 + discount_rate)**gb['life'] - 1)
        crf_t = (discount_rate * (1 + discount_rate)**tp['life']) / ((1 + discount_rate)**tp['life'] - 1)

        # --- STEP 1: CURRENT LEVELS (Market Baseline) ---
        m_gas_lcoh = (((gb['capex'] * crf_gb) + gb['opex']) / gb['util'] * 100) + (cp['gas_base'] / gb['eff'] * 100)
        m_elec_lcoh = ((tp['capex'] * crf_t) + tp['opex']) / tp['util'] * 100 + (cp['elec_raw'] / tp['eff'] * 100)
        market_gap = m_elec_lcoh - m_gas_lcoh

        # --- STEP 2: POLICY ADJUSTED REQUIREMENT ---
        # Flows into Gas
        tax_impact = (ci['tax'] * EMISSION_FACTOR / 1000 / gb['eff'] * 100)
        # Flows into Elec
        subsidy_savings = ((tp['capex'] * (ci['subsidy']/100)) * crf_t) / tp['util'] * 100
        bridge_savings = ((cp['elec_raw'] - cp['elec']) / tp['eff'] * 100)
        
        current_gas_lcoh = m_gas_lcoh + tax_impact
        current_elec_lcoh = m_elec_lcoh - subsidy_savings - bridge_savings
        residual_gap = current_elec_lcoh - current_gas_lcoh

        # DISPLAY METRICS
        st.subheader("1. Current Levels vs. Policy Impacts")
        c1, c2, c3 = st.columns(3)
        c1.metric("Market Gap", f"{market_gap:.2f} ct/kWh")
        c2.metric("Total Policy Support", f"-{(tax_impact + subsidy_savings + bridge_savings):.2f} ct/kWh")
        c3.metric("Residual Gap", f"{max(0, residual_gap):.2f} ct/kWh", 
                  delta="Parity Reached" if residual_gap <= 0 else f"+{residual_gap:.2f} shift needed",
                  delta_color="normal" if residual_gap <= 0 else "inverse")

        st.divider()

        # --- STEP 3: VISUALIZING THE GAP ---
        st.subheader("2. Visualizing the Stack")
        
        fig, ax = plt.subplots(figsize=(10, 5))
        scenarios = ["Market Baseline", "Policy Adjusted"]
        gas_vals = [m_gas_lcoh, current_gas_lcoh]
        elec_vals = [m_elec_lcoh, current_elec_lcoh]
        
        x = np.arange(len(scenarios))
        ax.bar(x - 0.2, gas_vals, 0.4, label='Gas Boiler', color='#95a5a6', edgecolor='black')
        ax.bar(x + 0.2, elec_vals, 0.4, label=s_tech, color='#3498db', edgecolor='black')
        
        # Parity Line (Target)
        ax.axhline(current_gas_lcoh, color='#e67e22', linestyle='--', lw=2, label="Parity Target", alpha=0.8)
        
        # Annotate Residual Gap
        if residual_gap > 0:
            ax.annotate('', xy=(1.25, current_gas_lcoh), xytext=(1.25, current_elec_lcoh),
                         arrowprops=dict(arrowstyle='<->', color='#c0392b', lw=2))
            ax.text(1.3, (current_elec_lcoh + current_gas_lcoh)/2, f'Gap: {residual_gap:.2f} ct', 
                     color='#c0392b', fontweight='bold', va='center')

        ax.set_ylabel("LCOH (ct/kWh)", fontweight='bold')
        ax.set_xticks(x)
        ax.set_xticklabels(scenarios)
        ax.legend(loc='upper right')
        sns.despine()
        st.pyplot(fig)

        st.divider()

        # --- STEP 4: CLOSING THE GAP (Menu of Solutions) ---
        st.subheader("3. Closing the Residual Gap")
        if residual_gap > 0:
            st.write("To eliminate the remaining gap, apply **one or a combination** of these further shifts:")
            
            # Additional required shifts
            add_tax = residual_gap * (gb['eff'] / 100) / (EMISSION_FACTOR / 1000)
            add_subsidy = (residual_gap * tp['util'] / 100) / (tp['capex'] * crf_t) * 100
            add_price_drop = residual_gap * tp['eff'] / 100

            s1, s2, s3 = st.columns(3)
            with s1:
                st.info("**Option A: Carbon Tax**")
                st.write(f"Add **+{add_tax:.1f} €/t**")
                st.caption(f"New Total: {ci['tax'] + add_tax:.1f} €/t")
            with s2:
                st.info("**Option B: CAPEX Subsidy**")
                st.write(f"Add **+{add_subsidy:.1f}%**")
                st.caption(f"New Total: {min(100, ci['subsidy'] + add_subsidy):.1f}%")
            with s3:
                st.info("**Option C: Elec Price**")
                st.write(f"Drop **-{add_price_drop:.2f} ct**")
                st.caption(f"New Total: {(cp['elec']*100) - add_price_drop:.2f} ct/kWh")
        else:
            st.success("✅ **Economic Parity Reached.** Current policy settings have successfully closed the gap.")

        # --- FLOW DENOTATION ---
        with st.expander("Technical Breakdown: Flow Logic"):
            st.markdown(f"""
            **How the Requirement is Adjusted:**
            * **Market Starting Point:** Gas starts at `{m_gas_lcoh:.2f} ct` and {s_tech} at `{m_elec_lcoh:.2f} ct`.
            * **Flow 1 (Carbon Tax):** Increases Gas LCOH by `{tax_impact:.2f} ct`.
            * **Flow 2 (CAPEX Subsidy):** Decreases {s_tech} LCOH by `{subsidy_savings:.2f} ct`.
            * **Flow 3 (Energy Bridge):** Decreases {s_tech} LCOH by `{bridge_savings:.2f} ct`.
            * **Result:** The **Residual Gap** is the difference between these final adjusted levels.
            """)

with t5:
    st.header("Techno-Economic Methodology & Data Sources")
    
    m_col1, m_col2 = st.columns(2)
    
    with m_col1:
        st.subheader("Economic Equations")
        st.markdown("**1. Levelized Cost of Heat (LCOH)**")
        st.latex(r"LCOH = \frac{(CAPEX_{net} \cdot CRF) + OPEX_{fixed}}{Utilization} + \frac{P_{fuel\_eff}}{Efficiency}")
        
        st.markdown("**2. Capital Recovery Factor (CRF)**")
        st.latex(r"CRF = \frac{i(1+i)^n}{(1+i)^n - 1}")
        
        st.markdown("**3. Net Present Value (NPV)**")
        st.latex(r"NPV = \sum_{t=1}^{n} \frac{S_t}{(1+i)^t} - \Delta CAPEX")

    with m_col2:
        st.subheader("German Policy Framework: Bridge Price Mechanism")
        st.write("The model implements the **Industriestrompreis** (Section 24c EnWG) logic as follows:")
        st.markdown("""
        * **Commodity Cap:** Eligible firms receive a weighted price where 50% of reference consumption is capped at **5.0 ct/kWh**.
        * **Grid Fee Stabilization:** The framework accounts for the 2024 grid fee subsidy reduction, resulting in the current benchmark charges.
        """)
        
        st.subheader("Non-Commodity Charges Breakdown (Germany)")
        levy_df = pd.DataFrame({
            "Component": ["Grid Fees", "Offshore Levy", "KWKG Levy", "StromNEV (§19)", "Electricity Tax"],
            "Value [ct/kWh]": [2.860, 0.941, 0.446, 1.559, 0.050],
            "Legal Basis": ["Netzentgelte", "EnFG §12", "KWKG §26", "StromNEV §19", "StromStG §3"]
        })
        st.table(levy_df)
        st.caption("Benchmark values based on 2024/2025 jurisdictional data.")

    st.divider()
    
    st.subheader("Data Sources & Literature")
    st.markdown("""
    * **Bridge Price Policy:** [BMWK - Industriestrompreis Strategy Document](https://www.bundesregierung.de/breg-en/news/reduction-in-energy-prices-2358994)
    * **Energy Prices:** [Eurostat - Energy price statistics](https://ec.europa.eu/eurostat/statistics-explained/index.php?title=Energy_price_statistics)
    * **Emission Factors:** [IPCC - Emission Factor Database](https://www.ipcc-nggip.iges.or.jp/EFDB/main.php)
    """)