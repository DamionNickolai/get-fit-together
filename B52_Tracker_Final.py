import streamlit as st
import pandas as pd
import datetime
import os

# App Config
st.set_page_config(page_title="Gibson Home Gym Tracker", layout="wide")

# 1. User Selection & Dynamic Color Coding
user = st.radio("Who is training today?", ["Jason", "Angelle"], horizontal=True)

# Custom CSS for Color Coding
if user == "Jason":
    # A deep "Power" Blue for Jason's profile
    page_bg_color = "#1E3A8A" 
else:
    # A vibrant "Energy" Teal for Angelle's profile
    page_bg_color = "#0D9488"

st.markdown(f"""
    <style>
    .stApp {{
        background-color: {page_bg_color};
        color: white;
    }}
    /* Make sidebar text readable */
    [data-testid="stSidebar"] {{
        background-color: rgba(255, 255, 255, 0.1);
    }}
    </style>
    """, unsafe_allow_html=True)

st.title(f"💪 Gibson Home Gym: {user}'s Session")

# --- Rest of the App Logic (Database and Logging) ---
FILE_NAME = "family_workout_log.csv"
if not os.path.exists(FILE_NAME):
    df = pd.DataFrame(columns=["User", "Date", "Activity", "Body Weight", "Details", "Mobility Done"])
    df.to_csv(FILE_NAME, index=False)

# 2. Logging Sidebar
st.sidebar.header(f"Log for {user}")
date = st.sidebar.date_input("Date", datetime.date.today())
activity = st.sidebar.selectbox("Session Type", ["B-52 Full Body", "LISS Cardio", "Yoga/Mobility", "Rest"])
weight = st.sidebar.number_input("Body Weight (lbs)", min_value=0.0, step=0.1)

# Dynamic Inputs
details = ""
if activity == "B-52 Full Body":
    ex = st.sidebar.text_input("Top Exercise Performed", "Smith Machine Squats")
    lbs = st.sidebar.number_input("Max Weight (lbs)", 0)
    details = f"{ex}: {lbs} lbs"
elif activity == "LISS Cardio":
    mins = st.sidebar.number_input("Duration (mins)", 0)
    details = f"{mins} min walk"

# 3. 40+ Recovery Checklist
st.sidebar.subheader("Post-Workout Mobility")
m1 = st.sidebar.checkbox("Chest & Lat Stretch (30s)")
m2 = st.sidebar.checkbox("Hip Flexor Stretch (30s)")
m3 = st.sidebar.checkbox("Hamstring/Glute Stretch (30s)")
mobility_status = "Complete" if (m1 and m2 and m3) else "Partial/None"

if st.sidebar.button("Log Workout"):
    new_entry = pd.DataFrame([[user, date, activity, weight, details, mobility_status]], 
                             columns=["User", "Date", "Activity", "Body Weight", "Details", "Mobility Done"])
    new_entry.to_csv(FILE_NAME, mode='a', header=False, index=False)
    st.sidebar.success(f"Great work, {user}!")

# 4. Dashboard Tabs
tab1, tab2, tab3 = st.tabs(["📈 Progress", "📅 History", "🧘 Recovery Guide"])

with tab1:
    log_df = pd.read_csv(FILE_NAME)
    user_df = log_df[log_df["User"] == user]
    if not user_df.empty:
        st.subheader(f"{user}'s Weight Journey")
        st.line_chart(user_df.set_index("Date")["Body Weight"])

with tab2:
    st.subheader("Family Training Log")
    st.dataframe(pd.read_csv(FILE_NAME).sort_values(by="Date", ascending=False), use_container_width=True)

with tab3:
    st.subheader("Recommended Post-B-52 Cooldown")
    st.write("**1. Doorway Chest Stretch** | **2. Lat Stretch** | **3. Kneeling Hip Flexor** | **4. Child's Pose**")