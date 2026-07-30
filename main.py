import os
import pandas as pd
import streamlit as st
import plotly.express as px
from gemini_parser import extract_transactions

st.set_page_config(page_title="Finance Dashboard", page_icon="💰", layout="wide")

def main():
    st.title("Finance Dashboard")

    uploaded_file = st.file_uploader(
        "Upload your bank statement",
        type=["csv", "pdf", "png", "jpg", "jpeg"]
    )

    if uploaded_file is None:
        return

    extension = uploaded_file.name.split(".")[-1].lower()

    if extension in ["csv", "pdf", "png", "jpg", "jpeg"]:
        with st.spinner("Hang on tight, we're extracting your transactions..."):
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

    all_categories = [
        "Groceries", "Transport", "Fuel", "Restaurants", "Takeaways", "Coffee", 
        "Shopping", "Entertainment", "Subscriptions", "Salary", "Interest", 
        "Transfer", "ATM Withdrawal", "Cash Deposit", "Utilities", "Rent", 
        "Insurance", "Medical", "Education", "Travel", "Investments", "Savings", 
        "Bank Charges", "Mobile & Internet", "Government", "Taxes", "Loan Payment", "Other"
    ]

    # TAB 1: EXPENSES
    with tab1:
        st.subheader("Your Expenses")
        if not debits_df.empty:
            display_df = debits_df[["Date", "Details", "Amount", "Category"]].copy()

            edited_df = st.dataframe(
                display_df,
                column_config={
                    "Date": st.column_config.DateColumn("Date", format="DD/MM/YYYY", width="small"),
                    "Details": st.column_config.TextColumn("Details", width="large"),
                    "Amount": st.column_config.NumberColumn("Amount", format="R %.2f", width="medium"),
                    "Category": st.column_config.SelectboxColumn(
                        "Category",
                        options=all_categories,
                        width="medium"
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
                    "Date": st.column_config.DateColumn("Date", format="DD/MM/YYYY", width="small"),
                    "Details": st.column_config.TextColumn("Details", width="large"),
                    "Amount": st.column_config.NumberColumn("Amount", format="R %.2f", width="medium"),
                    "Category": st.column_config.TextColumn("Category", width="medium")
                },
                hide_index=True,
                use_container_width=True
            )
        else:
            st.info("No credit (income) transactions found.")


if __name__ == "__main__":
    main()