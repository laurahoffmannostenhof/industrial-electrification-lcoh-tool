import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

# --- 1. CONFIG ---
st.set_page_config(page_title="Heat Decarbonization Tool", layout="wide")
st.title("🛡️ Industrial Heat Techno-Economic Suite")

# --- 2. SIDEBAR / INPUTS ---
with st.sidebar:
    st.header("📈 Market Parameters")
    gas_p = st.slider("Natural Gas ($/kWh)", 0.02, 0.15, 0.06, help="Industrial retail price")
    elec_p = st.slider("Electricity ($/kWh)", 0.05, 0.40, 0.18)
    c_tax = st.number_input("Carbon Tax ($/tCO2)", 0, 500, 80)
    
    st.divider()
    st.header("📂 Data Source")
    uploaded = st.file_uploader("Upload tech_inputs.csv", type="csv")

# Load Data
if uploaded:
    df = pd.read_csv(uploaded)
else:
    # Reliable fallback data
    df = pd.DataFrame({
        "Technology": ["Natural Gas Boiler", "Electric Boiler", "High-Temp Heat Pump", "Mechanical Vapor Recompression"],
        "Capex": [60, 130, 1000, 1250],
        "Opex": [1.2, 0.6, 0.5, 10.0],
        "Eff": [0.95, 0.99, 3.2, 7.5],
        "Fuel": ["Gas", "Elec", "Elec", "Elec"]
    })

# --- 3. MATH ENGINE ---
CRF = 0.0944 # 7% over 20 years
HRS = 8000
EF = 0.202 # kgCO2/kWh

def calc_lcoh(row, g, e, t):
    fuel_price = (g + (t * EF / 1000)) if row['Fuel'] == "Gas" else e
    fixed = ((row['Capex'] * CRF) + row['Opex']) / HRS * 100
    variable = (fuel_price / row['Eff']) * 100
    return fixed + variable

df['LCOH'] = df.apply(lambda x: calc_lcoh(x, gas_p, elec_p, c_tax), axis=1)

# Find the winner (lowest LCOH)
winner = df.loc[df['LCOH'].idxmin()]

# --- 4. DASHBOARD LAYOUT ---

# Top Row: Key Metrics
col1, col2, col3 = st.columns(3)
col1.metric("Lowest Cost Tech", winner['Technology'])
col2.metric("Min LCOH", f"{winner['LCOH']:.2f} ct/kWh")
col3.metric("Carbon Impact", f"{c_tax} $/tCO2", delta=f"{c_tax - 80} vs Base")

st.divider()

tab1, tab2, tab3 = st.tabs(["📊 Cost Comparison", "🗺️ Sensitivity Analysis", "📄 Technical Data"])

with tab1:
    fig, ax = plt.subplots(figsize=(10, 4))
    sns.barplot(data=df, x='Technology', y='LCOH', hue='Fuel', palette={'Gas': '#454545', 'Elec': '#3498db'}, ax=ax)
    ax.axhline(df[df['Fuel']=='Gas']['LCOH'].values[0], color='red', linestyle='--', alpha=0.7, label='Gas Baseline')
    ax.set_title("Levelized Cost of Heat by Technology")
    st.pyplot(fig)

with tab2:
    st.subheader("Electricity vs. Gas Sensitivity")
    st.write("How the winner changes as fuel prices shift:")
    
    # Create a sensitivity matrix for the Winner vs Gas
    g_range = np.linspace(0.02, 0.12, 10)
    e_range = np.linspace(0.05, 0.30, 10)
    matrix = np.zeros((len(e_range), len(g_range)))
    
    # Calculate which is cheaper: Best Electric Tech or Gas Boiler
    best_elec = df[df['Fuel'] == 'Elec'].copy()
    
    for i, e in enumerate(e_range):
        for j, g in enumerate(g_range):
            gas_lcoh = calc_lcoh(df.iloc[0], g, e, c_tax)
            elec_lcoh = min([calc_lcoh(row, g, e, c_tax) for _, row in best_elec.iterrows()])
            matrix[i, j] = elec_lcoh - gas_lcoh # Negative means Elec is cheaper
            
    fig2