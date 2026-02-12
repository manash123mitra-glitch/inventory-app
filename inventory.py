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

        html_content = f"""
        <html>
        <head>
            <style>
                table {{ border-collapse: collapse; width: 100%; font-family: Arial, sans-serif; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; color: #333; }}
                tr:nth-child(even) {{ background-color: #f9f9f9; }}
            </style>
        </head>
        <body>
            <h2 style="color: #d9534f;">🚨 Critical Stock Report ({today_str})</h2>
            <p>The following items are low on stock:</p>
            <table>
                <tr><th>Material Description</th><th>Stock</th><th>Location</th></tr>
        """
        
        count = 0
        for item in items_list:
            if str(item['name']).lower() in ['nan', '']: continue
            html_content += f"<tr><td>{item['name']}</td><td style='font-weight: bold; color: #d9534f;'>{item['qty']}</td><td>{item['loc']}</td></tr>"
            count += 1
            
        html_content += "</table></body></html>"
        
        if count == 0: return False

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
        # Inventory
        inv_raw = pd.read_csv(INV_URL, header=None).fillna("").astype(str)
        h_idx = next((i for i, r in inv_raw.iterrows() if "MATERIAL" in " ".join(r).upper()), None)
        if h_idx is None: return "Header Missing", None
        
        inv = pd.read_csv(INV_URL, skiprows=h_idx)
        inv.columns = [str(c).strip().upper().replace('DESCRIPTION', 'DISCRIPTION') for c in inv.columns]
        
        # Logs
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

crit = inv_df[(inv_df['LIVE STOCK'] <= 2) & (inv_df['MATERIAL DISCRIPTION'] != 'nan') & (inv_df['MATERIAL DISCRIPTION'] != '')]

c1, c2, c3 = st.columns(3)
c1.metric("Catalog Items", len(inv_df))
c2.metric("Total Stock", int(inv_df['LIVE STOCK'].sum()))
c3.metric("Critical Alerts", len(crit), delta=f"{len(crit)} Low", delta_color="inverse")

# Sidebar
st.sidebar.header("⚙️ Settings")
loc_list = sorted(inv_df['LOCATION'].replace('nan', 'Unassigned').unique().tolist())
sel_loc = st.sidebar.selectbox("Filter Location", ["All"] + loc_list)
filtered_inv = inv_df.copy()
if sel_loc != "All":
    filtered_inv = filtered_inv[filtered_inv['LOCATION'] == sel_loc]

# TABS
tab1, tab2, tab3 = st.tabs(["📦 Inventory Overview", "🚨 Critical Stock (Action Req.)", "📋 Usage Logs"])

# TAB 1: ALL INVENTORY
with tab1:
    cols = [c for c in ['MAKE', 'MATERIAL DISCRIPTION', 'TYPE(RATING)', 'SIZE', 'LOCATION', 'LIVE STOCK'] if c in inv_df.columns]
    st.dataframe(filtered_inv[cols], use_container_width=True, hide_index=True,
                 column_config={"LIVE STOCK": st.column_config.ProgressColumn("Availability", format="%d", min_value=0, max_value=int(inv_df['TOTAL NO'].max() or 100))})

# TAB 2: CRITICAL STOCK
with tab2:
    if not crit.empty:
        st.error(f"⚠️ Action Required: {len(crit)} items are at or below Minimum Stock Level (2).")
        crit_cols = [c for c in ['MAKE', 'MATERIAL DISCRIPTION', 'TYPE(RATING)', 'SIZE', 'LOCATION', 'LIVE STOCK'] if c in inv_df.columns]
        st.dataframe(crit[crit_cols], use_container_width=True, hide_index=True)
        
        csv = crit[crit_cols].to_csv(index=False).encode('utf-8')
        st.download_button(label="📥 Download Critical List (CSV)", data=csv, file_name=f"Critical_Stock.csv", mime='text/csv')
    else:
        st.success("✅ All Stock Levels are Healthy.")

# TAB 3: USAGE LOGS (FIXED LAYOUT)
with tab3:
    st.markdown("### 🔍 Material Drawal History")
    
    # Clean Data
    display_log = log_df[log_df['MATERIAL DISCRIPTION'].str.len() > 1].copy()
    display_log = display_log[display_log['MATERIAL DISCRIPTION'] != 'nan']
    
    # Rename & Select
    target_cols = ['DATE', 'MATERIAL DISCRIPTION', 'SIZE', 'MAKE', 'QTY_OUT', 'RECEIVER', 'REMARKS']
    final_cols = [c for c in target_cols if c in display_log.columns]
    
    final_view = display_log[final_cols].rename(columns={
        'MATERIAL DISCRIPTION': 'Item Name',
        'QTY_OUT': 'Qty',
        'RECEIVER': 'Issued To',
        'SIZE': 'Size',
        'MAKE': 'Make',
        'REMARKS': 'Remarks',
        'DATE': 'Date'
    })

    search_term = st.text_input("Search Logs", placeholder="Name, Item, or Date...")
    if search_term:
        final_view = final_view[final_view.apply(lambda row: search_term.upper() in row.astype(str).str.upper().to_string(), axis=1)]
    
    # --- THE LAYOUT FIX ---
    # We use column_config to constrain widths and force proper formatting
    st.dataframe(
        final_view,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Item Name": st.column_config.TextColumn("Item Name", width="medium"),
            "Remarks": st.column_config.TextColumn("Remarks", width="small"),
            "Issued To": st.column_config.TextColumn("Issued To", width="small"),
            "Date": st.column_config.TextColumn("Date", width="small"),
            "Qty": st.column_config.NumberColumn("Qty", format="%d")
        }
    )

# --- 6. EMAIL LOGIC ---
today_str = datetime.now(IST).strftime("%Y-%m-%d")
current_hour = datetime.now(IST).hour
if (current_hour >= 9) and (tracker.last_sent_date != today_str) and not crit.empty:
    clist = []
    for _, r in crit.iterrows():
        if str(r['MATERIAL DISCRIPTION']).lower() not in ['nan', '']:
            clist.append({'name': r['MATERIAL DISCRIPTION'], 'qty': r['LIVE STOCK'], 'loc': r['LOCATION']})
    
    if clist:
        if send_daily_summary_email(clist):
            tracker.last_sent_date = today_str 
            st.toast(f"✅ Daily Summary Sent ({len(clist)} items)")
