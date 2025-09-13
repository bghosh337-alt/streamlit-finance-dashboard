# app1.py -  Personal Finance Dashboard (corrected)
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import io

st.set_page_config(page_title="💸  Finance Dashboard", layout="wide", initial_sidebar_state="expanded")

# ---- Styling ----
st.markdown(
    """
    <style>
    .header {
        background: linear-gradient(90deg,#4f46e5,#06b6d4);
        padding: 18px;
        border-radius: 12px;
        color: white;
    }
    .big-title { font-size:28px; font-weight:700; margin:0; }
    .sub { opacity:0.9; margin-top:4px; }
    .card {
        background: linear-gradient(180deg, rgba(255,255,255,0.9), rgba(255,255,255,0.82));
        border-radius:12px;
        padding:12px;
        box-shadow: 0 6px 18px rgba(8,15,52,0.08);
        margin-bottom: 10px;
    }
    .kpi { font-size:20px; font-weight:700; }
    </style>
    """, unsafe_allow_html=True
)

# Header
with st.container():
    st.markdown(
        '<div class="header"><p class="big-title">💸 Attractive Personal Finance Dashboard</p>'
        '<p class="sub">Upload data, add transactions, and interact with charts & filters</p></div>',
        unsafe_allow_html=True,
    )

# ---- Utility functions ----
@st.cache_data
def load_sample_df():
    # Safe load sample; adjust path if needed
    try:
        df = pd.read_csv("sample_data/sample_expenses.csv")
    except FileNotFoundError:
        # fallback small dataset
        data = [
            {"Date": "2025-01-05", "Category": "Groceries", "Amount": 1200, "Notes": "Big bazaar", "Gender": "Not specified"},
            {"Date": "2025-01-07", "Category": "Transport", "Amount": 60, "Notes": "Auto", "Gender": "Not specified"},
            {"Date": "2025-02-02", "Category": "Utility", "Amount": 2100, "Notes": "Electricity Bill", "Gender": "Not specified"},
        ]
        df = pd.DataFrame(data)
    # Ensure columns exist
    if "Gender" not in df.columns:
        df["Gender"] = "Not specified"
    return df

def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")

def ensure_datetime_col(df: pd.DataFrame, col="Date") -> pd.DataFrame:
    # Coerce to datetime safely
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], errors="coerce")
    else:
        df[col] = pd.NaT
    return df

# ---- Sidebar: data source and input form ----
st.sidebar.header("Data & Input")

data_source = st.sidebar.radio("Load data from:", ("Load sample (recommended)", "Upload file"))

df = None
uploaded_file = None
if data_source == "Upload file":
    uploaded_file = st.sidebar.file_uploader("Upload CSV/Excel", type=["csv", "xlsx"])
    if uploaded_file is not None:
        try:
            if uploaded_file.name.lower().endswith(".csv"):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
        except Exception as e:
            st.sidebar.error("Error reading file: " + str(e))
else:
    df = load_sample_df()

# Defensive: ensure dataframe exists and expected columns exist
if df is None:
    df = pd.DataFrame(columns=["Date", "Category", "Amount", "Notes", "Gender"])

# Add missing columns if necessary
for col in ["Category", "Amount", "Notes", "Gender"]:
    if col not in df.columns:
        df[col] = "" if col != "Amount" else 0

# Ensure Date column is datetime (coerce invalid)
df = ensure_datetime_col(df, "Date")

# Normalize types: Amount numeric
df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce").fillna(0.0)

# Fill NaT Date with today's date for display convenience (but keep NaT if needed)
# (We will show NaT rows but avoid crashing)
# df["Date"].fillna(pd.Timestamp.today(), inplace=True)

# ---- Sidebar: Add new transaction form ----
st.sidebar.markdown("---")
st.sidebar.subheader("Add new transaction (session only)")

with st.sidebar.form("add_txn", clear_on_submit=True):
    gender = st.radio("Gender", options=["Male", "Female", "Other", "Prefer not to say"], index=3)
    # category options combine existing and some defaults
    cat_options = sorted(set(df["Category"].astype(str).unique().tolist() + ["Groceries", "Transport", "Entertainment", "Utility", "Health", "Travel"]))
    cat = st.selectbox("Category", options=cat_options, index=0)
    date_input = st.date_input("Date", value=datetime.today())
    amount = st.number_input("Amount (₹)", min_value=0.0, step=1.0, format="%.2f")
    notes = st.text_input("Notes (optional)")
    tags = st.multiselect("Tags (optional)", options=["food", "monthly", "one-time", "refund", "family"])
    submit = st.form_submit_button("Submit transaction")

if submit:
    new_row = {
        "Date": pd.to_datetime(date_input),
        "Category": cat,
        "Amount": float(amount),
        "Notes": notes or "",
        "Gender": gender,
    }
    if tags:
        new_row["Notes"] = (new_row["Notes"] + " | Tags: " + ", ".join(tags)).strip()
    # append to df (in-memory only for this session)
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    st.sidebar.success("Added ✅ — this change is in-memory for this session.")

# ---- Main layout: Filters & display controls ----
st.markdown("")  # spacer
with st.container():
    left_col, right_col = st.columns([3, 1])
    with left_col:
        st.markdown("### Filters & Controls")
        cats_all = sorted(df["Category"].astype(str).replace("", "(empty)").unique())
        selected_cats = st.multiselect("Categories", options=cats_all, default=cats_all)
        genders_all = sorted(df["Gender"].astype(str).replace("", "Not specified").unique())
        selected_genders = st.multiselect("Genders", options=genders_all, default=genders_all)
        # Date inputs: default to min/max in df if available, else current month
        if not df["Date"].dropna().empty:
            min_date = df["Date"].min().date()
            max_date = df["Date"].max().date()
        else:
            today = datetime.today().date()
            min_date = today
            max_date = today
        dr = st.date_input("Date range", value=(min_date, max_date))
    with right_col:
        st.markdown("### Display")
        show_raw = st.checkbox("Show raw data", value=False)
        show_percent = st.checkbox("Show pie % labels", value=True)
        chart_choice = st.selectbox("Chart Type", options=["Pie", "Bar (Category)", "Monthly line", "Treemap"], index=0)

# Apply filters safely
start_date, end_date = dr
# Convert start/end to timestamps for comparison
start_ts = pd.to_datetime(start_date)
end_ts = pd.to_datetime(end_date)

# Ensure Category and Gender comparisons don't break with empty strings
mask_cat = df["Category"].astype(str).replace("", "(empty)").isin(selected_cats)
mask_gender = df["Gender"].astype(str).replace("", "Not specified").isin(selected_genders)

# For Date between, coerce Date to datetime already done; rows with NaT will be False
mask_date = df["Date"].between(start_ts, end_ts)

mask = mask_cat & mask_gender & mask_date
dff = df.loc[mask].copy()

# Ensure Date column is datetime here as well (defensive)
dff = ensure_datetime_col(dff, "Date")

# Create Month column safely; if Date is NaT, Month will be NaN string "NaT"
if not dff.empty and dff["Date"].notna().any():
    dff["Month"] = dff["Date"].dt.to_period("M").astype(str)
else:
    dff["Month"] = ""

# ---- KPIs ----
total = dff["Amount"].sum()
avg = dff["Amount"].mean() if len(dff) else 0.0
count = len(dff)

k1, k2, k3, k4 = st.columns([2, 2, 2, 2])
k1.markdown(f'<div class="card"><div class="kpi">Total</div><div style="font-size:18px;font-weight:700">₹{total:,.2f}</div><div style="opacity:0.7">Transactions: {count}</div></div>', unsafe_allow_html=True)
k2.markdown(f'<div class="card"><div class="kpi">Average</div><div style="font-size:18px;font-weight:700">₹{avg:,.2f}</div><div style="opacity:0.7">Per transaction</div></div>', unsafe_allow_html=True)
k3.markdown(f'<div class="card"><div class="kpi">Max</div><div style="font-size:18px;font-weight:700">₹{dff["Amount"].max() if count else 0:,.2f}</div><div style="opacity:0.7">Largest single</div></div>', unsafe_allow_html=True)
k4.download_button("⬇️ Download CSV", data=to_csv_bytes(dff), file_name="filtered_expenses.csv", mime="text/csv")

# ---- Visuals ----
st.markdown("## Visuals")
col_a, col_b = st.columns([2, 3])

with col_a:
    st.markdown("### Breakdown")
    if not dff.empty:
        if chart_choice == "Pie":
            fig = px.pie(dff, values="Amount", names="Category", title="Category share", hole=0.4)
            if show_percent:
                fig.update_traces(textinfo="percent+label")
        elif chart_choice == "Bar (Category)":
            cat_sum = dff.groupby("Category", as_index=False)["Amount"].sum().sort_values("Amount", ascending=False)
            fig = px.bar(cat_sum, x="Amount", y="Category", orientation="h", title="Spending by Category", text="Amount")
            fig.update_layout(yaxis={"categoryorder": "total ascending"})
        elif chart_choice == "Treemap":
            fig = px.treemap(dff, path=["Category"], values="Amount", title="Spending Treemap")
        else:
            fig = px.pie(dff, values="Amount", names="Category", title="Category share")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No data for the selected filters to display chart.")

with col_b:
    st.markdown("### Trend & Top items")
    if not dff.empty and dff["Month"].astype(bool).any():
        monthly = (dff.groupby("Month", as_index=False)["Amount"].sum().sort_values("Month"))
        fig2 = px.line(monthly, x="Month", y="Amount", markers=True, title="Monthly expense trend")
        st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("No monthly trend data available for current filters.")

    if not dff.empty:
        st.markdown("Top 5 largest transactions")
        top5 = dff.nlargest(5, "Amount")[["Date", "Category", "Amount", "Notes", "Gender"]]
        # Format Date column for display
        top5_display = top5.copy()
        if "Date" in top5_display.columns:
            top5_display["Date"] = top5_display["Date"].dt.strftime("%Y-%m-%d").fillna("")
        st.table(top5_display.reset_index(drop=True))

# ---- Optional raw data ----
if show_raw:
    with st.expander("Raw data (first 200 rows)"):
        df_show = dff.copy()
        if "Date" in df_show.columns:
            df_show["Date"] = df_show["Date"].dt.strftime("%Y-%m-%d").fillna("")
        st.dataframe(df_show.head(200))

# ---- Footer tips ----
st.markdown("---")
st.markdown("#### Tips")
st.markdown("- Use the **left panel** to add transactions during your session (they are stored in-memory only).")
st.markdown("- Use **Download CSV** to save filtered results and re-upload later for persistence.")
