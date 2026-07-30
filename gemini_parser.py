import os
import json
import pandas as pd
import streamlit as st
from pydantic import BaseModel
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import ServerError, APIError
import time
from main import categorize_transactions

load_dotenv()

class Transaction(BaseModel):
    Date: str
    Details: str
    Amount: float
    Balance: float | None = None
    Debit_Credit: str
    Category: str


class Transactions(BaseModel):
    transactions: list[Transaction]

# Read API key from Streamlit Cloud or .env
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]
else:
    api_key = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=api_key)


PROMPT = """
You are an expert financial analyst.

The uploaded document is a bank statement from any bank.

Extract EVERY transaction.

For every transaction determine:

- Date
- Description
- Amount
- Balance (if available)
- Debit or Credit
- Spending Category

Choose ONE category only.

Use categories such as:

Groceries
Transport
Fuel
Restaurants
Takeaways
Coffee
Shopping
Entertainment
Subscriptions
Salary
Interest
Transfer
ATM Withdrawal
Cash Deposit
Utilities
Rent
Insurance
Medical
Education
Travel
Investments
Savings
Bank Charges
Mobile & Internet
Government
Taxes
Loan Payment
Other

Examples:

Checkers → Groceries
Shoprite → Groceries
Pick n Pay → Groceries
Woolworths Food → Groceries

Uber → Transport
Bolt → Transport
Engen → Fuel
Shell → Fuel

Netflix → Subscriptions
Spotify → Subscriptions
YouTube Premium → Subscriptions

McDonald's → Restaurants
KFC → Restaurants
Nando's → Restaurants

Clicks Pharmacy → Medical
Dis-Chem → Medical

Capitec Fee → Bank Charges
Monthly Account Fee → Bank Charges

If unsure, choose the closest category.

Return ONLY valid JSON.
"""

def extract_transactions(file):
    max_retries = 3
    df=None
    for attempt in range(max_retries):
        try:
            # Your existing Gemini API call here:
            # response = client.models.generate_content(...)
            
            # Convert response to DataFrame
            # df = ... 
            
            # CRITICAL: Always attach Category before returning
            if df is not None and not df.empty:
                if "Category" not in df.columns:
                    df["Category"] = "Uncategorized"
                return categorize_transactions(df)
            return None

        except ServerError as e:
            if attempt < max_retries - 1:
                time.sleep(2 * (attempt + 1))  # Wait 2, 4 seconds before retrying
                continue
            else:
                st.error("Google AI service is currently busy (503 High Demand). Please wait a moment and try uploading again.")
                return None
        except Exception as e:
            st.error(f"Error parsing document: {str(e)}")
            return None

    # Check if df was successfully populated
    if df is not None and not df.empty:
        if "Category" not in df.columns:
            df["Category"] = "Uncategorized"
    return categorize_transactions(df)

def extract_transactions(uploaded_file):

    uploaded_file.seek(0)

    gemini_file = client.files.upload(
    file=uploaded_file,
    config=types.UploadFileConfig(
        mime_type=uploaded_file.type
    )
)

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            PROMPT,
            gemini_file,
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=Transactions,
        ),
)

    if response.parsed is None:
        st.error(response.text)
        return None

    data = response.parsed

    rows = []

    for t in data.transactions:

        rows.append(
            {
                "Date": t.Date,
                "Details": t.Details,
                "Amount": abs(t.Amount),
                "Balance": t.Balance,
                "Debit/Credit": t.Debit_Credit,
            }
        )
    df = pd.DataFrame(rows)
    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")

    df["Balance"] = pd.to_numeric(df["Balance"], errors="coerce")

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    df = df.dropna(subset=["Date", "Amount"])

    return df