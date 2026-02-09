import streamlit as st
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from datetime import datetime

# --- 1. SETTINGS & GIDs ---
SHEET_ID = "1E0ZluX3o7vqnSBAdAMEn_cdxq3ro4F4DXxchOEFcS_g"
INV_GID = "804871972" 
LOG_GID = "1151083374" 

INV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={INV_GID}"
LOG_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={LOG_GID}"

# --- 2. DARK MODE CONFIG & CSS ---
st.set_page_config(page_title="EMD Command Center", layout="wide", page_icon="⚡")

if "email_history" not in st.session_state:
    st.session_state.email_history = []

# Injecting "NKSTPP Style" CSS
st.markdown("""
<style>
    /* 1. Main Dark Background */
    .stApp {
        background-color: #0b0e11;
        color: white;
    }
    
    /* 2. Header Style */
    .dashboard-title {
        font-size: 2.5rem;
        font-weight: 800;
        background: -webkit-linear-gradient(45deg, #3b82f6, #8b5cf6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0px;
    }
    .dashboard-subtitle {
        font-size: 1rem;
        color: #9ca3af;
        margin-bottom: 30px;
    }

    /* 3. KPI Cards (Neon Style) */
    .kpi-card {
        background-color: #1f2937;
        border-radius: 10px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.3);
        margin-bottom: 20px;
        border-left: 5px solid #3b82f6; /* Default Blue */
    }
    .card-title {
        color: #9ca3af;
        font-size: 0.9rem;
        text-transform: uppercase;
        font-weight: 600;
    }
    .card-value {
        color: white;
        font-size: 2rem;
        font-weight: 700;
    }
    .card-sub {
        font-size: 0.8rem;
        color: #10b981; /* Green success text */
    }

    /* Color Variants for Cards */
    .border-blue { border-left-color: #3b82f6; }
    .border-green { border-left-color: #10b981; }
    .border-purple { border-left-color: #8b5cf6; }
    .border-orange { border-left-color: #f59e0b; }
    .border-red { border-left-color: #ef4444; }

    /* 4. Critical Alert Box (Right Side) */
    .alert-box {
        background-color: #1f2937;
        border: 1px solid #374151;
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 10px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .alert-name {
        font-weight: bold;
        color: #e5e7eb;
    }
    .alert-badge {
        background-color: #7f1d1d;
        color: #fca5a5;
        padding: 4px 10px;
        border-radius: 15px;
        font-size: 0.8rem;
        font-weight: bold;
    }

    /* 5. Table Styling override */
    [data-testid="stDataFrame"] {
        border: 1px solid #374151;
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. DATA LOADING (Robust) ---
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
        
        return merged, log
    except Exception as e: return str(e), None

def send_email_alert(name, qty, location="N/A", is_test=False):
    try:
        creds = st.secrets["email"]
        label = "TEST" if is_test else "CRITICAL STOCK"
        msg = MIMEText(f"Action Required: {name} is at {qty} units in {location}.")
        msg['Subject'] = f"🚨 {label}: {name}"
        msg['From'], msg['To'] = creds["address"], creds["receiver"]
        
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as s:
            s.starttls()
            s.login(creds["address"], creds["password"])
            s.sendmail(creds["address"], creds["receiver"], msg.as_string())
        
        st.session_state.email_history.append({"Time": datetime.now().strftime("%H:%M"), "Item": name, "Status": "Sent"})
        return True
    except Exception as e:
        st.session_state.email_history.append({"Time": datetime.now().strftime("%H:%M"), "Item": name, "Status": "Failed"})
        return False

# --- 4. DASHBOARD RENDER ---
inv_df, log_df = load_data()

if isinstance(inv_df, str): st.error(inv_df); st.stop()

# -- HEADER --
st.markdown("""
    <div style='display: flex; justify-content: space-between; align-items: flex-end;'>
        <div>
            <div class='dashboard-title'>NKSTPP MATERIAL HUB</div>
            <div class='dashboard-subtitle'>Live Inventory Tracking & Procurement System</div>
        </div>
        <div>
            <span style='background:#1f2937; padding:10px 20px; border-radius:8px; border:1px solid #374151; color:#10b981; font-weight:bold;'>● LIVE DATA STREAM</span>
        </div>
    </div>
    <hr style='border-color: #374151;'>
""", unsafe_allow_html=True)

# -- TOP KPI ROW (HTML CARDS) --
total_stock = int(inv_df['LIVE STOCK'].sum())
total_items = len(inv_df)
crit_items = inv_df[inv_df['LIVE STOCK'] <= 2]
locations = inv_df['LOCATION'].nunique()

c1, c2, c3, c4 = st.columns(4)

with c1:
    st.markdown(f"""
    <div class="kpi-card border-blue">
        <div class="card-title">Real Stock Load</div>
        <div class="card-value">{total_stock}</div>
        <div class="card-sub">{total_items} Unique Items</div>
    </div>
    """, unsafe_allow_html=True)

with c2:
    st.markdown(f"""
    <div class="kpi-card border-green">
        <div class="card-title">System Uptime</div>
        <div class="card-value">100%</div>
        <div class="card-sub" style="color:#10b981;">Fully Operational</div>
    </div>
    """, unsafe_allow_html=True)

with c3:
    st.markdown(f"""
    <div class="kpi-card border-purple">
        <div class="card-title">Daily Activity</div>
        <div class="card-value">{len(log_df)}</div>
        <div class="card-sub" style="color:#c084fc;">Transactions Logged</div>
    </div>
    """, unsafe_allow_html=True)

with c4:
    st.markdown(f"""
    <div class="kpi-card border-orange">
        <div class="card-title">Critical Alerts</div>
        <div class="card-value" style="color:#fbbf24;">{len(crit_items)}</div>
        <div class="card-sub" style="color:#fbbf24;">Immediate Action Req.</div>
    </div>
    """, unsafe_allow_html=True)

# -- MAIN CONTENT AREA --
# Layout: Left Column (Table) - 70% | Right Column (Critical Alerts) - 30%
col_left, col_right = st.columns([0.75, 0.25])

with col_left:
    st.subheader("📦 Live Material Status")
    
    # Filter Bar
    raw_locs = inv_df['LOCATION'].fillna("Unassigned").astype(str).unique().tolist()
    sel_loc = st.selectbox("Filter Zone", ["All Locations"] + sorted(raw_locs))
    
    filtered = inv_df.copy()
    if sel_loc != "All Locations":
        filtered = filtered[filtered['LOCATION'].astype(str) == sel_loc]
        
    cols_to_show = [c for c in ['MAKE', 'MATERIAL DISCRIPTION', 'TYPE(RATING)', 'SIZE', 'LOCATION', 'LIVE STOCK'] if c in inv_df.columns]
    
    st.dataframe(
        filtered[cols_to_show],
        use_container_width=True,
        hide_index=True,
        height=500,
        column_config={
            "LIVE STOCK": st.column_config.ProgressColumn(
                "Availability", 
                format="%d", 
                min_value=0, 
                max_value=int(inv_df['TOTAL NO'].max() or 100)
            )
        }
    )

with col_right:
    st.markdown("<div style='height: 28px'></div>", unsafe_allow_html=True) # Spacer
    st.markdown(f"""
    <div class="kpi-card border-red" style="padding: 15px;">
        <div class="card-title" style="color:#fca5a5; margin-bottom:10px;">TOP 5 CRITICAL ZONES (%)</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Generate Red Alert Boxes dynamically
    if not crit_items.empty:
        for idx, row in crit_items.head(8).iterrows():
            name = row.get('MATERIAL DISCRIPTION', 'Item')[:20] + "..." # Truncate long names
            qty = row['LIVE STOCK']
            st.markdown(f"""
            <div class="alert-box">
                <div class="alert-name">{name}</div>
                <div class="alert-badge">{qty} LEFT</div>
            </div>
            """, unsafe_allow_html=True)
            
            # Trigger Email Logic
            alert_id = f"sent_{name}_{row.get('LOCATION')}"
            if alert_id not in st.session_state:
                if send_email_alert(row.get('MATERIAL DISCRIPTION'), qty, row.get('LOCATION')):
                    st.session_state[alert_id] = True
    else:
        st.success("System Healthy. No critical shortages.")

# -- FOOTER / LOGS --
with st.expander("🛠️ System Settings & Logs"):
    if st.button("📧 Send Test Email Signal"):
        if send_email_alert("TEST_SIGNAL", 0, is_test=True):
            st.success("Signal Sent.")
        else:
            st.error("Signal Failed.")
    
    if st.session_state.email_history:
        st.write("Transmission Log:")
        st.table(pd.DataFrame(st.session_state.email_history).iloc[::-1])
