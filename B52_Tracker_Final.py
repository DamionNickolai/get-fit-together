import streamlit as st
import pandas as pd
import datetime
import os

# --- PASSWORD PROTECTION ---
def check_password():
    """Returns True if the user had the correct password."""
    def password_entered():
        if st.session_state["password"] == st.secrets["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # don't store password
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("Enter Password", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Enter Password", type="password", on_change=password_entered, key="password")
        st.error("😕 Password incorrect")
        return False
    else:
        return True

if check_password():
    # --- YOUR ACTUAL APP LOGIC STARTS HERE ---
    st.set_page_config(page_title="Gibson Home Gym Tracker", layout="wide")
    
    user = st.radio("Who is training today?", ["Jason", "Angelle"], horizontal=True)
    
    # Custom CSS for Color Coding
    page_bg_color = "#1E3A8A" if user == "Jason" else "#0D9488"
    st.markdown(f"<style>.stApp {{background-color: {page_bg_color}; color: white;}}</style>", unsafe_allow_html=True)
    
    st.title(f"💪 Gibson Home Gym: {user}'s Session")
    
    # ... [Rest of your existing logging and dashboard code] ...
    st.write("Welcome back! Your recovery and B-52 stats are secured.")
