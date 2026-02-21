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

# --- 2. CSS FOR DASHBOARD DISPLAY ---
st.markdown("""
<style>
    .reportview-container .main .block-container { max-width: 95%; padding-top: 2rem; }
    .styled-table {
        border-collapse: collapse; margin: 25px 0; font-size: 0.9em;
        font-family: sans-serif; min-width: 100%; box-shadow: 0 0 20px rgba(0, 0, 0, 0.15);
    }
    .styled-table thead tr { background-color: #009879; color: #ffffff; text-align: left; }
    .styled-table th, .styled-table td {
        padding: 12px 15px; border: 1px solid #dddddd;
        white-space: normal !important; word-wrap: break-word; vertical-align: top;
    }
    .styled-table tbody tr { border-bottom: 1px solid #dddddd; }
    .styled-table tbody tr:nth-of-type(even) { background-color: #f3f3f3; }
    .styled-table tbody tr:last-of-type { border-bottom: 2px solid #009879; }
</style>
""", unsafe_allow_html=True)

# --- 3. PERSISTENT MEMORY ---
@st.cache_resource
class EmailTracker:
    def __init__(self):
        self.last_sent_date = None

tracker = EmailTracker()

# --- 4. EMAIL ENGINE (MATCHES DASHBOARD FORMAT) ---
def send_daily_summary_email(dataframe):
    try:
        if "email" not in st.secrets: return False
        creds = st.secrets["email"]
        today_str = datetime.now(IST).strftime("%d-%b-%Y")
        msg = MIMEMultipart("alternative")
        msg['Subject'] = f"🛡️ Daily Stock Alert ({today_str}): {len(dataframe)} Items Critical"
        msg['From'], msg['To'] = creds["address"], creds["receiver"]

        # Convert DataFrame to HTML with styling
        html_table = dataframe.to_html(index=False, border=1, justify="left")

        html_content = f"""
        <html>
        <head>
            <style>
                table {{ border-collapse: collapse; width: 100%; font-family: Arial, sans-serif; font-size: 12px; }}
                th {{ background-color: #d9534f; color: white; padding: 10px; text-align: left; }}
                td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                tr:nth-child(even) {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <h2 style="color: #d9534f;">🚨 Critical Stock Report ({today_str})</h2>
            <p>The following items are at or below re-order level:</p>
            {html_table}
            <br>
            <p style="font-size: 11px; color: #555;">Automated EMD Dashboard Report</p>
        </body>
        </html>
        """
        
        msg.attach(MIMEText(html_content, "html"))
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20, context=context) as s:
            s.login(creds["address"], creds["password"])
            s.sendmail(creds["address"], creds["receiver"], msg.as_string())
        return True
    except: return False

# --- 5. DATA LOADING (UPDATED FOR MANUAL STOCK) ---
@st.cache_data(ttl=60)
def load_data():
    try:
        # Load Inventory
        inv_raw = pd.read_csv(INV_URL, header=None).fillna("").astype(str)
        h_idx = next((i for i, r in inv_raw.iterrows() if "MATERIAL" in " ".join(r).upper()), None)
        inv = pd.read_csv(INV_URL, skiprows=h_idx)
        inv.columns = [str(c).strip().upper().replace('DESCRIPTION', 'DISCRIPTION') for c in inv.columns]
        
        # Load Logs
        log = pd.read_csv(LOG_URL)
        log.columns = [str(c).strip().upper().replace('DESCRIPTION', 'DISCRIPTION') for c in log.columns]
        
        # Format the TOTAL NO column as integer
        if 'TOTAL NO' in inv.columns: 
            inv['TOTAL NO'] = pd.to_numeric(inv['TOTAL NO'], errors='coerce').fillna(0).astype(int)
        
        # --- THE FIX ---
        # Instead of subtracting usage, we just set LIVE STOCK to equal TOTAL NO.
        # This keeps the rest of the dashboard running perfectly.
        if 'TOTAL NO' in inv.columns:
            inv['LIVE STOCK'] = inv['TOTAL NO']
        else:
            inv['LIVE STOCK'] = 0
            
        return True, inv, log
    except Exception as e: return False, str(e), None

# --- 6. UI RENDER ---
status, inv_df, log_raw = load_data()
if not status: st.error(inv_df); st.stop()

st.markdown("<h2 style='text-align: center; color: #1e3c72;'>🛡️ EMD Material Dashboard</h2>", unsafe_allow_html=True)

# SIDEBAR FILTER
st.sidebar.header("⚙️ Settings")
loc_list = sorted(inv_df['LOCATION'].replace('nan', 'Unassigned').astype(str).unique().tolist())
sel_loc = st.sidebar.selectbox("Filter Location", ["All"] + loc_list)

# Apply Filter
filtered_inv = inv_df.copy()
if sel_loc != "All":
    filtered_inv = filtered_inv[filtered_inv['LOCATION'].astype(str) == sel_loc]

# Define Columns to Show (The Exact Template)
display_cols = ['MAKE', 'MATERIAL DISCRIPTION', 'TYPE(RATING)', 'SIZE', 'LOCATION', 'LIVE STOCK']
# Filter columns that actually exist
final_cols = [c for c in display_cols if c in inv_df.columns]

# Critical Items
crit = filtered_inv[(filtered_inv['LIVE STOCK'] <= 2) & (filtered_inv['MATERIAL DISCRIPTION'] != 'nan') & (filtered_inv['MATERIAL DISCRIPTION'] != '')]

# Metrics
c1, c2, c3 = st.columns(3)
c1.metric("Catalog Items", len(filtered_inv))
c2.metric("Total Stock", int(filtered_inv['LIVE STOCK'].sum()))
c3.metric("Critical Alerts", len(crit), delta=f"{len(crit)} Low", delta_color="inverse")

# --- TABS ---
tab1, tab2, tab3 = st.tabs(["📦 Inventory Overview", "🚨 Critical Stock", "📋 Usage Log (Full View)"])

with tab1:
    st.dataframe(filtered_inv[final_cols], use_container_width=True, hide_index=True)

with tab2:
    if not crit.empty:
        st.dataframe(crit[final_cols], use_container_width=True, hide_index=True)
    else:
        st.success("✅ No critical items in this location.")

with tab3:
    st.markdown("### 🔍 Full Material Drawal History")
    display_log = log_raw.fillna("").astype(str)
    if 'MATERIAL DISCRIPTION' in display_log.columns:
        display_log = display_log[display_log['MATERIAL DISCRIPTION'].str.len() > 1]
    
    search = st.text_input("Search Logs...", placeholder="Type to filter rows...")
    if search:
        display_log = display_log[display_log.apply(lambda r: search.upper() in r.astype(str).str.upper().to_string(), axis=1)]

    # HTML Render for Text Wrapping
    html = display_log.to_html(classes='styled-table', index=False, escape=False)
    st.markdown(html, unsafe_allow_html=True)

# --- 7. EMAIL LOGIC (SENDS EXACT TABLE) ---
today = datetime.now(IST).strftime("%Y-%m-%d")

# Sends GLOBAL list to ensure nothing is missed.
global_crit = inv_df[(inv_df['LIVE STOCK'] <= 2) & (inv_df['MATERIAL DISCRIPTION'] != 'nan') & (inv_df['MATERIAL DISCRIPTION'] != '')]

if datetime.now(IST).hour >= 9 and tracker.last_sent_date != today and not global_crit.empty:
    # Pass the DataFrame with the exact columns you see in the dashboard
    email_df = global_crit[final_cols]
    
    if send_daily_summary_email(email_df):
        tracker.last_sent_date = today
        st.toast("✅ Daily Summary Sent")
