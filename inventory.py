import streamlit as st
import pandas as pd
import smtplib
from email.mime.text import MIMEText

# --- 1. PAGE CONFIG ---
st.set_page_config(page_title="EMD Smart Hub", layout="wide", page_icon="📈")

# --- 2. DATA LOADING ---
SHEET_ID = "1E0ZluX3o7vqnSBAdAMEn_cdxq3ro4F4DXxchOEFcS_g"
CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

@st.cache_data(ttl=60)
def load_data():
    try:
        df = pd.read_csv(CSV_URL)
        if "MATERIAL DISCRIPTION" not in df.columns:
            df = pd.read_csv(CSV_URL, skiprows=1)
        df.columns = [c.strip() for c in df.columns]
        df['TOTAL NO'] = pd.to_numeric(df['TOTAL NO'], errors='coerce').fillna(0).astype(int)
        return df
    except:
        return None

# --- 3. EMAIL ALERT FUNCTION ---
def send_email_alert(item_name):
    """Sends an email when an item hits zero."""
    # NOTE: You must set these in Streamlit Secrets for security
    sender_email = st.secrets["email"]["address"]
    sender_password = st.secrets["email"]["password"]
    receiver_email = st.secrets["email"]["receiver"]

    msg = MIMEText(f"CRITICAL ALERT: The item '{item_name}' has reached ZERO stock in the EMD Inventory.")
    msg['Subject'] = f"🚨 Stock Out: {item_name}"
    msg['From'] = sender_email
    msg['To'] = receiver_email

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, receiver_email, msg.as_string())
        return True
    except Exception as e:
        st.error(f"Email failed: {e}")
        return False

# --- 4. DASHBOARD UI ---
st.title("📈 EMD Advanced Analytics")
df = load_data()

if df is not None:
    # --- AUTO-CHECK FOR ZERO STOCK ---
    zero_items = df[df['TOTAL NO'] == 0]
    if not zero_items.empty:
        for item in zero_items['MATERIAL DISCRIPTION']:
            # This avoids sending 100 emails at once by checking session state
            if f"alert_{item}" not in st.session_state:
                if send_email_alert(item):
                    st.session_state[f"alert_{item}"] = True
                    st.toast(f"Email Alert Sent for {item}!", icon="📧")

    # --- TABS FOR ORGANIZED VIEW ---
    tab_dash, tab_charts = st.tabs(["📊 Inventory Status", "📉 Consumption Trends"])

    with tab_dash:
        # (Your existing code for KPI cards and table goes here)
        st.subheader("Current Stock Levels")
        st.dataframe(df, use_container_width=True)

    with tab_charts:
        st.subheader("Consumption Analysis")
        
        col_c1, col_c2 = st.columns(2)
        
        with col_c1:
            st.write("📦 **Stock Volume by Location**")
            # Image showing a sample distribution chart
            
            loc_data = df.groupby('LOCATION')['TOTAL NO'].sum()
            st.bar_chart(loc_data)

        with col_c2:
            st.write("⚠️ **Critical Stock Items**")
            # Filtering for items that are nearly consumed
            low_stock = df[df['TOTAL NO'] < 10].sort_values('TOTAL NO')
            st.area_chart(low_stock.set_index('MATERIAL DISCRIPTION')['TOTAL NO'])

else:
    st.error("Connection lost. Please check Google Sheet Sharing settings.")
