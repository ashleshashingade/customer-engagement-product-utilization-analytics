import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

st.set_page_config(page_title="Customer Engagement & Product Utilization", page_icon="📊", layout="wide")

st.title("📊 Customer Engagement & Product Utilization Analytics")
st.subheader("Retention Strategy Dashboard")
st.write("Upload your project dataset (CSV) to explore engagement, product utilization, churn, and retention patterns.")

with st.sidebar:
    st.header("Upload dataset")
    uploaded_file = st.file_uploader("Choose a CSV file", type=["csv"])
    st.caption("Use the same customer dataset used for your project. Avoid uploading confidential or personally identifiable information.")

if uploaded_file is None:
    st.info("Upload your CSV file from the sidebar to begin. The dashboard will use available columns and explain when a field is missing.")
    st.markdown("""
    **Suggested analyses**
    - Engagement level distribution
    - Churn rate and retention rate
    - Product utilization by number of products
    - Geography-wise customer patterns
    - High-value, low-engagement customer segment
    """)
    st.stop()

try:
    df = pd.read_csv(uploaded_file)
except Exception as e:
    st.error(f"Could not read this CSV file: {e}")
    st.stop()

if df.empty:
    st.error("The uploaded CSV contains no rows.")
    st.stop()

df.columns = [str(c).strip() for c in df.columns]
st.success(f"Dataset loaded: {len(df):,} rows and {len(df.columns):,} columns.")

def find_col(candidates):
    lowered = {c.lower().replace("_", "").replace(" ", ""): c for c in df.columns}
    for candidate in candidates:
        key = candidate.lower().replace("_", "").replace(" ", "")
        if key in lowered:
            return lowered[key]
    for c in df.columns:
        normalized = c.lower().replace("_", "").replace(" ", "")
        if any(candidate.lower().replace("_", "").replace(" ", "") in normalized for candidate in candidates):
            return c
    return None

churn_col = find_col(["Exited", "Churn", "Churned", "IsChurn"])
products_col = find_col(["NumOfProducts", "NumberOfProducts", "ProductsUsed", "ProductCount"])
geo_col = find_col(["Geography", "Country", "Region"])
engagement_col = find_col(["EngagementLevel", "Engagement Level", "EngagementTier"])
engagement_score_col = find_col(["EngagementScore", "Engagement Score"])
balance_col = find_col(["Balance", "AccountBalance"])
customer_id_col = find_col(["CustomerId", "CustomerID", "ClientId"])

def churn_to_numeric(series):
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_numeric(series, errors="coerce")
    mapping = {"yes": 1, "true": 1, "churn": 1, "churned": 1, "exited": 1,
               "no": 0, "false": 0, "retained": 0, "active": 0, "not churned": 0}
    return series.astype(str).str.strip().str.lower().map(mapping)

work = df.copy()
if churn_col:
    work["_churn_numeric"] = churn_to_numeric(work[churn_col])
    # Common bank churn datasets use 1 = churned and 0 = retained.
    if work["_churn_numeric"].dropna().isin([0, 1]).all():
        pass

if engagement_col:
    work["_engagement"] = work[engagement_col].astype(str)
elif engagement_score_col:
    score = pd.to_numeric(work[engagement_score_col], errors="coerce")
    work["_engagement"] = pd.cut(score, bins=[-np.inf, 0, 1, 2, np.inf],
                                 labels=["Low", "Low", "Moderate", "Highly"]).astype(str)
else:
    work["_engagement"] = None

# Top-level metrics
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total customers", f"{len(work):,}")
if "_churn_numeric" in work and work["_churn_numeric"].notna().any():
    churn_rate = work["_churn_numeric"].mean() * 100
    c2.metric("Churn rate", f"{churn_rate:.2f}%")
    c3.metric("Retention rate", f"{100-churn_rate:.2f}%")
else:
    c2.metric("Churn rate", "N/A")
    c3.metric("Retention rate", "N/A")
if products_col:
    products = pd.to_numeric(work[products_col], errors="coerce")
    c4.metric("Avg. products per customer", f"{products.mean():.2f}" if products.notna().any() else "N/A")
else:
    c4.metric("Avg. products per customer", "N/A")

tab1, tab2, tab3, tab4 = st.tabs(["Overview", "Engagement", "Product utilization", "Geography & segments"])

with tab1:
    st.markdown("### Dataset preview")
    st.dataframe(df.head(20), use_container_width=True)
    st.markdown("### Data quality")
    quality = pd.DataFrame({
        "Column": df.columns,
        "Missing values": [int(df[c].isna().sum()) for c in df.columns],
        "Missing %": [round(df[c].isna().mean()*100, 2) for c in df.columns],
        "Unique values": [int(df[c].nunique(dropna=True)) for c in df.columns]
    })
    st.dataframe(quality, use_container_width=True)

with tab2:
    st.markdown("### Engagement analysis")
    if work["_engagement"].notna().any():
        counts = work["_engagement"].fillna("Unknown").value_counts().rename_axis("Engagement level").reset_index(name="Customers")
        st.plotly_chart(px.bar(counts, x="Engagement level", y="Customers", title="Customers by engagement level"), use_container_width=True)
        if "_churn_numeric" in work and work["_churn_numeric"].notna().any():
            rate = work.groupby("_engagement", dropna=False)["_churn_numeric"].mean().mul(100).reset_index(name="Churn rate (%)")
            rate = rate.rename(columns={"_engagement":"Engagement level"})
            st.plotly_chart(px.bar(rate, x="Engagement level", y="Churn rate (%)", title="Churn rate by engagement level"), use_container_width=True)
        else:
            st.info("A churn column was not detected, so churn by engagement cannot be calculated.")
    else:
        st.info("No engagement level or engagement score column was detected. If your CSV contains one, name it EngagementLevel or EngagementScore for automatic analysis.")

with tab3:
    st.markdown("### Product utilization")
    if products_col:
        prod = pd.to_numeric(work[products_col], errors="coerce")
        product_counts = prod.value_counts(dropna=True).sort_index().rename_axis("Number of products").reset_index(name="Customers")
        st.plotly_chart(px.bar(product_counts, x="Number of products", y="Customers", title="Customer count by number of products"), use_container_width=True)
        if "_churn_numeric" in work and work["_churn_numeric"].notna().any():
            churn_by_product = work.assign(_product_count=prod).groupby("_product_count")["_churn_numeric"].mean().mul(100).reset_index(name="Churn rate (%)")
            churn_by_product = churn_by_product.rename(columns={"_product_count":"Number of products"})
            st.plotly_chart(px.bar(churn_by_product, x="Number of products", y="Churn rate (%)", title="Churn rate by number of products"), use_container_width=True)
    else:
        st.info("No product count column was detected. A column named NumOfProducts or ProductCount is recommended.")

with tab4:
    st.markdown("### Geography and customer segments")
    if geo_col and work["_engagement"].notna().any():
        geo_engagement = work.groupby([geo_col, "_engagement"], dropna=False).size().reset_index(name="Customers")
        geo_engagement = geo_engagement.rename(columns={geo_col:"Geography", "_engagement":"Engagement level"})
        st.plotly_chart(px.bar(geo_engagement, x="Geography", y="Customers", color="Engagement level",
                               barmode="group", title="Engagement levels by geography"), use_container_width=True)
        if "_churn_numeric" in work and work["_churn_numeric"].notna().any():
            geo_churn = work.groupby(geo_col)["_churn_numeric"].mean().mul(100).reset_index(name="Churn rate (%)")
            geo_churn = geo_churn.rename(columns={geo_col:"Geography"})
            st.plotly_chart(px.bar(geo_churn, x="Geography", y="Churn rate (%)", title="Churn rate by geography"), use_container_width=True)
    else:
        st.info("Geography and engagement columns are needed for geography-wise engagement analysis.")

    if balance_col and "_engagement" in work and work["_engagement"].notna().any():
        balance = pd.to_numeric(work[balance_col], errors="coerce")
        seg = work.assign(_balance=balance).groupby("_engagement")["_balance"].agg(["mean", "median", "count"]).reset_index()
        seg = seg.rename(columns={"_engagement":"Engagement level", "mean":"Average balance", "median":"Median balance", "count":"Customers"})
        st.dataframe(seg, use_container_width=True)

st.markdown("---")
st.caption("This dashboard is a project demonstration. Validate column meanings and results against your research paper before submitting.")
