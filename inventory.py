# --- REFINED DATA LOADING & SYNC ---
@st.cache_data(ttl=60)
def load_synchronized_data():
    try:
        # 1. LOAD MAIN INVENTORY
        inv_df_raw = pd.read_csv(INV_URL, header=None)
        
        # Find the row that contains 'MATERIAL DESCRIPTION'
        header_row_idx = None
        for i, row in inv_df_raw.iterrows():
            if row.astype(str).str.contains('MATERIAL DESCRIPTION').any():
                header_row_idx = i
                break
        
        if header_row_idx is None:
            st.error("❌ Could not find 'MATERIAL DESCRIPTION' in the Main Sheet. Please check spelling.")
            return None, None
            
        # Reload with the correct header row
        inv_df = pd.read_csv(INV_URL, skiprows=header_row_idx)
        inv_df.columns = [str(c).strip() for c in inv_df.columns]
        
        # 2. LOAD USAGE LOG
        log_df = pd.read_csv(LOG_URL)
        log_df.columns = [str(c).strip() for c in log_df.columns]

        # 3. CLEAN NUMERIC DATA
        inv_df['TOTAL NO'] = pd.to_numeric(inv_df['TOTAL NO'], errors='coerce').fillna(0).astype(int)
        
        if 'Quantity Issued' in log_df.columns:
            log_df['Quantity Issued'] = pd.to_numeric(log_df['Quantity Issued'], errors='coerce').fillna(0).astype(int)
        else:
            # Create empty log if columns aren't ready to prevent crash
            log_df = pd.DataFrame(columns=['MATERIAL DESCRIPTION', 'TYPE(RATING)', 'LOCATION', 'Quantity Issued', 'Issued To', 'Purpose'])

        # 4. SYNC LOGIC (The "Triple Match")
        # Ensure the USAGE LOG columns match the INVENTORY columns for the merge
        consumed = log_df.groupby(['MATERIAL DESCRIPTION', 'TYPE(RATING)', 'LOCATION'])['Quantity Issued'].sum().reset_index()
        
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
