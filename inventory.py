import streamlit as st
import pandas as pd
import smtplib
import ssl
from email.mime.text import MIMEText
from datetime import datetime
import pytz # Required for Indian Standard Time

# --- 1. SETTINGS & TIMEZONE ---
SHEET_ID = "1E0ZluX3o7vqnSBAdAMEn_cdxq3ro4F4DXxchOEFcS_g"
INV_GID = "804871972" 
LOG_GID = "1151083374" 

# Define India Timezone
IST = pytz.timezone('Asia/Kolkata')

INV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={INV_GID}"
LOG_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={LOG_GID}"

st.set_page_config(page_title="EMD Material Dashboard", layout="wide", page_icon="🛡️")

# --- 2. EMAIL ENGINE (Safe & Secure) ---
def send_daily_summary_email(items_list):
    try:
        if "email" not in st.secrets: return False
        creds = st.secrets["email"]
        
        # Get Current Date for the Email Subject
        today_str = datetime.now(IST).strftime("%d-%b-%Y")
        
        body = f"🚨 EMD DAILY STOCK REPORT ({today_str})\n" + "="*40 + "\n\n"
        for item in items_list:
            body += f"• {item['name']} | Stock: {item['qty']} | Loc: {item['loc']}\n"
        body += "\n" + "-"*40 + "\nAutomated Alert - Sent once daily after 9:00 AM."
        
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

# --- 3. ROBUST DATA LOADING ---
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

        # Type Safety (Fix for Merge Errors)
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

# --- 4. DASHBOARD UI ---
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

# Sidebar Settings
st.sidebar.header("⚙️ Settings")
if st.sidebar.button("Test Email (Force Send)"):
    # This button allows you to manually force an email instantly for testing
    clist = []
    for _, r in crit.iterrows():
        clist.append({'name': r['MATERIAL DISCRIPTION'], 'qty': r['LIVE STOCK'], 'loc': r['LOCATION']})
    if send_daily_summary_email(clist):
        st.sidebar.success("Test Email Sent Successfully!")
    else:
        st.sidebar.error("Email Failed.")

# Filter Location
loc_list = sorted(inv_df['LOCATION'].replace('nan', 'Unassigned').unique().tolist())
sel_loc = st.sidebar.selectbox("Filter Location", ["All"] + loc_list)
filtered_inv = inv_df.copy()
if sel_loc != "All":
    filtered_inv = filtered_inv[filtered_inv['LOCATION'] == sel_loc]

# Tabs
tab1, tab2 = st.tabs(["📦 Inventory Overview", "📋 Usage Logs"])

with tab1:
    cols = [c for c in ['MAKE', 'MATERIAL DISCRIPTION', 'TYPE(RATING)', 'SIZE', 'LOCATION', 'LIVE STOCK'] if c in inv_df.columns]
    st.dataframe(filtered_inv[cols], use_container_width=True, hide_index=True,
                 column_config={"LIVE STOCK": st.column_config.ProgressColumn("Availability", format="%d", min_value=0, max_value=int(inv_df['TOTAL NO'].max() or 100))})

with tab2:
    st.markdown("### 🔍 Search Material Drawal History")
    search_term = st.text_input("Search Logs (Name, Person, or Item)", placeholder="Type to find transaction...")
    display_log = log_df.copy()
    if search_term:
        display_log = display_log[display_log.apply(lambda row: search_term.upper() in row.astype(str).str.upper().to_string(), axis=1)]
    st.dataframe(display_log, use_container_width=True, hide_index=True)


# --- 5. "ONCE-A-DAY AT 9 AM" LOGIC ---

# Initialize Session State
if "daily_email_sent" not in st.session_state:
    st.session_state.daily_email_sent = False

# Get Current Time in India (IST)
now_ist = datetime.now(IST)
current_hour = now_ist.hour
current_minute = now_ist.minute

# CHECK 1: Is it past 9:00 AM?
is_time_to_send = current_hour >= 9

# CHECK 2: Have we already sent it this session?
has_not_sent_yet = not st.session_state.daily_email_sent

# CHECK 3: Are there critical items?
has_critical_items = not crit.empty

if is_time_to_send and has_not_sent_yet and has_critical_items:
    
    # Prepare the list
    clist = []
    for _, r in crit.iterrows():
        clist.append({'name': r['MATERIAL DISCRIPTION'], 'qty': r['LIVE STOCK'], 'loc': r['LOCATION']})
    
    # Attempt to Send
    if send_daily_summary_email(clist):
        st.toast(f"✅ Daily Summary Email Sent ({len(clist)} items)")
        st.session_state.daily_email_sent = True # LOCK it so it doesn't send again
    else:
        st.toast("⚠️ Daily Email Failed (Check Connection)")

# Display status in sidebar for peace of mind
st.sidebar.markdown("---")
if st.session_state.daily_email_sent:
    st.sidebar.info(f"✅ Daily Email Status: **SENT**")
else:
    if current_hour < 9:
        st.sidebar.warning(f"⏳ Daily Email Status: **WAITING (Scheduled for 09:00 AM)**")
    else:
        st.sidebar.warning(f"⚠️ Daily Email Status: **PENDING (Processing...)**")
