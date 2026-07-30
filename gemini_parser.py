import os
import time
import pandas as pd
import streamlit as st
from pydantic import BaseModel
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.genai.errors import ServerError, APIError

load_dotenv()

# --- PYDANTIC SCHEMAS ---
class Transaction(BaseModel):
    Date: str
    Details: str
    Amount: float
    Balance: float | None = None
    Debit_Credit: str
    Category: str

class Transactions(BaseModel):
    transactions: list[Transaction]

# --- GEMINI CLIENT INITIALIZATION ---
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

def extract_transactions(uploaded_file):
    max_retries = 3
    df = None

    for attempt in range(max_retries):
        try:
            # 1. Prepare and Upload File
            uploaded_file.seek(0)
            gemini_file = client.files.upload(
                file=uploaded_file,
                config=types.UploadFileConfig(mime_type=uploaded_file.type)
            )

            # 2. Call Gemini API
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[PROMPT, gemini_file],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=Transactions,
                ),
            )

            if response.parsed is None:
                st.error("Failed to parse document response.")
                return None

            data = response.parsed
            rows = []

            # 3. Build DataFrame Rows (Explicitly including Category)
            for t in data.transactions:
                rows.append(
                    {
                        "Date": t.Date,
                        "Details": t.Details,
                        "Amount": abs(t.Amount),
                        "Balance": t.Balance,
                        "Debit/Credit": t.Debit_Credit.title().strip(), # Standardize e.g. 'Debit'/'Credit'
                        "Category": t.Category if t.Category else "Uncategorized",
                    }
                )

            df = pd.DataFrame(rows)

            # 4. Clean Data Types safely
            df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
            df["Balance"] = pd.to_numeric(df["Balance"], errors="coerce")
            df["Date"] = pd.to_datetime(df["Date"], format="mixed", errors="coerce")

            # Drop unusable rows
            df = df.dropna(subset=["Date", "Amount"])

            # Break out of loop on success
            break

        except ServerError:
            if attempt < max_retries - 1:
                time.sleep(2 * (attempt + 1))  # Exponential backoff (2s, 4s)
                continue
            else:
                st.error("Google AI service is currently busy (503 High Demand). Please wait a moment and try uploading again.")
                return None
        except Exception as e:
            st.error(f"Error parsing document: {str(e)}")
            return None

    # Ensure Category column is guaranteed to exist
    if df is not None and not df.empty:
        if "Category" not in df.columns:
            df["Category"] = "Uncategorized"
        return df

    return None