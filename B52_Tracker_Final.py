# --- 1. APP CONFIGURATION & IMPORTS ---
import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import datetime

# Must be the very first Streamlit command
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

    # --- 4.5 GARMIN INTEGRATION (SAFEGUARDED) ---
    try:
        from garminconnect import Garmin
        import datetime
        
        @st.cache_data(ttl=3600, show_spinner=False)
        def get_garmin_metrics(user_email, user_pass):
            try:
                from garminconnect import Garmin
                from zoneinfo import ZoneInfo
                import datetime
                
                client = Garmin(user_email, user_pass)
                client.login()
                
                # Lock the clock to Central Time so the server doesn't pull "tomorrow's" data at night
                tz = ZoneInfo("America/Chicago")
                today = datetime.datetime.now(tz).date().isoformat()
                
                # Ask Garmin for the main data bucket
                stats = client.get_stats(today) or {}
                
                # Ask Garmin for the specific steps bucket
                try:
                    steps_data = client.get_steps_data(today)
                except:
                    steps_data = "Endpoint unavailable"
                
                # 1. STEPS
                raw_steps = stats.get('totalSteps')
                steps = f"{int(raw_steps):,}" if raw_steps else "0"
                
                # 2. RESTING HEART RATE
                raw_rhr = stats.get('restingHeartRate')
                if not raw_rhr:
                    try:
                        rhr_data = client.get_rhr_day(today)
                        raw_rhr = rhr_data.get('restingHeartRate') if rhr_data else None
                    except: pass
                rhr = int(raw_rhr) if raw_rhr else "--"
                
                # 3. BODY BATTERY
                bb_max = "--"
                try:
                    bb_data = client.get_body_battery(today)
                    if bb_data and isinstance(bb_data, list) and len(bb_data) > 0:
                        bb_max = bb_data[0].get('charged') or bb_data[0].get('highestBodyBatteryValue') or "--"
                except: pass

                # Package the raw data for the debugger
                debug_info = {
                    "Date_Queried": today,
                    "Main_Stats": stats
                }

                return {"Steps": steps, "RHR": rhr, "Body Battery": bb_max, "Raw": str(debug_info)}
                
            except Exception as e:
                return {"Steps": "0", "RHR": "--", "Body Battery": "--", "Raw": f"Garmin Server Error: {str(e)}"}

        # Attempt to pull credentials
        if user == "Jason":
            g_email = st.secrets["garmin"]["jason_email"]
            g_pass = st.secrets["garmin"]["jason_pass"]
        else:
            g_email = st.secrets["garmin"]["angelle_email"]
            g_pass = st.secrets["garmin"]["angelle_pass"]

        daily_metrics = get_garmin_metrics(g_email, g_pass)
        garmin_status = "active"

    except KeyError as e:
        garmin_status = "missing_secrets"
        daily_metrics = {"Steps": "0", "RHR": "--", "Body Battery": "--", "Raw": f"Missing Secret Key: {str(e)}"}
    except ImportError as e:
        garmin_status = "missing_library"
        daily_metrics = {"Steps": "0", "RHR": "--", "Body Battery": "--", "Raw": f"Missing Library: {str(e)}"}
    except Exception as e:
        garmin_status = "unknown_error"
        daily_metrics = {"Steps": "0", "RHR": "--", "Body Battery": "--", "Raw": f"Outer Error: {str(e)}"}
    
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
        ex = st.sidebar.selectbox("Choose Exercise", ["Smith Machine Squats", "Cable Lat Pulldowns", "Smith Machine Bench Press", "Cable Rows", "Cable Woodchoppers", "Smith Machine RDLs"])
        
        # --- UNIVERSAL MEMORY LOGIC ---
        if not log_df.empty:
            try:
                has_details = log_df['Details'].notna()
                past_sets = log_df[(log_df["User"] == user) & (has_details) & (log_df["Details"].str.contains(ex, case=False, na=False))]
                
                if not past_sets.empty:
                    last_entry = str(past_sets.iloc[-1]["Details"])
                    parts = [p.strip() for p in last_entry.split("|") if ex.lower() in p.lower()]
                    
                    if parts:
                        raw_stat = parts[-1].split('(')[-1].split(')')[0]
                        clean_stat = raw_stat.replace('lbs', '').replace('reps', '').replace(' ', '')
                        stats = clean_stat.split('x')
                        
                        if len(stats) >= 2:
                            weight_val = stats[-2]
                            reps_val = stats[-1]
                            display_stat = f"{weight_val} lbs x {reps_val} reps"
                            st.sidebar.markdown(f"🟢 **Last time:** `{display_stat}`")
            except Exception as e:
                st.sidebar.caption("History format mismatch.")

        col_s, col_w, col_r = st.sidebar.columns(3)
        with col_s:
            sets = st.number_input("Sets", min_value=1, step=1, value=3)
        with col_w:
            lbs = st.number_input("Lbs", min_value=0, step=5)
        with col_r:
            reps = st.number_input("Reps", min_value=0, step=1)
        
        if st.sidebar.button("➕ Add Exercise to List", use_container_width=True):
            st.session_state["current_workout_list"].append(f"{ex} ({sets}x{lbs}x{reps})")
            st.toast(f"Added {ex}!")

        if st.session_state["current_workout_list"]:
            st.sidebar.write("**Current Session Stack:**")
            for item in st.session_state["current_workout_list"]:
                st.sidebar.caption(f"• {item}")
            if st.sidebar.button("🗑️ Clear List", use_container_width=True):
                st.session_state["current_workout_list"] = []
                st.rerun()

            st.sidebar.markdown("---")
            if st.sidebar.button("💾 SAVE ENTIRE WORKOUT", type="primary", use_container_width=True):
                if st.session_state["current_workout_list"]:
                    all_details = " | ".join(st.session_state["current_workout_list"])
                    save_triggered = True
                else:
                    st.sidebar.error("Workout list is empty!")
                
    elif activity == "Cardio":
        mins = st.sidebar.number_input("Duration (minutes)", min_value=0, step=5)
        if st.sidebar.button("Log Cardio Session", use_container_width=True):
            all_details = f"{mins} min walk"
            save_triggered = True
        
    else: 
        stretch_focus = st.sidebar.selectbox("Select Mobility", ["Full Body Flow", "Lower Back & Hips", "Chest & Lat Opening", "Hamstring & Glute", "Custom"])
        if st.sidebar.button("Log Mobility Session", use_container_width=True):
            all_details = f"Mobility: {stretch_focus}"
            save_triggered = True

    # --- MASTER SAVE LOGIC ---
    if save_triggered:
        new_row = pd.DataFrame([[user, str(date), activity, weight, all_details]], columns=["User", "Date", "Activity", "Body Weight", "Details"])
        updated_df = pd.concat([log_df, new_row], ignore_index=True)
        conn.update(data=updated_df)
        st.cache_data.clear() 
        st.session_state["current_workout_list"] = []
        st.toast("Saved to Google Sheets!")
        st.rerun()

    # --- 6. MAIN DASHBOARD TABS ---
    tab1, tab2, tab3 = st.tabs(["📈 Progress Charts", "📅 Training History", "📚 Reference Library"])

    with tab1:
        # --- SECTION A: GARMIN METRICS ---
        st.subheader("⌚ Today's Garmin Vitals")
        
        if garmin_status == "missing_secrets":
            st.error("⚠️ Garmin Secrets are missing. Check your Streamlit Cloud Settings -> Secrets.")
        elif garmin_status == "missing_library":
            st.error("⚠️ 'garminconnect' library is missing. Make sure it is in your requirements.txt file.")
        elif garmin_status == "unknown_error":
            st.error("⚠️ An unknown error occurred with the Garmin connection.")
            
        g_col1, g_col2, g_col3 = st.columns(3)
        g_col1.metric("Steps", daily_metrics["Steps"])
        g_col2.metric("Resting Heart Rate", f"{daily_metrics['RHR']} bpm")
        g_col3.metric("Peak Body Battery", daily_metrics["Body Battery"])

        # THE X-RAY: This will print the raw data Garmin sends us
        with st.expander("Garmin Debugger - Click to see Raw Data"):
            st.write(daily_metrics.get("Raw", "No raw data found"))
        
        st.divider()

        # --- SECTION C: STRENGTH DASHBOARD ---
        st.subheader("🚀 Strength Dashboard")
        if not log_df.empty:
            lift_data = log_df[(log_df["User"] == user) & (log_df["Activity"] == "Full Body Circuit")]
            
            if not lift_data.empty:
                def get_lift_df(exercise_name):
                    records = []
                    for _, row in lift_data.iterrows():
                        if exercise_name in row["Details"]:
                            try:
                                parts = [p.strip() for p in row["Details"].split("|") if exercise_name in p]
                                for p in parts:
                                    raw_stat = p.split('(')[-1].split(')')[0]
                                    stats = raw_stat.replace(' ', '').split('x')
                                    if len(stats) == 3:
                                        w, r = float(stats[1]), float(stats[2])
                                        est_1rm = w * (36 / (37 - r)) if r < 37 else w
                                        records.append({"Date": row["Date"], "Weight": w, "Est_1RM": round(est_1rm, 1)})
                            except: continue
                    return pd.DataFrame(records).set_index("Date") if records else pd.DataFrame()

                st.markdown("### The Big Three")
                col1, col2 = st.columns(2)
                
                with col1:
                    st.caption("Smith Machine Squats")
                    df_squat = get_lift_df("Smith Machine Squats")
                    if not df_squat.empty: st.line_chart(df_squat["Est_1RM"])
                    else: st.info("No squat data.")

                with col2:
                    st.caption("Smith Machine Bench Press")
                    df_bench = get_lift_df("Smith Machine Bench Press")
                    if not df_bench.empty: st.line_chart(df_bench["Est_1RM"])
                    else: st.info("No bench data.")

                st.markdown("---")
                
                st.markdown("### Specialized Tracking")
                other_ex = st.selectbox("Select other exercise", ["Cable Lat Pulldowns", "Cable Rows", "Cable Woodchoppers", "Smith Machine RDLs"])
                df_other = get_lift_df(other_ex)
                if not df_other.empty:
                    st.line_chart(df_other[["Weight", "Est_1RM"]])
                else:
                    st.info(f"No data for {other_ex}")

            else:
                st.info("Log some 'Full Body Circuit' sessions to see your strength charts!")

    with tab2:
        st.subheader(f"{user}'s Training History")
        if not log_df.empty:
            user_history_df = log_df[log_df["User"] == user].sort_values(by="Date", ascending=False)
            
            if not user_history_df.empty:
                edited_df = st.data_editor(user_history_df, num_rows="dynamic", use_container_width=True, disabled=["User", "Date", "Activity", "Body Weight", "Details"], key="log_editor")
                
                if len(edited_df) < len(user_history_df):
                    if st.button("🔴 Confirm Deletion and Update Sheet", type="primary", use_container_width=True):
                        other_users_df = log_df[log_df["User"] != user]
                        final_df = pd.concat([other_users_df, edited_df], ignore_index=True)
                        conn.update(data=final_df)
                        st.cache_data.clear()
                        st.success("Google Sheet Updated!")
                        st.rerun()
            else:
                st.info("No history found for this user.")

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
