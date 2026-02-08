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

# --- 2. CONFIG & CUSTOM CSS (THE HTML LOOK) ---
st.set_page_config(page_title="EMD Material Dashboard", layout="wide", page_icon="🛡️")

# Inject Custom CSS to make it look like a Web Dashboard
st.markdown("""
<style>
    /* Main Background */
    .stApp {
        background-color: #f8f9fa;
    }
    
    /* Top Header Bar */
    .header-box {
        background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 30px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .header-title {
        font-size: 2.5rem;
        font-weight: 700;
        margin: 0;
    }
    .header-subtitle {
        font-size: 1rem;
        opacity: 0.8;
        margin-top: 5px;
    }

    /* Metric Cards */
    div[data-testid="stMetric"] {
        background-color: white;
        padding: 15px 25px;
        border-radius: 10px;
        border-left: 5px solid #1e3c72;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    div[data-testid="stMetricValue"] {
        font-size: 28px;
        color: #1e3c72;
    }

    /* DataFrame Styling */
    div[data-testid="stDataFrame"] {
        background-color: white;
        padding: 10px;
        border-radius: 10px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
</style>
""", unsafe_allow_html=True)

# --- 3. LOGIC FUNCTIONS (Unchanged) ---
def send_email_alert(item_name, rating, location, current_qty):
    try:
        email_creds = st.secrets["email"]
        msg = MIMEText(f"Alert: {item_name} ({rating}) at {location} is low ({current_qty}).")
        msg['Subject'] = f"🚨 LOW STOCK: {item_name}"
        msg['From'] = email_creds["address"]
        msg['To'] = email_creds["receiver"]
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(email_creds["address"], email_creds["password"])
            server.sendmail(email_creds["address"], email_creds["receiver"], msg.as_string())
        return True
    except: return False

@st.cache_data(ttl=60)
def load_data():
    try:
        # Inventory
        inv_raw = pd.read_csv(INV_URL, header=None).fillna("").astype(str)
        h_idx = next((i for i, r in inv_raw.iterrows() if "MATERIAL" in " ".join(r).upper() and ("DISCRIPTION" in " ".join(r).upper() or "DESCRIPTION" in " ".join(r).upper())), None)
        if h_idx is None: return "ERROR", None
        inv = pd.read_csv(INV_URL, skiprows=h_idx)
        inv.columns = [str(c).strip().replace('\n', '').upper() for c in inv.columns]
        inv['TOTAL NO'] = pd.to_numeric(inv['TOTAL NO'], errors='coerce').fillna(0).astype(int)

        # Logs
        log = pd.read_csv(LOG_URL)
        log.columns = [str(c).strip().replace('\n', '').upper() for c in log.columns]
        log = log.rename(columns={'QUANTITY ISSUED': 'QTY_OUT'})
        if 'QTY_OUT' in log.columns:
            log['QTY_OUT'] = pd.to_numeric(log['QTY_OUT'], errors='coerce').fillna(0).astype(int)
        else:
            log = pd.DataFrame(columns=['MATERIAL DESCRIPTION', 'TYPE(RATING)', 'LOCATION', 'QTY_OUT'])

        # Sync
        keys = [k for k in ['MATERIAL DESCRIPTION', 'MATERIAL DISCRIPTION', 'MAKE', 'TYPE(RATING)', 'SIZE', 'LOCATION'] if k in inv.columns and k in log.columns]
        cons = log.groupby(keys)['QTY_OUT'].sum().reset_index()
        merged = pd.merge(inv, cons, on=keys, how='left')
        merged['QTY_OUT'] = merged['QTY_OUT'].fillna(0)
        merged['LIVE STOCK'] = merged['TOTAL NO'] - merged['QTY_OUT']
        return merged, log
    except Exception as e: return str(e), None

# --- 4. DASHBOARD UI ---
inv_df, log_df = load_data()
if isinstance(inv_df, str): st.error(inv_df); st.stop()

# Custom HTML Header
st.markdown("""
<div class="header-box">
    <div class="header-title">🛡️ EMD Material Dashboard</div>
    <div class="header-subtitle">Real-time Executive Inventory Monitoring System</div>
</div>
""", unsafe_allow_html=True)

# Check Alerts
crit = inv_df[inv_df['LIVE STOCK'] <= 2]
if not crit.empty:
    for _, r in crit.iterrows():
        k = f"alert_{r.get('MATERIAL DISCRIPTION')}_{r.get('LOCATION')}"
        if k not in st.session_state and send_email_alert(r.get('MATERIAL DISCRIPTION'), r.get('TYPE(RATING)'), r.get('LOCATION'), r['LIVE STOCK']):
            st.session_state[k]=True

# Top KPI Row
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Items", len(inv_df))
col2.metric("Total Units", int(inv_df['LIVE STOCK'].sum()))
col3.metric("Stock Out Alerts", len(crit), delta_color="inverse")
col4.metric("Locations Monitored", inv_df['LOCATION'].nunique())

st.markdown("---")

# Layout: Sidebar Control + Main Data
with st.sidebar:
    st.header("⚙️ Control Panel")
    locs = ["All"] + sorted(inv_df['LOCATION'].dropna().unique().tolist())
    sel_loc = st.selectbox("Select Location", locs)
    
    st.info("ℹ️ **Pro Tip:** Update the 'Usage Log' in Google Sheets to see changes here instantly.")

# Main Data Table
filtered_df = inv_df if sel_loc == "All" else inv_df[inv_df['LOCATION'] == sel_loc]



tab1, tab2 = st.tabs(["📦 Live Inventory Grid", "📋 Audit Log"])

with tab1:
    st.dataframe(
        filtered_df[['MAKE', 'MATERIAL DISCRIPTION', 'TYPE(RATING)', 'SIZE', 'LOCATION', 'TOTAL NO', 'LIVE STOCK']],
        use_container_width=True,
        hide_index=True,
        column_config={
            "LIVE STOCK": st.column_config.ProgressColumn(
                "Availability",
                help="Current stock level",
                format="%d",
                min_value=0,
                max_value=int(inv_df['TOTAL NO'].max()),
            ),
            "TOTAL NO": st.column_config.NumberColumn("Original Qty"),
        }
    )

with tab2:
    st.dataframe(log_df, use_container_width=True, hide_index=True)
