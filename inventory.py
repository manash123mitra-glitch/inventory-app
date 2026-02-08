import streamlit as st
import pandas as pd
import re
import os

st.set_page_config(page_title="Inventory Dashboard", layout="wide")
DEFAULT_FILE_PATH = "EMD MATERIAL STOCK - EMD MATERIAL.csv"

def clean_currency_or_units(val):
    if pd.isna(val): return 0
    match = re.search(r"(\d+(\.\d+)?)", str(val))
    return float(match.group(1)) if match else 0

def load_data(file_path):
    if not os.path.exists(file_path): return None
    temp_df = pd.read_csv(file_path, header=None, dtype=str)
    header_row = None
    for i, row in temp_df.iterrows():
        if "MATERIAL DISCRIPTION" in row.astype(str).values:
            header_row = i
            break
    if header_row is None: return pd.DataFrame()
    df = pd.read_csv(file_path, header=header_row, dtype=str)
    df.columns = [c.strip() for c in df.columns]
    df = df[df['TOTAL NO'] != 'TOTAL NO']
    df = df[df['MATERIAL DISCRIPTION'].notna()]
    df['TOTAL NO'] = df['TOTAL NO'].apply(clean_currency_or_units)
    if 'LOCATION' in df.columns: df['LOCATION'] = df['LOCATION'].fillna('Unknown')
    else: df['LOCATION'] = 'Unknown'
    return df

st.title("🏭 EMD Inventory Manager")

if 'data' not in st.session_state:
    df = load_data(DEFAULT_FILE_PATH)
    if df is not None: st.session_state.data = df
    else: st.error(f"File '{DEFAULT_FILE_PATH}' not found."); st.stop()

df = st.session_state.data

# Sidebar
st.sidebar.header("Filter Inventory")
locs = sorted(list(df['LOCATION'].unique()))
sel_loc = st.sidebar.multiselect("Select Location", locs, default=locs)
thresh = st.sidebar.slider("Low Stock Level", 0, 50, 5)

filtered = df[df['LOCATION'].isin(sel_loc)]

# Stats
c1, c2, c3 = st.columns(3)
c1.metric("Items", len(filtered))
c2.metric("Total Stock", int(filtered['TOTAL NO'].sum()))
low_stock = filtered[filtered['TOTAL NO'] <= thresh]
c3.metric("⚠️ Low Stock", len(low_stock))

# Alerts
if not low_stock.empty:
    st.error(f"⚠️ Items below {thresh} units:")
    st.dataframe(low_stock[['LOCATION', 'MATERIAL DISCRIPTION', 'TOTAL NO']].sort_values("TOTAL NO"), hide_index=True)

# Editor
st.subheader("📝 Update Stock")
edited = st.data_editor(filtered, num_rows="dynamic", key="editor", hide_index=True)

if st.button("💾 Save Changes"):
    edited.to_csv("EMD_UPDATED_STOCK.csv", index=False)
    st.session_state.data = edited
    st.success("Saved 'EMD_UPDATED_STOCK.csv' to your folder!")