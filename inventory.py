import streamlit as st
import pandas as pd

# --- 1. SETTINGS & GIDs ---
SHEET_ID = "1E0ZluX3o7vqnSBAdAMEn_cdxq3ro4F4DXxchOEFcS_g"
INV_GID = "804871972" 
LOG_GID = "1151083374" 

INV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={INV_GID}"
LOG_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={LOG_GID}"

# --- 2. DYNAMIC DATA LOADING & SYNC ---
@st.cache_data(ttl=60)
def load_synchronized_data():
    try:
        # A. LOAD MAIN INVENTORY
        inv_df_raw = pd.read_csv(INV_URL, header=None).fillna("").astype(str)
        
        # Fuzzy search for the header row
        header_row_idx = None
        for i, row in inv_df_raw.iterrows():
            row_text = " ".join(row).upper()
            if "MATERIAL" in row_text and ("DISCRIPTION" in row_text or "DESCRIPTION" in row_text):
                header_row_idx = i
                break
        
        if header_row_idx is None:
            return "HEADER_NOT_FOUND", inv_df_raw.head(10)
            
        inv_df = pd.read_csv(INV_URL, skiprows=header_row_idx)
        # Clean headers: Remove spaces, newlines, and standardize to UPPERCASE
        inv_df.columns = [str(c).strip().replace('\n', '').upper() for c in inv_df.columns]
        
        # B. LOAD USAGE LOG
        log_df = pd.read_csv(LOG_URL)
        log_df.columns = [str(c).strip().replace('\n', '').upper() for c in log_df.columns]
        
        # Standardize Quantity column name
        log_df = log_df.rename(columns={'QUANTITY ISSUED': 'QTY_OUT'})

        # C. NUMERIC CLEANING
        if 'TOTAL NO' in inv_df.columns:
            inv_df['TOTAL NO'] = pd.to_numeric(inv_df['TOTAL NO'], errors='coerce').fillna(0).astype(int)
        
        if 'QTY_OUT' in log_df.columns:
            log_df['QTY_OUT'] = pd.to_numeric(log_df['QTY_OUT'], errors='coerce').fillna(0).astype(int)
        else:
            # Create a blank log structure if the sheet is empty to prevent crashes
            log_df = pd.DataFrame(columns=['MATERIAL DESCRIPTION', 'TYPE(RATING)', 'LOCATION', 'QTY_OUT'])

        # D. THE DYNAMIC MATCHING LOGIC (The "Smart Sync")
        # The app checks which identifiers exist in BOTH tabs to perform the math
        possible_match_keys = [
            'MATERIAL DESCRIPTION', 'MATERIAL DISCRIPTION', 
            'MAKE', 'TYPE(RATING)', 'SIZE', 'LOCATION'
        ]
        
        # Find columns that are present in both sheets
        match_keys = [k for k in possible_match_keys if k in inv_df.columns and k in log_df.columns]
        
        if not match_keys:
            return "ERROR: No matching identifier columns (Description, Type, Location, etc.) found in BOTH sheets.", None

        # Group consumption in the log
        consumed = log_df.groupby(match_keys)['QTY_OUT'].sum().reset_index()
        
        # Merge Inventory with Consumption based on the shared keys
        merged = pd.merge(inv_df, consumed, on=match_keys, how='left')
        merged['QTY_OUT'] = merged['QTY_OUT'].fillna(0)
        merged['LIVE STOCK'] = merged['TOTAL NO'] - merged['QTY_OUT']
        
        return merged, log_df

    except Exception as e:
        return f"ERROR: {str(e)}", None

# --- 3. PAGE CONFIG & UI ---
st.set_page_config(page_title="EMD Inventory Hub", layout="wide", page_icon="🛡️")

st.title("🛡️ EMD Executive Inventory Dashboard")
st.markdown("---")

inv_df, log_df = load_synchronized_data()

# Handle Errors gracefully in the UI
if isinstance(inv_df, str):
    st.error(f"🚨 {inv_df}")
    if isinstance(log_df, pd.DataFrame):
        st.write("Current Sheet Headers (Diagnostic):")
        st.dataframe(log_df)
    st.stop()

# --- 4. DASHBOARD RENDER ---
st.success("✅ System Online: Data Synced with Google Sheets")

# TOP METRICS
c1, c2, c3 = st.columns(3)
c1.metric("Total Line Items", len(inv_df))
c2.metric("Total Quantity in Hand", int(inv_df['LIVE STOCK'].sum()))
low_stock_count = len(inv_df[inv_df['LIVE STOCK'] <= 5])
c3.metric("Critical Low Stock", low_stock_count, delta="-Low" if low_stock_count > 0 else "OK")

# FILTER SIDEBAR
st.sidebar.header("🕹️ Filter Options")
loc_list = sorted(inv_df['LOCATION'].dropna().unique().tolist())
sel_loc = st.sidebar.selectbox("Storage Location", ["All"] + loc_list)

# Apply Filter
display_df = inv_df if sel_loc == "All" else inv_df[inv_df['LOCATION'] == sel_loc]

# TABS
tab1, tab2 = st.tabs(["📊 Live Stock Status", "📜 Audit Trail"])

with tab1:
    st.subheader(f"Current Stock: {sel_loc}")
    # Display the table with the LIVE STOCK calculation
    st.dataframe(
        display_df, 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "LIVE STOCK": st.column_config.ProgressColumn(
                "Stock Health", 
                min_value=0, 
                max_value=int(inv_df['TOTAL NO'].max() or 100), 
                format="%d"
            )
        }
    )

with tab2:
    st.subheader("Transaction History")
    st.caption("Detailed logs from the USAGE LOG sheet.")
    st.dataframe(log_df, use_container_width=True, hide_index=True)
