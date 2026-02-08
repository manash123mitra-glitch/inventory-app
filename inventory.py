import streamlit as st
import pandas as pd
import smtplib
from email.mime.text import MIMEText

# --- 1. SETTINGS & GIDs ---
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
        inv_df_raw = pd.read_csv(INV_URL, header=None)
        
        # Fuzzy search for the header row to prevent 'MATERIAL DESCRIPTION' errors
        header_row_idx = None
        for i, row in inv_df_raw.iterrows():
            if row.astype(str).str.contains('MATERIAL DESCRIPTION').any():
                header_row_idx = i
                break
        
        if header_row_idx is None:
            return "HEADER_NOT_FOUND", None
            
        inv_df = pd.read_csv(INV_URL, skiprows=header_row_idx)
        inv_df.columns = [str(c).strip() for c in inv_df.columns]
        
        # B. LOAD USAGE LOG
        log_df = pd.read_csv(LOG_URL)
        log_df.columns = [str(c).strip() for c in log_df.columns]

        # C. DATA CLEANING & NUMERIC CONVERSION
        if 'TOTAL NO' in inv_df.columns:
            inv_df['TOTAL NO'] = pd.to_numeric(inv_df['TOTAL NO'], errors='coerce').fillna(0).astype(int)
        
        if 'Quantity Issued' in log_df.columns:
            log_df['Quantity Issued'] = pd.to_numeric(log_df['Quantity Issued'], errors='coerce').fillna(0).astype(int)
        else:
            # Create a blank log structure if the sheet is empty to prevent crashes
            log_df = pd.DataFrame(columns=['MATERIAL DESCRIPTION', 'TYPE(RATING)', 'LOCATION', 'Quantity Issued', 'Issued To', 'Purpose'])

        # D. TRIPLE-MATCH SYNC LOGIC
        # Grouping by 3 identifiers to ensure identical names don't clash
        consumed = log_df.groupby(['MATERIAL DESCRIPTION', 'TYPE(RATING)', 'LOCATION'])['Quantity Issued'].sum().reset_index()
        
        merged = pd.merge(
            inv_df, 
            consumed, 
            on=['MATERIAL DESCRIPTION', 'TYPE(RATING)', 'LOCATION'], 
            how='left'
        )
        
        merged['Quantity Issued'] = merged['Quantity Issued'].fillna(0)
        merged['LIVE STOCK'] = merged['TOTAL NO'] - merged['Quantity Issued']
        
        return merged, log_df

    except Exception as e:
        return str(e), None

# --- 3. PAGE CONFIG & UI ---
st.set_page_config(page_title="EMD Executive Hub", layout="wide", page_icon="🛡️")

st.title("🛡️ EMD Executive Inventory & Audit")
st.markdown("---")

inv_df, log_df = load_synchronized_data()

# Error Handling for the UI
if isinstance(inv_df, str):
    if inv_df == "HEADER_NOT_FOUND":
        st.error("❌ Could not find column 'MATERIAL DESCRIPTION' in Main Sheet. Check spelling/GID.")
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
    # Highlighting the calculated LIVE STOCK column
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
            person_data = log_df.groupby('Issued To')['Quantity Issued'].sum()
            st.bar_chart(person_data, color="#007bff")
        with c2:
            st.write("**Usage by Purpose/Project**")
            purpose_data = log_df.groupby('Purpose')['Quantity Issued'].sum()
            st.bar_chart(purpose_data, color="#28a745")
    else:
        st.info("No data found in USAGE LOG. Record issues in Google Sheets to see charts.")

with t3:
    st.subheader("📜 Detailed Audit Trail")
    st.caption("Complete history of all material movements.")
    st.dataframe(log_df, use_container_width=True, hide_index=True)
