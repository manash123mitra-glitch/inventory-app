import streamlit as st
import pandas as pd
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import pytz

# --- 1. GLOBAL SETTINGS ---
SHEET_ID = "1E0ZluX3o7vqnSBAdAMEn_cdxq3ro4F4DXxchOEFcS_g"
INV_GID = "804871972" 
LOG_GID = "1151083374" 

IST = pytz.timezone('Asia/Kolkata')

INV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={INV_GID}"
LOG_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={LOG_GID}"

st.set_page_config(page_title="EMD Material Intelligence", layout="wide", page_icon="⚡")

# --- 2. PREMIUM ENTERPRISE CSS ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif !important;
    }
    .reportview-container .main .block-container { 
        max-width: 98%; padding-top: 1rem; 
    }
    .header-box {
        background: linear-gradient(90deg, #0f2027 0%, #203a43 50%, #2c5364 100%);
        padding: 20px 30px; 
        border-radius: 12px; 
        color: white;
        margin-bottom: 25px; 
        box-shadow: 0 10px 20px rgba(0,0,0,0.1);
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .header-box h1 { margin: 0; font-size: 2rem; font-weight: 700; letter-spacing: -0.5px; }
    .header-box p { margin: 0; opacity: 0.8; font-size: 0.9rem; }
    
    [data-testid="stDataFrame"] td, [data-testid="stDataFrame"] th {
        padding: 8px 12px !important; font-size: 0.9rem !important;
    }

    /* CSS For Text-Wrapping HTML Table in Tab 4 */
    .wrap-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.85rem;
        background-color: white;
        border: 1px solid #e6e9ef;
        margin-top: 15px;
    }
    .wrap-table th {
        background-color: #f8f9fa;
        color: #31333F;
        padding: 10px;
        border-bottom: 2px solid #e6e9ef;
        border-right: 1px solid #e6e9ef;
        text-align: left;
        font-weight: 600;
    }
    .wrap-table td {
        padding: 10px;
        border-bottom: 1px solid #e6e9ef;
        border-right: 1px solid #e6e9ef;
        white-space: normal !important;  
        word-wrap: break-word;           
        vertical-align: top;
        color: #4a5568;
    }
    .wrap-table tr:hover {
        background-color: #f1f5f9;
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
        msg['Subject'] = f"🚨 EMD Alert ({today_str}): {len(dataframe)} Critical Items"
        msg['From'], msg['To'] = creds["address"], creds["receiver"]

        html_table = dataframe.to_html(index=False, border=1, justify="left")
        html_content = f"""
        <html>
        <head><style>
            table {{ border-collapse: collapse; width: 100%; font-family: 'Inter', sans-serif; font-size: 12px; }}
            th {{ background-color: #d9534f; color: white; padding: 10px; text-align: left; }}
            td {{ border: 1px solid #e2e8f0; padding: 8px; color: #2d3748; }}
        </style></head>
        <body>
            <h2 style="color: #d9534f;">Critical Stock Report ({today_str})</h2>
            {html_table}
        </body></html>
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

# --- 5. DATA LOADING, CLEANING & PREDICTIVE CALCS ---
@st.cache_data(ttl=60)
def load_data():
    try:
        inv_raw = pd.read_csv(INV_URL, header=None).fillna("").astype(str)
        h_idx = next((i for i, r in inv_raw.iterrows() if "MATERIAL" in " ".join(r).upper()), None)
        inv = pd.read_csv(INV_URL) if h_idx is None else pd.read_csv(INV_URL, skiprows=h_idx)
        inv.columns = [str(c).strip().upper().replace('DESCRIPTION', 'DISCRIPTION') for c in inv.columns]
        
        if 'MATERIAL DISCRIPTION' in inv.columns:
            inv = inv[inv['MATERIAL DISCRIPTION'].astype(str).str.lower() != 'nan']
            inv = inv[inv['MATERIAL DISCRIPTION'].str.upper() != 'MATERIAL DISCRIPTION']
            inv = inv[inv['MATERIAL DISCRIPTION'].str.strip() != '']

        log = pd.read_csv(LOG_URL)
        log.columns = [str(c).strip().upper().replace('DESCRIPTION', 'DISCRIPTION') for c in log.columns]
        
        rename_dict = {
            'DATE': 'Date', 'MATERIAL DISCRIPTION': 'Material Discription',
            'QUANTITY ISSUED': 'Qty', 'ISSUED QUANTITY': 'Qty', 'QTY': 'Qty'
        }
        log_clean = log.rename(columns=rename_dict)
        if 'Qty' in log_clean.columns:
            log_clean['Qty'] = pd.to_numeric(log_clean['Qty'], errors='coerce').fillna(0).astype(int)
        if 'Date' in log_clean.columns:
            log_clean['Date'] = pd.to_datetime(log_clean['Date'], format='mixed', dayfirst=True, errors='coerce')

        if 'TOTAL NO' in inv.columns: 
            inv['TOTAL NO'] = pd.to_numeric(inv['TOTAL NO'], errors='coerce').fillna(0).astype(int)
            inv['LIVE STOCK'] = inv['TOTAL NO']
        else:
            inv['LIVE STOCK'] = 0

        if 'Date' in log_clean.columns and 'Material Discription' in log_clean.columns:
            thirty_days_ago = pd.Timestamp.now() - pd.Timedelta(days=30)
            recent_logs = log_clean[log_clean['Date'] >= thirty_days_ago]
            
            usage_stats = recent_logs.groupby('Material Discription')['Qty'].sum().reset_index()
            usage_stats.rename(columns={'Qty': '30-Day Usage'}, inplace=True)
            
            inv = pd.merge(inv, usage_stats, left_on='MATERIAL DISCRIPTION', right_on='Material Discription', how='left')
            inv['30-Day Usage'] = inv['30-Day Usage'].fillna(0).astype(int)
            
            inv['Run Rate (Daily)'] = (inv['30-Day Usage'] / 30).round(2)
            
            def calc_days_left(row):
                if row['Run Rate (Daily)'] <= 0: return "999+ (No Recent Usage)"
                days = int(row['LIVE STOCK'] / row['Run Rate (Daily)'])
                return str(days) if days > 0 else "0 (Stockout Imminent)"
                
            inv['Predicted Days Left'] = inv.apply(calc_days_left, axis=1)
        else:
            inv['30-Day Usage'] = 0
            inv['Predicted Days Left'] = "N/A"

        return True, inv, log
    except Exception as e: return False, str(e), None

# --- 6. UI RENDER ---
status, inv_df, log_raw = load_data()
if not status: st.error(inv_df); st.stop()

st.markdown("""
<div class='header-box'>
    <div>
        <h1>⚡ EMD Material Intelligence</h1>
        <p>Advanced Inventory Tracking & Predictive Analytics</p>
    </div>
    <div style="text-align: right;">
        <p style="opacity: 0.7; font-size: 0.8rem;">Status</p>
        <p style="font-weight: 600; color: #4ade80;">🟢 System Online</p>
    </div>
</div>
""", unsafe_allow_html=True)

st.sidebar.header("⚙️ Global Controls")
loc_list = sorted(inv_df['LOCATION'].replace('nan', 'Unassigned').astype(str).unique().tolist())
sel_loc = st.sidebar.selectbox("📍 Filter Zone", ["All Locations"] + loc_list)

filtered_inv = inv_df.copy()
if sel_loc != "All Locations":
    filtered_inv = filtered_inv[filtered_inv['LOCATION'].astype(str) == sel_loc]

display_cols = ['MAKE', 'MATERIAL DISCRIPTION', 'TYPE(RATING)', 'SIZE', 'LOCATION', 'LIVE STOCK']
final_cols = [c for c in display_cols if c in inv_df.columns]

crit = filtered_inv[filtered_inv['LIVE STOCK'] <= 2]
top_item = filtered_inv.sort_values(by='30-Day Usage', ascending=False).iloc[0] if '30-Day Usage' in filtered_inv.columns and not filtered_inv.empty else None

kpi1, kpi2, kpi3, kpi4 = st.columns(4)
kpi1.metric("📦 Catalog Size", len(filtered_inv))
kpi2.metric("📊 Total Stock Units", int(filtered_inv['LIVE STOCK'].sum()))
kpi3.metric("🚨 Critical Alerts", len(crit), delta=f"{len(crit)} Need Reorder", delta_color="inverse")
if top_item is not None and top_item['30-Day Usage'] > 0:
    kpi4.metric("🔥 High-Velocity Item", top_item['MATERIAL DISCRIPTION'][:15]+"...", f"{top_item['30-Day Usage']} used/mo", delta_color="off")
else:
    kpi4.metric("🔥 High-Velocity Item", "Awaiting Data", "0 used/mo", delta_color="off")

def style_critical_rows(df):
    return df.style.apply(lambda x: ['background-color: #fff0f0; color: #c0392b; font-weight: 600' if x['LIVE STOCK'] <= 2 else '' for i in x], axis=1)

compact_config = {
    "MAKE": st.column_config.TextColumn("Make", width="small"),
    "MATERIAL DISCRIPTION": st.column_config.TextColumn("Material Discription", width="large"),
    "TYPE(RATING)": st.column_config.TextColumn("Type(Rating)", width="medium"),
    "SIZE": st.column_config.TextColumn("Size", width="small"),
    "LOCATION": st.column_config.TextColumn("Location", width="medium"),
    "LIVE STOCK": st.column_config.NumberColumn("Live Stock", format="%d", width="small"),
}

# --- TABS ---
tab1, tab2, tab3, tab4 = st.tabs(["📦 Master Inventory", "🚨 Action Required", "📈 Predictive Analytics", "📋 Drawal History"])

with tab1:
    # --- NEW: INVENTORY SEARCH BAR ---
    search_inv = st.text_input("🔍 Search Inventory...", placeholder="Filter by material name, make, size, or location...")
    
    display_inv = filtered_inv.copy()
    if search_inv:
        # Filter the dataframe dynamically based on the search term across all columns
        display_inv = display_inv[display_inv.apply(lambda r: search_inv.upper() in r.astype(str).str.upper().to_string(), axis=1)]
        
    st.dataframe(
        style_critical_rows(display_inv[final_cols]), 
        use_container_width=True, 
        hide_index=True, 
        height=600, 
        column_config=compact_config
    )

with tab2:
    if not crit.empty:
        st.error(f"⚠️ **{len(crit)} items are at or below re-order level (2 units).**")
        st.dataframe(style_critical_rows(crit[final_cols]), use_container_width=True, hide_index=True, column_config=compact_config)
    else:
        st.success("✅ Stock levels are healthy. No critical alerts.")

with tab3:
    st.markdown("### 📈 Inventory Forecasting & Health")
    st.info("💡 **How this works:** The system analyzes the last 30 days of drawal history to calculate your daily consumption rate and predicts exactly when you will run out of stock.")
    
    pred_cols = ['MATERIAL DISCRIPTION', 'LOCATION', 'LIVE STOCK', '30-Day Usage', 'Run Rate (Daily)', 'Predicted Days Left']
    if all(c in filtered_inv.columns for c in pred_cols):
        forecast_df = filtered_inv[pred_cols].sort_values(by='30-Day Usage', ascending=False)
        colA, colB = st.columns([2, 1])
        with colA:
            csv_data = forecast_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Forecast Report (CSV)", data=csv_data, file_name=f"Inventory_Forecast_{datetime.now(IST).strftime('%Y%m%d')}.csv", mime="text/csv")
            st.dataframe(forecast_df, use_container_width=True, hide_index=True, height=500, column_config={
                "MATERIAL DISCRIPTION": st.column_config.TextColumn("Material Name", width="large"),
                "Predicted Days Left": st.column_config.TextColumn("Days to Stockout ⚠️", width="medium")
            })
        with colB:
            st.markdown("#### Top 5 Consumed Materials (30 Days)")
            top_chart_data = forecast_df.head(5)
            st.bar_chart(data=top_chart_data, x='MATERIAL DISCRIPTION', y='30-Day Usage', color="#2c5364")
    else:
        st.warning("Not enough usage history yet to generate accurate predictions.")

with tab4:
    dlog = log_raw.fillna("").astype(str)
    rename_dict = {
        'DATE': 'Date', 'MAKE': 'Make', 'MATERIAL DISCRIPTION': 'Material Discription',
        'TYPE(RATING)': 'Type(Rating)', 'SIZE': 'Size', 'LOCATION': 'Location',
        'QUANTITY ISSUED': 'Quantity Issued', 'ISSUED QUANTITY': 'Quantity Issued', 'QTY': 'Quantity Issued',
        'UNIT': 'Unit', 'ISSUED TO': 'Issued To', 'NAME': 'Issued To',
        'PURPOSE': 'Purpose', 'REMARKS': 'Purpose'
    }
    dlog = dlog.rename(columns=rename_dict)
    
    target_10_cols = ['Date', 'Make', 'Material Discription', 'Type(Rating)', 'Size', 'Location', 'Quantity Issued', 'Unit', 'Issued To', 'Purpose']
    dlog_cols = [c for c in target_10_cols if c in dlog.columns]
    dlog = dlog[dlog_cols]

    if 'Material Discription' in dlog.columns:
        dlog = dlog[dlog['Material Discription'].str.len() > 1]
        dlog = dlog[dlog['Material Discription'].str.lower() != 'nan']
    
    # Sort LIFO (LAST IN, FIRST OUT)
    if 'Date' in dlog.columns:
        dlog['Temp_Date'] = pd.to_datetime(dlog['Date'], format='mixed', dayfirst=True, errors='coerce')
        dlog = dlog.sort_values(by='Temp_Date', ascending=False)
        unique_dates = dlog['Temp_Date'].dropna().dt.strftime('%d-%b-%Y').unique().tolist()
        dlog = dlog.drop(columns=['Temp_Date'])
    else:
        unique_dates = []

    # DATE DROPDOWN & SEARCH UI
    col1, col2 = st.columns([1, 2])
    with col1:
        if unique_dates:
            selected_date = st.selectbox("📅 Filter by Date", ["All Dates"] + unique_dates)
        else:
            selected_date = "All Dates"
            
    with col2:
        search = st.text_input("🔍 Search History...", placeholder="Filter by name, material, or purpose...")

    # Apply Date Filter
    if selected_date != "All Dates" and 'Date' in dlog.columns:
        temp_filter_dates = pd.to_datetime(dlog['Date'], format='mixed', dayfirst=True, errors='coerce').dt.strftime('%d-%b-%Y')
        dlog = dlog[temp_filter_dates == selected_date]

    # Apply Search Filter
    if search:
        dlog = dlog[dlog.apply(lambda r: search.upper() in r.astype(str).str.upper().to_string(), axis=1)]

    # --- HTML RENDERER FOR FORCED WRAPPING ---
    if dlog.empty:
        st.info("No records found for the selected criteria.")
    else:
        html_output = dlog.to_html(index=False, classes="wrap-table", escape=False)
        st.markdown(html_output, unsafe_allow_html=True)

# --- 7. AUTOMATED EMAIL LOGIC ---
today = datetime.now(IST).strftime("%Y-%m-%d")
global_crit = inv_df[inv_df['LIVE STOCK'] <= 2]

if datetime.now(IST).hour >= 9 and tracker.last_sent_date != today and not global_crit.empty:
    email_df = global_crit[final_cols]
    if send_daily_summary_email(email_df):
        tracker.last_sent_date = today
        st.toast("✅ Automated 9:00 AM Summary Dispatched!")
