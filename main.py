import os
import json
import csv
import io
import pandas as pd
import streamlit as st
import plotly.express as px
from gemini_parser import extract_transactions

st.set_page_config(page_title="Finance Dashboard", page_icon="💰", layout="wide")

def load_transactions(file):
    try:
        file.seek(0)
        file_contents = file.read().decode("utf-8-sig")
        f = io.StringIO(file_contents)
        reader = csv.reader(f)
        
        lines = [[cell.strip() for cell in row] for row in reader if row and any(cell.strip() for cell in row)]
        
        if not lines:
            st.error("Uploaded CSV file is empty.")
            return None

        # Detect Header Row
        header_idx = 0
        for i, row in enumerate(lines):
            row_str = "".join(row).lower()
            if any(k in row_str for k in ["date", "amount", "detail", "desc"]):
                header_idx = i
                break

        headers = lines[header_idx]
        data_rows = lines[header_idx + 1:]

        if data_rows:
            max_cols = max(len(r) for r in data_rows)
            if max_cols > len(headers):
                headers += [f"Extra_{x}" for x in range(max_cols - len(headers))]

        df = pd.DataFrame(data_rows, columns=headers)

        # Dynamic Column Mapping
        date_col, details_col, amount_col, type_col = None, None, None, None
        for col in df.columns:
            c_low = str(col).lower()
            if "date" in c_low and not date_col:
                date_col = col
            elif any(k in c_low for k in ["amount", "value", "sum", "rand"]) and not amount_col:
                amount_col = col
            elif any(k in c_low for k in ["type", "debit/credit", "d/c", "cr/dr"]) and not type_col:
                type_col = col
            elif any(k in c_low for k in ["detail", "desc", "narrative", "statement", "transaction"]):
                details_col = col

        if not date_col and len(df.columns) > 0: date_col = df.columns[0]
        if not details_col and len(df.columns) > 1: details_col = df.columns[1]
        if not amount_col and len(df.columns) > 2: amount_col = df.columns[2]

        df = df.rename(columns={
            date_col: "Date",
            details_col: "Details",
            amount_col: "Amount"
        })

        if type_col:
            df = df.rename(columns={type_col: "Debit/Credit"})
            df["Debit/Credit"] = df["Debit/Credit"].astype(str).str.title()
        else:
            df["Amount_Clean"] = pd.to_numeric(
                df["Amount"].astype(str).str.replace("R", "", regex=False).str.replace(",", "", regex=False).str.strip(),
                errors="coerce"
            )
            df["Debit/Credit"] = df["Amount_Clean"].apply(lambda x: "Debit" if (pd.notnull(x) and x < 0) else "Credit")

        df["Amount"] = pd.to_numeric(
            df["Amount"].astype(str).str.replace("R", "", regex=False).str.replace(",", "", regex=False).str.strip(),
            errors="coerce"
        )
        df["Amount"] = df["Amount"].abs()

        df["Date"] = pd.to_datetime(df["Date"], format="mixed", errors="coerce")
        df = df.dropna(subset=["Date", "Amount"])
        df["Category"] = "Other"

        return df

    except Exception as e:
        st.error(f"Error processing CSV file: {e}")
        return None


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
    elif extension in ["pdf", "png", "jpg", "jpeg"]:
        df = extract_transactions(uploaded_file)
    else:
        st.error("Unsupported file type.")
        return

    if df is None or df.empty:
        st.warning("No valid transaction data could be retrieved from the file.")
        return

    # Ensure required columns exist
    required_cols = ["Date", "Details", "Amount", "Debit/Credit", "Category"]
    for col in required_cols:
        if col not in df.columns:
            df[col] = "Other" if col == "Category" else ""

    debits_df = df[df["Debit/Credit"] == "Debit"].copy()
    credits_df = df[df["Debit/Credit"] == "Credit"].copy()

    tab1, tab2 = st.tabs(["Expense (Debits)", "Payments (Credits)"])

    # TAB 1: EXPENSES
    with tab1:
        st.subheader("Your Expenses")
        if not debits_df.empty:
            display_df = debits_df[["Date", "Details", "Amount", "Category"]].copy()

            all_categories = [
                "Groceries", "Transport", "Fuel", "Restaurants", "Takeaways", "Coffee", 
                "Shopping", "Entertainment", "Subscriptions", "Salary", "Interest", 
                "Transfer", "ATM Withdrawal", "Cash Deposit", "Utilities", "Rent", 
                "Insurance", "Medical", "Education", "Travel", "Investments", "Savings", 
                "Bank Charges", "Mobile & Internet", "Government", "Taxes", "Loan Payment", "Other"
            ]

            edited_df = st.dataframe(
                display_df,
                column_config={
                    "Date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
                    "Details": st.column_config.TextColumn("Details"),
                    "Amount": st.column_config.NumberColumn("Amount", format="R %.2f"),
                    "Category": st.column_config.SelectboxColumn(
                        "Category",
                        options=all_categories
                    )
                },
                hide_index=True,
                use_container_width=True,
                key="expense_editor"
            )

            st.subheader('Expense Summary')
            category_totals = display_df.groupby("Category")["Amount"].sum().reset_index()
            category_totals = category_totals.sort_values("Amount", ascending=False)

            fig = px.pie(
                category_totals,
                values="Amount",
                names="Category",
                title="Expenses by Category"
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No expense (debit) transactions found.")

    # TAB 2: PAYMENTS / CREDITS
    with tab2:
        st.subheader("Income Summary")
        if not credits_df.empty:
            total_payments = credits_df["Amount"].sum()
            st.metric("Total Payments", f"R {total_payments:,.2f}")
            st.dataframe(
                credits_df[["Date", "Details", "Amount", "Category"]],
                column_config={
                    "Date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
                    "Amount": st.column_config.NumberColumn("Amount", format="R %.2f")
                },
                hide_index=True,
                use_container_width=True
            )
        else:
            st.info("No credit (income) transactions found.")


if __name__ == "__main__":
    main()