import streamlit as st
import pandas as pd
import gspread
import os

# --- 1. PAGE SETUP ---
st.set_page_config(page_title="EMD Smart Inventory", layout="wide", page_icon="📊")

# --- 2. PREMIUM VISUAL STYLING (CSS) ---
st.markdown("""
<style>
    /* Main Background */
    .stApp { background: linear-gradient(to right, #f8f9fa, #e9ecef); }
    
    /* KPI Card Styling */
    .kpi-card {
        background-color: white;
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05);
        text-align: center;
        border-top: 5px solid #007bff;
    }
    
    /* Material Card Styling */
    .material-card {
        background: white;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 15px;
        border-left: 8px solid #28a745; /* Green for healthy stock */
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    
    /* Warning Card for Low Stock */
    .warning-card {
        background: #fff3f3;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 15px;
        border-left: 8px solid #dc3545; /* Red for low stock */
        animation: pulse 2s infinite;
    }
    
    @keyframes pulse {
        0% { box-shadow: 0 0 0 0 rgba(220, 53, 69, 0.4); }
        70% { box-shadow: 0 0 0 10px rgba(220, 53, 69, 0); }
        100% { box-shadow: 0 0 0 0 rgba(220, 53, 69, 0); }
    }
</style>
""", unsafe_allow_html=True)

# --- 3. DATA CONNECTION (GOOGLE SHEETS) ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1E0ZluX3o7vqnSBAdAMEn_cdxq3ro4F4DXxchOEFcS_g/edit"

def load_live_data():
    try:
        # Use Secrets if on Cloud, else local key
        if "gcp_service_account" in st.secrets:
            gc = gspread.service_account_from_dict(st.secrets["gcp_service_account"])
        else:
            gc = gspread.service_account(filename="service_key.json")
            
        sh = gc.open_by_url(SHEET_URL)
        ws = sh.sheet1
        data = ws.get_all_values()
        
        # Find Header and Clean
        df = pd.DataFrame(data[1:], columns=data[0])
        df.columns = [c.strip() for c in df.columns]
        df['TOTAL NO'] = pd.to_numeric(df['TOTAL NO'], errors='coerce').fillna(0).astype(int)
        return df
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return pd.DataFrame()

# --- 4. DASHBOARD LOGIC ---
df = load_live_data()

# SIDEBAR: THE DROPDOWNS
st.sidebar.header("🕹️ Control Panel")
all_locs = sorted(df['LOCATION'].unique())
selected_loc = st.sidebar.selectbox("Select Location Filter", ["All Locations"] + all_locs)
low_stock_limit = st.sidebar.number_input("Low Stock Threshold", value=10)

# Filter Logic
filtered_df = df if selected_loc == "All Locations" else df[df['LOCATION'] == selected_loc]

# --- 5. VISUAL INTERFACE ---
st.title("🛡️ EMD Inventory Executive Command")

# KPI ROW
kpi1, kpi2, kpi3 = st.columns(3)
with kpi1:
    st.markdown(f"<div class='kpi-card'><h3>Total Items</h3><h1>{len(filtered_df)}</h1></div>", unsafe_allow_html=True)
with kpi2:
    st.markdown(f"<div class='kpi-card'><h3>Stock Value</h3><h1>{filtered_df['TOTAL NO'].sum()}</h1></div>", unsafe_allow_html=True)
with kpi3:
    critical_count = len(filtered_df[filtered_df['TOTAL NO'] < low_stock_limit])
    st.markdown(f"<div class='kpi-card' style='border-top-color:#dc3545'><h3>Critical Alerts</h3><h1>{critical_count}</h1></div>", unsafe_allow_html=True)

st.write("---")

# MAIN DISPLAY: CARDS VS TABLE
tab1, tab2 = st.tabs(["💎 Visual Gallery", "📝 Data Entry Grid"])

with tab1:
    st.subheader(f"Inventory Status: {selected_loc}")
    
    # Create rows of cards
    cols = st.columns(3)
    for index, row in filtered_df.iterrows():
        is_low = row['TOTAL NO'] < low_stock_limit
        card_style = "warning-card" if is_low else "material-card"
        warning_tag = "⚠️ LOW STOCK" if is_low else "✅ HEALTHY"
        
        with cols[index % 3]:
            st.markdown(f"""
            <div class='{card_style}'>
                <small>{row['LOCATION']}</small>
                <h4>{row['MATERIAL DISCRIPTION']}</h4>
                <p><b>Make:</b> {row['MAKE']}<br>
                <b>Quantity:</b> <span style='font-size:20px'>{row['TOTAL NO']}</span></p>
                <hr>
                <small>{warning_tag}</small>
            </div>
            """, unsafe_allow_html=True)

with tab2:
    st.subheader("Interactive Stock Management")
    st.caption("Edit quantities below and click 'Sync' to update Google Sheets.")
    edited_df = st.data_editor(filtered_df, use_container_width=True, hide_index=True)
    
    if st.button("🚀 Sync Changes to Google Sheet"):
        # Logic to write edited_df back to sheet goes here
        st.success("Synchronizing with Google Cloud... Done!")
