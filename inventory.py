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

# --- 2. PREMIUM ENTERPRISE CSS (STRICT WRAPPING) ---
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
    
    /* ENHANCED TABLE STYLE TO FIX ALL COLUMN OVERFLOWS */
    .wrap-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.85rem;
        background-color: white;
        border: 1px solid #e6e9ef;
        margin-top: 15px;
        table-layout: auto;
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
        white-space: normal !important;    /* FORCES WRAPPING */
        word-wrap: break-word !important;  /* BREAKS LONG WORDS */
        word-break: break-all !important;  /* ENSURES CODES/SIZES BREAK */
        overflow-wrap: anywhere !important;
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
        # 1. Master Inventory
        inv_raw = pd.read_csv(INV_URL, header=None).fillna("").astype(str)
        h_idx = next((i for i, r in inv_raw.iterrows() if "MATERIAL" in " ".join(r).upper()), None)
        inv = pd.read_csv(INV_URL) if h_idx is None else pd.read_csv(INV_URL, skiprows=h_idx)
        inv.columns = [str(c).strip().upper().replace('DESCRIPTION', 'DISCRIPTION') for c in inv.columns]
        
        # Smart Column Renamer
        inv_rename_dict = {
            'TYPE': 'TYPE(RATING)',
            'TYPE (RATING)': 'TYPE(RATING)',
            'RATING': 'TYPE(RATING)'
        }
        inv = inv.rename(columns=inv_rename_dict)
        
        if 'MATERIAL DISCRIPTION' in inv.columns:
            inv = inv[inv['MATERIAL DISCRIPTION'].astype(str).str.lower() != 'nan']
            inv = inv[inv['MATERIAL DISCRIPTION'].str.upper() != 'MATERIAL DISCRIPTION']
            inv = inv[inv['MATERIAL DISCRIPTION'].str.strip() != '']

        # 2. Usage Logs
        log = pd.read_csv(LOG_URL).fillna("")
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

        # 3. Live Stock Setting
        if 'TOTAL NO' in inv.columns: 
            inv['TOTAL NO'] = pd.to_numeric(inv['TOTAL NO'], errors='coerce').fillna(0).astype(int)
            inv['LIVE STOCK'] = inv['TOTAL NO']
        else:
            inv['LIVE STOCK'] = 0

        # 4. Predictive Engine Calculations
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

# Header
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

# Sidebar
st.sidebar.header("⚙️ Global Controls")
loc_list = sorted(inv_df['LOCATION'].replace('nan', 'Unassigned').astype(str).unique().tolist())
sel_loc = st.sidebar.selectbox("📍 Filter Zone", ["All Locations"] + loc_list)

filtered_inv = inv_df.copy()
if sel_loc != "All Locations":
    filtered_inv = filtered_inv[filtered_inv['LOCATION'].astype(str) == sel_loc]

display_cols = ['MAKE', 'MATERIAL DISCRIPTION', 'TYPE(RATING)', 'SIZE', 'LOCATION', 'LIVE STOCK']
final_cols = [c for c in display_cols if c in inv_df.columns]

# KPIs
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
    """Applies inline CSS for critical stock rows so it exports perfectly to HTML."""
    return df.style.apply(lambda x: ['background-color: #fff0f0; color: #c0392b; font-weight: 600' if x['LIVE STOCK'] <= 2 else '' for i in x], axis=1)

# --- 7. TABS ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📦 Master Inventory", "🚨 Action Required", "📈 Predictive Analytics", "📋 Drawal History", "⚡ Power Query"
])

# TAB 1: MASTER INVENTORY
with tab1:
    search_inv = st.text_input("🔍 Search Inventory...", placeholder="Filter by material name, make, size, or location...")
    
    display_inv = filtered_inv.copy()
    if search_inv:
        # Robust search across all columns avoiding Pandas truncation
        mask = display_inv.astype(str).apply(lambda row: row.str.contains(search_inv, case=False, na=False, regex=False)).any(axis=1)
        display_inv = display_inv[mask]
        
    if display_inv.empty:
        st.info("No items match your search.")
    else:
        # Apply the 'wrap-table' class to force the Size column (and others) to wrap
        styled_inv = style_critical_rows(display_inv[final_cols]).set_table_attributes('class="wrap-table"')
        st.markdown(styled_inv.to_html(escape=False), unsafe_allow_html=True)

# TAB 2: ACTION REQUIRED
with tab2:
    if not crit.empty:
        st.error(f"⚠️ **{len(crit)} items are at or below re-order level (2 units).**")
        styled_crit = style_critical_rows(crit[final_cols]).set_table_attributes('class="wrap-table"')
        st.markdown(styled_crit.to_html(escape=False), unsafe_allow_html=True)
    else:
        st.success("✅ Stock levels are healthy. No critical alerts.")

# TAB 3: PREDICTIVE ANALYTICS
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
            html_forecast = forecast_df.to_html(index=False, classes="wrap-table", escape=False)
            st.markdown(html_forecast, unsafe_allow_html=True)
            
        with colB:
            st.markdown("#### Top 5 Consumed Materials (30 Days)")
            top_chart_data = forecast_df.head(5)
            st.bar_chart(data=top_chart_data, x='MATERIAL DISCRIPTION', y='30-Day Usage', color="#2c5364")
    else:
        st.warning("Not enough usage history yet to generate accurate predictions.")

# TAB 4: DRAWAL HISTORY
with tab4:
    dlog = log_raw.astype(str)
    rename_dict_log = {
        'DATE': 'Date', 'MAKE': 'Make', 'MATERIAL DISCRIPTION': 'Material Discription',
        'TYPE(RATING)': 'Type(Rating)', 'SIZE': 'Size', 'LOCATION': 'Location',
        'QUANTITY ISSUED': 'Quantity Issued', 'ISSUED QUANTITY': 'Quantity Issued', 'QTY': 'Quantity Issued',
        'UNIT': 'Unit', 'ISSUED TO': 'Issued To', 'NAME': 'Issued To',
        'PURPOSE': 'Purpose', 'REMARKS': 'Purpose'
    }
    dlog = dlog.rename(columns=rename_dict_log)
    
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
        search_log = st.text_input("🔍 Search History...", placeholder="Filter by name, material, or purpose...")

    # Apply Date Filter
    if selected_date != "All Dates" and 'Date' in dlog.columns:
        temp_filter_dates = pd.to_datetime(dlog['Date'], format='mixed', dayfirst=True, errors='coerce').dt.strftime('%d-%b-%Y')
        dlog = dlog[temp_filter_dates == selected_date]

    # Apply Search Filter
    if search_log:
        mask = dlog.astype(str).apply(lambda row: row.str.contains(search_log, case=False, na=False, regex=False)).any(axis=1)
        dlog = dlog[mask]

    # Render HTML for auto-wrapping
    if dlog.empty:
        st.info("No records found for the selected criteria.")
    else:
        html_output = dlog.to_html(index=False, classes="wrap-table", escape=False)
        st.markdown(html_output, unsafe_allow_html=True)

# TAB 5: POWER QUERY
with tab5:
    st.markdown("### 🔍 Interactive Consumption Query")
    st.info("Calculate exactly how much of a specific material was used over a custom time period.")
    
    # Safely prep log data for numerical/date analysis
    query_log = log_raw.copy()
    query_log.columns = [str(c).strip().upper().replace('DESCRIPTION', 'DISCRIPTION') for c in query_log.columns]
    
    rename_query_dict = {
        'DATE': 'Date', 'MATERIAL DISCRIPTION': 'Material Discription',
        'QUANTITY ISSUED': 'Qty', 'ISSUED QUANTITY': 'Qty', 'QTY': 'Qty',
        'NAME': 'ISSUED TO', 'REMARKS': 'PURPOSE'
    }
    query_log = query_log.rename(columns=rename_query_dict)
    
    if 'Qty' in query_log.columns:
        query_log['Qty'] = pd.to_numeric(query_log['Qty'], errors='coerce').fillna(0).astype(int)
    if 'Date' in query_log.columns:
        query_log['Date'] = pd.to_datetime(query_log['Date'], format='mixed', dayfirst=True, errors='coerce')
    
    col_a, col_b = st.columns(2)
    
    with col_a:
        # Get unique materials from inventory
        if 'MATERIAL DISCRIPTION' in filtered_inv.columns:
            material_list = sorted(filtered_inv['MATERIAL DISCRIPTION'].dropna().unique().tolist())
        else:
            material_list = []
        selected_material = st.selectbox("🎯 Select Material to Analyze", material_list)
    
    with col_b:
        days_lookback = st.number_input("📅 Lookback Period (Number of Days)", min_value=1, max_value=365, value=30)

    if selected_material and 'Date' in query_log.columns and 'Material Discription' in query_log.columns:
        cutoff_date = pd.Timestamp.now() - pd.Timedelta(days=days_lookback)
        query_mask = (query_log['Material Discription'] == selected_material) & (query_log['Date'] >= cutoff_date)
        filtered_logs = query_log[query_mask].copy()
        
        total_consumed = filtered_logs['Qty'].sum()
        burn_rate = round(total_consumed / days_lookback, 2)
        
        # KPI Display
        q1, q2, q3 = st.columns(3)
        q1.metric(f"Total Consumed (Last {days_lookback} days)", f"{int(total_consumed)} Units")
        q2.metric("Daily Burn Rate", f"{burn_rate} / day")
        q3.metric("Transaction Count", len(filtered_logs))
        
        if not filtered_logs.empty:
            st.markdown(f"#### 📋 Detailed Logs for '{selected_material}'")
            # Determine which columns are available to show
            display_cols_query = ['Date', 'Qty']
            if 'ISSUED TO' in filtered_logs.columns: display_cols_query.append('ISSUED TO')
            if 'PURPOSE' in filtered_logs.columns: display_cols_query.append('PURPOSE')
            
            display_query = filtered_logs[display_cols_query].copy()
            display_query['Date'] = display_query['Date'].dt.strftime('%d-%b-%Y')
            
            st.markdown(display_query.to_html(index=False, classes="wrap-table", escape=False), unsafe_allow_html=True)
        else:
            st.warning(f"No consumption recorded for this item in the last {days_lookback} days.")
    else:
        st.warning("Insufficient log data to perform query.")

# --- 8. AUTOMATED EMAIL LOGIC ---
today = datetime.now(IST).strftime("%Y-%m-%d")
global_crit = inv_df[inv_df['LIVE STOCK'] <= 2]

if datetime.now(IST).hour >= 9 and tracker.last_sent_date != today and not global_crit.empty:
    email_df = global_crit[final_cols]
    if send_daily_summary_email(email_df):
        tracker.last_sent_date = today
        st.toast("✅ Automated 9:00 AM Summary Dispatched!")
