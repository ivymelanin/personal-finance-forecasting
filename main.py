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
    categories = st.session_state.categories

    df["Category"] = "Other"

    for index, row in df.iterrows():

        details = str(row["Details"]).upper()

        for category, keywords in categories.items():

            if any(keyword.upper() in details for keyword in keywords):

                df.at[index, "Category"] = category
                break

    return df
            
ef load_transactions(file):
    try:
        import csv
        import io

        file.seek(0)
        content = file.read().decode("utf-8-sig")

        reader = csv.reader(io.StringIO(content))

        rows = []

        for row in reader:
            row = [cell.strip() for cell in row]

            if not any(row):
                continue

            rows.append(row)

        # Find the transaction table header
        header_index = None

        for i, row in enumerate(rows):

            lower = [x.lower() for x in row]

            if (
                len(lower) >= 4
                and lower[0] == "date"
                and "amount" in lower
                and "balance" in lower
                and "description" in lower
            ):
                header_index = i
                break

        if header_index is None:
            st.error("Could not locate transaction table.")
            return None

        transactions = []

        for row in rows[header_index + 1:]:

            # Ignore incomplete rows
            if len(row) < 4:
                continue

            # Merge extra columns into Description
            if len(row) > 4:
                row = row[:3] + [",".join(row[3:])]

            transactions.append({
                "Date": row[0],
                "Amount": row[1],
                "Balance": row[2],
                "Details": row[3]
            })

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

        # Dates
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