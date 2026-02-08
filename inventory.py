# --- REFINED DATA LOADING & SYNC ---
@st.cache_data(ttl=60)
def load_synchronized_data():
    try:
        # 1. Load Main Inventory
        inv_df = pd.read_csv(INV_URL)
        # Clean all column names immediately (removes spaces/newlines)
        inv_df.columns = [str(c).strip() for c in inv_df.columns]
        
        # 2. Check for Header row if the first read failed
        if "MATERIAL DESCRIPTION" not in inv_df.columns:
            inv_df = pd.read_csv(INV_URL, skiprows=1)
            inv_df.columns = [str(c).strip() for c in inv_df.columns]

        # 3. Load Usage Log
        log_df = pd.read_csv(LOG_URL)
        log_df.columns = [str(c).strip() for c in log_df.columns]

        # --- SAFETY CHECK FOR 'TOTAL NO' ---
        if 'TOTAL NO' in inv_df.columns:
            inv_df['TOTAL NO'] = pd.to_numeric(inv_df['TOTAL NO'], errors='coerce').fillna(0).astype(int)
        else:
            st.error(f"❌ Column 'TOTAL NO' not found in Main Sheet. Found: {list(inv_df.columns)}")
            return None, None

        if 'Quantity Issued' in log_df.columns:
            log_df['Quantity Issued'] = pd.to_numeric(log_df['Quantity Issued'], errors='coerce').fillna(0).astype(int)
        else:
            # If log is empty or columns are wrong, we create a dummy to prevent crash
            log_df = pd.DataFrame(columns=['MATERIAL DESCRIPTION', 'TYPE(RATING)', 'LOCATION', 'Quantity Issued', 'Issued To', 'Purpose'])

        # --- UNIQUE MATCH LOGIC ---
        # Group by the 3 identifiers that distinguish identical item names
        consumed = log_df.groupby(['MATERIAL DESCRIPTION', 'TYPE(RATING)', 'LOCATION'])['Quantity Issued'].sum().reset_index()
        
        # Merge with Main Sheet
        merged = pd.merge(
            inv_df, 
            consumed, 
            on=['MATERIAL DESCRIPTION', 'TYPE(RATING)', 'LOCATION'], 
            how='left'
        )
        
        merged['Quantity Issued'] = merged['Quantity Issued'].fillna(0)
        merged['LIVE STOCK'] = merged['TOTAL NO'] - merged['Quantity Issued']
        
        return merged, log_df

    except Exception as e:
        st.error(f"🚨 Sync Error: {e}")
        return None, None
