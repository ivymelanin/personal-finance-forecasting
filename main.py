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
        # 1. Read and decode the raw text data safely
        file.seek(0)
        file_contents = file.read().decode("utf-8")
        
        f = io.StringIO(file_contents)
        reader = csv.reader(f)
        
        # Clean out completely empty rows and trailing spaces
        lines = [[cell.strip() for cell in row] for row in reader if row and any(cell.strip() for cell in row)]
        
        if not lines:
            st.error("The uploaded file is empty.")
            return None
            
        # 2. Find the true header row dynamically
        header_idx = 0
        for i, row in enumerate(lines):
            row_joined = "".join(row).lower()
            # Look for indicators of structural bank headers
            if any(k in row_joined for k in ["date", "amount", "detail", "desc", "balance"]):
                header_idx = i
                break
                
        headers = lines[header_idx]
        data_rows = lines[header_idx + 1:]
        
        # Pad headers if any row has unexpected trailing comma data
        if data_rows:
            max_cols = max(len(row) for row in data_rows)
            if max_cols > len(headers):
                headers = headers + [f"Extra_{x}" for x in range(max_cols - len(headers))]
                
        # 3. Create the initial dataframe
        df = pd.DataFrame(data_rows, columns=headers)
        
        # 4. DYNAMIC COLUMN MAPPING (The Secret Sauce)
        # This scans the actual data to determine what each column represents
        date_col, details_col, amount_col, type_col = None, None, None, None
        
        for col in df.columns:
            col_lower = str(col).lower()
            
            # Map Date Column
            if "date" in col_lower and not date_col:
                date_col = col
            # Map Amount Column
            elif any(k in col_lower for k in ["amount", "value", "rand", "sum"]) and not amount_col:
                amount_col = col
            # Map Debit/Credit column flags
            elif any(k in col_lower for k in ["type", "debit/credit", "d/c", "cr/dr"]) and not type_col:
                type_col = col
            # Map Description/Details column
            elif any(k in col_lower for k in ["detail", "desc", "narrative", "statement"]):
                details_col = col

        # Fallback Strategy: If bank has weird names, guess by column position
        if not date_col and len(df.columns) > 0: date_col = df.columns[0]
        if not details_col and len(df.columns) > 1: details_col = df.columns[1]
        if not amount_col and len(df.columns) > 2: amount_col = df.columns[2]
        if not type_col and len(df.columns) > 3: type_col = df.columns[3]

        # 5. Normalize structural values into what the rest of your script expects
        df = df.rename(columns={
            date_col: "Date",
            details_col: "Details",
            amount_col: "Amount"
        })
        
        if type_col:
            df = df.rename(columns={type_col: "Debit/Credit"})
        else:
            # If the CSV doesn't track debit/credit explicitly, assume negative numbers are Debits
            df["Amount_Float"] = df["Amount"].astype(str).str.replace(",", "").str.replace("R", "").str.strip().astype(float)
            df["Debit/Credit"] = df["Amount_Float"].apply(lambda x: "Debit" if x < 0 else "Credit")
            df["Amount"] = df["Amount_Float"].abs()

        # 6. Safe conversion of core metrics
        df["Amount"] = df["Amount"].astype(str).str.replace(",", "").str.replace("R", "").str.strip().astype(float)
        
        # Flexible date parser that naturally handles different formats (DD/MM/YYYY, DD-MMM-YYYY, etc)
        df["Date"] = pd.to_datetime(df["Date"], errors='coerce')
        df = df.dropna(subset=["Date", "Amount"]) # Remove row metadata padding errors
        
        return categorize_transactions(df)
        
    except Exception as e:
        st.error(f"Error processing file structurally: {str(e)}")
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