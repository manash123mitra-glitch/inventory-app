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

# --- 2. PREMIUM CSS STYLING ---
st.markdown("""
<style>
    /* Import Premium Modern Font */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    /* Apply font globally */
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif !important;
    }

    /* Widen the container */
    .reportview-container .main .block-container { 
        max-width: 95%; 
        padding-top: 2rem; 
    }

    /* Beautiful Header */
    .header-box {
        background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
        padding: 25px; 
        border-radius: 12px; 
        color: white;
        text-align: center; 
        margin-bottom: 30px; 
        box-shadow: 0 8px 16px rgba(30, 60, 114, 0.2);
    }

    /* 3D Elevated Metric Cards */
    div[data-testid="metric-container"] {
        background-color: #ffffff;
        border: 1px solid #f0f2f6;
        padding: 15px 20px;
        border-radius: 12px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.04);
        transition: all 0.3s ease;
        border-left: 5px solid #2a5298;
    }
    div[data-testid="metric-container"]:hover {
        transform: translateY(-4px);
        box-shadow: 0 10px 15px rgba(0,0,0,0.1);
    }

    /* Modern SaaS HTML Table (For Tab 3) */
    .styled-table {
        border-collapse: collapse; 
        margin: 20px 0; 
        font-size: 0.95em;
        min-width: 100%; 
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
        border-radius: 8px;
        overflow: hidden;
    }
    .styled-table thead tr { 
        background-color: #f8f9fa;
        color: #1e3c72; 
        text-align: left; 
        font-weight: 700;
        border-bottom: 2px solid #e2e8f0;
    }
    .styled-table th, .styled-table td {
        padding: 14px 18px; 
        border-bottom: 1px solid #edf2f7;
        white-space: normal !important; 
        word-wrap: break-word; 
        vertical-align: middle;
        color: #2d3748;
    }
    .styled-table tbody tr { transition: background-color 0.2s ease; }
    .styled-table tbody tr:hover { background-color: #f1f5f9; }
    .styled-table tbody tr:last-of-type { border-bottom: 3px solid #1e3c72; }
</style>
""", unsafe_allow_html=True)

# --- 3. PERSISTENT MEMORY ---
@st.cache_resource
class EmailTracker:
    def __init__(self):
        self.last_sent_date = None

tracker = EmailTracker()

# --- 4. EMAIL ENGINE ---
def send_daily_summary_email(dataframe):
    try:
        if "email" not in st.secrets: return False
        creds = st.secrets["email"]
        today_str = datetime.now(IST).strftime("%d-%b-%Y")
        msg = MIMEMultipart("alternative")
        msg['Subject'] = f"🛡️ Daily Stock Alert ({today_str}): {len(dataframe)} Items Critical"
        msg['From'], msg['To'] = creds["address"], creds["receiver"]

        html_table = dataframe.to_html(index=False, border=1, justify="left")

        html_content = f"""
        <html>
        <head>
            <style>
                table {{ border-collapse: collapse; width: 100%; font-family: 'Segoe UI', Arial, sans-serif; font-size: 13px; }}
                th {{ background-color: #d9534f; color: white; padding: 12px; text-align: left; font-weight: bold; }}
                td {{ border: 1px solid #e2e8f0; padding: 10px; text-align: left; color: #2d3748; }}
                tr:nth-child(even) {{ background-color: #f7fafc; }}
            </style>
        </head>
        <body>
            <h2 style="color: #d9534f; font-family: 'Segoe UI', Arial, sans-serif;">🚨 Critical Stock Report ({today_str})</h2>
            <p style="font-family: 'Segoe UI', Arial, sans-serif; color: #4a5568;">The following items are at or below re-order level:</p>
            {html_table}
            <br>
            <p style="font-size: 11px; color: #a0aec0; font-family: 'Segoe UI', Arial, sans-serif;">Automated EMD Dashboard Report</p>
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
        
        if 'TOTAL NO' in inv.columns: 
            inv['TOTAL NO'] = pd.to_numeric(inv['TOTAL NO'], errors='coerce').fillna(0).astype(int)
        
        # LIVE STOCK is directly the Manual Stock (TOTAL NO)
        if 'TOTAL NO' in inv.columns:
            inv['LIVE STOCK'] = inv['TOTAL NO']
        else:
            inv['LIVE STOCK'] = 0
            
        return True, inv, log
    except Exception as e: return False, str(e), None

# --- 6. UI RENDER ---
status, inv_df, log_raw = load_data()
if not status: st.error(inv_df); st.stop()

# Header Banner
st.markdown("<div class='header-box'><h1 style='margin:0; font-weight:700;'>🛡️ EMD Material Dashboard</h1></div>", unsafe_allow_html=True)

# SIDEBAR FILTER
st.sidebar.header("⚙️ Dashboard Controls")
loc_list = sorted(inv_df['LOCATION'].replace('nan', 'Unassigned').astype(str).unique().tolist())
sel_loc = st.sidebar.selectbox("📍 Filter Zone", ["All Locations"] + loc_list)

filtered_inv = inv_df.copy()
if sel_loc != "All Locations":
    filtered_inv = filtered_inv[filtered_inv['LOCATION'].astype(str) == sel_loc]

display_cols = ['MAKE', 'MATERIAL DISCRIPTION', 'TYPE(RATING)', 'SIZE', 'LOCATION', 'LIVE STOCK']
final_cols = [c for c in display_cols if c in inv_df.columns]

crit = filtered_inv[(filtered_inv['LIVE STOCK'] <= 2) & (filtered_inv['MATERIAL DISCRIPTION'] != 'nan') & (filtered_inv['MATERIAL DISCRIPTION'] != '')]

# Metrics
c1, c2, c3 = st.columns(3)
c1.metric("Catalog Size", len(filtered_inv))
c2.metric("Total Stock Units", int(filtered_inv['LIVE STOCK'].sum()))
c3.metric("Critical Alerts", len(crit), delta=f"{len(crit)} Need Reorder", delta_color="inverse")

# --- CUSTOM DATAFRAME STYLING FUNCTION ---
def style_dataframe(df):
    """Adds a soft red background and bold text to critical stock rows."""
    def highlight_critical(row):
        is_critical = row['LIVE STOCK'] <= 2
        bg_color = 'background-color: #fff0f0' if is_critical else ''
        text_color = 'color: #d9534f; font-weight: 600' if is_critical else 'color: #2d3748'
        return [f"{bg_color}; {text_color}"] * len(row)
    
    return df.style.apply(highlight_critical, axis=1)

# --- TABS ---
tab1, tab2, tab3 = st.tabs(["📦 Master Inventory", "🚨 Action Required", "📋 Drawal History"])

with tab1:
    # Applying the Pandas styling to the main table
    styled_inv = style_dataframe(filtered_inv[final_cols])
    st.dataframe(styled_inv, use_container_width=True, hide_index=True, height=600)

with tab2:
    if not crit.empty:
        st.error(f"⚠️ **Attention:** {len(crit)} items have fallen to or below the minimum stock level of 2.")
        styled_crit = style_dataframe(crit[final_cols])
        st.dataframe(styled_crit, use_container_width=True, hide_index=True)
    else:
        st.success("✅ **All Clear!** No critical stock items in this location.")

with tab3:
    st.markdown("### 🔍 Complete Material History")
    display_log = log_raw.fillna("").astype(str)
    if 'MATERIAL DISCRIPTION' in display_log.columns:
        display_log = display_log[display_log['MATERIAL DISCRIPTION'].str.len() > 1]
    
    search = st.text_input("🔍 Search Logs...", placeholder="Search by name, date, receiver...")
    if search:
        display_log = display_log[display_log.apply(lambda r: search.upper() in r.astype(str).str.upper().to_string(), axis=1)]

    # Clean HTML Render for Wrapping and Fonts
    html = display_log.to_html(classes='styled-table', index=False, escape=False)
    st.markdown(html, unsafe_allow_html=True)

# --- 7. EMAIL LOGIC ---
today = datetime.now(IST).strftime("%Y-%m-%d")
global_crit = inv_df[(inv_df['LIVE STOCK'] <= 2) & (inv_df['MATERIAL DISCRIPTION'] != 'nan') & (inv_df['MATERIAL DISCRIPTION'] != '')]

if datetime.now(IST).hour >= 9 and tracker.last_sent_date != today and not global_crit.empty:
    email_df = global_crit[final_cols]
    if send_daily_summary_email(email_df):
        tracker.last_sent_date = today
        st.toast("✅ Daily Summary Email Delivered!")
