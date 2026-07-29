import os
import json
import pandas as pd
import streamlit as st
from pydantic import BaseModel
from dotenv import load_dotenv
from google import genai

load_dotenv()

class Transaction(BaseModel):
    Date: str
    Details: str
    Amount: float
    Balance: float | None = None
    Debit_Credit: str


class Transactions(BaseModel):
    transactions: list[Transaction]

# Read API key from Streamlit Cloud or .env
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"]
else:
    api_key = os.getenv("GEMINI_API_KEY")

client = genai.Client(api_key=api_key)


PROMPT = """
You are an expert financial document parser.

The uploaded file is a bank statement.

It may be:
- PDF
- Image
- Scan
- Screenshot

It may come from ANY bank.

Extract EVERY transaction.

Ignore:
- Headers
- Footers
- Logos
- Addresses
- Running totals
- Opening balances
- Closing balances

Return every transaction exactly as it appears.

Determine whether each transaction is Debit or Credit.

Convert dates to YYYY-MM-DD whenever possible.
"""

def extract_transactions(uploaded_file):

    uploaded_file.seek(0)

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=[
            PROMPT,
            {
                "mime_type": uploaded_file.type,
                "data": uploaded_file.read(),
            },
        ],
        config={
            "response_mime_type": "application/json",
            "response_schema": Transactions,
        },
    )

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

    df["Amount"] = pd.to_numeric(df["Amount"], errors="coerce")

    df["Balance"] = pd.to_numeric(df["Balance"], errors="coerce")

    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    df = df.dropna(subset=["Date", "Amount"])

    return pd.DataFrame(rows)