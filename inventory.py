import streamlit as st
import pandas as pd
import smtplib
import time
from email.mime.text import MIMEText
from datetime import datetime

# --- 1. SETTINGS & GIDs ---
SHEET_ID = "1E0ZluX3o7vqnSBAdAMEn_cdxq3ro4F4DXxchOEFcS_g"
INV_GID = "804871972" 
LOG_GID = "1151083374" 

INV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={INV_GID}"
LOG_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={LOG_GID}"

# --- 2. PREMIUM UI CONFIG & CSS ---
st.set_page_config(page_title="EMD Material Hub", layout="wide", page_icon="⚡")

if "email_history" not in st.session_state:
    st.session_state.email_history = []

# High-End Custom CSS
st.markdown("""
<style>
    /* Main Background Gradient */
    .stApp {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
    }
    
    /* Executive Header */
    .header-container {
        background: #1e3c72;
        background: linear-gradient(90deg, #1e3c72 0%, #2a5298 100%);
        padding: 40px;
        border-radius: 15px;
        color: white;
        text-align: left;
        margin-bottom: 30px;
        box-shadow: 0 10px 20px rgba(0,0,0,0.1);
    }
    
    /* Metric Card Styling */
    div[data-testid="stMetric"] {
        background: rgba(255, 255, 255, 0.8);
        backdrop-filter: blur(10px);
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05);
        border: 1px solid rgba(255, 255, 255, 0.3);
    }
    
    /* Table Styling */
    .stDataFrame {
        background: white;
        border-radius: 15px;
        padding: 10px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05);
    }
    
    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e0e0e0;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. DATA ENGINE ---
@st.cache_data(ttl=60)
def load_data():
    try:
        inv_raw = pd.read_csv(INV_URL, header=None).fillna("").astype(str)
        h_idx = next((i for i, r in inv_raw.iterrows() if "MATERIAL" in " ".join(r).upper()), None)
        if h_idx is None: return "HEADER_NOT_FOUND", None
        
        inv = pd.read_csv(INV_URL, skiprows=h_idx)
        inv.columns = [str(c).strip().replace('\n', ' ').upper() for c in inv.columns]
        inv.columns = [c.replace("DESCRIPTION", "DISCRIPTION") for c in inv.columns]
        
        if 'TOTAL NO' in inv.columns:
            inv['TOTAL NO'] = pd.to_numeric(inv['TOTAL NO'], errors='coerce').fillna(0).astype(int)

        log = pd.read_csv(LOG_URL)
        log.columns = [str(c).strip().replace('\n', ' ').upper() for c in log.columns]
        log.columns = [c.replace("DESCRIPTION", "DISCRIPTION") for c in log.columns]
        log = log.rename(columns={'QUANTITY ISSUED': 'QTY_OUT'})
        
        if 'QTY_OUT' in log.columns:
            log['QTY_OUT'] = pd.to_numeric(log['QTY_OUT'], errors='coerce').fillna(0).astype(int)
        
        keys = [k for k in ['MAKE', 'MATERIAL DISCRIPTION', 'TYPE(RATING)', 'SIZE', 'LOCATION'] if k in inv.columns and k in log.columns]
        cons = log.groupby(keys)['QTY_OUT'].sum().reset_index()
        merged = pd.merge(inv, cons, on=keys, how='left')
        merged['QTY_OUT'] = merged['QTY_OUT'].fillna(0)
        merged['LIVE STOCK'] = merged['TOTAL NO'] - merged['QTY_OUT']
        
        # Add Status Logic for Visuals
        def get_status(qty):
            if qty <= 0: return "🔴 Out of Stock"
            if qty <= 2: return "🟡 Low Stock"
            return "🟢 Healthy"
        
        merged['STATUS'] = merged['LIVE STOCK'].apply(get_status)
        return merged, log
    except Exception as e: return str(e), None

def send_email_alert(name, qty, location="N/A", is_test=False):
    try:
        creds = st.secrets["email"]
        label = "TEST" if is_test else "STOCK ALERT"
        msg = MIMEText(f"{label}: {name} is at {qty} units in {location}.")
        msg['Subject'] = f"🚨 {label}: {name}"
        msg['From'], msg['To'] = creds["address"], creds["receiver"]
        
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as s:
            s.starttls()
            s.login(creds["address"], creds["password"])
            s.sendmail(creds["address"], creds["receiver"], msg.as_string())
        
        st.session_state.email_history.append({
            "Time": datetime.now().strftime("%I:%M %p"),
            "Item": name, "Status": "Delivered"
        })
        return True
    except Exception as e:
        st.session_state.email_history.append({
            "Time": datetime.now().strftime("%I:%M %p"),
            "Item": name, "Status": f"Failed: {str(e)}"
        })
        return False

# --- 4. THE VIEW ---
inv_df, log_df = load_data()

if isinstance(inv_df, str):
    st.error(f"Sync Error: {inv_df}"); st.stop()

# Header
st.markdown("""
<div class="header-container">
    <h1 style='margin:0;'>EMD Material Hub</h1>
    <p style='margin:0; opacity:0.8;'>Engineering & Maintenance Department | Real-Time Inventory Control</p>
</div>
""", unsafe_allow_html=True)

# KPI Section
c1, c2, c3, c4 = st.columns(4)
c1.metric("Catalog Size", len(inv_df))
c2.metric("In-Hand Units", int(inv_df['LIVE STOCK'].sum()))
crit_count = len(inv_df[inv_df['LIVE STOCK'] <= 2])
c3.metric("Critical Alerts", crit_count, delta=f"-{crit_count}" if crit_count > 0 else None, delta_color="inverse")
c4.metric("Locations", inv_df['LOCATION'].nunique())

st.markdown("---")

# Navigation & Filter
st.sidebar.title("Navigation")
page = st.sidebar.radio("Go to", ["Dashboard", "Usage Analytics", "Settings & Logs"])

if page == "Dashboard":
    # Sidebar Filtering
    st.sidebar.subheader("Quick Filters")
    raw_locs = inv_df['LOCATION'].fillna("Unassigned").astype(str).unique().tolist()
    sel_loc = st.sidebar.selectbox("Filter Location", ["All"] + sorted(raw_locs))
    
    filtered = inv_df.copy()
    if sel_loc != "All":
        filtered = filtered[filtered['LOCATION'].astype(str) == sel_loc]

    # Search Bar
    search = st.text_input("🔍 Quick Search (Name, Rating, or Make)", placeholder="Type to filter...")
    if search:
        filtered = filtered[filtered.apply(lambda row: search.upper() in row.astype(str).str.upper().to_string(), axis=1)]

    cols = [c for c in ['STATUS', 'MAKE', 'MATERIAL DISCRIPTION', 'TYPE(RATING)', 'SIZE', 'LOCATION', 'LIVE STOCK'] if c in inv_df.columns]
    
    

    st.dataframe(
        filtered[cols],
        use_container_width=True,
        hide_index=True,
        column_config={
            "LIVE STOCK": st.column_config.ProgressColumn("Availability", format="%d", min_value=0, max_value=int(inv_df['TOTAL NO'].max() or 100)),
            "STATUS": st.column_config.TextColumn("Condition")
        }
    )

elif page == "Usage Analytics":
    st.subheader("📊 Consumption Overview")
    if not log_df.empty:
        col_a, col_b = st.columns(2)
        with col_a:
            st.write("**Top Consumed Items**")
            st.bar_chart(log_df.groupby('MATERIAL DISCRIPTION')['QTY_OUT'].sum().sort_values(ascending=False).head(10))
        with col_b:
            st.write("**Activity Log**")
            st.dataframe(log_df, use_container_width=True)
    else:
        st.info("No usage data available yet.")

elif page == "Settings & Logs":
    st.subheader("⚙️ System Diagnostics")
    if st.button("📧 Run Email Test"):
        if send_email_alert("TEST_RUN", 0, is_test=True):
            st.success("Test email sent!")
        else:
            st.error("Test failed. Check Email History below.")
    
    st.markdown("### 📋 Email History")
    if st.session_state.email_history:
        st.table(pd.DataFrame(st.session_state.email_history).iloc[::-1])
    else:
        st.info("No emails triggered in this session.")

# Trigger Alerts
for _, r in inv_df[inv_df['LIVE STOCK'] <= 2].iterrows():
    alert_id = f"sent_{r['MATERIAL DISCRIPTION']}_{r['LOCATION']}"
    if alert_id not in st.session_state:
        if send_email_alert(r['MATERIAL DISCRIPTION'], r['LIVE STOCK'], r['LOCATION']):
            st.session_state[alert_id] = True
