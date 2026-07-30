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
The uploaded document is a bank statement.
Extract EVERY transaction.

For every transaction determine:
- Date: Format as YYYY-MM-DD. If year is not printed on statement, assume current year or extract from header.
- Details: Description / Merchant name / Transaction info
- Amount: Positive numerical value
- Balance: Balance after transaction (if available)
- Debit_Credit: 'Debit' (for expenses/withdrawals/fees) or 'Credit' (for deposits/income/transfers in)
- Category: Mandatory field. YOU MUST CLASSIFY EVERY SINGLE TRANSACTION.

Choose ONE category from this exact list:
Groceries, Transport, Fuel, Restaurants, Takeaways, Coffee, Shopping, Entertainment, 
Subscriptions, Salary, Interest, Transfer, ATM Withdrawal, Cash Deposit, Utilities, 
Rent, Insurance, Medical, Education, Travel, Investments, Savings, Bank Charges, 
Mobile & Internet, Government, Taxes, Loan Payment, Other

Rule Examples:
- Shein, POS Purchase -> Shopping
- Shoprite, Pick n Pay, Checkers -> Groceries
- Int Pymt Fee, Eft Charge, Service Fees, Activity Based Pmnt -> Bank Charges
- FNB App Payment -> Transfer

Return ONLY valid JSON matching the schema. Do not leave Category empty.
"""

def extract_transactions(uploaded_file):
    max_retries = 3

    for attempt in range(max_retries):
        try:
            uploaded_file.seek(0)
            gemini_file = client.files.upload(
                file=uploaded_file,
                config=types.UploadFileConfig(mime_type=uploaded_file.type)
            )

            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=[PROMPT, gemini_file],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=Transactions,
                ),
            )

            if response.parsed is None:
                st.error("Failed to extract data from document.")
                return None

            data = response.parsed
            rows = []

            for t in data.transactions:
                rows.append({
                    "Date": t.Date,
                    "Details": t.Details,
                    "Amount": abs(t.Amount),
                    "Balance": t.Balance,
                    "Debit/Credit": t.Debit_Credit.title().strip(),
                    "Category": t.Category if t.Category and t.Category.strip() else "Other",
                })

            df = pd.DataFrame(rows)

            # Fix Numeric Conversion
            df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")
            df["Balance"] = pd.to_numeric(df["Balance"], errors="coerce")

            # Fix Date Parsing (handles year 0001 bugs)
            df["Date"] = pd.to_datetime(df["Date"], format="mixed", errors="coerce")
            current_year = pd.Timestamp.now().year
            df["Date"] = df["Date"].apply(
                lambda d: d.replace(year=current_year) if pd.notnull(d) and d.year < 2000 else d
            )

            df = df.dropna(subset=["Date", "Amount"])
            return df

        except ServerError:
            if attempt < max_retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            else:
                st.error("Google AI service is currently busy. Please retry in a moment.")
                return None
        except Exception as e:
            st.error(f"Error parsing document: {str(e)}")
            return None

    return None