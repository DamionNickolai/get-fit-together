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
            st.toast(f"Added {ex}!")

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
    tab1, tab2, tab3 = st.tabs(["📈 Progress Charts", "📅 Training History", "🧘 Recovery Protocols"])

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
        st.caption("Check the boxes on the left side of any row and use Delete/Backspace or the trash icon to remove logs.")
        
        if not log_df.empty:
            sorted_df = log_df.sort_values(by="Date", ascending=False)
            
            edited_df = st.data_editor(
                sorted_df,
                hide_index=False,
                num_rows="dynamic",
                use_container_width=True,
                disabled=["User", "Date", "Activity", "Body Weight", "Details"], 
                key="log_editor"
            )
            
            if len(edited_df) < len(sorted_df):
                if st.button("🔴 Confirm Deletion and Resave Log", type="primary"):
                    edited_df.to_csv(FILE_NAME, index=False)
                    st.success("Log updated successfully!")
                    st.rerun()
        else:
            st.write("The log is currently empty.")

    # --- RESTORED DESCRIPTIVE RECOVERY PROTOCOLS ---
    with tab3:
        st.subheader("Recommended Post-Workout Recovery Guide")
        st.markdown("Maximize recovery, prevent stiffness, and protect your joints to stay consistent week-over-week:")
        st.write("---")
        
        st.markdown("### **1. Frame Lat Stretch**")
        st.write("""
        * **Target:** Latissimus Dorsi, Upper Back, Thoracic Spine.
        * **How to do it:** Face your gym rack's vertical steel frame. Grab an upright pillar firmly with both hands at roughly chest height. Step back, hinge deeply at your hips, and drop your head between your shoulders while pushing your hips away from the rack. 
        * **Duration:** Hold for 30 seconds while focusing on deep belly breathing to decompress the upper back.
        """)
        
        st.markdown("### **2. Doorway Chest Fly Stretch**")
        st.write("""
        * **Target:** Pectorals (Chest), Anterior Deltoids (Front Shoulders).
        * **How to do it:** Stand in the center of your rack frame or a doorway. Place your forearms or hands flat against the vertical pillars with your elbows bent at 90 degrees. Gently step one foot forward, shifting your body weight frontward until you feel a deep, comfortable stretch open up across your chest.
        * **Duration:** Hold for 30 seconds. Do not bounce; let gravity and your body weight do the work.
        """)
        
        st.markdown("### **3. Deep Kneeling Hip Flexor Stretch**")
        st.write("""
        * **Target:** Psoas, Hip Flexors, Quads.
        * **How to do it:** Drop down into a half-kneeling position on a comfortable gym mat (one knee down, one foot flat in front of you, both knees at 90-degree angles). Squeeze the glute of your trailing leg tight, keep your torso upright, and gently push your hips forward slightly. You will feel a strong pull down the front of your hip and thigh.
        * **Duration:** Hold for 30 seconds per side. Crucial for counteracting tension built up from sitting or heavy squatting.
        """)
        
        st.markdown("### **4. Spinal Decompression (Child's Pose)**")
        st.write("""
        * **Target:** Lower Back, Spinal Erectors, Glutes.
        * **How to do it:** Kneel on your gym mat, bring your big toes together, and sit your hips back completely onto your heels. Separate your knees about hip-width apart. Fold your torso forward over your thighs and extend your hands as far forward across the floor as possible, resting your forehead gently on the mat.
        * **Duration:** Hold for 45–60 seconds. Breathe deeply into your lower back to separate and relieve compressed spinal discs after structural loading.
        """)
