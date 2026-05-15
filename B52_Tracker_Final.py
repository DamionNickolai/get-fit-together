# --- 1. APP CONFIGURATION & IMPORTS ---
import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import datetime
from garminconnect import Garmin

st.set_page_config(
    page_title="Home Gym Tracker", 
    layout="wide", 
    initial_sidebar_state="expanded"
)

# --- 2. PASSWORD PROTECTION SYSTEM ---
def check_password():
    def password_entered():
        if st.session_state["password"] == st.secrets["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
        else:
            st.session_state["password_correct"] = False
            
    if "password_correct" not in st.session_state:
        st.text_input("Enter Password", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Enter Password", type="password", on_change=password_entered, key="password")
        st.error("😕 Password incorrect")
        return False
    return True

if check_password():
    # --- 3. MULTI-USER & COLOR THEMING ---
    user = st.radio("Who is training today?", ["Jason", "Angelle"], horizontal=True)
    page_bg_color = "#1E3A8A" if user == "Jason" else "#0D9488"
    side_bg = "#162A61" if user == "Jason" else "#0A6E65"

    st.markdown(f"""
        <style>
        .stApp {{ background-color: {page_bg_color}; color: white; }}
        [data-testid="stSidebar"] {{ background-color: {side_bg} !important; opacity: 1 !important; }}
        .stTabs [data-baseweb="tab"] {{ color: white !important; }}
        </style>
        """, unsafe_allow_html=True)
    
    st.title(f"💪 Get Fit Together: {user}'s Session")

    # --- 4. CONNECT TO GOOGLE SHEETS ---
    conn = st.connection("gsheets", type=GSheetsConnection)

    try:
        log_df = conn.read(ttl=600)
        if not log_df.empty:
            log_df['Date'] = log_df['Date'].astype(str)
    except:
        log_df = pd.DataFrame(columns=["User", "Date", "Activity", "Body Weight", "Details"])

    if "current_workout_list" not in st.session_state:
        st.session_state["current_workout_list"] = []

    # --- 4.5 GARMIN INTEGRATION ---
    @st.cache_data(ttl=3600, show_spinner=False)
    def get_garmin_metrics(user_email, user_pass):
        try:
            client = Garmin(user_email, user_pass)
            client.login()
            today = datetime.date.today().isoformat()
            stats = client.get_stats(today)
            
            steps = stats.get('totalSteps', 0)
            rhr = stats.get('restingHeartRate', '--')
            bb_max = stats.get('maxBodyBattery', '--')
            
            return {"Steps": steps, "RHR": rhr, "Body Battery": bb_max}
        except Exception as e:
            return {"Steps": "Sync Error", "RHR": "--", "Body Battery": "--"}

    if user == "Jason":
        g_email = st.secrets["garmin"]["jason_email"]
        g_pass = st.secrets["garmin"]["jason_pass"]
    else:
        g_email = st.secrets["garmin"]["angelle_email"]
        g_pass = st.secrets["garmin"]["angelle_pass"]

    daily_metrics = get_garmin_metrics(g_email, g_pass)
    
    # --- 5. LOGGING SIDEBAR ---
    st.sidebar.header(f"Log Details for {user}")
    date = st.sidebar.date_input("Date", datetime.date.today())
    activity = st.sidebar.selectbox("Session Type", ["Full Body Circuit", "Cardio", "Yoga/Mobility", "Body Weight"])

    weight = 0.0 
    all_details = ""
    save_triggered = False

    if activity == "Body Weight":
        weight = st.sidebar.number_input("Current Weight (lbs)", min_value=0.0, step=0.1)
        if st.sidebar.button("Log Weight Only", use_container_width=True):
            all_details = f"Weight Entry: {weight} lbs"
            save_triggered = True

    elif activity == "Full Body Circuit":
        st.sidebar.subheader("Add Exercises")
        ex = st.sidebar.selectbox("Choose Exercise", ["Smith Machine Squats", "Cable Lat Pulldowns", "Smith Machine Bench Press", "Cable Rows", "Cable Woodchoppers", "Smith Machine R
