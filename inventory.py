import streamlit as st
import pandas as pd
import smtplib
import ssl
from email.mime.text import MIMEText

# --- 1. SETTINGS ---
SHEET_ID = "1E0ZluX3o7vqnSBAdAMEn_cdxq3ro4F4DXxchOEFcS_g"
INV_GID = "804871972" 
LOG_GID = "1151083374" 

INV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={INV_GID}"
LOG_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={LOG_GID}"

st.set_page_config(page_title="EMD Material Dashboard", layout="wide", page_icon="🛡️")

# --- 2. EMAIL ENGINE ---
def send_summary_email(items_list):
    try:
        if "email" not in st.secrets: return False
        creds = st.secrets["email"]
        
        body = f"🚨 CRITICAL STOCK REPORT ({len(items_list)} Items)\n" + "-"*35 + "\n"
        for item in items_list:
            body += f"• {item['name']} | Stock: {item['qty']} | Loc: {item['loc']}\n"
        
        msg = MIMEText(body)
        msg['Subject'] = f"🛡️ EMD Alert: {len(items_list)} Items Low"
        msg['From'], msg['To'] = creds["address"], creds["receiver"]

        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10, context=context) as s:
            s.login(creds["address"], creds["password"])
            s.sendmail(creds["address"], creds["receiver"], msg.as_string())
        return True
    except: return False

# --- 3. ROBUST DATA LOADING (Fixes the Merge Error) ---
@st.cache_data(ttl=60)
def load_data():
    try:
        # Load Inventory
        inv_raw = pd.read_csv(INV_URL, header=None).fillna("").astype(str)
        h_idx = next((i for i, r in inv_raw.iterrows() if "MATERIAL" in " ".join(r).upper()), None)
        if h_idx is None: return "Header Missing", None
        
        inv = pd.read_csv(INV_URL, skiprows=h_idx)
        inv.columns = [str(c).strip().upper().replace('DESCRIPTION', 'DISCRIPTION') for c in inv.columns]
        
        # Load Logs
        log = pd.read_csv(LOG_URL)
        log.columns = [str(c).strip().upper().replace('DESCRIPTION', 'DISCRIPTION') for c in log.columns]
        log = log.rename(columns={'QUANTITY ISSUED': 'QTY_OUT'})

        # --- THE FIX: Force all Merge Keys to String ---
        merge_keys = ['MAKE', 'MATERIAL DISCRIPTION', 'TYPE(RATING)', 'SIZE', 'LOCATION']
        
        # Only use keys that actually exist in both sheets
        valid_keys = [k for k in merge_keys if k in inv.columns and k in log.columns]
        
        # Convert valid keys to string in BOTH dataframes to prevent MergeError
        for k in valid_keys:
            inv[k] = inv[k].astype(str).str.strip()
            log[k] = log[k].astype(str).str.strip()

        # Handle Numeric Columns
        if 'TOTAL NO' in inv.columns:
            inv['TOTAL NO'] = pd.to_numeric(inv['TOTAL NO'], errors='coerce').fillna(0).astype(int)
        
        if 'QTY_OUT' in log.columns:
            log['QTY_OUT'] = pd.to_numeric(log['QTY_OUT'], errors='coerce').fillna(0).astype(int)

        # Merge
        cons = log.groupby(valid_keys)['QTY_OUT'].sum().reset_index()
        merged = pd.merge(inv, cons, on=valid_keys, how='left').fillna(0)
        merged['LIVE STOCK'] = merged['TOTAL NO'] - merged['QTY_OUT']
        
        return merged, log
    except Exception as e: return str(e), None

# --- 4. UI RENDER ---
inv_df, log_df = load_data()
if isinstance(inv_df, str): st.error(inv_df); st.stop()

st.markdown("""
    <div style='background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%); padding: 20px; border-radius: 10px; color: white; text-align: center; margin-bottom: 20px;'>
        <h1>🛡️ EMD Material Dashboard</h1>
    </div>
""", unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)
c1.metric("Catalog Items", len(inv_df))
c2.metric("Total Stock", int(inv_df['LIVE STOCK'].sum()))
crit = inv_df[inv_df['LIVE STOCK'] <= 2]
c3.metric("Critical Alerts", len(crit))

# Filter & View
loc_list = sorted(inv_df['LOCATION'].replace('nan', 'Unassigned').unique().tolist())
sel_loc = st.sidebar.selectbox("Filter Location", ["All"] + loc_list)
filtered = inv_df.copy()
if sel_loc != "All":
    filtered = filtered[filtered['LOCATION'] == sel_loc]

# Display
cols = [c for c in ['MAKE', 'MATERIAL DISCRIPTION', 'TYPE(RATING)', 'SIZE', 'LOCATION', 'LIVE STOCK'] if c in inv_df.columns]



st.dataframe(filtered[cols], use_container_width=True, hide_index=True,
             column_config={"LIVE STOCK": st.column_config.ProgressColumn("Availability", format="%d", min_value=0, max_value=int(inv_df['TOTAL NO'].max() or 100))})

# Safe Auto-Email Logic
if "email_sent_session" not in st.session_state:
    st.session_state.email_sent_session = False

if not st.session_state.email_sent_session and not crit.empty:
    clist = []
    for _, r in crit.iterrows():
        clist.append({'name': r['MATERIAL DISCRIPTION'], 'qty': r['LIVE STOCK'], 'loc': r['LOCATION']})
    
    if send_summary_email(clist):
        st.toast(f"✅ Alert Sent for {len(clist)} items!")
        st.session_state.email_sent_session = True
