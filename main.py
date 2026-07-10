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
        # 1. Decode the uploaded file data into a text string
        file.seek(0)
        file_contents = file.read().decode("utf-8")
        
        # 2. Parse using Python's built-in csv reader
        f = io.StringIO(file_contents)
        reader = csv.reader(f)
        
        # Filter out completely empty rows and strip extra whitespace
        lines = [[col.strip() for col in row] for row in reader if row and any(cell.strip() for cell in row)]
        
        if not lines:
            st.error("The uploaded file is empty or contains no valid data.")
            return None
            
        # 3. Find where the actual headers start
        # If your CSV has bank description text at the top, we skip until we find "Date" or "Amount"
        header_idx = 0
        for i, row in enumerate(lines):
            row_joined = "".join(row).lower()
            if "date" in row_joined or "amount" in row_joined:
                header_idx = i
                break
        
        headers = lines[header_idx]
        data_rows = lines[header_idx + 1:]
        
        # 4. Rebuild the DataFrame safely using matched columns
        df = pd.DataFrame(data_rows, columns=headers)
        
        # 5. Standardize Data Types
        df["Amount"] = df["Amount"].astype(str).str.replace(",", "").astype(float)
        df["Date"] = pd.to_datetime(df["Date"], format="%d %b %Y")
        
        return categorize_transactions(df)
        
    except Exception as e:
        st.error(f"Error processing file: {str(e)}")
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