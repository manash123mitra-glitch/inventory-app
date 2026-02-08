import streamlit as st
import pandas as pd
import smtplib
from email.mime.text import MIMEText

# --- 1. SETTINGS & CONNECTIONS ---
# Using the specific GIDs you provided
SHEET_ID = "1E0ZluX3o7vqnSBAdAMEn_cdxq3ro4F4DXxchOEFcS_g"
INV_GID = "804871972" 
LOG_GID = "1151083374" 

INV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={INV_GID}"
LOG_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={LOG_GID}"

# --- 2. DATA LOADING FUNCTIONS ---
@st.cache_data(ttl=60)
def load_data(url, is_inventory=True):
    try:
        df = pd.read_csv(url)
        # Clean column names
        df.columns = [c.strip() for c in df.columns]
        
        if is_inventory:
            # Skip potential sub-headers like 'ALMIRA NO.1'
            if "MATERIAL DISCRIPTION" not in df.columns:
                df = pd.read_csv(url, skiprows=1)
                df.columns = [c.strip() for c in df.columns]
            df['TOTAL NO'] = pd.to_numeric(df['TOTAL NO'], errors='coerce').fillna(0).astype(int)
        else:
            # Process Usage Log
            if 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
            if 'Quantity Issued' in df.columns:
                df['Quantity Issued'] = pd.to_numeric(df['Quantity Issued'], errors='coerce').fillna(0)
        return df
    except Exception as e:
        return None

# --- 3. EMAIL ALERT LOGIC ---
def send_email_alert(item_name):
    try:
        # These must be set in your Streamlit Cloud Secrets
        email_creds = st.secrets["email"]
        msg = MIMEText(f"CRITICAL: '{item_name}' is out of stock in the EMD Inventory.")
        msg['Subject'] = f"🚨 Stock Out: {item_name}"
        msg['From'] = email_creds["address"]
        msg['To'] = email_creds["receiver"]

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(email_creds["address"], email_creds["password"])
            server.sendmail(email_creds["address"], email_creds["receiver"], msg.as_string())
        return True
    except:
        return False

# --- 4. DASHBOARD UI ---
st.title("📈 EMD Advanced Analytics Hub")

inv_df = load_data(INV_URL, is_inventory=True)
log_df = load_data(LOG_URL, is_inventory=False)

if inv_df is not None:
    # Check for Zero Stock and Trigger Emails
    zero_stock = inv_df[inv_df['TOTAL NO'] == 0]
    for _, item in zero_stock.iterrows():
        item_name = item['MATERIAL DISCRIPTION']
        if f"alert_{item_name}" not in st.session_state:
            if send_email_alert(item_name):
                st.session_state[f"alert_{item_name}"] = True
                st.toast(f"Email Alert Sent for {item_name}", icon="📧")

    # Layout Tabs
    tab_status, tab_trends = st.tabs(["📊 Inventory Status", "📉 Consumption Trends"])

    with tab_status:
        st.sidebar.header("🕹️ Filter Controls")
        locs = sorted(inv_df['LOCATION'].dropna().unique().tolist())
        selected_loc = st.sidebar.selectbox("Location Filter", ["All Locations"] + locs)
        
        display_df = inv_df if selected_loc == "All Locations" else inv_df[inv_df['LOCATION'] == selected_loc]
        
        st.subheader(f"Current Stock: {selected_loc}")
        st.dataframe(display_df, use_container_width=True, hide_index=True)

    with tab_trends:
        if log_df is not None and not log_df.empty:
            st.subheader("Material Consumption Patterns")
            
            c1, c2 = st.columns(2)
            with c1:
                st.write("**Usage Over Time**")
                # Grouping consumption by date
                
                time_data = log_df.groupby('Date')['Quantity Issued'].sum()
                st.line_chart(time_data)
                
            with c2:
                st.write("**Top 10 Most Used Items**")
                
                top_items = log_df.groupby('Material Description')['Quantity Issued'].sum().nlargest(10)
                st.bar_chart(top_items)
        else:
            st.info("No logs found. Record your daily issues in the 'USAGE LOG' sheet tab.")

else:
    st.error("Failed to connect to the Inventory tab. Verify GID 804871972 is correct.")
