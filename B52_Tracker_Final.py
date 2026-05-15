import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import datetime

# --- 1. PASSWORD PROTECTION SYSTEM ---
def check_password():
    """Returns True if the user entered the correct password."""
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
    else:
        return True

if check_password():

    # --- 2. APP CONFIGURATION ---
    st.set_page_config(page_title="Home Gym Tracker", layout="wide")

    # --- 3. MULTI-USER & COLOR THEMING ---
    user = st.radio("Who is training today?", ["Jason", "Angelle"], horizontal=True)

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

    # --- 4. CONNECT TO GOOGLE SHEETS ---
    conn = st.connection("gsheets", type=GSheetsConnection)

    # Initial read to establish log_df
    try:
        log_df = conn.read(ttl=0)
        if not log_df.empty:
            log_df['Date'] = log_df['Date'].astype(str)
    except:
        log_df = pd.DataFrame(columns=["User", "Date", "Activity", "Body Weight", "Details"])

    if "current_workout_list" not in st.session_state:
        st.session_state["current_workout_list"] = []

# --- 5. LOGGING SIDEBAR ---
    st.sidebar.header(f"Log Details for {user}")
    date = st.sidebar.date_input("Date", datetime.date.today())
    
    # Updated Session Type list
    activity = st.sidebar.selectbox("Session Type", ["Full Body Circuit", "LISS Cardio", "Yoga/Mobility", "Body Weight", "Rest"])

    # We initialize these variables at the top so they exist for every 'if' statement
    weight = 0.0 
    all_details = ""
    save_triggered = False

    # 1. BODY WEIGHT LOGGING
    if activity == "Body Weight":
        weight = st.sidebar.number_input("Current Weight (lbs)", min_value=0.0, step=0.1)
        if st.sidebar.button("Log Weight Only"):
            all_details = f"Weight Entry: {weight} lbs"
            save_triggered = True

    # 2. WORKOUT LOGGING
    elif activity == "Full Body Circuit":
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
                save_triggered = True
            else:
                st.sidebar.error("Your workout list is empty!")
                
    # 3. CARDIO LOGGING
    elif activity == "LISS Cardio":
        mins = st.sidebar.number_input("Duration (minutes)", min_value=0, step=5)
        if st.sidebar.button("Log Cardio Session"):
            all_details = f"{mins} min walk"
            save_triggered = True
        
    # 4. MOBILITY LOGGING
    elif activity == "Yoga/Mobility":
        stretch_focus = st.sidebar.selectbox("Select Mobility Routine", [
            "Full Body Flow", "Lower Back Decompression & Hips", 
            "Upper Body Chest & Lat Opening", "Hamstring & Glute Flexibility", 
            "Custom/Static Stretching"
        ])
        if st.sidebar.button("Log Mobility Session"):
            all_details = f"Mobility: {stretch_focus}"
            save_triggered = True
        
    # 5. REST DAY
    else:
        if st.sidebar.button("Log Rest Day"):
            all_details = "Recovery/Rest Day"
            save_triggered = True
            
    # --- 6. MAIN DASHBOARD TABS ---
    tab1, tab2, tab3 = st.tabs(["📈 Progress Charts", "📅 Training History", "📚 Reference Library"])

    with tab1:
        user_df = log_df[log_df["User"] == user] if not log_df.empty else pd.DataFrame()
        if not user_df.empty:
            st.subheader(f"{user}'s Weight Journey")
            weight_df = user_df.dropna(subset=["Body Weight"])
            if not weight_df.empty:
                st.line_chart(weight_df.set_index("Date")["Body Weight"])
            
            col1, col2 = st.columns(2)
            col1.metric("Total Sessions Tracked", len(user_df))
            col2.metric("Dedicated Mobility Days", len(user_df[user_df["Activity"] == "Yoga/Mobility"]))
        else:
            st.info("No data logged yet.")

    with tab2:
        st.subheader("Shared Family Training Log")
        st.caption("Select rows and use Delete/Backspace to remove logs, then click Confirm.")
        if not log_df.empty:
            sorted_df = log_df.sort_values(by="Date", ascending=False)
            edited_df = st.data_editor(
                sorted_df,
                num_rows="dynamic",
                use_container_width=True,
                disabled=["User", "Date", "Activity", "Body Weight", "Details"], 
                key="log_editor"
            )
            if len(edited_df) < len(sorted_df):
                if st.button("🔴 Confirm Deletion and Update Sheet", type="primary"):
                    conn.update(data=edited_df)
                    st.success("Google Sheet Updated!")
                    st.rerun()

    with tab3:
        st.subheader("Home Gym Reference Library")
        st.markdown("## 🏋️ Workout Exercises")
        col_ex1, col_ex2 = st.columns(2)
        with col_ex1:
            st.markdown("### **Lower Body**")
            st.write("**Smith Machine Squats:** Focus on sitting 'back' into hips, chest up.")
            st.write("**Smith Machine RDLs:** Hinge at hips, bar to mid-shin, squeeze glutes.")
        with col_ex2:
            st.markdown("### **Upper Body**")
            st.write("**Smith Machine Bench Press:** Control descent, explode upward.")
            st.write("**Cable Lat Pulldowns:** Drive elbows down, squeeze shoulder blades.")
            st.write("**Cable Rows:** Pull toward navel, squeeze shoulder blades together.")
        
        st.write("---")
        st.markdown("## 🧘 Recovery Protocols")
        
        st.markdown("### **1. Frame Lat Stretch**")
        st.caption("Target: Upper Back & Lats | 30 Seconds")
        st.write("Grab an upright pillar firmly with both hands. Step back, hinge deeply at your hips, and drop your head between your shoulders while pushing your hips away.")

        st.markdown("### **2. Doorway Chest Fly Stretch**")
        st.caption("Target: Chest & Shoulders | 30 Seconds")
        st.write("Place forearms flat against the vertical pillars with elbows at 90 degrees. Gently step one foot forward to open up the chest.")

        st.markdown("### **3. Deep Kneeling Hip Flexor Stretch**")
        st.caption("Target: Hips & Quads | 30 Seconds per side")
        st.write("Half-kneeling position. Squeeze the trailing glute and push hips forward slightly. Essential for counteracting squat tension.")

        st.markdown("### **4. Spinal Decompression (Child's Pose)**")
        st.caption("Target: Lower Back | 45-60 Seconds")
        st.write("Kneel, sit back on heels, and reach hands forward on the mat. Relieves spinal compression after structural loading.")
