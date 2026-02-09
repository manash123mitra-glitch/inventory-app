import streamlit as st
import pandas as pd
import smtplib
import ssl
from email.mime.text import MIMEText
from datetime import datetime

# --- 1. SETTINGS ---
SHEET_ID = "1E0ZluX3o7vqnSBAdAMEn_cdxq3ro4F4DXxchOEFcS_g"
INV_GID = "804871972" 
LOG_GID = "1151083374" 

INV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={INV_GID}"
LOG_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={LOG_GID}"

st.set_page_config(page_title="EMD Material Dashboard", layout="wide", page_icon="🛡️")

# --- 2. SAFE EMAIL ENGINE (Won't Crash the App) ---
def send_summary_email(items_list, is_test=False):
    try:
        # Check if secrets exist
        if "email" not in st.secrets:
            return False, "Secrets Missing"

        creds = st.secrets["email"]
        label = "TEST" if is_test else "CRITICAL STOCK"
        subject = f"🛡️ EMD: {label} Signal"
        
        # Build Body
        if is_test:
            body = "Connection Test Successful."
        else:
            body = f"🚨 CRITICAL STOCK REPORT ({len(items_list)} Items)\n" + "-"*35 + "\n"
            for item in items_list:
                body += f"• {item['name']} | Stock: {item['qty']} | Loc: {item['loc']}\n"
            body += "\n" + "-"*35
        
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'], msg['To'] = creds["address"], creds["receiver"]

        # FAIL-SAFE CONNECTION (Attempts to connect, catches 'Block' errors safely)
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10, context=context) as s:
            s.login(creds["address"], creds["password"])
            s.sendmail(creds["address"], creds["receiver"], msg.as_string())
        
        return True, "Email Sent"

    except Exception as e:
        # If Gmail blocks us, we just return the error nicely instead of crashing
        error_msg = str(e)
        if "closed" in error_msg or "421" in error_msg:
            return False, "Gmail Temporary Ban (Wait 24hrs)"
        return False, f"Connection Error: {error_msg}"

# --- 3. DATA LOADING ---
@st.cache_data(ttl=60)
def load_data():
    try:
        # Load Inventory
        inv_raw = pd.read_csv(INV_URL, header=None).fillna("").astype(str)
        h_idx = next((i for i, r in inv_raw.iterrows() if "MATERIAL" in " ".join(r).upper()), None)
        if h_idx is None: return "Header Missing", None
        inv = pd.read_csv(INV_URL, skiprows=h_idx)
        inv.columns = [str(c).strip().upper().replace('DESCRIPTION', 'DISCRIPTION') for c in inv.columns]
        if 'TOTAL NO' in inv.columns:
            inv['TOTAL NO'] = pd.to_numeric(inv['TOTAL NO'], errors='coerce').fillna(0).astype(int)

        # Load Logs
        log = pd.read_csv(LOG_URL)
        log.columns = [str(c).strip().upper().replace('DESCRIPTION', 'DISCRIPTION') for c in log.columns]
        log = log.rename(columns={'QUANTITY ISSUED': 'QTY_OUT'})
        if 'QTY_OUT' in log.columns:
            log['QTY_OUT'] = pd.to_numeric(log['QTY_OUT'], errors='coerce').fillna(0).astype(int)

        # Merge
        keys = [k for k in ['MAKE', 'MATERIAL DISCRIPTION', 'TYPE(RATING)', 'SIZE', 'LOCATION'] if k in inv.columns and k in log.columns]
        cons = log.groupby(keys)['QTY_OUT'].sum().reset_index()
        merged = pd.merge(inv, cons, on=keys, how='left').fillna(0)
        merged['LIVE STOCK'] = merged['TOTAL NO'] - merged['QTY_OUT']
        return merged, log
    except Exception as e: return str(e), None

# --- 4. DASHBOARD RENDER ---
inv_df, log_df = load_data()
if isinstance(inv_df, str): st.error(inv_df); st.stop()

# Header
st.markdown("""
    <div style='background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%); padding: 20px; border-radius: 10px; color: white; text-align: center; margin-bottom: 20px;'>
        <h1>🛡️ EMD Material Dashboard</h1>
    </div>
""", unsafe_allow_html=True)

# Metrics
c1, c2, c3 = st.columns(3)
c1.metric("Catalog Items", len(inv_df))
c2.metric("Total Stock", int(inv_df['LIVE STOCK'].sum()))
crit = inv_df[inv_df['LIVE STOCK'] <= 2]
c3.metric("Critical Alerts", len(crit))

# --- SIDEBAR STATUS ---
st.sidebar.header("⚙️ System Status")

# Manual Test Button
if st.sidebar.button("Test Email Connection"):
    success, msg = send_summary_email([], is_test=True)
    if success:
        st.sidebar.success(msg)
    else:
        st.sidebar.warning(f"⚠️ {msg}")

# Filter
loc_list = sorted(inv_df['LOCATION'].fillna("Unassigned").astype(str).unique().tolist())
sel_loc = st.sidebar.selectbox("Filter Location", ["All"] + loc_list)
filtered = inv_df.copy()
if sel_loc != "All":
    filtered = filtered[filtered['LOCATION'].astype(str) == sel_loc]

# Data Table
cols = [c for c in ['MAKE', 'MATERIAL DISCRIPTION', 'TYPE(RATING)', 'SIZE', 'LOCATION', 'LIVE STOCK'] if c in inv_df.columns]
st.dataframe(filtered[cols], use_container_width=True, hide_index=True,
             column_config={"LIVE STOCK": st.column_config.ProgressColumn("Availability", format="%d", min_value=0, max_value=int(inv_df['TOTAL NO'].max() or 100))})

# --- AUTO ALERT LOGIC (SAFE MODE) ---
# This runs silently. If it fails, it prints to logs but DOES NOT CRASH the app.
if "email_attempted" not in st.session_state:
    st.session_state.email_attempted = False

if not st.session_state.email_attempted and not crit.empty:
    critical_list = []
    for _, r in crit.iterrows():
        critical_list.append({'name': r['MATERIAL DISCRIPTION'], 'qty': r['LIVE STOCK'], 'loc': r['LOCATION']})
    
    # Attempt to send (Silently)
    success, msg = send_summary_email(critical_list)
    
    if success:
        st.toast(f"✅ Alert Sent for {len(critical_list)} items!")
        st.session_state.email_attempted = True
    else:
        # Show a small warning toast instead of crashing
        st.toast(f"⚠️ Email Offline: {msg}", icon="🔌")
        st.session_state.email_attempted = True # Stop trying for this session
