import streamlit as st
import pandas as pd
import smtplib
from email.mime.text import MIMEText

# --- 1. SETTINGS ---
# Using the GIDs you provided
SHEET_ID = "1E0ZluX3o7vqnSBAdAMEn_cdxq3ro4F4DXxchOEFcS_g"
INV_GID = "804871972" 
LOG_GID = "1151083374" 

INV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={INV_GID}"
LOG_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={LOG_GID}"

# --- 2. DATA LOADING & SYNC ---
@st.cache_data(ttl=60)
def load_synchronized_data():
    try:
        # Load Main Inventory
        inv_df = pd.read_csv(INV_URL)
        inv_df.columns = [str(c).strip() for c in inv_df.columns]
        
        # Handle case where headers are in the second row
        if "MATERIAL DESCRIPTION" not in inv_df.columns:
            inv_df = pd.read_csv(INV_URL, skiprows=1)
            inv_df.columns = [str(c).strip() for c in inv_df.columns]
        
        # Load Usage Log
        log_df = pd.read_csv(LOG_URL)
        log_df.columns = [str(c).strip() for c in log_df.columns]
        
        # Clean Numeric Columns
        if 'TOTAL NO' in inv_df.columns:
            inv_df['TOTAL NO'] = pd.to_numeric(inv_df['TOTAL NO'], errors='coerce').fillna(0).astype(int)
        
        if 'Quantity Issued' in log_df.columns:
            log_df['Quantity Issued'] = pd.to_numeric(log_df['Quantity Issued'], errors='coerce').fillna(0).astype(int)

        # UNIQUE MATCH LOGIC: Subtraction based on 3 identifiers
        # This prevents deducting stock from the wrong item when names are identical
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
        st.error(f"🚨 Sync Error: {e}")
        return None, None

# --- 3. DASHBOARD UI ---
st.set_page_config(page_title="EMD Executive Inventory", layout="wide")
st.title("🛡️ EMD Executive Inventory & Audit")

inv_df, log_df = load_synchronized_data()

if inv_df is not None:
    # Sidebar Filters
    st.sidebar.header("🕹️ Filter Controls")
    loc_list = sorted(inv_df['LOCATION'].dropna().unique().tolist())
    sel_loc = st.sidebar.selectbox("Location", ["All"] + loc_list)
    
    # Filtered Data
    disp_df = inv_df if sel_loc == "All" else inv_df[inv_df['LOCATION'] == sel_loc]

    # Layout Tabs
    t1, t2, t3 = st.tabs(["📊 Stock Status", "📈 Usage Trends", "🕵️ Audit Log"])

    with t1:
        st.subheader(f"Current Stock - {sel_loc}")
        # Displaying with the dynamic LIVE STOCK calculation
        st.dataframe(disp_df[['MAKE', 'MATERIAL DESCRIPTION', 'TYPE(RATING)', 'LOCATION', 'LIVE STOCK']], 
                     use_container_width=True, hide_index=True)

    with t2:
        st.subheader("Consumption Analytics")
        if not log_df.empty:
            c1, c2 = st.columns(2)
            with c1:
                st.write("**Usage by Person (Issued To)**")
                person_data = log_df.groupby('Issued To')['Quantity Issued'].sum()
                st.bar_chart(person_data)
            with c2:
                st.write("**Usage by Purpose**")
                purpose_data = log_df.groupby('Purpose')['Quantity Issued'].sum()
                st.bar_chart(purpose_data)
        else:
            st.info("No logs found in USAGE LOG tab.")

    with t3:
        st.subheader("📜 Detailed Transaction History")
        st.dataframe(log_df, use_container_width=True, hide_index=True)
