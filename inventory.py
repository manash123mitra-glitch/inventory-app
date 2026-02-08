import streamlit as st
import pandas as pd

# --- 1. SETTINGS ---
SHEET_ID = "1E0ZluX3o7vqnSBAdAMEn_cdxq3ro4F4DXxchOEFcS_g"
INV_GID = "804871972" 
LOG_GID = "1151083374" 

INV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={INV_GID}"
LOG_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={LOG_GID}"

# --- 2. DATA LOADING & SYNC ---
@st.cache_data(ttl=60)
def load_synchronized_data():
    try:
        # Load Inventory
        inv_df = pd.read_csv(INV_URL)
        inv_df.columns = [c.strip() for c in inv_df.columns]
        
        # Load Usage Log
        log_df = pd.read_csv(LOG_URL)
        log_df.columns = [c.strip() for c in log_df.columns]
        
        # Numeric Cleaning
        inv_df['TOTAL NO'] = pd.to_numeric(inv_df['TOTAL NO'], errors='coerce').fillna(0).astype(int)
        log_df['Quantity Issued'] = pd.to_numeric(log_df['Quantity Issued'], errors='coerce').fillna(0).astype(int)
        
        # UNIQUE MATCH LOGIC: Group by Name, Type(Rating), and Location
        consumed = log_df.groupby(['MATERIAL DESCRIPTION', 'TYPE(RATING)', 'LOCATION'])['Quantity Issued'].sum().reset_index()
        
        # Merge with Main Sheet
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
        st.error(f"Error Syncing Data: {e}")
        return None, None

# --- 3. DASHBOARD UI ---
st.title("🛡️ EMD Executive Inventory & Audit")

inv_df, log_df = load_synchronized_data()

if inv_df is not None:
    # --- FILTERS ---
    st.sidebar.header("🕹️ Filter Controls")
    sel_loc = st.sidebar.selectbox("Location", ["All"] + sorted(inv_df['LOCATION'].unique()))
    
    # Filtered Data
    disp_df = inv_df if sel_loc == "All" else inv_df[inv_df['LOCATION'] == sel_loc]

    # --- TABS ---
    t1, t2, t3 = st.tabs(["📊 Stock Status", "📈 Trends", "🕵️ Audit Trail"])

    with t1:
        st.subheader(f"Current Stock - {sel_loc}")
        st.dataframe(disp_df[['MAKE', 'MATERIAL DESCRIPTION', 'TYPE(RATING)', 'LOCATION', 'LIVE STOCK']], 
                     use_container_width=True, hide_index=True)

    with t2:
        st.subheader("Consumption Analysis")
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Usage by Person (Issued To)**")
            
            person_usage = log_df.groupby('Issued To')['Quantity Issued'].sum()
            st.bar_chart(person_usage)
        with col2:
            st.write("**Usage by Purpose**")
            
            purpose_usage = log_df.groupby('Purpose')['Quantity Issued'].sum()
            st.bar_chart(purpose_usage)

    with t3:
        st.subheader("📜 Complete Transaction History")
        # Showing the detailed log with your new headers
        st.dataframe(log_df[['Date', 'MATERIAL DESCRIPTION', 'Quantity Issued', 'Issued To', 'Purpose']], 
                     use_container_width=True, hide_index=True)
