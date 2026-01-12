# personal-finance-forecasting

# 💰 Finance Forecasting Dashboard

A **Streamlit-based personal finance dashboard** that allows users to upload bank transaction CSV files, automatically categorize transactions, edit categories, and visualize expenses and income summaries.

---

## 🚀 Features

- Upload transaction CSV files
- Automatic transaction categorization using saved keywords
- Create and manage custom spending categories
- Editable transaction table with category selection
- Persistent category storage using `categories.json`
- Expense summary table
- Interactive pie chart of expenses by category
-  (credits) summary

---

## 🛠️ Tech Stack

- **Python**
- **Streamlit** – Web dashboard framework
- **Pandas** – Data processing
- **Plotly Express** – Interactive charts
- **JSON** – Category storage

---

## 📂 Project Structure

.
├── main.py # Streamlit application
├── categories.json # Saved category keywords (auto-generated)
├── README.md # Project documentation
└── requirements.txt # Python dependencies

## 📑 CSV File Format Requirements

Your uploaded CSV must contain the following columns:

- `Date` (format: `DD Mon YYYY`, e.g., `25 Jan 2026`)
- `Details` (transaction description)
- `Amount` (numeric, commas allowed)
- `Debit/Credit` (values: `Debit` or `Credit`)


## ⚙️ Installation

1. Clone the repository
2. pip install -r requirements.txt
3. streamlit run main.py

