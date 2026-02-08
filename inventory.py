@st.cache_data(ttl=60)
def load_synchronized_data():
    try:
        # 1. LOAD MAIN INVENTORY
        inv_df_raw = pd.read_csv(INV_URL, header=None).astype(str)
        
        # Super-Flexible Search: Find row containing "MATERIAL" and "DESCRIPTION"
        header_row_idx = None
        for i, row in inv_df_raw.iterrows():
            # Join all cells in the row and check for the keywords
            row_text = " ".join(row).upper()
            if "MATERIAL" in row_text and "DESCRIPTION" in row_text:
                header_row_idx = i
                break
        
        if header_row_idx is None:
            return "HEADER_NOT_FOUND", None
            
        # Reload with the correct header row found
        inv_df = pd.read_csv(INV_URL, skiprows=header_row_idx)
        # Clean all column names: remove spaces and make UPPERCASE for the code to match
        inv_df.columns = [str(c).strip().upper() for c in inv_df.columns]
        
        # 2. LOAD USAGE LOG
        log_df = pd.read_csv(LOG_URL)
        log_df.columns = [str(c).strip().upper() for c in log_df.columns]
        
        # Rename "QUANTITY ISSUED" to match our logic if needed
        log_df = log_df.rename(columns={'QUANTITY ISSUED': 'QTY_OUT'})

        # 3. CLEAN NUMERIC DATA
        if 'TOTAL NO' in inv_df.columns:
            inv_df['TOTAL NO'] = pd.to_numeric(inv_df['TOTAL NO'], errors='coerce').fillna(0).astype(int)
        
        if 'QTY_OUT' in log_df.columns:
            log_df['QTY_OUT'] = pd.to_numeric(log_df['QTY_OUT'], errors='coerce').fillna(0).astype(int)
        else:
            log_df = pd.DataFrame(columns=['MATERIAL DESCRIPTION', 'TYPE(RATING)', 'LOCATION', 'QTY_OUT', 'ISSUED TO', 'PURPOSE'])

        # 4. TRIPLE-MATCH SYNC
        # We group the log by the 3 identifiers to get total used per item
        consumed = log_df.groupby(['MATERIAL DESCRIPTION', 'TYPE(RATING)', 'LOCATION'])['QTY_OUT'].sum().reset_index()
        
        merged = pd.merge(
            inv_df, 
            consumed, 
            on=['MATERIAL DESCRIPTION', 'TYPE(RATING)', 'LOCATION'], 
            how='left'
        )
        
        merged['QTY_OUT'] = merged['QTY_OUT'].fillna(0)
        merged['LIVE STOCK'] = merged['TOTAL NO'] - merged['QTY_OUT']
        
        return merged, log_df

    except Exception as e:
        return str(e), None
