import streamlit as st
import pandas as pd

# --- 1. SETTINGS ---
SHEET_ID = "1E0ZluX3o7vqnSBAdAMEn_cdxq3ro4F4DXxchOEFcS_g"
INV_GID = "804871972" 
LOG_GID = "1151083374" 

INV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={INV_GID}"
LOG_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={LOG_GID}"

# --- 2. DATA LOADING & ROBUST SYNC ---
@st.cache_data(ttl=60)
def load_synchronized_data():
    try:
        # A. LOAD MAIN INVENTORY
        inv_df_raw = pd.read_csv(INV_URL, header=None).fillna("").astype(str)
        
        # Find the header row (looking for DISCRIPTION or DESCRIPTION)
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
        
        # Standardize Qty column name
        log_df = log_df.rename(columns={'QUANTITY ISSUED': 'QTY_OUT'})

        # C. NUMERIC CLEANING
        if 'TOTAL NO' in inv_df.columns:
            inv_df['TOTAL NO'] = pd.to_numeric(inv_df['TOTAL NO'], errors='coerce').fillna(0).astype(int)
        
        if 'QTY_OUT' in log_df.columns:
            log_df['QTY_OUT'] = pd.to_numeric(log_df['QTY_OUT'], errors='coerce').fillna(0).astype(int)
        else:
            # Create dummy if log is empty
            log_df = pd.DataFrame(columns=['MATERIAL DESCRIPTION', 'TYPE(RATING)', 'LOCATION', 'QTY_OUT'])

        # D. THE "PERFECT MATCH" LOGIC
        # We group usage by Description + Type + Size + Location
        # This handles multiple items with the same name
        match_cols = []
        for col in ['MATERIAL DESCRIPTION', 'MATERIAL DISCRIPTION', 'TYPE(RATING)', 'SIZE', 'LOCATION']:
            if col in log_df.columns: match_cols.append(col)
            
        consumed = log_df.groupby(match_cols)['QTY_OUT'].sum().reset_index()
        
        # Standardize join columns for the merge
        inv_cols = [c for c in ['MATERIAL DESCRIPTION', 'MATERIAL DISCRIPTION', 'TYPE(RATING)', 'SIZE', 'LOCATION'] if c in inv_df.columns]
        
        merged = pd.merge(inv_df, consumed, on=inv_cols, how='left')
        merged['QTY_OUT'] = merged['QTY_OUT'].fillna(0)
        merged['LIVE STOCK'] = merged['TOTAL NO'] - merged['QTY_OUT']
        
        return merged, log_df

    except Exception as e:
        return f"ERROR: {str(e)}", None

# --- 3. UI RENDER ---
st.set_page_config(page_title="EMD Inventory Hub", layout="wide")
st.title("🛡️ EMD Executive Inventory Dashboard")

inv_df, log_df = load_synchronized_data()

if isinstance(inv_df, str):
    st.error(f"🚨 {inv_df}")
    if isinstance(log_df, pd.DataFrame):
        st.write("Check your headers in the table below:")
        st.dataframe(log_df)
    st.stop()

# --- 4. DASHBOARD UI ---
st.success("✅ Live Data Synced with Google Sheets")

# Metrics
c1, c2, c3 = st.columns(3)
c1.metric("Total Items", len(inv_df))
c2.metric("Total Units in Stock", int(inv_df['LIVE STOCK'].sum()))
c3.metric("Critical Alerts", len(inv_df[inv_df['LIVE STOCK'] <= 5]))

# Filter
loc_list = sorted(inv_df['LOCATION'].dropna().unique().tolist())
sel_loc = st.sidebar.selectbox("Filter by Storage Location", ["All"] + loc_list)

display_df = inv_df if sel_loc == "All" else inv_df[inv_df['LOCATION'] == sel_loc]

# Visual Table

st.dataframe(
    display_df, 
    use_container_width=True, 
    hide_index=True,
    column_config={
        "LIVE STOCK": st.column_config.ProgressColumn("Stock Level", min_value=0, max_value=int(inv_df['TOTAL NO'].max()), format="%d")
    }
)

# Audit Trail
with st.expander("📜 View Usage Log (Audit Trail)"):
    st.dataframe(log_df, use_container_width=True)
