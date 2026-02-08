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

# --- 2. CONFIG & CUSTOM CSS ---
st.set_page_config(page_title="EMD Material Dashboard", layout="wide", page_icon="🛡️")

st.markdown("""
<style>
    .stApp { background-color: #f8f9fa; }
    .header-box {
        background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%);
        padding: 20px; border-radius: 10px; color: white;
        text-align: center; margin-bottom: 30px; box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    div[data-testid="stMetric"] {
        background-color: white; padding: 15px; border-radius: 10px;
        border-left: 5px solid #1e3c72; box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
</style>
""", unsafe_allow_html=True)

# --- 3. DATA LOADING ---
@st.cache_data(ttl=60)
def load_data():
    try:
        # Load Inventory
        inv_raw = pd.read_csv(INV_URL, header=None).fillna("").astype(str)
        h_idx = next((i for i, r in inv_raw.iterrows() if "MATERIAL" in " ".join(r).upper()), None)
        if h_idx is None: return "HEADER_NOT_FOUND", None
        
        inv = pd.read_csv(INV_URL, skiprows=h_idx)
        inv.columns = [str(c).strip().replace('\n', ' ').upper() for c in inv.columns]
        inv.columns = [c.replace("DESCRIPTION", "DISCRIPTION") for c in inv.columns]
        
        if 'TOTAL NO' in inv.columns:
            inv['TOTAL NO'] = pd.to_numeric(inv['TOTAL NO'], errors='coerce').fillna(0).astype(int)

        # Usage Log
        log = pd.read_csv(LOG_URL)
        log.columns = [str(c).strip().replace('\n', ' ').upper() for c in log.columns]
        log.columns = [c.replace("DESCRIPTION", "DISCRIPTION") for c in log.columns]
        log = log.rename(columns={'QUANTITY ISSUED': 'QTY_OUT'})
        
        if 'QTY_OUT' in log.columns:
            log['QTY_OUT'] = pd.to_numeric(log['QTY_OUT'], errors='coerce').fillna(0).astype(int)
        
        # Sync Logic
        keys = [k for k in ['MAKE', 'MATERIAL DISCRIPTION', 'TYPE(RATING)', 'SIZE', 'LOCATION'] if k in inv.columns and k in log.columns]
        cons = log.groupby(keys)['QTY_OUT'].sum().reset_index()
        merged = pd.merge(inv, cons, on=keys, how='left')
        merged['QTY_OUT'] = merged['QTY_OUT'].fillna(0)
        merged['LIVE STOCK'] = merged['TOTAL NO'] - merged['QTY_OUT']
        
        return merged, log
    except Exception as e: return str(e), None

def send_email_alert(name, qty):
    try:
        creds = st.secrets["email"]
        msg = MIMEText(f"Low Stock Alert: {name} is at {qty} units.")
        msg['Subject'] = f"🚨 Stock Alert: {name}"
        msg['From'], msg['To'] = creds["address"], creds["receiver"]
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(creds["address"], creds["password"])
            s.sendmail(creds["address"], creds["receiver"], msg.as_string())
        return True
    except: return False

# --- 4. DASHBOARD UI ---
inv_df, log_df = load_data()

if isinstance(inv_df, str):
    st.error(f"Sync Error: {inv_df}")
    st.stop()

st.markdown('<div class="header-box"><h1>🛡️ EMD Material Inventory Dashboard</h1></div>', unsafe_allow_html=True)

# Metrics
c1, c2, c3 = st.columns(3)
c1.metric("Total Line Items", len(inv_df))
c2.metric("Total Stock Units", int(inv_df['LIVE STOCK'].sum()))
crit = inv_df[inv_df['LIVE STOCK'] <= 2]
c3.metric("Low Stock Alerts", len(crit))

# Email Alerts
for _, r in crit.iterrows():
    key = f"sent_{r['MATERIAL DISCRIPTION']}_{r['LOCATION']}"
    if key not in st.session_state:
        if send_email_alert(r['MATERIAL DISCRIPTION'], r['LIVE STOCK']):
            st.session_state[key] = True

# FILTER PANEL - FIXED SORTING
st.sidebar.header("Filter Panel")
if 'LOCATION' in inv_df.columns:
    # Convert all locations to string and fill empty ones to prevent sorting crash
    raw_locs = inv_df['LOCATION'].fillna("Unassigned").astype(str).unique().tolist()
    locs = ["All"] + sorted(raw_locs)
else:
    locs = ["All"]

sel_loc = st.sidebar.selectbox("Select Location", locs)

# Apply Filter
filtered = inv_df.copy()
if sel_loc != "All":
    filtered = filtered[filtered['LOCATION'].astype(str) == sel_loc]

# Dynamic Column Selection
cols_to_show = [c for c in ['MAKE', 'MATERIAL DISCRIPTION', 'TYPE(RATING)', 'SIZE', 'LOCATION', 'TOTAL NO', 'LIVE STOCK'] if c in inv_df.columns]



tab1, tab2 = st.tabs(["📦 Inventory Grid", "📋 Usage History"])

with tab1:
    st.dataframe(
        filtered[cols_to_show],
        use_container_width=True,
        hide_index=True,
        column_config={"LIVE STOCK": st.column_config.ProgressColumn("Availability", format="%d", min_value=0, max_value=int(inv_df['TOTAL NO'].max() or 100))}
    )

with tab2:
    st.dataframe(log_df, use_container_width=True, hide_index=True)
