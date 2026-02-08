import streamlit as st
import pandas as pd

# --- PAGE CONFIG ---
st.set_page_config(page_title="EMD Inventory Hub", layout="wide", page_icon="📦")

# Executive Styling
st.markdown("""
<style>
    .stApp { background-color: #f8f9fa; }
    .kpi-box { background-color: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center; border-top: 5px solid #007bff; }
    .alert-card { background-color: #fff5f5; border-left: 5px solid #ff4b4b; padding: 15px; border-radius: 5px; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

# --- DATA LOADING ---
# Replace this ID with your actual Google Sheet ID
SHEET_ID = "1E0ZluX3o7vqnSBAdAMEn_cdxq3ro4F4DXxchOEFcS_g"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

@st.cache_data(ttl=60)
def load_data():
    try:
        # Read the sheet
        df = pd.read_csv(CSV_URL)
        
        # CLEANING: If the first row is 'ALMIRA NO.1', we skip it
        if "MATERIAL DISCRIPTION" not in df.columns:
            df = pd.read_csv(CSV_URL, skiprows=1)
            
        df.columns = [c.strip() for c in df.columns]
        df['TOTAL NO'] = pd.to_numeric(df['TOTAL NO'], errors='coerce').fillna(0).astype(int)
        return df
    except Exception as e:
        return None

# --- UI LOGIC ---
st.title("🛡️ EMD Executive Inventory")

df = load_data()

if df is not None:
    # 1. SIDEBAR DROPDOWN
    st.sidebar.header("🕹️ Filter Console")
    unique_locs = sorted(df['LOCATION'].dropna().unique().tolist())
    selected_loc = st.sidebar.selectbox("Choose Location", ["All Locations"] + unique_locs)
    
    limit = st.sidebar.slider("Low Stock Alert Level", 0, 50, 10)

    # Filter data
    filtered_df = df if selected_loc == "All Locations" else df[df['LOCATION'] == selected_loc]

    # 2. KPI METRICS
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"<div class='kpi-box'><h4>Items Cataloged</h4><h2>{len(filtered_df)}</h2></div>", unsafe_allow_html=True)
    with c2:
        st.markdown(f"<div class='kpi-box'><h4>Total Stock Count</h4><h2>{filtered_df['TOTAL NO'].sum()}</h2></div>", unsafe_allow_html=True)
    with c3:
        low_stock = filtered_df[filtered_df['TOTAL NO'] <= limit]
        st.markdown(f"<div class='kpi-box' style='border-top-color:red'><h4>Critical Alerts</h4><h2>{len(low_stock)}</h2></div>", unsafe_allow_html=True)

    # 3. VISUAL DASHBOARD
    st.divider()
    left, right = st.columns([2, 1])

    with left:
        st.subheader("📋 Detailed Inventory")
        st.dataframe(filtered_df, use_container_width=True, hide_index=True, column_config={
            "TOTAL NO": st.column_config.ProgressColumn("Stock Health", min_value=0, max_value=int(df['TOTAL NO'].max()))
        })

    with right:
        st.subheader("🚨 Low Stock Warnings")
        if not low_stock.empty:
            for _, row in low_stock.iterrows():
                st.markdown(f"""
                <div class='alert-card'>
                    <strong>{row['MATERIAL DISCRIPTION']}</strong><br>
                    Current Qty: {row['TOTAL NO']} | Loc: {row['LOCATION']}
                </div>
                """, unsafe_allow_html=True)
        else:
            st.success("✅ All locations are well-stocked.")

else:
    st.error("📡 Unable to connect to Google Sheets. Check your Sheet's 'Share' settings (must be 'Anyone with the link') and the Sheet ID.")
