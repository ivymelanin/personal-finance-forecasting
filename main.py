import streamlit as st
import pandas as pd
import plotly.express as px
import json 
import os
import csv
import io

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
    df["Category"] = "Uncategorized" 

    for category, keywords in st.session_state.categories.items():
        if category == "Uncategorized" or not keywords:
            continue
        
        lowered_keywords = [keyword.lower().strip() for keyword in keywords ]

        for idx, row in df.iterrows():
            details = row["Details"].lower().strip()
            if details in lowered_keywords:
               df.at[idx, "Category"] = category 

    return df
            
def load_transactions(file):
    try:
        file.seek(0)

        # Read CSV while allowing inconsistent rows
        df = pd.read_csv(
            file,
            skip_blank_lines=True,
            engine="python",
            on_bad_lines="skip"
        )

        # Find the actual transaction header
        if "Date" not in df.columns:
            file.seek(0)

            lines = file.read().decode("utf-8-sig").splitlines()

            header_line = None

            for i, line in enumerate(lines):
                cols = [c.strip().lower() for c in line.split(",")]

                if (
                    "date" in cols
                    and "amount" in cols
                    and "balance" in cols
                    and (
                        "description" in cols
                        or "details" in cols
                    )
                ):
                    header_line = i
                    break

            if header_line is None:
                st.error("Could not locate transaction table.")
                return None

            file.seek(0)

            df = pd.read_csv(
                file,
                skiprows=header_line,
                engine="python"
            )

        # Rename columns
        rename_map = {}

        for col in df.columns:

            lower = col.lower()

            if lower == "date":
                rename_map[col] = "Date"

            elif lower == "amount":
                rename_map[col] = "Amount"

            elif lower == "balance":
                rename_map[col] = "Balance"

            elif lower in ["description", "details"]:
                rename_map[col] = "Details"

        df = df.rename(columns=rename_map)

        required = ["Date", "Amount", "Details"]

        for col in required:
            if col not in df.columns:
                st.error(f"Missing required column: {col}")
                return None

        # Clean amount
        df["Amount"] = (
            df["Amount"]
            .astype(str)
            .str.replace("R", "", regex=False)
            .str.replace(",", "", regex=False)
            .str.strip()
        )

        df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")

        # Clean balance if available
        if "Balance" in df.columns:

            df["Balance"] = (
                df["Balance"]
                .astype(str)
                .str.replace("R", "", regex=False)
                .str.replace(",", "", regex=False)
                .str.strip()
            )

            df["Balance"] = pd.to_numeric(df["Balance"], errors="coerce")

        # Parse dates
        df["Date"] = pd.to_datetime(
            df["Date"],
            errors="coerce"
        )

        df = df.dropna(subset=["Date", "Amount"])

        # Debit / Credit
        df["Debit/Credit"] = df["Amount"].apply(
            lambda x: "Debit" if x < 0 else "Credit"
        )

        df["Amount"] = df["Amount"].abs()

        # Remove duplicate transactions
        df = df.drop_duplicates()

        # Categorize
        df = categorize_transactions(df)

        return df

    except Exception as e:
        st.error(f"Error processing file: {e}")
        return None

        headers = lines[header_idx]
        data = lines[header_idx + 1:]

        fixed_rows = []

        for row in data:
            if len(row) > len(headers):
        # Merge any extra columns into the Description column
                row = row[:3] + [",".join(row[3:])]
            elif len(row) < len(headers):
                row += [""] * (len(headers) - len(row))

            fixed_rows.append(row)

        df = pd.DataFrame(fixed_rows, columns=headers)

        df = df.rename(columns={
            "Date": "Date",
            "Amount": "Amount",
            "Description": "Details",
        })

        df["Amount"] = (
            df["Amount"]
            .astype(str)
            .str.replace(",", "", regex=False)
            .str.replace("R", "", regex=False)
            .str.strip()
        )

        df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
        df = df.dropna(subset=["Amount"])

        df["Debit/Credit"] = df["Amount"].apply(
            lambda x: "Debit" if x < 0 else "Credit"
        )
        df["Amount"] = df["Amount"].abs()

        df["Date"] = pd.to_datetime(
            df["Date"],
            format="%Y/%m/%d",
            errors="coerce"
        )
        df = df.dropna(subset=["Date"])

        return categorize_transactions(df)

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
def main():
    st.title("Finance Dashboard")

    uploaded_file = st.file_uploader("upload your transaction CSV file", type=["csv"])

    if uploaded_file is not None:
        df = load_transactions(uploaded_file)
        if df is not None:
            debits_df = df[df["Debit/Credit"] == "Debit"].copy()
            credits_df = df[df["Debit/Credit"] == "Credit"].copy()

            st.session_state.debits_df = debits_df.copy()

            tab1, tab2 = st.tabs(["Expense (Debits)", "Payments (Credits)"])
            with tab1:
                new_category = st.text_input("New Category Name")
                add_button = st.button("Add category")

                if add_button and new_category:
                    if new_category not in st.session_state.categories:
                        st.session_state.categories[new_category] = []
                        save_categories()
                        st.success(f"Added a new category:{new_category}")
                        st.rerun()

                st.subheader("Your Expenses")
                edited_df = st.data_editor(
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

                save_button = st.button("Apply Changes", type="primary")
                if save_button:
                    for idx, row in edited_df.iterrows():
                        new_category = row["Category"]
                        if new_category == st.session_state.debits_df.at[idx, "Category"]:
                            continue

                        details = row["Details"]
                        st.session_state.debits_df.at[idx, "Category"] = new_category
                        add_keyword_to_category(new_category, details)

                    
                st.subheader('Expense Summary')
                category_totals = st.session_state.debits_df.groupby("Category")["Amount"].sum().reset_index()
                category_totals = category_totals.sort_values("Amount", ascending=False)

                st.dataframe(
                    category_totals,
                    column_config={
                        "Amount": st.column_config.NumberColumn("Amount", format="R %.2f")
                    },
                    use_container_width=True,
                    hide_index=True
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