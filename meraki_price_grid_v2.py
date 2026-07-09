"""
meraki_price_grid_v2.py
========================
MERAKI // PRICE_GRID — a formal, professional analytics dashboard with a
subtle 2026 futuristic accent (roughly 10% stylistic flourish, 90% clean
enterprise design). Compares Cisco Meraki pricing across BuyMeraki.com.au
and Dragon-Networks.com.au.

Usage:
    streamlit run meraki_price_grid_v2.py

Requires (same folder):
    buymeraki_all_categories_enriched.csv
    dragon_networks_products.csv
"""

import os
import glob
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Meraki Price Grid",
    page_icon="◆",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap');

:root {
    --bg-main: #0f1115;
    --bg-panel: #161920;
    --bg-panel-2: #1c2029;
    --border-soft: #2a2e38;
    --text-primary: #eceef2;
    --text-secondary: #8b909c;
    --accent: #3ecfb2;
    --accent-dim: #23594c;
    --accent-glow: rgba(62,207,178,0.15);
}

html, body, [class*="css"] {
    font-family: 'Inter', -apple-system, sans-serif;
}

.stApp {
    background: var(--bg-main);
    color: var(--text-primary);
}

h1, h2, h3 {
    font-family: 'Inter', sans-serif !important;
    font-weight: 600 !important;
    letter-spacing: -0.2px;
}

h1 {
    color: var(--text-primary) !important;
    font-size: 1.9rem;
    display: flex;
    align-items: center;
    gap: 10px;
}

h1::before {
    content: "";
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--accent);
    box-shadow: 0 0 8px var(--accent-glow);
}

h2, h3 {
    color: var(--text-primary) !important;
    font-size: 1.05rem;
    font-weight: 600 !important;
    border-left: 2px solid var(--accent-dim);
    padding-left: 10px;
}

section[data-testid="stSidebar"] {
    background: var(--bg-panel);
    border-right: 1px solid var(--border-soft);
}

section[data-testid="stSidebar"] h2 {
    color: var(--text-primary) !important;
    font-size: 0.95rem;
    border-left: none;
    padding-left: 0;
    border-bottom: 1px solid var(--border-soft);
    padding-bottom: 10px;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    font-size: 0.8rem;
    color: var(--text-secondary) !important;
}

div[data-testid="stMetric"] {
    background: var(--bg-panel);
    border: 1px solid var(--border-soft);
    border-radius: 8px;
    padding: 16px 18px;
    position: relative;
    overflow: hidden;
}

div[data-testid="stMetric"]::before {
    content: "";
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 2px;
    background: linear-gradient(90deg, var(--accent), transparent);
    opacity: 0.6;
}

div[data-testid="stMetricValue"] {
    color: var(--text-primary) !important;
    font-family: 'IBM Plex Mono', monospace;
    font-weight: 500;
    font-size: 1.6rem !important;
}

div[data-testid="stMetricLabel"] {
    color: var(--text-secondary) !important;
    font-size: 0.72rem;
    letter-spacing: 0.6px;
    text-transform: uppercase;
}

.stDataFrame {
    border: 1px solid var(--border-soft);
    border-radius: 8px;
}

hr {
    border-color: var(--border-soft) !important;
}

.stButton>button, .stDownloadButton>button {
    background: var(--bg-panel-2);
    color: var(--text-primary);
    border: 1px solid var(--border-soft);
    border-radius: 6px;
    font-weight: 500;
    font-size: 0.85rem;
    transition: all 0.2s ease;
}
.stButton>button:hover, .stDownloadButton>button:hover {
    border-color: var(--accent);
    color: var(--accent);
}

.subtle-divider {
    height: 1px;
    background: linear-gradient(90deg, var(--border-soft), transparent);
    margin: 16px 0 22px 0;
}

.status-box {
    background: var(--bg-panel);
    border: 1px solid var(--border-soft);
    border-radius: 8px;
    padding: 14px 18px;
    color: var(--text-secondary);
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.82rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.status-dot {
    display: inline-block;
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: var(--accent);
    margin-right: 6px;
    box-shadow: 0 0 6px var(--accent-glow);
}

[data-testid="stExpander"] {
    border: 1px solid var(--border-soft);
    background: var(--bg-panel);
    border-radius: 8px;
}

.stMultiSelect [data-baseweb="tag"] {
    background-color: var(--bg-panel-2) !important;
    border: 1px solid var(--accent-dim) !important;
    color: var(--text-primary) !important;
}
</style>
""", unsafe_allow_html=True)

PLOT_TEMPLATE = go.layout.Template()
PLOT_TEMPLATE.layout = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(22,25,32,0.4)",
    font=dict(color="#eceef2", family="Inter"),
    colorway=["#3ecfb2", "#5a6072", "#7fe6d0", "#3a3f4b", "#23594c"],
    xaxis=dict(gridcolor="rgba(255,255,255,0.06)", zerolinecolor="rgba(255,255,255,0.1)"),
    yaxis=dict(gridcolor="rgba(255,255,255,0.06)", zerolinecolor="rgba(255,255,255,0.1)"),
)


def _first_existing(patterns):
    for p in patterns:
        matches = glob.glob(p)
        if matches:
            return matches[0]
    return None


@st.cache_data
def load_data():
    buymeraki_path = _first_existing([
        "buymeraki_all_categories_enriched.csv",
        "buymeraki_all_categories.csv",
        "*buymeraki*enriched*.csv",
        "*buymeraki*.csv",
    ])
    dragon_path = _first_existing([
        "dragon_networks_products.csv",
        "*dragon*networks*.csv",
        "*dragon*.csv",
    ])

    frames = []

    if buymeraki_path and os.path.exists(buymeraki_path):
        bm = pd.read_csv(buymeraki_path)
        bm["Source"] = "BuyMeraki"
        frames.append(bm)

    if dragon_path and os.path.exists(dragon_path):
        dn = pd.read_csv(dragon_path)
        dn["Source"] = "Dragon Networks"
        frames.append(dn)

    if not frames:
        return pd.DataFrame(), False

    combined = pd.concat(frames, ignore_index=True, sort=False)

    for col in ["MSRP (Inc. GST)", "Price (Inc. GST)", "MSRP (Ex. GST)", "Price (Ex. GST)", "Discount %"]:
        if col not in combined.columns:
            combined[col] = np.nan
        combined[col] = pd.to_numeric(combined[col], errors="coerce")

    for col in ["Category", "Brand", "Manufacturer", "SKU", "MPN", "Availability", "Title", "Product URL"]:
        if col not in combined.columns:
            combined[col] = None

    if "On Sale/Discount" not in combined.columns:
        combined["On Sale/Discount"] = False
    combined["On Sale/Discount"] = combined["On Sale/Discount"].fillna(False).astype(bool)

    combined["Brand"] = combined["Brand"].fillna("Meraki")
    combined["Category"] = combined["Category"].fillna("Uncategorised")
    combined = combined.dropna(subset=["Title"])

    return combined, True


df, data_found = load_data()

st.markdown("# Meraki Price Grid")
st.markdown(
    '<div class="status-box">'
    '<span><span class="status-dot"></span>Combined intel feed &mdash; BuyMeraki.com.au + Dragon-Networks.com.au</span>'
    '<span style="color:#3ecfb2;">LIVE</span>'
    '</div>',
    unsafe_allow_html=True,
)
st.write("")

if not data_found:
    st.error(
        "No scraped data found. Run `buymeraki_scraper.py` and "
        "`dragon_networks_scraper.py` first, and keep this app in the same folder "
        "as the CSVs they produce (`buymeraki_all_categories_enriched.csv` and "
        "`dragon_networks_products.csv`)."
    )
    st.stop()

st.sidebar.markdown("## Filters")

sources = sorted(df["Source"].dropna().unique().tolist())
sel_sources = st.sidebar.multiselect("Source", sources, default=sources)

categories = sorted(df["Category"].dropna().unique().tolist())
sel_categories = st.sidebar.multiselect("Category", categories, default=[])

search_term = st.sidebar.text_input("Search title / SKU", "")

sale_only = st.sidebar.checkbox("On sale only", value=False)

price_col = "Price (Inc. GST)" if df["Price (Inc. GST)"].notna().any() else "Price (Ex. GST)"
valid_prices = df[price_col].dropna()
if not valid_prices.empty:
    p_min, p_max = float(valid_prices.min()), float(valid_prices.max())
    sel_price = st.sidebar.slider("Price range (AUD)", p_min, p_max, (p_min, p_max))
else:
    sel_price = (0.0, 0.0)

filtered = df.copy()
if sel_sources:
    filtered = filtered[filtered["Source"].isin(sel_sources)]
if sel_categories:
    filtered = filtered[filtered["Category"].isin(sel_categories)]
if search_term:
    term = search_term.lower()
    mask = (
        filtered["Title"].astype(str).str.lower().str.contains(term, na=False)
        | filtered["SKU"].astype(str).str.lower().str.contains(term, na=False)
        | filtered["MPN"].astype(str).str.lower().str.contains(term, na=False)
    )
    filtered = filtered[mask]
if sale_only:
    filtered = filtered[filtered["On Sale/Discount"]]
if valid_prices.any():
    filtered = filtered[
        filtered[price_col].isna()
        | filtered[price_col].between(sel_price[0], sel_price[1])
    ]

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Total SKUs", f"{len(filtered):,}")
c2.metric("On Sale", f"{int(filtered['On Sale/Discount'].sum()):,}")
avg_price = filtered[price_col].mean()
c3.metric("Avg Price", f"${avg_price:,.2f}" if pd.notna(avg_price) else "—")
max_price = filtered[price_col].max()
c4.metric("Most Expensive", f"${max_price:,.2f}" if pd.notna(max_price) else "—")
c5.metric("Sources Live", f"{filtered['Source'].nunique()}")

st.markdown('<div class="subtle-divider"></div>', unsafe_allow_html=True)

col_a, col_b = st.columns([1.3, 1])

with col_a:
    st.markdown("### Avg Price by Category")
    cat_avg = (
        filtered.dropna(subset=[price_col])
        .groupby("Category")[price_col]
        .mean()
        .sort_values(ascending=False)
        .head(15)
        .reset_index()
    )
    if not cat_avg.empty:
        fig = px.bar(cat_avg, x=price_col, y="Category", orientation="h", template=PLOT_TEMPLATE)
        fig.update_traces(marker_line_width=0)
        fig.update_layout(height=460, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, width='stretch')
    else:
        st.info("No priced items in current filter.")

with col_b:
    st.markdown("### Source Split")
    src_counts = filtered["Source"].value_counts().reset_index()
    src_counts.columns = ["Source", "Count"]
    if not src_counts.empty:
        fig2 = px.pie(src_counts, names="Source", values="Count", hole=0.6, template=PLOT_TEMPLATE)
        fig2.update_traces(textfont_color="#eceef2", marker=dict(line=dict(color="#0f1115", width=2)))
        fig2.update_layout(height=460, margin=dict(l=10, r=10, t=10, b=10),
                            legend=dict(font=dict(color="#eceef2")))
        st.plotly_chart(fig2, width='stretch')

st.markdown("### Price Distribution")
price_data = filtered.dropna(subset=[price_col])
if not price_data.empty:
    fig3 = px.histogram(price_data, x=price_col, nbins=40, template=PLOT_TEMPLATE,
                         color="Source", barmode="overlay", opacity=0.85)
    fig3.update_layout(height=320, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig3, width='stretch')

st.markdown('<div class="subtle-divider"></div>', unsafe_allow_html=True)

st.markdown("### Cross-Source Match: Same SKU, Different Vendor")
if {"SKU", "MPN"}.issubset(filtered.columns):
    key_series = filtered["SKU"].fillna(filtered["MPN"]).astype(str).str.upper().str.strip()
    tmp = filtered.assign(_key=key_series)
    tmp = tmp[tmp["_key"].notna() & (tmp["_key"] != "NAN") & (tmp["_key"] != "")]

    pivot = (
        tmp.groupby(["_key", "Source"])[price_col]
        .min()
        .unstack("Source")
    )
    pivot = pivot.dropna(how="all")
    matched = pivot.dropna(thresh=2) if pivot.shape[1] > 1 else pd.DataFrame()

    if not matched.empty:
        matched = matched.copy()
        matched["Cheapest"] = matched.idxmin(axis=1)
        matched["Price Gap ($)"] = matched.drop(columns="Cheapest").max(axis=1) - matched.drop(columns="Cheapest").min(axis=1)
        matched = matched.sort_values("Price Gap ($)", ascending=False)
        st.dataframe(matched.reset_index().rename(columns={"_key": "SKU / Model"}), width='stretch')
    else:
        st.info("No overlapping SKUs found between sources in the current filter.")
else:
    st.info("SKU/MPN columns not available for cross-matching.")

st.markdown('<div class="subtle-divider"></div>', unsafe_allow_html=True)

st.markdown("### Product Grid")
display_cols = [c for c in [
    "Source", "Category", "Title", "Brand", "SKU", "MPN", "Manufacturer",
    "Availability", "MSRP (Inc. GST)", "Price (Inc. GST)", "Price (Ex. GST)",
    "On Sale/Discount", "Discount %", "Product URL",
] if c in filtered.columns]

st.dataframe(
    filtered[display_cols].sort_values(price_col, ascending=False, na_position="last"),
    width='stretch',
    height=480,
)

st.download_button(
    "Export Filtered Data (.csv)",
    data=filtered[display_cols].to_csv(index=False).encode("utf-8"),
    file_name="meraki_combined_filtered.csv",
    mime="text/csv",
)

st.markdown('<div class="subtle-divider"></div>', unsafe_allow_html=True)
st.caption("Meraki Price Grid — data refreshed from local CSV cache. Re-run the scrapers to update.")
