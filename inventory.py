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

# --- 2. CSS STYLING (For Wrapping Table) ---
st.markdown("""
<style>
    /* Force the Table to Wrap Text and look professional */
    table {
        width: 100% !important;
        border-collapse: collapse !important;
    }
    thead tr th {
        background-color: #f0f2f6 !important;
        color: #31333F !important;
        font-weight: bold !important;
        border: 1px solid #e6e9ef !important;
    }
    tbody tr td {
        word-wrap: break-word !important;
        white-space: normal !important; /* This triggers the wrapping */
        vertical-align: top !important;
        border: 1px solid #e6e9ef !important;
        padding: 8px !important;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. PERSISTENT MEMORY ---
@st.cache_resource
class EmailTracker:
    def __init__(self):
        self.last_sent_date = None

tracker = EmailTracker()

# --- 4. EMAIL ENGINE ---
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

# --- 5. DATA LOADING ---
@st.cache_data(ttl=60)
def load_data():
    try:
        inv_raw = pd.read_csv(INV_URL, header=None).fillna("").astype(str)
        h_idx = next((i for i, r in inv_raw.iterrows() if "MATERIAL" in " ".join(r).upper()), None)
        inv = pd.read_csv(INV_URL, skiprows=h_idx)
        inv.columns = [str(c).strip().upper().replace('DESCRIPTION', 'DISCRIPTION') for c in inv.columns]
        
        log = pd.read_csv(LOG_URL)
        log.columns = [str(c).strip().upper().replace('DESCRIPTION', 'DISCRIPTION') for c in log.columns]
        log = log.rename(columns={'QUANTITY ISSUED': 'QTY_OUT', 'ISSUED QUANTITY': 'QTY_OUT', 'QTY': 'QTY_OUT'})

        # Clean Column Names in Log for Display
        log = log.rename(columns={
            'MATERIAL DISCRIPTION': 'Item Name',
            'QTY_OUT': 'Qty',
            'ISSUED TO': 'Receiver',
            'NAME': 'Receiver',
            'REMARKS': 'Remarks',
            'DATE': 'Date',
            'SIZE': 'Size',
            'MAKE': 'Make'
        })

        merge_keys = ['MAKE', 'MATERIAL DISCRIPTION', 'TYPE(RATING)', 'SIZE', 'LOCATION']
        # Note: We use original column names for merging, so we map them back briefly if needed, 
        # but for simplicity, we will just use the renamed ones for display logic.
        # To avoid breaking the Merge, let's keep original names in backend and rename ONLY for display.
        
        # Reloading cleanly to separate Backend vs Frontend Logic
        return True, inv, log
    except Exception as e: return False, str(e), None

# --- 6. DATA PROCESSING ---
status, inv, log = load_data()
if not status: st.error(inv); st.stop()

# Backend Merge Logic (Using raw names)
inv_cols = inv.columns
log_cols = log.columns

# Normalize for Merge
# We need to ensure we merge on the right columns even if we renamed them above? 
# Actually, let's be safer: Load raw for calc, rename later for display.
# Re-implementing load_data specifically to be safe.
inv_raw = pd.read_csv(INV_URL, skiprows=next((i for i, r in pd.read_csv(INV_URL, header=None).fillna("").astype(str).iterrows() if "MATERIAL" in " ".join(r).upper()), 0))
inv_raw.columns = [str(c).strip().upper().replace('DESCRIPTION', 'DISCRIPTION') for c in inv_raw.columns]

log_raw = pd.read_csv(LOG_URL)
log_raw.columns = [str(c).strip().upper().replace('DESCRIPTION', 'DISCRIPTION') for c in log_raw.columns]
log_raw = log_raw.rename(columns={'QUANTITY ISSUED': 'QTY_OUT'})

# Fix Types
keys = ['MAKE', 'MATERIAL DISCRIPTION', 'TYPE(RATING)', 'SIZE', 'LOCATION']
actual_keys = [k for k in keys if k in inv_raw.columns and k in log_raw.columns]

for k in actual_keys:
    inv_raw[k] = inv_raw[k].astype(str).str.strip()
    log_raw[k] = log_raw[k].astype(str).str.strip()

if 'TOTAL NO' in inv_raw.columns: inv_raw['TOTAL NO'] = pd.to_numeric(inv_raw['TOTAL NO'], errors='coerce').fillna(0).astype(int)
if 'QTY_OUT' in log_raw.columns: log_raw['QTY_OUT'] = pd.to_numeric(log_raw['QTY_OUT'], errors='coerce').fillna(0).astype(int)

# Merge
cons = log_raw.groupby(actual_keys)['QTY_OUT'].sum().reset_index()
merged = pd.merge(inv_raw, cons, on=actual_keys, how='left').fillna(0)
merged['LIVE STOCK'] = merged['TOTAL NO'] - merged['QTY_OUT']

# --- 7. UI RENDER ---
st.markdown("<h2 style='text-align: center;'>🛡️ EMD Material Dashboard</h2>", unsafe_allow_html=True)
crit = merged[(merged['LIVE STOCK'] <= 2) & (merged['MATERIAL DISCRIPTION'] != 'nan') & (merged['MATERIAL DISCRIPTION'] != '')]

tab1, tab2, tab3 = st.tabs(["📦 Inventory", "🚨 Critical Stock", "📋 Usage Log (Auto-Wrap)"])

with tab1:
    st.dataframe(merged, use_container_width=True, hide_index=True)

with tab2:
    st.dataframe(crit, use_container_width=True, hide_index=True)

# --- TAB 3: THE WRAPPING FIX ---
with tab3:
    st.markdown("### 🔍 Material Drawal History")
    
    # 1. Prepare Display Data
    display_log = log_raw.copy()
    display_log = display_log[display_log['MATERIAL DISCRIPTION'].str.len() > 1] # Remove empty rows
    
    # 2. Select & Rename Columns for nice display
    # We select only the most important columns to ensure it fits on one screen width
    cols_to_show = ['DATE', 'MATERIAL DISCRIPTION', 'SIZE', 'QTY_OUT', 'ISSUED TO', 'REMARKS']
    # Check if they exist (sometimes names vary)
    final_cols = [c for c in cols_to_show if c in display_log.columns]
    
    view = display_log[final_cols].rename(columns={
        'MATERIAL DISCRIPTION': 'Item Name',
        'QTY_OUT': 'Qty',
        'ISSUED TO': 'Receiver',
        'REMARKS': 'Remarks',
        'DATE': 'Date',
        'SIZE': 'Size'
    })
    
    # 3. Search Filter
    search = st.text_input("Search Logs...", placeholder="Type to filter...")
    if search:
        view = view[view.apply(lambda r: search.upper() in r.astype(str).str.upper().to_string(), axis=1)]
    
    # 4. Limit Rows for Performance (Optional, keeps it fast)
    # We show the last 50 entries by default so the page doesn't crash with huge tables
    if len(view) > 50 and not search:
        st.caption("Showing last 50 transactions. Use search to find older logs.")
        view = view.tail(50)
    
    view = view.iloc[::-1] # Reverse order (newest first)

    # 5. RENDER AS HTML TABLE (This supports wrapping!)
    # st.table automatically wraps text to fit the column width.
    st.table(view)

# --- 8. EMAIL LOGIC ---
today = datetime.now(IST).strftime("%Y-%m-%d")
if datetime.now(IST).hour >= 9 and tracker.last_sent_date != today and not crit.empty:
    clist = [{'name': r['MATERIAL DISCRIPTION'], 'qty': r['LIVE STOCK'], 'loc': r['LOCATION']} for _, r in crit.iterrows()]
    if send_daily_summary_email(clist):
        tracker.last_sent_date = today
        st.toast("✅ Daily Summary Sent")
