import streamlit as st
import pandas as pd
import smtplib
from email.mime.text import MIMEText

# --- 1. SETTINGS & GIDs ---
# These are the IDs you provided
SHEET_ID = "1E0ZluX3o7vqnSBAdAMEn_cdxq3ro4F4DXxchOEFcS_g"
INV_GID = "804871972" 
LOG_GID = "1151083374" 

INV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={INV_GID}"
LOG_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={LOG_GID}"

# --- 2. ROBUST DATA LOADING ---
@st.cache_data(ttl=60)
def load_synchronized_data():
    try:
        # A. LOAD MAIN INVENTORY
        # We read raw first to find where the headers actually start
        inv_df_raw = pd.read_csv(INV_URL, header=None).astype(str)
        
        header_row_idx = None
        for i, row in inv_df_raw.iterrows():
            row_text = " ".join(row).upper()
            if "MATERIAL" in row_text and "DESCRIPTION" in row_text:
                header_row_idx = i
                break
        
        if header_row_idx is None:
            return "HEADER_NOT_FOUND", None
            
        inv_df = pd.read_csv(INV_URL, skiprows=header_row_idx)
        # Standardize headers to UPPERCASE to prevent spelling/case errors
        inv_df.columns = [str(c).strip().upper() for c in inv_df.columns]
        
        # B. LOAD USAGE LOG
        log_df = pd.read_csv(LOG_URL)
        log_df.columns = [str(c).strip().upper() for c in log_df.columns]
        
        # Standardize 'Quantity Issued' name in log
        log_df = log_df.rename(columns={'QUANTITY ISSUED': 'QTY_OUT'})

        # C. DATA CLEANING
        if 'TOTAL NO' in inv_df.columns:
            inv_df['TOTAL NO'] = pd.to_numeric(inv_df['TOTAL NO'], errors='coerce').fillna(0).astype(int)
        
        if 'QTY_OUT' in log_df.columns:
            log_df['QTY_OUT'] = pd.to_numeric(log_df['QTY_OUT'], errors='coerce').fillna(0).astype(int)
        else:
            # Fallback if log is empty
            log_df = pd.DataFrame(columns=['MATERIAL DESCRIPTION', 'TYPE(RATING)', 'LOCATION', 'QTY_OUT', 'ISSUED TO', 'PURPOSE'])

        # D. TRIPLE-MATCH SYNC LOGIC
        # Group by the 3 keys that distinguish identical item names
        consumed = log_df.groupby(['MATERIAL DESCRIPTION', 'TYPE(RATING)', 'LOCATION'])['QTY_OUT'].sum().reset_index()
        
        merged = pd.merge(
            inv_df, 
            consumed, 
            on=['MATERIAL DESCRIPTION', 'TYPE(RATING)', 'LOCATION'], 
            how='left'
        )
        
        merged['QTY_OUT'] = merged['QTY_OUT'].fillna(0)
        merged['LIVE STOCK'] = merged['TOTAL NO'] - merged['QTY_OUT']
        
        return merged, log_df

    except Exception as e:
        return str(e), None

# --- 3. PAGE CONFIG & UI ---
st.set_page_config(page_title="EMD Executive Hub", layout="wide", page_icon="🛡️")

st.title("🛡️ EMD Executive Inventory & Audit")
st.markdown("---")

# Execute Data Load
inv_df, log_df = load_synchronized_data()

# Error Handling
if isinstance(inv_df, str):
    if inv_df == "HEADER_NOT_FOUND":
        st.error("❌ Could not find 'MATERIAL DESCRIPTION' in your Main Sheet. Please check the spelling or GID.")
    else:
        st.error(f"🚨 Sync Error: {inv_df}")
    st.stop()

# --- 4. DASHBOARD LOGIC ---

# SIDEBAR FILTERS
st.sidebar.header("🕹️ Filter Controls")
loc_list = sorted(inv_df['LOCATION'].dropna().unique().tolist())
sel_loc = st.sidebar.selectbox("Filter by Location", ["All"] + loc_list)

# Filter Logic
disp_df = inv_df if sel_loc == "All" else inv_df[inv_df['LOCATION'] == sel_loc]

# TABS
t1, t2, t3 = st.tabs(["📊 Stock Status", "📈 Usage Trends", "🕵️ Audit Log"])

with t1:
    st.subheader(f"Current Live Inventory - {sel_loc}")
    # Show combined data with the new LIVE STOCK calculation
    st.dataframe(
        disp_df[['MAKE', 'MATERIAL DESCRIPTION', 'TYPE(RATING)', 'LOCATION', 'TOTAL NO', 'LIVE STOCK']], 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "LIVE STOCK": st.column_config.ProgressColumn(
                "Stock Health", min_value=0, max_value=int(inv_df['TOTAL NO'].max() or 100), format="%d"
            )
        }
    )

with t2:
    st.subheader("Consumption Analytics")
    if not log_df.empty:
        c1, c2 = st.columns(2)
        with c1:
            st.write("**Usage by Personnel (Issued To)**")
            if 'ISSUED TO' in log_df.columns:
                person_data = log_df.groupby('ISSUED TO')['QTY_OUT'].sum()
                st.bar_chart(person_data, color="#007bff")
        with c2:
            st.write("**Usage by Purpose/Project**")
            if 'PURPOSE' in log_df.columns:
                purpose_data = log_df.groupby('PURPOSE')['QTY_OUT'].sum()
                st.bar_chart(purpose_data, color="#28a745")
    else:
        st.info("No data found in USAGE LOG. Record issues in Google Sheets to see charts.")

with t3:
    st.subheader("📜 Detailed Audit Trail")
    st.dataframe(log_df, use_container_width=True, hide_index=True)
