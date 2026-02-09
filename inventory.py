import streamlit as st
import pandas as pd
import smtplib
import ssl
from email.mime.text import MIMEText
from datetime import datetime
import pytz

# --- 1. GLOBAL SETTINGS ---
SHEET_ID = "1E0ZluX3o7vqnSBAdAMEn_cdxq3ro4F4DXxchOEFcS_g"
INV_GID = "804871972" 
LOG_GID = "1151083374" 

# Define India Timezone
IST = pytz.timezone('Asia/Kolkata')

INV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={INV_GID}"
LOG_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={LOG_GID}"

st.set_page_config(page_title="EMD Material Dashboard", layout="wide", page_icon="🛡️")

# --- 2. PERSISTENT MEMORY (Prevents Email Spam) ---
@st.cache_resource
class EmailTracker:
    def __init__(self):
        self.last_sent_date = None

tracker = EmailTracker()

# --- 3. EMAIL ENGINE ---
def send_daily_summary_email(items_list):
    try:
        if "email" not in st.secrets: return False
        creds = st.secrets["email"]
        
        today_str = datetime.now(IST).strftime("%d-%b-%Y")
        
        body = f"🚨 EMD DAILY STOCK REPORT ({today_str})\n" + "="*40 + "\n\n"
        for item in items_list:
            body += f"• {item['name']} | Stock: {item['qty']} | Loc: {item['loc']}\n"
        body += "\n" + "-"*40 + "\nAutomated Alert - Sent once daily."
        
        msg = MIMEText(body)
        msg['Subject'] = f"🛡️ Daily Alert ({today_str}): {len(items_list)} Items Critical"
        msg['From'], msg['To'] = creds["address"], creds["receiver"]

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
        # Load Inventory
        inv_raw = pd.read_csv(INV_URL, header=None).fillna("").astype(str)
        h_idx = next((i for i, r in inv_raw.iterrows() if "MATERIAL" in " ".join(r).upper()), None)
        if h_idx is None: return "Header Missing", None
        
        inv = pd.read_csv(INV_URL, skiprows=h_idx)
        inv.columns = [str(c).strip().upper().replace('DESCRIPTION', 'DISCRIPTION') for c in inv.columns]
        
        # Load Logs
        log = pd.read_csv(LOG_URL)
        log.columns = [str(c).strip().upper().replace('DESCRIPTION', 'DISCRIPTION') for c in log.columns]
        log = log.rename(columns={'QUANTITY ISSUED': 'QTY_OUT', 'ISSUED QUANTITY': 'QTY_OUT', 'QTY': 'QTY_OUT'})

        # Type Safety
        merge_keys = ['MAKE', 'MATERIAL DISCRIPTION', 'TYPE(RATING)', 'SIZE', 'LOCATION']
        valid_keys = [k for k in merge_keys if k in inv.columns and k in log.columns]
        
        for k in valid_keys:
            inv[k] = inv[k].astype(str).str.strip()
            log[k] = log[k].astype(str).str.strip()

        # Numerics
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

# --- 5. DASHBOARD UI ---
inv_df, log_df = load_data()
if isinstance(inv_df, str): st.error(inv_df); st.stop()

st.markdown("""
    <div style='background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%); padding: 20px; border-radius: 10px; color: white; text-align: center; margin-bottom: 20px;'>
        <h1>🛡️ EMD Material Dashboard</h1>
    </div>
""", unsafe_allow_html=True)

# Identify Critical Items
crit = inv_df[inv_df['LIVE STOCK'] <= 2]

c1, c2, c3 = st.columns(3)
c1.metric("Catalog Items", len(inv_df))
c2.metric("Total Stock", int(inv_df['LIVE STOCK'].sum()))
c3.metric("Critical Alerts", len(crit), delta=f"{len(crit)} Items Low", delta_color="inverse")

# Sidebar Status
st.sidebar.header("⚙️ Status Panel")
current_time_str = datetime.now(IST).strftime("%I:%M %p")
st.sidebar.write(f"🕒 Time: {current_time_str}")

today_str = datetime.now(IST).strftime("%Y-%m-%d")
if tracker.last_sent_date == today_str:
    st.sidebar.success("✅ Email Sent Today")
else:
    st.sidebar.info("⏳ Email Pending (9 AM)")

# Filters
loc_list = sorted(inv_df['LOCATION'].replace('nan', 'Unassigned').unique().tolist())
sel_loc = st.sidebar.selectbox("Filter Location", ["All"] + loc_list)
filtered_inv = inv_df.copy()
if sel_loc != "All":
    filtered_inv = filtered_inv[filtered_inv['LOCATION'] == sel_loc]

# --- TABS ---
tab1, tab2, tab3 = st.tabs(["📦 Inventory Overview", "🚨 Critical Stock (Action Req.)", "📋 Usage Logs"])

# TAB 1: ALL INVENTORY
with tab1:
    cols = [c for c in ['MAKE', 'MATERIAL DISCRIPTION', 'TYPE(RATING)', 'SIZE', 'LOCATION', 'LIVE STOCK'] if c in inv_df.columns]
    st.dataframe(filtered_inv[cols], use_container_width=True, hide_index=True,
                 column_config={"LIVE STOCK": st.column_config.ProgressColumn("Availability", format="%d", min_value=0, max_value=int(inv_df['TOTAL NO'].max() or 100))})

# TAB 2: CRITICAL STOCK (NEW)
with tab2:
    if not crit.empty:
        st.error(f"⚠️ Action Required: {len(crit)} items are at or below Minimum Stock Level (2).")
        
        # Display Critical Table
        crit_cols = [c for c in ['MAKE', 'MATERIAL DISCRIPTION', 'TYPE(RATING)', 'SIZE', 'LOCATION', 'LIVE STOCK'] if c in inv_df.columns]
        st.dataframe(crit[crit_cols], use_container_width=True, hide_index=True)
        
        # Download Button
        csv = crit[crit_cols].to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Critical List (CSV)",
            data=csv,
            file_name=f"Critical_Stock_{today_str}.csv",
            mime='text/csv',
        )
    else:
        st.success("✅ All Stock Levels are Healthy.")

# TAB 3: USAGE LOGS
with tab2: # Note: This should be tab3 logic, fixing indent below
    pass 

with tab3:
    st.markdown("### 🔍 Material Drawal History")
    search_term = st.text_input("Search Logs", placeholder="Name or Item...")
    display_log = log_df.copy()
    if search_term:
        display_log = display_log[display_log.apply(lambda row: search_term.upper() in row.astype(str).str.upper().to_string(), axis=1)]
    st.dataframe(display_log, use_container_width=True, hide_index=True)


# --- 6. EMAIL LOGIC (ONCE A DAY) ---
current_hour = datetime.now(IST).hour
email_already_sent_today = (tracker.last_sent_date == today_str)
is_time = (current_hour >= 9)
items_exist = not crit.empty

if is_time and items_exist and not email_already_sent_today:
    
    clist = []
    for _, r in crit.iterrows():
        clist.append({'name': r['MATERIAL DISCRIPTION'], 'qty': r['LIVE STOCK'], 'loc': r['LOCATION']})
    
    if send_daily_summary_email(clist):
        tracker.last_sent_date = today_str 
        st.toast(f"✅ Daily Summary Sent ({len(clist)} items)")
        st.sidebar.success("✅ Daily Email: SENT")
