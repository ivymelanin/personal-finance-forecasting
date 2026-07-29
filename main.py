import streamlit as st
import pandas as pd
import plotly.express as px
import json 
import os
import csv
import io
from PIL import Image
import pdfplumber
import re
import fitz 


st.set_page_config(page_title="Finance Forecasting", page_icon="", layout="wide")

category_file = "categories.json"

if "categories" not in st.session_state:
    st.session_state.categories = {
        "Uncategorized": [], 
        "New category": []
    }
if os.path.exists("categories.json"): 
    with open(category_file, "r") as f:
        st.session_state.categories = json.load(f)

def save_categories():
    with open(category_file, "w") as f:
        json.dump(st.session_state.categories, f)
    
def categorize_transactions(df):

    df["Category"] = "Other"

    for index, row in df.iterrows():

        details = str(row["Details"]).upper()

        for category, keywords in st.session_state.categories.items():

            for keyword in keywords:

                if keyword.upper() in details:

                    df.at[index, "Category"] = category
                    break

    return df
            
def load_transactions(file):
    try:
        file.seek(0)

        lines = file.read().decode("utf-8-sig").splitlines()

        transactions = []

        start = False

        for line in lines:

            line = line.strip()

            if not line:
                continue

            # Detect transaction header
            if line.startswith("Date"):
                start = True
                continue

            if not start:
                continue

            # Split ONLY first 3 commas
            parts = line.split(",", 3)

            if len(parts) != 4:
                continue

            date = parts[0].strip()
            amount = parts[1].strip()
            balance = parts[2].strip()
            details = parts[3].strip()

            transactions.append({
                "Date": date,
                "Amount": amount,
                "Balance": balance,
                "Details": details
            })

        if len(transactions) == 0:
            st.error("No transactions found.")
            return None

        df = pd.DataFrame(transactions)

        # Clean Amount
        df["Amount"] = (
            df["Amount"]
            .str.replace("R", "", regex=False)
            .str.replace(",", "", regex=False)
            .str.strip()
        )

        df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")

        # Clean Balance
        df["Balance"] = (
            df["Balance"]
            .str.replace("R", "", regex=False)
            .str.replace(",", "", regex=False)
            .str.strip()
        )

        df["Balance"] = pd.to_numeric(df["Balance"], errors="coerce")

        # Parse dates
        df["Date"] = pd.to_datetime(
            df["Date"],
            format="%Y/%m/%d",
            errors="coerce"
        )

        df = df.dropna(subset=["Date", "Amount"])

        # Debit / Credit
        df["Debit/Credit"] = df["Amount"].apply(
            lambda x: "Debit" if x < 0 else "Credit"
        )

        df["Amount"] = df["Amount"].abs()

        # Categorize
        df = categorize_transactions(df)

        return df

    except Exception as e:
        st.error(f"Error processing file: {e}")
        return None
    
def add_keyword_to_category(category, keyword):
    keyword = keyword.strip()
    if keyword and keyword not in st.session_state.categories[category]:
        st.session_state.categories[category].append(keyword)
        save_categories()
        return True
    
    return False

def load_pdf(file):

    doc = fitz.open(stream=file.read(), filetype="pdf")

    transactions = []

    current_year = "2026"

    for page in doc:

        text = page.get_text("text")

        lines = text.split("\n")

        for line in lines:

            line = line.strip()

            # Skip blank lines
            if not line:
                continue

            # Only process transaction lines
            if not re.match(r"^\d{2}\s[A-Za-z]{3}", line):
                continue

            # Ignore summary/footer lines
            if "Closing Balance" in line:
                continue

            parts = line.split()

            # Require at least:
            # 14 Apr Amount Balance Description
            if len(parts) < 4:
                continue

            date = parts[0] + " " + parts[1]

            amount = None
            balance = None
            description = []

            for word in parts[2:]:

                clean = word.replace(",", "")

                if amount is None and re.match(r"^\d+\.\d+(Cr|Dr)?$", clean):

                    amount = clean

                elif amount is not None and balance is None and re.match(r"^\d+\.\d+(Cr|Dr)?$", clean):

                    balance = clean

                else:

                    description.append(word)

            if amount is None:
                continue

            debit_credit = "Credit"

            if "Cr" in amount:

                amount = amount.replace("Cr", "")

            elif "Dr" in amount:

                amount = amount.replace("Dr", "")

                debit_credit = "Debit"

            amount = float(amount)

            transactions.append({

                "Date": pd.to_datetime(
                    f"{date} {current_year}",
                    format="%d %b %Y"
                ),

                "Details": " ".join(description),

                "Amount": abs(amount),

                "Balance": balance,

                "Debit/Credit": debit_credit

            })

    if len(transactions) == 0:

        st.error("No transactions detected.")

        return None

    df = pd.DataFrame(transactions)

    df = categorize_transactions(df)

    return df


def main():
    st.title("Finance Dashboard")

    uploaded_file = st.file_uploader(
        "Upload your bank statement",
        type=["csv", "pdf", "png", "jpg", "jpeg"]
    )

    if uploaded_file is None:
        return

    extension = uploaded_file.name.split(".")[-1].lower()

    if extension == "csv":
        df = load_transactions(uploaded_file)

    elif extension == "pdf":
        df = load_pdf(uploaded_file)

    elif extension in ["png", "jpg", "jpeg"]:
        df = load_image(uploaded_file)

    else:
        st.error("Unsupported file type.")
        return

    if df is None:
        return

    debits_df = df[df["Debit/Credit"] == "Debit"].copy()
    credits_df = df[df["Debit/Credit"] == "Credit"].copy()

    st.session_state.debits_df = debits_df.copy()

    tab1, tab2 = st.tabs(["Expense (Debits)", "Payments (Credits)"])

    st.subheader("Your Expenses")
    edited_df = st.dataframe(
                    st.session_state.debits_df[["Date", "Details", "Amount", "Category"]],
                    column_config={
                        "Date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
                        "Amount": st.column_config.NumberColumn("Amount", format="R %.2f"),
                        "Category": st.column_config.SelectboxColumn(
                            "Category",
                            options=list(st.session_state.categories.keys())
                        )
                    },
                    hide_index=True,
                    use_container_width=True,
                    key="category_editor"

                )
                    
    st.subheader('Expense Summary')
    category_totals = st.session_state.debits_df.groupby("Category")["Amount"].sum().reset_index()
    category_totals = category_totals.sort_values("Amount", ascending=False)

    st.dataframe(
                st.session_state.debits_df[["Date", "Details", "Amount", "Category"]],
                column_config={
                "Date": st.column_config.DateColumn(
                "Date",
                format="DD/MM/YYYY",
                width="small",
                ),
                "Details": st.column_config.TextColumn(
                "Details",
                width="large",
                ),
                "Amount": st.column_config.NumberColumn(
                "Amount",
                format="R %.2f",
                width="small",
                ),
                "Category": st.column_config.TextColumn(
                "Category",
                width="medium",
                 ),
                },
            hide_index=True,
            use_container_width=True,
            )

    fig = px.pie(
                    category_totals,
                    values="Amount",
                    names="Category",
                    title="Expenses by Category"
                )
    st.plotly_chart(fig, use_container_width=True)

    with tab2: 
                st.subheader("Income Summary")
                total_payments = credits_df["Amount"].sum()
                st.metric("Total Payments", f"R {total_payments:,.2f}")
                st.write(credits_df)

main()