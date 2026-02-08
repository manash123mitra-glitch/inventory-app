import streamlit as st
import pandas as pd
import smtplib
from email.mime.text import MIMEText

# --- 1. SETTINGS & GIDs ---
SHEET_ID = "1E0ZluX3o7vqnSBAdAMEn_cdxq3ro4F4DXxchOEFcS_g"
INV_GID = "804871972" 
LOG_GID = "1151083374" 

INV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={INV_GID}"
LOG_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={LOG_GID}"

# --- 2. EMAIL ALERT FUNCTION ---
def send_email_alert(item_name, rating, location, current_qty):
    """Sends a professional email alert using Streamlit Secrets."""
    try:
        email_creds = st.secrets["email"]
        
        subject = f"🚨 LOW STOCK ALERT: {item_name}"
        body = f"""
        EMD Material Inventory Alert
        ----------------------------
        Item: {item_name}
        Rating/Type: {rating}
        Location: {location}
        Current Live Stock: {current_qty}
        
        This is an automated notification from the EMD Material Inventory Dashboard.
        """
        
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From'] = email_creds["address"]
        msg['To'] = email_creds["receiver"]

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(email_creds["address"], email_creds["password"])
            server.sendmail(email_creds["address"], email_creds["receiver"], msg.as_string())
        return True
    except Exception as e:
        return False

# --- 3. DATA LOADING & SYNC LOGIC ---
@st.cache_data(ttl=60)
def load_synchronized_data():
    try:
        # Load Inventory
        inv_df_raw = pd.read_csv(INV_URL, header=None).fillna("").astype(str)
        header_row_idx = None
        for i, row in inv_df_raw.iterrows():
            row_text = " ".join(row).upper()
            if "MATERIAL" in row_text and ("DISCRIPTION" in row_text or "DESCRIPTION" in row_text):
                header_row_idx = i
                break
        
        if header_row_idx is None: return "HEADER_NOT_FOUND", inv_df_raw.head(10)
            
        inv_df = pd.read_csv(INV_URL, skiprows=header_row_idx)
        inv_df.columns = [str(c).strip().replace('\n', '').upper() for c in inv_df.columns]
        
        # Load Logs
        log_df = pd.read_csv(LOG_URL)
        log_df.columns = [str(c).strip().replace('\n', '').upper() for c in log_df.columns]
        log_df = log_df.rename(columns={'QUANTITY ISSUED': 'QTY_OUT'})

        # Cleaning
        inv_df['TOTAL NO'] = pd.to_numeric(inv_df['TOTAL NO'], errors='coerce').fillna(0).astype(int)
        if 'QTY_OUT' in log_df.columns:
            log_df['QTY_OUT'] = pd.to_numeric(log_df['QTY_OUT'], errors='coerce').fillna(0).astype(int)
        else:
            log_df = pd.DataFrame(columns=['MATERIAL DESCRIPTION', 'TYPE(RATING)', 'LOCATION', 'QTY_OUT'])

        # Dynamic Matching Keys
        possible_keys = ['MATERIAL DESCRIPTION', 'MATERIAL DISCRIPTION', 'MAKE', 'TYPE(RATING)', 'SIZE', 'LOCATION']
        match_keys = [k for k in possible_keys if k in inv_df.columns and k in log_df.columns]
        
        consumed = log_df.groupby(match_keys)['QTY_OUT'].sum().reset_index()
        merged = pd.merge(inv_df, consumed, on=match_keys, how='left')
        merged['QTY_OUT'] = merged['QTY_OUT'].fillna(0)
        merged['LIVE STOCK'] = merged['TOTAL NO'] - merged['QTY_OUT']
        
        return merged, log_df
    except Exception as e:
        return f"ERROR: {str(e)}", None

# --- 4. PAGE CONFIG & UI ---
st.set_page_config(page_title="EMD Material Inventory", layout="wide", page_icon="🛡️")

# --- UPDATED HEADER HERE ---
st.title("🛡️ EMD Material Inventory Dashboard")
st.markdown("---")

inv_df, log_df = load_synchronized_data()

if isinstance(inv_df, str):
    st.error(f"🚨 {inv_df}")
    st.stop()

# --- 5. EMAIL TRIGGER LOGIC ---
ALERT_THRESHOLD = 2
critical_items = inv_df[inv_df['LIVE STOCK'] <= ALERT_THRESHOLD]

if not critical_items.empty:
    for _, row in critical_items.iterrows():
        item_name = row.get('MATERIAL DISCRIPTION', row.get('MATERIAL DESCRIPTION', 'Unknown'))
        rating = row.get('TYPE(RATING)', 'N/A')
        loc = row.get('LOCATION', 'N/A')
        item_id = f"alert_{item_name}_{rating}_{loc}".replace(" ", "_")
        
        if item_id not in st.session_state:
            if send_email_alert(item_name, rating, loc, row['LIVE STOCK']):
                st.session_state[item_id] = True
                st.toast(f"Email Alert Sent: {item_name}", icon="📧")

# --- 6. DASHBOARD DISPLAY ---
st.success(f"✅ System Live | {len(critical_items)} items require attention.")

# Filters
loc_list = sorted(inv_df['LOCATION'].dropna().unique().tolist())
sel_loc = st.sidebar.selectbox("Filter Location", ["All"] + loc_list)
disp_df = inv_df if sel_loc == "All" else inv_df[inv_df['LOCATION'] == sel_loc]

# Visual Table

st.dataframe(
    disp_df, 
    use_container_width=True, 
    hide_index=True,
    column_config={
        "LIVE STOCK": st.column_config.ProgressColumn(
            "Inventory Level", min_value=0, max_value=int(inv_df['TOTAL NO'].max() or 100), format="%d"
        )
    }
)

with st.expander("📜 View Audit Trail (Recent Transactions)"):
    st.dataframe(log_df, use_container_width=True, hide_index=True)
