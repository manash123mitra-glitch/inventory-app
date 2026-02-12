import streamlit as st
import pandas as pd
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import pytz

# --- 1. GLOBAL SETTINGS ---
SHEET_ID = "1E0ZluX3o7vqnSBAdAMEn_cdxq3ro4F4DXxchOEFcS_g"
INV_GID = "804871972" 
LOG_GID = "1151083374" 

IST = pytz.timezone('Asia/Kolkata')

INV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={INV_GID}"
LOG_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={LOG_GID}"

st.set_page_config(page_title="EMD Material Dashboard", layout="wide", page_icon="🛡️")

# --- 2. PERSISTENT MEMORY ---
@st.cache_resource
class EmailTracker:
    def __init__(self):
        self.last_sent_date = None

tracker = EmailTracker()

# --- 3. HTML EMAIL ENGINE ---
def send_daily_summary_email(items_list):
    try:
        if "email" not in st.secrets: return False
        creds = st.secrets["email"]
        today_str = datetime.now(IST).strftime("%d-%b-%Y")
        msg = MIMEMultipart("alternative")
        msg['Subject'] = f"🛡️ Daily Stock Alert ({today_str}): {len(items_list)} Items Critical"
        msg['From'], msg['To'] = creds["address"], creds["receiver"]

        html_content = f"<html><body><h2 style='color: #d9534f;'>🚨 Critical Stock Report</h2><table border='1' style='border-collapse: collapse; width: 100%;'><tr><th>Material</th><th>Stock</th><th>Location</th></tr>"
        for item in items_list:
            html_content += f"<tr><td>{item['name']}</td><td>{item['qty']}</td><td>{item['loc']}</td></tr>"
        html_content += "</table></body></html>"
        
        msg.attach(MIMEText(html_content, "html"))
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20, context=context) as s:
            s.login(creds["address"], creds["password"])
            s.sendmail(creds["address"], creds["receiver"], msg.as_string())
        return True
    except: return False

# --- 4. DATA LOADING ---
@st.cache_data(ttl=60)
def load_data():
    try:
        inv_raw = pd.read_csv(INV_URL, header=None).fillna("").astype(str)
        h_idx = next((i for i, r in inv_raw.iterrows() if "MATERIAL" in " ".join(r).upper()), None)
        inv = pd.read_csv(INV_URL, skiprows=h_idx)
        inv.columns = [str(c).strip().upper().replace('DESCRIPTION', 'DISCRIPTION') for c in inv.columns]
        
        log = pd.read_csv(LOG_URL)
        log.columns = [str(c).strip().upper().replace('DESCRIPTION', 'DISCRIPTION') for c in log.columns]
        log = log.rename(columns={'QUANTITY ISSUED': 'QTY_OUT', 'QTY': 'QTY_OUT'})

        merge_keys = ['MAKE', 'MATERIAL DISCRIPTION', 'TYPE(RATING)', 'SIZE', 'LOCATION']
        valid_keys = [k for k in merge_keys if k in inv.columns and k in log.columns]
        
        for k in valid_keys:
            inv[k] = inv[k].astype(str).str.strip()
            log[k] = log[k].astype(str).str.strip()

        if 'TOTAL NO' in inv.columns:
            inv['TOTAL NO'] = pd.to_numeric(inv['TOTAL NO'], errors='coerce').fillna(0).astype(int)
        if 'QTY_OUT' in log.columns:
            log['QTY_OUT'] = pd.to_numeric(log['QTY_OUT'], errors='coerce').fillna(0).astype(int)

        cons = log.groupby(valid_keys)['QTY_OUT'].sum().reset_index()
        merged = pd.merge(inv, cons, on=valid_keys, how='left').fillna(0)
        merged['LIVE STOCK'] = merged['TOTAL NO'] - merged['QTY_OUT']
        return merged, log
    except Exception as e: return str(e), None

# --- 5. UI ---
inv_df, log_df = load_data()
if isinstance(inv_df, str): st.error(inv_df); st.stop()

st.markdown("<h1 style='text-align: center; color: #1e3c72;'>🛡️ EMD Material Dashboard</h1>", unsafe_allow_html=True)
crit = inv_df[(inv_df['LIVE STOCK'] <= 2) & (inv_df['MATERIAL DISCRIPTION'] != 'nan') & (inv_df['MATERIAL DISCRIPTION'] != '')]

# Sidebar
loc_list = sorted(inv_df['LOCATION'].replace('nan', 'Unassigned').unique().tolist())
sel_loc = st.sidebar.selectbox("Filter Location", ["All"] + loc_list)
filtered_inv = inv_df.copy()
if sel_loc != "All":
    filtered_inv = filtered_inv[filtered_inv['LOCATION'] == sel_loc]

tab1, tab2, tab3 = st.tabs(["📦 Inventory", "🚨 Critical", "📋 Usage Log"])

with tab1:
    st.dataframe(filtered_inv, use_container_width=True, hide_index=True)

with tab2:
    st.dataframe(crit, use_container_width=True, hide_index=True)

# --- TAB 3: THE FORMATTING FIX ---
with tab3:
    st.markdown("### 📋 Material Drawal History")
    
    # 1. Cleaning
    clean_log = log_df.copy().replace('nan', '')
    clean_log = clean_log[clean_log['MATERIAL DISCRIPTION'].str.len() > 1]
    
    # 2. Search
    search = st.text_input("Search Logs...")
    if search:
        clean_log = clean_log[clean_log.apply(lambda r: search.upper() in r.astype(str).str.upper().to_string(), axis=1)]

    # 3. DISPLAY WITH WRAPPING & AUTO-WIDTH
    # This configuration forces columns to be wide enough or wrap text to fit.
    st.dataframe(
        clean_log,
        use_container_width=True,
        hide_index=True,
        column_config={
            "DATE": st.column_config.TextColumn("Date", width="small"),
            "MATERIAL DISCRIPTION": st.column_config.TextColumn("Material Name", width="large"),
            "MAKE": st.column_config.TextColumn("Make", width="medium"),
            "SIZE": st.column_config.TextColumn("Size", width="medium"),
            "QTY_OUT": st.column_config.NumberColumn("Qty", width="small"),
            "REMARKS": st.column_config.TextColumn("Remarks", width="large"),
        }
    )

# --- 6. EMAIL LOGIC ---
today = datetime.now(IST).strftime("%Y-%m-%d")
if datetime.now(IST).hour >= 9 and tracker.last_sent_date != today and not crit.empty:
    clist = [{'name': r['MATERIAL DISCRIPTION'], 'qty': r['LIVE STOCK'], 'loc': r['LOCATION']} for _, r in crit.iterrows()]
    if send_daily_summary_email(clist):
        tracker.last_sent_date = today
        st.toast("✅ Daily Summary Sent")
