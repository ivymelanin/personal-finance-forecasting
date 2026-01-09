import streamlit as st
import pandas as pd
import plotly.express as px
import json 
import os

st.set_page_config(page_title="Finance Forecasting", page_icon="", layout="wide")

def load_transactions(file):
    pass
def main():
    st.title("Finance Dashboard")

    uploaded_file = st.file_uploader("upload your transaction CSV file", type=["csv"])

    if uploaded_file is not None:
        df = load_transactions(uploaded_file)

main()