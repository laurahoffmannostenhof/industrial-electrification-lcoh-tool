import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

# --- 1. SETUP ---
st.set_page_config(page_title="Industrial Heat Analysis", layout="wide")
st.title("📊 Industrial Heat: Multi-Metric Analysis")
st.markdown("This tool calculates heat costs based strictly on your uploaded technology parameters.")

# --- 2. DATA INPUT ---
uploaded_file = st.sidebar.file_uploader("Upload your tech_inputs.csv", type="csv")

if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
else:
    # Use the template we created earlier as the default
    df = pd.read_csv("tech_inputs.csv")

# --- 3. THE CALCULATION ENGINE ---
def run_calculations(data):
    # Standard Constants
    CRF = (0.07 * (1 + 0.07)**20) / ((1 + 0.07)**20 - 1)
    HRS = 8000
    GAS_PRICE = 0.06  # Base default
    ELEC_PRICE = 0.18 # Base default

    # Derived Columns
    data['Avg_Capex'] = (data['Capex_Min'] + data['Capex_Max']) / 2
    data['Avg_Eff'] = (data['Eff_Min'] + data['Eff_Max']) / 2
    
    # Calculate Fixed Portion (Hardware + Maintenance)
    data['Fixed_LCOH'] = ((data['Avg_Capex'] * CRF) + data['Opex_Fixed']) / HRS * 100
    
    # Calculate Variable Portion (Fuel)
    data['Fuel_Price'] = np.where(data['Fuel_Type'] == 'Gas', GAS_PRICE, ELEC_PRICE)
    data['Variable_LCOH'] = (data['Fuel_Price'] / data['Avg_Eff']) * 100
    
    data['Total_LCOH'] = data['Fixed_LCOH'] + data['Variable_LCOH']
    return data

df = run_calculations(df)

# --- 4. THE INTERFACE (TABS) ---
tab1, tab2, tab3 = st.tabs(["🏆 LCOH Comparison", "🏗️ Cost Structure", "🎯 Efficiency Map"])

with tab1:
    st.subheader("Total Levelized Cost of Heat")
    fig1, ax1 = plt.subplots(figsize=(10, 4))
    ax1.bar(df['Technology'], df['Total_LCOH'], color='#3498db', edgecolor='black')
    ax1.set_ylabel("ct/kWh")
    plt.xticks(rotation=45)
    st.pyplot(fig1)

with tab2:
    st.subheader("CAPEX vs. Fuel Breakdown")
    # Stacked Bar Chart
    fig2, ax2 = plt.subplots(figsize=(10, 4))
    ax2.bar(df['Technology'], df['Fixed_LCOH'], label='CAPEX & OPEX (Fixed)', color='#2c3e50')
    ax2.bar(df['Technology'], df['Variable_LCOH'], bottom=df['Fixed_LCOH'], label='Fuel Cost (Variable)', color='#e74c3c')
    ax2.set_ylabel("ct/kWh")
    ax2.legend()
    plt.xticks(rotation=45)
    st.pyplot(fig2)

with tab3:
    st.subheader("Efficiency vs. Total Cost")
    # Scatter plot to show "The Sweet Spot"
    fig3, ax3 = plt.subplots(figsize=(10, 4))
    for i, txt in enumerate(df['Technology']):
        ax3.scatter(df.loc[i, 'Avg_Eff'], df.loc[i, 'Total_LCOH'], s=100)
        ax3.annotate(txt, (df.loc[i, 'Avg_Eff'], df.loc[i, 'Total_LCOH'] + 0.5))
    
    ax3.set_xlabel("Efficiency (COP / %)")
    ax3.set_ylabel("Total LCOH (ct/kWh)")
    ax3.grid(True, linestyle='--', alpha=0.6)
    st.pyplot(fig3)

# --- 5. DATA VIEW ---
st.divider()
st.subheader("Raw Results Table")
st.dataframe(df[['Technology', 'Fuel_Type', 'Fixed_LCOH', 'Variable_LCOH', 'Total_LCOH']].style.format("{:.2f}", subset=['Fixed_LCOH', 'Variable_LCOH', 'Total_LCOH']))