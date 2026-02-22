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

# --- 2. COMPACT & PREMIUM CSS ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif !important;
    }
    .reportview-container .main .block-container { 
        max-width: 98%; 
        padding-top: 1rem; 
        padding-right: 1rem;
        padding-left: 1rem;
    }
    .header-box {
        background: linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%);
        padding: 15px; 
        border-radius: 8px; 
        color: white;
        text-align: center; 
        margin-bottom: 20px; 
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    .header-box h1 { margin: 0; font-size: 1.8rem; font-weight: 600; }
    div[data-testid="metric-container"] {
        background-color: #fff; border: 1px solid #e0e0e0;
        padding: 10px 15px; border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05); border-left: 4px solid #2c5364;
    }
    [data-testid="stDataFrame"] td, [data-testid="stDataFrame"] th {
        padding: 6px 10px !important; font-size: 0.9rem !important;
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
                table {{ border-collapse: collapse; width: 100%; font-family: 'Inter', Arial, sans-serif; font-size: 12px; }}
                th {{ background-color: #d9534f; color: white; padding: 8px; text-align: left; font-weight: bold; }}
                td {{ border: 1px solid #e2e8f0; padding: 6px; text-align: left; color: #2d3748; white-space: nowrap; }}
                tr:nth-child(even) {{ background-color: #f7fafc; }}
            </style>
        </head>
        <body>
            <h2 style="color: #d9534f; font-family: 'Inter', sans-serif; margin-bottom: 10px;">🚨 Critical Stock Report ({today_str})</h2>
            {html_table}
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

# --- 5. DATA LOADING & CLEANING ---
@st.cache_data(ttl=60)
def load_data():
    try:
        inv_raw = pd.read_csv(INV_URL, header=None).fillna("").astype(str)
        h_idx = next((i for i, r in inv_raw.iterrows() if "MATERIAL" in " ".join(r).upper() and "DESCRIPTION" in " ".join(r).upper()), None)
        
        if h_idx is None:
             inv = pd.read_csv(INV_URL)
        else:
             inv = pd.read_csv(INV_URL, skiprows=h_idx)

        inv.columns = [str(c).strip().upper().replace('DESCRIPTION', 'DISCRIPTION') for c in inv.columns]
        
        if 'MATERIAL DISCRIPTION' in inv.columns:
            inv = inv[inv['MATERIAL DISCRIPTION'].astype(str) != 'nan']
            inv = inv[inv['MATERIAL DISCRIPTION'].notna()]
            inv = inv[inv['MATERIAL DISCRIPTION'].str.upper() != 'MATERIAL DISCRIPTION']
            inv = inv[inv['MATERIAL DISCRIPTION'].str.strip() != '']

        log = pd.read_csv(LOG_URL)
        log.columns = [str(c).strip().upper().replace('DESCRIPTION', 'DISCRIPTION') for c in log.columns]
        
        if 'TOTAL NO' in inv.columns: 
            inv['TOTAL NO'] = pd.to_numeric(inv['TOTAL NO'], errors='coerce').fillna(0).astype(int)
        
        if 'TOTAL NO' in inv.columns:
            inv['LIVE STOCK'] = inv['TOTAL NO']
        else:
            inv['LIVE STOCK'] = 0
            
        return True, inv, log
    except Exception as e: return False, str(e), None

# --- 6. UI RENDER ---
status, inv_df, log_raw = load_data()
if not status: st.error(inv_df); st.stop()

st.markdown("<div class='header-box'><h1>🛡️ EMD Material Dashboard</h1></div>", unsafe_allow_html=True)

st.sidebar.header("⚙️ Controls")
loc_list = sorted(inv_df['LOCATION'].replace('nan', 'Unassigned').astype(str).unique().tolist())
sel_loc = st.sidebar.selectbox("📍 Filter Zone", ["All Locations"] + loc_list)

filtered_inv = inv_df.copy()
if sel_loc != "All Locations":
    filtered_inv = filtered_inv[filtered_inv['LOCATION'].astype(str) == sel_loc]

display_cols = ['MAKE', 'MATERIAL DISCRIPTION', 'TYPE(RATING)', 'SIZE', 'LOCATION', 'LIVE STOCK']
final_cols = [c for c in display_cols if c in inv_df.columns]

crit = filtered_inv[filtered_inv['LIVE STOCK'] <= 2]

c1, c2, c3 = st.columns(3)
c1.metric("Catalog Size", len(filtered_inv))
c2.metric("Total Stock Units", int(filtered_inv['LIVE STOCK'].sum()))
c3.metric("Critical Alerts", len(crit), delta=f"{len(crit)} Need Reorder", delta_color="inverse")

def style_critical_rows(df):
    return df.style.apply(lambda x: ['background-color: #fff0f0; color: #c0392b; font-weight: 600' if x['LIVE STOCK'] <= 2 else '' for i in x], axis=1)

compact_config = {
    "MAKE": st.column_config.TextColumn("Make", width="small"),
    "MATERIAL DISCRIPTION": st.column_config.TextColumn("Material Discription", width="large"),
    "TYPE(RATING)": st.column_config.TextColumn("Type/Rating", width="medium"),
    "SIZE": st.column_config.TextColumn("Size", width="small"),
    "LOCATION": st.column_config.TextColumn("Location", width="medium"),
    "LIVE STOCK": st.column_config.NumberColumn("Stock", format="%d", width="small"),
}

tab1, tab2, tab3 = st.tabs(["📦 Master Inventory", "🚨 Action Required", "📋 Drawal History"])

with tab1:
    st.dataframe(
        style_critical_rows(filtered_inv[final_cols]),
        use_container_width=True, hide_index=True, height=700, column_config=compact_config
    )

with tab2:
    if not crit.empty:
        st.error(f"⚠️ **{len(crit)} items are below re-order level.**")
        st.dataframe(
            style_critical_rows(crit[final_cols]),
            use_container_width=True, hide_index=True, column_config=compact_config
        )
    else:
        st.success("✅ No critical stock items found.")

# --- TAB 3: PERFECTLY FORMATTED USAGE LOG ---
with tab3:
    st.markdown("### 🔍 Drawal History")
    
    # 1. Clean Log Data
    dlog = log_raw.fillna("").astype(str)
    
    # 2. Rename Columns to match exactly the screenshot format
    rename_dict = {
        'DATE': 'Date',
        'MAKE': 'Make',
        'MATERIAL DISCRIPTION': 'Material Discription',
        'TYPE(RATING)': 'Type(Rating)',
        'SIZE': 'Size',
        'LOCATION': 'Location',
        'QUANTITY ISSUED': 'Quantity Issued',
        'ISSUED QUANTITY': 'Quantity Issued',
        'QTY': 'Quantity Issued',
        'UNIT': 'Unit',
        'ISSUED TO': 'Issued To',
        'NAME': 'Issued To',
        'PURPOSE': 'Purpose',
        'REMARKS': 'Purpose'
    }
    dlog = dlog.rename(columns=rename_dict)
    
    # Ensure only the specific 10 columns are shown if they exist
    target_10_cols = ['Date', 'Make', 'Material Discription', 'Type(Rating)', 'Size', 'Location', 'Quantity Issued', 'Unit', 'Issued To', 'Purpose']
    dlog_cols = [c for c in target_10_cols if c in dlog.columns]
    dlog = dlog[dlog_cols]

    # Remove garbage rows
    if 'Material Discription' in dlog.columns:
        dlog = dlog[dlog['Material Discription'].str.len() > 1]
        dlog = dlog[dlog['Material Discription'].str.lower() != 'nan']
    
    # 3. Search Filter
    search = st.text_input("Search Logs...", placeholder="Type to filter...")
    if search:
        dlog = dlog[dlog.apply(lambda r: search.upper() in r.astype(str).str.upper().to_string(), axis=1)]

    # 4. EXPLICIT COLUMN CONFIGURATION TO PREVENT OVERFLOW
    # By strictly defining sizes, Streamlit will not stretch rows out of proportion
    log_config = {
        "Date": st.column_config.TextColumn("Date", width="small"),
        "Make": st.column_config.TextColumn("Make", width="small"),
        "Material Discription": st.column_config.TextColumn("Material Discription", width="large"),
        "Type(Rating)": st.column_config.TextColumn("Type(Rating)", width="medium"),
        "Size": st.column_config.TextColumn("Size", width="small"),
        "Location": st.column_config.TextColumn("Location", width="medium"),
        "Quantity Issued": st.column_config.TextColumn("Quantity Issued", width="small"),
        "Unit": st.column_config.TextColumn("Unit", width="small"),
        "Issued To": st.column_config.TextColumn("Issued To", width="medium"),
        "Purpose": st.column_config.TextColumn("Purpose", width="large")
    }
    
    st.dataframe(
        dlog,
        use_container_width=True,
        hide_index=True,
        column_config=log_config,
        height=700
    )

# --- 7. EMAIL LOGIC ---
today = datetime.now(IST).strftime("%Y-%m-%d")
global_crit = inv_df[inv_df['LIVE STOCK'] <= 2]

if datetime.now(IST).hour >= 9 and tracker.last_sent_date != today and not global_crit.empty:
    email_df = global_crit[final_cols]
    if send_daily_summary_email(email_df):
        tracker.last_sent_date = today
        st.toast("✅ Daily Summary Email Delivered!")
