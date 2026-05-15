import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import datetime

# --- 1. PASSWORD PROTECTION SYSTEM ---
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

    # --- 2. APP CONFIGURATION ---
    st.set_page_config(page_title="Home Gym Tracker", layout="wide")

    # --- 3. MULTI-USER & COLOR THEMING ---
    user = st.radio("Who is training today?", ["Jason", "Angelle"], horizontal=True)
    page_bg_color = "#1E3A8A" if user == "Jason" else "#0D9488"
    st.markdown(f"<style>.stApp {{background-color: {page_bg_color}; color: white;}} [data-testid='stSidebar'] {{background-color: rgba(255, 255, 255, 0.1);}} .stTabs [data-baseweb='tab'] {{color: white !important;}}</style>", unsafe_allow_html=True)
    st.title(f"💪 Home Gym: {user}'s Session")

    # --- 4. CONNECT TO GOOGLE SHEETS (WITH CACHING TO REDUCE LAG) ---
    conn = st.connection("gsheets", type=GSheetsConnection)

    # We use ttl=600 (10 minutes) so it doesn't fetch on every single click, reducing lag.
    # We will use st.cache_data.clear() on save to force a fresh pull.
    try:
        log_df = conn.read(ttl=600)
        if not log_df.empty:
            log_df['Date'] = log_df['Date'].astype(str)
    except:
        log_df = pd.DataFrame(columns=["User", "Date", "Activity", "Body Weight", "Details"])

    if "current_workout_list" not in st.session_state:
        st.session_state["current_workout_list"] = []

    # --- 5. LOGGING SIDEBAR ---
    st.sidebar.header(f"Log Details for {user}")
    date = st.sidebar.date_input("Date", datetime.date.today())
    activity = st.sidebar.selectbox("Session Type", ["Full Body Circuit", "LISS Cardio", "Yoga/Mobility", "Body Weight", "Rest"])

    # Initialize save variables
    weight = 0.0 
    all_details = ""
    save_triggered = False

    if activity == "Body Weight":
        weight = st.sidebar.number_input("Current Weight (lbs)", min_value=0.0, step=0.1)
        if st.sidebar.button("Log Weight"):
            all_details = f"Weight Entry: {weight} lbs"
            save_triggered = True

    elif activity == "Full Body Circuit":
        st.sidebar.subheader("Add Exercises")
        ex = st.sidebar.selectbox("Choose Exercise", ["Smith Machine Squats", "Cable Lat Pulldowns", "Smith Machine Bench Press", "Cable Rows", "Cable Woodchoppers", "Smith Machine RDLs"])
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
                st.sidebar.error("Workout list is empty!")
                
    elif activity == "LISS Cardio":
        mins = st.sidebar.number_input("Duration (minutes)", min_value=0, step=5)
        if st.sidebar.button("Log Cardio Session"):
            all_details = f"{mins} min walk"
            save_triggered = True
        
    elif activity == "Yoga/Mobility":
        stretch_focus = st.sidebar.selectbox("Select Mobility", ["Full Body Flow", "Lower Back & Hips", "Chest & Lat Opening", "Hamstring & Glute", "Custom"])
        if st.sidebar.button("Log Mobility Session"):
            all_details = f"Mobility: {stretch_focus}"
            save_triggered = True

    # --- MASTER SAVE LOGIC ---
    if save_triggered:
        new_row = pd.DataFrame([[user, str(date), activity, weight, all_details]], columns=["User", "Date", "Activity", "Body Weight", "Details"])
        updated_df = pd.concat([log_df, new_row], ignore_index=True)
        conn.update(data=updated_df)
        st.cache_data.clear() # Clears the cache so the Progress tab updates immediately
        st.session_state["current_workout_list"] = []
        st.toast("Saved to Google Sheets!")
        st.rerun()

    # --- 6. MAIN DASHBOARD TABS ---
    tab1, tab2, tab3 = st.tabs(["📈 Progress Charts", "📅 Training History", "📚 Reference Library"])

    with tab1:
        # We only want to chart rows where a weight was actually recorded
        user_df = log_df[(log_df["User"] == user) & (log_df["Body Weight"] > 0)] if not log_df.empty else pd.DataFrame()
        if not user_df.empty:
            st.subheader(f"{user}'s Weight Journey")
            st.line_chart(user_df.set_index("Date")["Body Weight"])
        else:
            st.info("No weight data logged yet. Use 'Body Weight' session type to start your chart.")

    with tab2:
        st.subheader("Shared Family Training Log")
        if not log_df.empty:
            sorted_df = log_df.sort_values(by="Date", ascending=False)
            edited_df = st.data_editor(sorted_df, num_rows="dynamic", use_container_width=True, disabled=["User", "Date", "Activity", "Body Weight", "Details"], key="log_editor")
            if len(edited_df) < len(sorted_df):
                if st.button("🔴 Confirm Deletion and Update Sheet", type="primary"):
                    conn.update(data=edited_df)
                    st.cache_data.clear()
                    st.success("Google Sheet Updated!")
                    st.rerun()

    with tab3:
        st.subheader("Home Gym Reference Library")
        st.markdown("## 🏋️ Workout Exercises")
        col_ex1, col_ex2 = st.columns(2)
        with col_ex1:
            st.markdown("### **Lower Body**")
            st.write("**Smith Machine Squats:** Sit 'back' into hips, chest up.")
            st.write("**Smith Machine RDLs:** Hinge at hips, bar to mid-shin, squeeze glutes.")
        with col_ex2:
            st.markdown("### **Upper Body**")
            st.write("**Smith Machine Bench Press:** Control descent, explode upward.")
            st.write("**Cable Lat Pulldowns:** Drive elbows down, squeeze shoulder blades.")
            st.write("**Cable Rows:** Pull toward navel, squeeze shoulder blades.")
        
        st.write("---")
        st.markdown("## 🧘 Recovery Protocols")
        st.markdown("### **1. Frame Lat Stretch (30s)**")
        st.write("Grab upright, hinge at hips, head between shoulders.")
        st.markdown("### **2. Doorway Chest Fly Stretch (30s)**")
        st.write("Forearms on pillars at 90 deg, step forward to open chest.")
        st.markdown("### **3. Deep Kneeling Hip Flexor Stretch (30s/side)**")
        st.write("Half-kneeling, squeeze glute, push hips forward.")
        st.markdown("### **4. Spinal Decompression (45-60s)**")
        st.write("Child's Pose: Kneel, sit on heels, reach forward.")
