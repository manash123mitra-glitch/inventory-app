import streamlit as st
import pandas as pd
import smtplib
import time
from email.mime.text import MIMEText
from datetime import datetime

# --- 1. SETTINGS & GIDs ---
SHEET_ID = "1E0ZluX3o7vqnSBAdAMEn_cdxq3ro4F4DXxchOEFcS_g"
INV_GID = "804871972" 
LOG_GID = "1151083374" 

INV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={INV_GID}"
LOG_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={LOG_GID}"

# --- 2. CLEAN UI CONFIG & CSS ---
st.set_page_config(page_title="EMD Material Dashboard", layout="wide", page_icon="🛡️")

# Initialize persistent log
if "email_history" not in st.session_state:
    st.session_state.email_history = []

# CSS: Clean, Professional, Light Theme
st.markdown("""
<style>
    /* Light Grey Background */
    .stApp {
        background-color: #f8f9fa;
    }
    
    /* Professional Blue Header Box */
    .header-box {
        background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 30px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    /* Clean White Metric Cards */
    div[data-testid="stMetric"] {
        background-color: white;
        padding: 15px;
        border-radius: 10px;
        border-left: 5px solid #1e3c72;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
</style>
""", unsafe_allow_html=True)

# --- 3. DATA LOADING (Robust) ---
@st.cache_data(ttl=60)
def load_data():
    try:
        inv_raw = pd.read_csv(INV_URL, header=None).fillna("").astype(str)
        h_idx = next((i for i, r in inv_raw.iterrows() if "MATERIAL" in " ".join(r).upper()), None)
        if h_idx is None: return "HEADER_NOT_FOUND", None
        
        inv = pd.read_csv(INV_URL, skiprows=h_idx)
        inv.columns = [str(c).strip().replace('\n', ' ').upper() for c in inv.columns]
        inv.columns = [c.replace("DESCRIPTION", "DISCRIPTION") for c in inv.columns]
        
        if 'TOTAL NO' in inv.columns:
            inv['TOTAL NO'] = pd.to_numeric(inv['TOTAL NO'], errors='coerce').fillna(0).astype(int)

        log = pd.read_csv(LOG_URL)
        log.columns = [str(c).strip().replace('\n', ' ').upper() for c in log.columns]
        log.columns = [c.replace("DESCRIPTION", "DISCRIPTION") for c in log.columns]
        log = log.rename(columns={'QUANTITY ISSUED': 'QTY_OUT'})
        
        if 'QTY_OUT' in log.columns:
            log['QTY_OUT'] = pd.to_numeric(log['QTY_OUT'], errors='coerce').fillna(0).astype(int)
        
        keys = [k for k in ['MAKE', 'MATERIAL DISCRIPTION', 'TYPE(RATING)', 'SIZE', 'LOCATION'] if k in inv.columns and k in log.columns]
        cons = log.groupby(keys)['QTY_OUT'].sum().reset_index()
        merged = pd.merge(inv, cons, on=keys, how='left')
        merged['QTY_OUT'] = merged['QTY_OUT'].fillna(0)
        merged['LIVE STOCK'] = merged['TOTAL NO'] - merged['QTY_OUT']
        
        return merged, log
    except Exception as e: return str(e), None

def send_email_alert(name, qty, location="N/A", is_test=False):
    try:
        creds = st.secrets["email"]
        label = "TEST" if is_test else "STOCK ALERT"
        msg = MIMEText(f"{label}: {name} is at {qty} units in {location}.")
        msg['Subject'] = f"🚨 {label}: {name}"
        msg['From'], msg['To'] = creds["address"], creds["receiver"]
        
        # Resilient Connection (15s Timeout for Office Networks)
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as s:
            s.starttls()
            s.login(creds["address"], creds["password"])
            s.sendmail(creds["address"], creds["receiver"], msg.as_string())
        
        # Log Success
        st.session_state.email_history.append({
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Item": name,
            "Status": "Sent Successfully"
        })
        return True
    except Exception as e:
        # Log Failure
        st.session_state.email_history.append({
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Item": name,
            "Status": f"Failed: {str(e)}"
        })
        return False

# --- 4. DASHBOARD UI ---
inv_df, log_df = load_data()

if isinstance(inv_df, str):
    st.error(f"Sync Error: {inv_df}"); st.stop()

# Professional Blue Header
st.markdown('<div class="header-box"><h1>🛡️ EMD Material Inventory Dashboard</h1></div>', unsafe_allow_html=True)

# Metrics
c1, c2, c3 = st.columns(3)
c1.metric("Total Line Items", len(inv_df))
c2.metric("Total Stock Units", int(inv_df['LIVE STOCK'].sum()))
crit = inv_df[inv_df['LIVE STOCK'] <= 2]
c3.metric("Low Stock Alerts", len(crit))

# Sidebar Controls
st.sidebar.header("⚙️ Control Panel")

# Test Button
if st.sidebar.button("📧 Send Test Email"):
    if send_email_alert("TEST_CONNECTION", 99, is_test=True):
        st.sidebar.success("Test email sent!")
    else:
        st.sidebar.error("Test failed. Check Email Log tab.")

# Filtering
raw_locs = inv_df['LOCATION'].fillna("Unassigned").astype(str).unique().tolist()
locs = ["All"] + sorted(raw_locs)
sel_loc = st.sidebar.selectbox("Filter Location", locs)

filtered = inv_df.copy()
if sel_loc != "All":
    filtered = filtered[filtered['LOCATION'].astype(str) == sel_loc]

# Column Logic: Hide 'Total No', Show 'Availability'
cols_to_show = [c for c in ['MAKE', 'MATERIAL DISCRIPTION', 'TYPE(RATING)', 'SIZE', 'LOCATION', 'LIVE STOCK'] if c in inv_df.columns]

# --- 5. TABS ---
tab1, tab2, tab3 = st.tabs(["📦 Inventory Grid", "📋 Usage History", "📧 Email Log"])

with tab1:
    st.dataframe(
        filtered[cols_to_show],
        use_container_width=True,
        hide_index=True,
        column_config={
            "LIVE STOCK": st.column_config.ProgressColumn(
                "Availability", 
                help="Units remaining in stock",
                format="%d", 
                min_value=0, 
                max_value=int(inv_df['TOTAL NO'].max() or 100)
            )
        }
    )

with tab2:
    st.dataframe(log_df, use_container_width=True, hide_index=True)

with tab3:
    st.caption("System Communication Log (Newest First)")
    if st.session_state.email_history:
        # Reverse order to show newest first
        st.table(pd.DataFrame(st.session_state.email_history).iloc[::-1])
    else:
        st.info("No email activity recorded in this session.")

# Automatic Alert Trigger
for _, r in crit.iterrows():
    alert_key = f"sent_{r['MATERIAL DISCRIPTION']}_{r['LOCATION']}"
    if alert_key not in st.session_state:
        if send_email_alert(r['MATERIAL DISCRIPTION'], r['LIVE STOCK'], r['LOCATION']):
            st.session_state[alert_key] = True
