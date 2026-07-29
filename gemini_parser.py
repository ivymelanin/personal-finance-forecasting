import os
import json
import pandas as pd
import streamlit as st

from dotenv import load_dotenv
from google import genai

load_dotenv()

api_key = (
    st.secrets["GEMINI_API_KEY"]
    if "GEMINI_API_KEY" in st.secrets
    else os.getenv("GEMINI_API_KEY")
)

client = genai.Client(api_key=api_key)