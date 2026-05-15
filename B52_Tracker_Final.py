import streamlit as st
import pandas as pd
import datetime
import os

# --- 1. PASSWORD PROTECTION SYSTEM ---
def check_password():
    """Returns True if the user entered the correct password."""
    def password_entered():
        if st.session_state["password"] == st.secrets["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Clear password from memory
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

# Only run the app if the password checks out
if check_password():

    # --- 2. APP CONFIGURATION ---
    st.set_page_config(page_title="Gibson Home Gym Tracker", layout="wide")

    # --- 3. MULTI-USER & COLOR THEMING ---
    user = st.radio("Who is training today?", ["Jason", "Angelle"], horizontal=True)

    # Dynamic Background Color Shift
    page_bg_color = "#1E3A8A" if user == "Jason" else "#0D9488"
    st.markdown(f"""
        <style>
        .stApp {{
            background-color: {page_bg_color};
            color: white;
        }}
        [data-testid="stSidebar"] {{
            background-color: rgba(255, 255, 255, 0.1);
        }}
        .stTabs [data-baseweb="tab"] {{
            color: white !important;
        }}
        </style>
        """, unsafe_allow_html=True)

    st.title(f"💪 Gibson Home Gym: {user}'s Session")

    # --- 4. DATABASE INITIALIZATION ---
    FILE_NAME = "family_workout_log.csv"
    if not os.path.exists(FILE_NAME):
        df = pd.DataFrame(columns=["User", "Date", "Activity", "Body Weight", "Details"])
        df.to_csv(FILE_NAME, index=False)

    # Initialize a temporary session state memory bucket for the active workout
    if "current_workout_list" not in st.session_state:
        st.session_state["current_workout_list"] = []

    # --- 5. LOGGING SIDEBAR ---
    st.sidebar.header(f"Log Details for {user}")
    date = st.sidebar.date_input("Date", datetime.date.today())
    activity = st.sidebar.selectbox("Session Type", ["B-52 Full Body", "LISS Cardio", "Yoga/Mobility", "Rest"])
    weight = st.sidebar.number_input("Body Weight (lbs)", min_value=0.0, step=0.1)

    # Dynamic Input Elements Based on Session Type
    if activity == "B-52 Full Body":
        st.sidebar.subheader("Add Exercises to Session")
        ex = st.sidebar.selectbox("Choose Exercise", [
            "Smith Machine Squats", "Cable Lat Pulldowns", 
            "Smith Machine Bench Press", "Cable Rows", 
            "Cable Woodchoppers", "Smith Machine RDLs"
        ])
        lbs = st.sidebar.number_input("Max Weight (lbs)", min_value=0, step=5)
        reps = st.sidebar.number_input("Reps", min_value=0, step=1)
        
        # Button to append this specific lift to the temporary round table list
        if st.sidebar.button("➕ Add Exercise to List"):
            st.session_state["current_workout_list"].append(f"{ex} ({lbs} lbs x {reps})")
            st.sidebar.toast(f"Added {ex}!")

        # Display current active items waiting to be recorded
        if st.session_state["current_workout_list"]:
            st.sidebar.write("**Current Session Stack:**")
            for item in st.session_state["current_workout_list"]:
                st.sidebar.caption(f"• {item}")
            
            if st.sidebar.button("🗑️ Clear List"):
                st.session_state["current_workout_list"] = []
                st.rerun()

        # The master button that writes everything into one single line row item
        st.sidebar.markdown("---")
        if st.sidebar.button("💾 SAVE ENTIRE WORKOUT", type="primary"):
            if st.session_state["current_workout_list"]:
                all_details = " | ".join(st.session_state["current_workout_list"])
                new_entry = pd.DataFrame([[user, date, activity, weight, all_details]], 
                                         columns=["User", "Date", "Activity", "Body Weight", "Details"])
                new_entry.to_csv(FILE_NAME, mode='a', header=False, index=False)
                
                # Clear memory loop upon tracking complete
                st.session_state["current_workout_list"] = []
                st.sidebar.success(f"Entire session saved, {user}!")
                st.rerun()
            else:
                st.sidebar.error("Your workout list is empty! Add exercises first.")
                
    elif activity == "LISS Cardio":
        mins = st.sidebar.number_input("Duration (minutes)", min_value=0, step=5)
        if st.sidebar.button("Log Cardio Session"):
            new_entry = pd.DataFrame([[user, date, activity, weight, f"{mins} min walk"]], 
                                     columns=["User", "Date", "Activity", "Body Weight", "Details"])
            new_entry.to_csv(FILE_NAME, mode='a', header=False, index=False)
            st.sidebar.success("Cardio saved!")
            st.rerun()
        
    elif activity == "Yoga/Mobility":
        stretch_focus = st.sidebar.selectbox("Select Mobility Routine", [
            "Full Body Flow",
            "Lower Back Decompression & Hips",
            "Upper Body Chest & Lat Opening",
            "Hamstring & Glute Flexibility",
            "Custom/Static Stretching"
        ])
        if st.sidebar.button("Log Mobility Session"):
            new_entry = pd.DataFrame([[user, date, activity, weight, f"Mobility: {stretch_focus}"]], 
                                     columns=["User", "Date", "Activity", "Body Weight", "Details"])
            new_entry.to_csv(FILE_NAME, mode='a', header=False, index=False)
            st.sidebar.success("Mobility saved!")
            st.rerun()
        
    else:
        if st.sidebar.button("Log Rest Day"):
            new_entry = pd.DataFrame([[user, date, activity, weight, "Recovery/Rest Day"]], 
                                     columns=["User", "Date", "Activity", "Body Weight", "Details"])
            new_entry.to_csv(FILE_NAME, mode='a', header=False, index=False)
            st.sidebar.success("Rest day logged!")
            st.rerun()

    # --- 6. MAIN DASHBOARD TABS ---
    tab1, tab2, tab3 = st.tabs(["📈 Progress Charts", "📅 Training History", "🧘 Recovery Protocols"])

    with tab1:
        log_df = pd.read_csv(FILE_NAME)
        user_df = log_df[log_df["User"] == user]
        
        if not user_df.empty:
            st.subheader(f"{user}'s Weight Journey")
            weight_df = user_df.dropna(subset=["Body Weight"])
            if not weight_df.empty:
                st.line_chart(weight_df.set_index("Date")["Body Weight"])
            
            total_sessions = user_df.shape[0]
            mobility_sessions = user_df[user_df["Activity"] == "Yoga/Mobility"].shape[0]
            
            col1, col2 = st.columns(2)
            col1.metric("Total Sessions Tracked", total_sessions)
            col2.metric("Dedicated Mobility Days", mobility_sessions)
        else:
            st.info("No data logged yet. Use the sidebar to log your first workout session!")

    with tab2:
        st.subheader("Shared Family Training Log")
        if os.path.exists(FILE_NAME):
            display_df = pd.read_csv(FILE_NAME)
            if not display_df.empty:
                st.dataframe(display_df.sort_values(by="Date", ascending=False), use_container_width=True)
            else:
                st.write("The log is currently empty.")

    with tab3:
        st.subheader("B-52 Post-Workout Recovery Guide")
        st.write("""
        Even if today isn't a dedicated mobility day, take 5 minutes after using the B-52 rack to hit these core movements:
        
        *   **Frame Lat Stretch:** Grab the B-52 upright frame with both hands, hinge at your hips, and drop your head between your shoulders. Hold for 30s.
        *   **Doorway Chest Fly Stretch:** Step through the center of the B-52 rack, place your forearms on the vertical pillars, and lean forward to open up the shoulders.
        *   **Deep Kneeling Hip Flexor Stretch:** Drop to one knee. Tighten your glutes and push your hips forward slightly to pull out the tension from heavy squats.
        *   **Spinal Decompression (Child's Pose):** Sit back onto your heels on a gym mat and extend your hands forward across the floor to relieve compressed spinal discs.
        """)
