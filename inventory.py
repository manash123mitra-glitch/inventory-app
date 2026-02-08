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
        # A. LOAD MAIN INVENTORY (Raw mode)
        inv_df_raw = pd.read_csv(INV_URL, header=None).fillna("").astype(str)
        
        # SCANNER: Look for the header row by checking every cell
        header_row_idx = None
        for i, row in inv_df_raw.iterrows():
            # Check if 'MATERIAL' and 'DESCRIPTION' exist anywhere in this row
            row_content = " ".join(row).upper()
            if "MATERIAL" in row_content and "DESCRIPTION" in row_content:
                header_row_idx = i
                break
        
        if header_row_idx is None:
            # DIAGNOSTIC: Show the actual headers found in the first 10 rows
            return "DIAGNOSTIC", inv_df_raw.head(10)
            
        inv_df = pd.read_csv(INV_URL, skiprows=header_row_idx)
        # Clean headers: remove non-visible characters and spaces
        inv_df.columns = [str(c).replace('\n', ' ').strip().upper() for c in inv_df.columns]
        
        # B. LOAD USAGE LOG
        log_df = pd.read_csv(LOG_URL)
        log_df.columns = [str(c).replace('\n', ' ').strip().upper() for c in log_df.columns]
        
        # Standardize 'Quantity Issued' name
        log_df = log_df.rename(columns={'QUANTITY ISSUED': 'QTY_OUT'})

        # C. DATA CLEANING
        if 'TOTAL NO' in inv_df.columns:
            inv_df['TOTAL NO'] = pd.to_numeric(inv_df['TOTAL NO'], errors='coerce').fillna(0).astype(int)
        
        if 'QTY_OUT' in log_df.columns:
            log_df['QTY_OUT'] = pd.to_numeric(log_df['QTY_OUT'], errors='coerce').fillna(0).astype(int)
        else:
            log_df = pd.DataFrame(columns=['MATERIAL DESCRIPTION', 'TYPE(RATING)', 'LOCATION', 'QTY_OUT', 'ISSUED TO', 'PURPOSE'])

        # D. TRIPLE-MATCH SYNC
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
        return f"ERROR: {str(e)}", None

# --- 3. UI SETUP ---
st.set_page_config(page_title="EMD Inventory Hub", layout="wide")
st.title("🛡️ EMD Executive Inventory")

inv_df, log_df = load_synchronized_data()

# Error/Diagnostic Handling
if isinstance(inv_df, str):
    if inv_df == "DIAGNOSTIC":
        st.error("❌ Still cannot find 'MATERIAL DESCRIPTION'. Check the table below to see what I see:")
        st.write("First 10 rows of your Sheet (Raw):")
        st.dataframe(log_df) # log_df contains raw inv data in diagnostic mode
        st.info("💡 Tip: Ensure your headers are in a single row and not merged.")
    else:
        st.error(f"🚨 Sync Error: {inv_df}")
    st.stop()

# --- 4. DASHBOARD RENDER ---
# (The rest of your dashboard code continues here...)
st.success("✅ Data Synced Successfully!")
st.dataframe(inv_df[['MATERIAL DESCRIPTION', 'TYPE(RATING)', 'LOCATION', 'LIVE STOCK']], use_container_width=True)
