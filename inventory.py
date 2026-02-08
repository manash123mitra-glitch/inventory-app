import streamlit as st
import pandas as pd
import re
import os
import time

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(
    page_title="EMD Inventory Hub",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. CUSTOM STYLING (CSS) ---
# This makes the app look modern with blue cards and clean fonts
st.markdown("""
<style>
    /* Background & Font */
    .stApp { background-color: #f4f6f9; }
    h1 { color: #0e1117; font-weight: 700; }
    
    /* KPI Cards styling */
    div[data-testid="stMetric"] {
        background-color: white;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #3498db;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    /* Button Styling */
    div.stButton > button {
        background-color: #2ecc71;
        color: white;
        border: none;
        padding: 10px 24px;
        border-radius: 5px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. FILE CONFIGURATION ---
DEFAULT_FILE_PATH = "EMD MATERIAL STOCK - EMD MATERIAL.csv"

# --- 4. DATA LOADING FUNCTIONS ---
def clean_currency_or_units(val):
    if pd.isna(val): return 0
    # Extracts numbers from strings like "10 Nos" or "500 Mtr"
    match = re.search(r"(\d+(\.\d+)?)", str(val))
    return float(match.group(1)) if match else 0

def load_data(file_path):
    if not os.path.exists(file_path): return None
    
    # 1. Read blindly to find the header
    temp_df = pd.read_csv(file_path, header=None, dtype=str)
    header_row = None
    for i, row in temp_df.iterrows():
        if "MATERIAL DISCRIPTION" in row.astype(str).values:
            header_row = i
            break
            
    if header_row is None: return pd.DataFrame()
    
    # 2. Reload with correct header
    df = pd.read_csv(file_path, header=header_row, dtype=str)
    df.columns = [c.strip() for c in df.columns]
    
    # 3. Clean Data
    df = df[df['TOTAL NO'] != 'TOTAL NO']
    df = df[df['MATERIAL DISCRIPTION'].notna()]
    df['TOTAL NO'] = df['TOTAL NO'].apply(clean_currency_or_units)
    
    if 'LOCATION' in df.columns:
        df['LOCATION'] = df['LOCATION'].fillna('Unknown')
    else:
        df['LOCATION'] = 'Unknown'
        
    return df

# --- 5. MAIN APPLICATION ---

# Header
c1, c2 = st.columns([6, 1])
with c1:
    st.title("🏭 EMD Inventory Manager")
    st.caption("Local File Edition")
with c2:
    if st.button("🔄 Reload"):
        st.cache_data.clear()
        if 'data' in st.session_state: del st.session_state.data
        st.rerun()

# Load Data
if 'data' not in st.session_state:
    df = load_data(DEFAULT_FILE_PATH)
    if df is not None:
        st.session_state.data = df
    else:
        st.error(f"❌ File '{DEFAULT_FILE_PATH}' not found in this folder.")
        st.stop()

df = st.session_state.data

# --- 6. KPI METRICS ---
st.markdown("### 📊 Dashboard Overview")

total_stock = int(df['TOTAL NO'].sum())
thresh = st.sidebar.slider("Low Stock Level", 0, 50, 5)
low_stock = df[df['TOTAL NO'] <= thresh]

m1, m2, m3, m4 = st.columns(4)
m1.metric("📦 Items", len(df))
m2.metric("🔢 Total Stock", f"{total_stock:,}")
m3.metric("⚠️ Low Stock", len(low_stock), delta_color="inverse")
m4.metric("📍 Locations", df['LOCATION'].nunique())

# --- 7. CHARTS ---
if not df.empty:
    with st.expander("📈 Click to View Stock Distribution"):
        st.bar_chart(df['LOCATION'].value_counts(), color="#3498db")

# --- 8. FILTERS ---
st.sidebar.header("Filter Inventory")
locs = sorted(list(df['LOCATION'].unique()))
sel_loc = st.sidebar.multiselect("Select Location", locs, default=locs)
filtered = df[df['LOCATION'].isin(sel_loc)]

# --- 9. EDITOR WITH PROGRESS BARS ---
st.subheader("📝 Update Stock")

# Calculate max for progress bar
max_val = int(df['TOTAL NO'].max()) if not df.empty else 100

edited = st.data_editor(
    filtered,
    num_rows="dynamic",
    use_container_width=True,
    height=600,
    hide_index=True,
    column_config={
        "MATERIAL DISCRIPTION": st.column_config.TextColumn("Item Name", width="medium"),
        "LOCATION": st.column_config.SelectboxColumn("Location", options=locs),
        "TOTAL NO": st.column_config.ProgressColumn(
            "Stock Level",
            format="%d",
            min_value=0,
            max_value=max_val,
        ),
        "MAKE": st.column_config.TextColumn("Brand"),
    },
    key="editor"
)

# --- 10. SAVE BUTTON ---
st.divider()
if st.button("💾 Save Changes to CSV", type="primary"):
    save_name = "EMD_UPDATED_STOCK.csv"
    edited.to_csv(save_name, index=False)
    st.session_state.data = edited
    st.success(f"✅ Saved successfully! Created file: {save_name}")
    time.sleep(1)
