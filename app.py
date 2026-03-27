import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# 1. Page Setup
st.set_page_config(page_title="Heat Decarbonization Tool", layout="wide")
st.title("🔥 Industrial Heat: Techno-Economic Policy Tool")

# 2. Sidebar for Policy Interventions
st.sidebar.header("Step 1: Policy Settings")
carbon_tax = st.sidebar.slider("Carbon Tax ($/tonne CO2)", 0, 500, 80)
elec_cap = st.sidebar.slider("Electricity Price Cap ($/kWh)", 0.05, 0.30, 0.18)

st.sidebar.header("Step 2: Market Prices")
gas_price = st.sidebar.number_input("Base Gas Price ($/kWh)", value=0.055, format="%.3f")

# 3. File Upload Logic
st.sidebar.header("Step 3: Data Input")
uploaded_file = st.sidebar.file_uploader("Upload tech_inputs.csv", type="csv")

# Use uploaded data or default to the template values
if uploaded_file is not None:
    df = pd.read_csv(uploaded_file)
else:
    st.info("Using default template data. Upload your own CSV in the sidebar to update.")
    df = pd.read_csv("tech_inputs.csv")

# 4. The Math (LCOH Engine)
def calculate_lcoh(row):
    crf = (0.07 * (1 + 0.07)**20) / ((1 + 0.07)**20 - 1)
    # Use the 'Mid' point of the ranges provided
    capex = (row['Capex_Min'] + row['Capex_Max']) / 2
    eff = (row['Eff_Min'] + row['Eff_Max']) / 2
    
    # Apply Policy Caps
    current_fuel = elec_cap if row['Fuel_Type'] == "Electricity" else gas_price
    
    # Add Carbon Tax to Gas
    if row['Fuel_Type'] == "Gas":
        current_fuel += (carbon_tax * 0.202 / 1000)
        
    fixed = ((capex * crf) + row['Opex_Fixed']) / 8000 * 100
    variable = (current_fuel / eff) * 100
    return fixed + variable

df['LCOH'] = df.apply(calculate_lcoh, axis=1)

# 5. Display Results
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("Levelized Cost of Heat (ct/kWh)")
    fig, ax = plt.subplots()
    colors = ['#4F4F4F' if x == "Gas" else '#3498db' for x in df['Fuel_Type']]
    ax.bar(df['Technology'], df['LCOH'], color=colors)
    ax.set_ylabel("ct/kWh")
    st.pyplot(fig)

with col2:
    st.subheader("Calculated Values")
    st.dataframe(df[['Technology', 'LCOH']].style.format({"LCOH": "{:.2f}"}))

# Download link for the template
st.sidebar.download_button("Download Template CSV", data=open("tech_inputs.csv").read(), file_name="template.csv")
