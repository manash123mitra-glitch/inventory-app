import streamlit as st
import pandas as pd

# --- 1. PAGE CONFIG & STYLING ---
st.set_page_config(page_title="EMD Inventory Hub", layout="wide", page_icon="📦")

# Professional CSS for a modern look
st.markdown("""
<style>
    .stApp { background-color: #f0f2f6; }
    .metric-card {
        background-color: white;
        padding: 20px;
        border-radius: 10px;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.05);
        border-left: 5px solid #007bff;
    }
    .low-stock-card {
        background-color: #fff3f3;
        border-left: 5px solid #dc3545;
        padding: 10px;
        border-radius: 5px;
        margin-bottom: 5px;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. THE GOOGLE SHEET LINK ---
# Replace the ID below with the ID from YOUR Google Sheet link
SHEET_ID = "1E0ZluX3o7vqnSBAdAMEn_cdxq3ro4F4DXxchOEFcS_g"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv"

@st.cache_data(ttl=600) # Refresh every 10 minutes
def get_data():
    try:
        # We read the shared CSV link directly
        df = pd.read_csv(SHEET_URL)
        
        # Data Cleaning
        df.columns = [c.strip() for c in df.columns]
        # Find the row where actual data starts (skipping 'ALMIRA NO.1' etc if present)
        if "MATERIAL DISCRIPTION" not in df.columns:
             df = pd.read_csv(SHEET_URL, skiprows=1)
        
        # Convert Stock to Number
        df['TOTAL NO'] = pd.to_numeric(df['TOTAL NO'], errors='coerce').fillna(0).astype(int)
        return df
    except Exception as e:
        st.error(f"Error connecting to Sheet: {e}")
        return pd.DataFrame()

# --- 3. DASHBOARD LOGIC ---
st.title("🛡️ EMD Executive Inventory Dashboard")

df = get_data()

if not df.empty:
    # --- SIDEBAR DROPDOWN ---
    st.sidebar.header("🕹️ Filter Controls")
    locations = sorted(df['LOCATION'].unique().tolist())
    selected_location = st.sidebar.selectbox("Select Storage Location", ["All Locations"] + locations)
    
    threshold = st.sidebar.slider("Low Stock Threshold", 0, 50, 10)

    # Filter Data
    if selected_location != "All Locations":
        display_df = df[df['LOCATION'] == selected_location]
    else:
        display_df = df

    # --- TOP METRICS ---
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown(f"<div class='metric-card'><h4>Total Items</h4><h2>{len(display_df)}</h2></div>", unsafe_allow_html=True)
    with col2:
        st.markdown(f"<div class='metric-card'><h4>Total Quantity</h4><h2>{display_df['TOTAL NO'].sum()}</h2></div>", unsafe_allow_html=True)
    with col3:
        low_stock_list = display_df[display_df['TOTAL NO'] < threshold]
        st.markdown(f"<div class='metric-card' style='border-left-color:red'><h4>Low Stock Alerts</h4><h2>{len(low_stock_list)}</h2></div>", unsafe_allow_html=True)

    # --- VISUAL DASHBOARD ---
    st.write("---")
    
    # Left Side: The Table
    left_col, right_col = st.columns([2, 1])
    
    with left_col:
        st.subheader("📝 Material Records")
        st.dataframe(display_df, use_container_width=True, hide_index=True, column_config={
            "TOTAL NO": st.column_config.ProgressColumn("Stock Level", min_value=0, max_value=int(df['TOTAL NO'].max()))
        })

    with right_col:
        st.subheader("⚠️ Critical Shortages")
        if not low_stock_list.empty:
            for _, row in low_stock_list.iterrows():
                st.markdown(f"""
                <div class='low-stock-card'>
                    <strong>{row['MATERIAL DISCRIPTION']}</strong><br>
                    Qty: {row['TOTAL NO']} | Location: {row['LOCATION']}
                </div>
                """, unsafe_allow_html=True)
        else:
            st.success("All stock levels are optimal.")

else:
    st.info("Please ensure your Google Sheet link is correct and set to 'Anyone with the link'.")
