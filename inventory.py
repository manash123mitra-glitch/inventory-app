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

# --- 2. SAFE EMAIL ENGINE ---
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

# --- 3. ROBUST DATA LOADING ---
@st.cache_data(ttl=60)
def load_data():
    try:
        # A. LOAD INVENTORY SHEET
        inv_raw = pd.read_csv(INV_URL, header=None).fillna("").astype(str)
        # Find header row dynamically
        h_idx = next((i for i, r in inv_raw.iterrows() if "MATERIAL" in " ".join(r).upper()), None)
        if h_idx is None: return "Header Missing", None
        
        inv = pd.read_csv(INV_URL, skiprows=h_idx)
        inv.columns = [str(c).strip().upper().replace('DESCRIPTION', 'DISCRIPTION') for c in inv.columns]
        
        # B. LOAD LOG SHEET (Usage Details)
        log = pd.read_csv(LOG_URL)
        log.columns = [str(c).strip().upper().replace('DESCRIPTION', 'DISCRIPTION') for c in log.columns]
        
        # Standardize 'Quantity Issued' column name
        log = log.rename(columns={
            'QUANTITY ISSUED': 'QTY_OUT',
            'ISSUED QUANTITY': 'QTY_OUT',
            'QTY': 'QTY_OUT'
        })

        # --- THE TYPE-SAFE FIX (Prevents Merge Errors) ---
        # We force these columns to be text strings in BOTH sheets
        merge_keys = ['MAKE', 'MATERIAL DISCRIPTION', 'TYPE(RATING)', 'SIZE', 'LOCATION']
        valid_keys = [k for k in merge_keys if k in inv.columns and k in log.columns]
        
        for k in valid_keys:
            inv[k] = inv[k].astype(str).str.strip()
            log[k] = log[k].astype(str).str.strip()

        # Handle Numbers
        if 'TOTAL NO' in inv.columns:
            inv['TOTAL NO'] = pd.to_numeric(inv['TOTAL NO'], errors='coerce').fillna(0).astype(int)
        
        if 'QTY_OUT' in log.columns:
            log['QTY_OUT'] = pd.to_numeric(log['QTY_OUT'], errors='coerce').fillna(0).astype(int)

        # C. MERGE FOR LIVE STOCK CALCULATION
        cons = log.groupby(valid_keys)['QTY_OUT'].sum().reset_index()
        merged = pd.merge(inv, cons, on=valid_keys, how='left').fillna(0)
        merged['LIVE STOCK'] = merged['TOTAL NO'] - merged['QTY_OUT']
        
        return merged, log
    except Exception as e: return str(e), None

# --- 4. DASHBOARD UI ---
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
c2.metric("Current Stock", int(inv_df['LIVE STOCK'].sum()))
crit = inv_df[inv_df['LIVE STOCK'] <= 2]
c3.metric("Critical Alerts", len(crit))

# Sidebar Filters
loc_list = sorted(inv_df['LOCATION'].replace('nan', 'Unassigned').unique().tolist())
sel_loc = st.sidebar.selectbox("Filter Location", ["All"] + loc_list)

filtered_inv = inv_df.copy()
if sel_loc != "All":
    filtered_inv = filtered_inv[filtered_inv['LOCATION'] == sel_loc]

# --- 5. TABS ---
tab1, tab2 = st.tabs(["📦 Inventory Overview", "📋 Detailed Usage Logs"])

# TAB 1: INVENTORY GRID
with tab1:
    cols = [c for c in ['MAKE', 'MATERIAL DISCRIPTION', 'TYPE(RATING)', 'SIZE', 'LOCATION', 'LIVE STOCK'] if c in inv_df.columns]
    st.dataframe(
        filtered_inv[cols], 
        use_container_width=True, 
        hide_index=True,
        column_config={
            "LIVE STOCK": st.column_config.ProgressColumn(
                "Availability", 
                format="%d", 
                min_value=0, 
                max_value=int(inv_df['TOTAL NO'].max() or 100)
            )
        }
    )

# TAB 2: DETAILED USAGE LOGS (The Missing Part)
with tab2:
    st.markdown("### 🔍 Search Material Drawal History")
    
    # Filter Controls for Usage
    c_search, c_filter = st.columns([3, 1])
    search_term = c_search.text_input("Search Logs (Name, Person, or Item)", placeholder="Type to find transaction...")
    
    # Show Raw Log Data
    display_log = log_df.copy()
    
    # Filter Logic
    if search_term:
        display_log = display_log[display_log.apply(lambda row: search_term.upper() in row.astype(str).str.upper().to_string(), axis=1)]
    
    # Define columns to show (Ensure DATE and ISSUED TO are visible)
    # We try to find columns that look like "Issued To", "Receiver", "Name", "Date"
    log_cols = display_log.columns.tolist()
    priority_cols = ['DATE', 'MATERIAL DISCRIPTION', 'SIZE', 'QTY_OUT', 'ISSUED TO', 'NAME', 'REMARKS']
    
    # Sort columns to put priority ones first
    final_cols = [c for c in priority_cols if c in log_cols] + [c for c in log_cols if c not in priority_cols]
    
    st.dataframe(
        display_log[final_cols], 
        use_container_width=True, 
        hide_index=True
    )

# --- 6. AUTO-EMAIL LOGIC (Silent Mode) ---
if "email_sent_session" not in st.session_state:
    st.session_state.email_sent_session = False

if not st.session_state.email_sent_session and not crit.empty:
    # Prepare list
    clist = []
    for _, r in crit.iterrows():
        clist.append({'name': r['MATERIAL DISCRIPTION'], 'qty': r['LIVE STOCK'], 'loc': r['LOCATION']})
    
    # Send Summary
    if send_summary_email(clist):
        st.toast(f"✅ Alert Sent for {len(clist)} items!")
        st.session_state.email_sent_session = True
