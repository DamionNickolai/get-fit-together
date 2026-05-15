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
    st.set_page_config(page_title="Home Gym Tracker", layout="wide")

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

    st.title(f"💪 Home Gym: {user}'s Session")

    # --- 4. DATABASE INITIALIZATION ---
    FILE_NAME = "family_workout_log.csv"
    if not os.path.exists(FILE_NAME):
        df = pd.DataFrame(columns=["User", "Date", "Activity", "Body Weight", "Details"])
        df.to_csv(FILE_NAME, index=False)

    # Initialize temporary workout list
    if "current_workout_list" not in st.session_state:
        st.session_state["current_workout_list"] = []

    # --- 5. LOGGING SIDEBAR ---
    st.sidebar.header(f"Log Details for {user}")
    date = st.sidebar.date_input("Date", datetime.date.today())
    activity = st.sidebar.selectbox("Session Type", ["Full Body Circuit", "LISS Cardio", "Yoga/Mobility", "Rest"])
    weight = st.sidebar.number_input("Body Weight (lbs)", min_value=0.0, step=0.1)

    # Dynamic Input Elements Based on Session Type
    if activity == "Full Body Circuit":
        st.sidebar.subheader("Add Exercises to Session")
        ex = st.sidebar.selectbox("Choose Exercise", [
            "Smith Machine Squats", "Cable Lat Pulldowns", 
            "Smith Machine Bench Press", "Cable Rows", 
            "Cable Woodchoppers", "Smith Machine RDLs"
        ])
        lbs = st.sidebar.number_input("Max Weight (lbs)", min_value=0, step=5)
        reps = st.sidebar.number_input("Reps", min_value=0, step=1)
        
        if st.sidebar.button("➕ Add Exercise to List"):
            st.session_state["current_workout_list"].append(f"{ex} ({lbs} lbs x {reps})")
            st.sidebar.toast(f"Added {ex}!")

        if st.session_state["current_workout_list"]:
            st.sidebar.write("**Current Session Stack:**")
            for item in st.session_state["current_workout_list"]:
                st.sidebar.caption(f"• {item}")
            
            if st.sidebar.button("🗑️ Clear List"):
                st.session_state["current_workout_list"] = []
                st.rerun()

        st.sidebar.markdown("---")
        if st.sidebar.button("💾 SAVE ENTIRE WORKOUT", type="primary"):
            if st.session_state["current_workout_list"]:
                all_details = " | ".join(st.session_state["current_workout_list"])
                new_entry = pd.DataFrame([[user, date, activity, weight, all_details]], 
                                         columns=["User", "Date", "Activity", "Body Weight", "Details"])
                new_entry.to_csv(FILE_NAME, mode='a', header=False, index=False)
                
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
            "Full Body Flow", "Lower Back Decompression & Hips", 
            "Upper Body Chest & Lat Opening", "Hamstring & Glute Flexibility", 
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
    tab1, tab2, tab3, tab4 = st.tabs(["📈 Progress Charts", "📅 Training History", "🧘 Recovery Protocols", "🛠️ Manage Logs"])

    # Load data for tabs
    log_df = pd.read_csv(FILE_NAME)

    with tab1:
        user_df = log_df[log_df["User"] == user] if not log_df.empty else pd.DataFrame()
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
        if not log_df.empty:
            st.dataframe(log_df.sort_values(by="Date", ascending=False), use_container_width=True)
        else:
            st.write("The log is currently empty.")

    with tab3:
        st.subheader("Post-Workout Recovery Guide")
        st.write("""
        Take 5 minutes after your circuit to hit these core movements:
        * **Frame Lat Stretch (30s)** | **Doorway Chest Fly Stretch (30s)** | **Deep Kneeling Hip Flexor Stretch (30s)** | **Child's Pose**
        """)

    # --- NEW: TAB 4 - DELETION MANAGEMENT ---
    with tab4:
        st.subheader("Delete a Logged Entry")
        if not log_df.empty:
            # Create a user-friendly dropdown label combining Row index, User, Date, and Activity
            log_df['Delete_Label'] = log_df.index.astype(str) + " - " + log_df['User'] + " (" + log_df['Date'] + "): " + log_df['Activity']
            
            # Select item to delete
            item_to_delete = st.selectbox("Select row to permanently delete:", log_df['Delete_Label'].unique())
            
            if st.button("🔴 Permanently Delete Selected Row", type="primary"):
                # Extract the original index from our label string
                index_to_drop = int(item_to_delete.split(" - ")[0])
                
                # Drop row, drop our temporary label column, and resave the file
                log_df = log_df.drop(index_to_drop).drop(columns=['Delete_Label'])
                log_df.to_csv(FILE_NAME, index=False)
                
                st.success("Entry successfully deleted!")
                st.rerun()
        else:
            st.info("No logs available to delete.")
