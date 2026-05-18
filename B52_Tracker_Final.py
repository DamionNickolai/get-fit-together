# --- 1. APP CONFIGURATION & IMPORTS ---
import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import datetime
import plotly.express as px
APP_VERSION = "1.0.0"

# Must be the very first Streamlit command
st.set_page_config(
    page_title="Our Fitness App",
    page_icon="💪",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. ENVIRONMENT DETECTION & PASSWORD SYSTEM ---
def check_password():
    if st.session_state.get("password_correct", False):
        return True

    with st.container():
        st.subheader("🔒 Gym Access Portal")
        
        with st.form("login_form", clear_on_submit=False):
            typed_user = st.text_input("Profile Name", key="login_username", autocomplete="username").strip()
            entered_pass = st.text_input("Password", type="password", key="login_password", autocomplete="current-password")
            login_clicked = st.form_submit_button("🚀 Log In", width="stretch", type="primary")
        
        if login_clicked:
            if not typed_user or not entered_pass:
                st.warning("⚠️ Please fill in both fields.")
                return False
                
            profile_meta = st.secrets["user_profiles"].get(typed_user)
            credentials = st.secrets["passwords"]
            
            if profile_meta:
                secret_key = profile_meta["password_key"]
                correct_password = credentials.get(secret_key)
                
                if entered_pass == correct_password:
                    st.session_state["password_correct"] = True
                    
                    # 🌐 ENVIRONMENT DETECTION LOGIC
                    host_header = st.context.headers.get("Host", "")
                    is_local = "localhost" in host_header or "127.0.0.1" in host_header or "192.168" in host_header
                    
                    if profile_meta["role"] == "developer" and is_local:
                        st.session_state["user_role"] = "developer"
                        # Pulls your default dev workspace directly from TOML
                        st.session_state["logged_in_user"] = st.secrets["app_config"]["default_dev_workspace"]
                    else:
                        st.session_state["user_role"] = "user"
                        st.session_state["logged_in_user"] = typed_user
                        
                    st.rerun()
                else:
                    st.error("😕 Access denied. Check your credentials.")
                    return False
            else:
                st.error("😕 Access denied. Check your credentials.")
                return False
                
        return False
    return True

if check_password():
    # --- 3. DYNAMIC METADATA & COLOR THEMING ---
    user = st.session_state["logged_in_user"]
    role = st.session_state["user_role"]
    
    current_profile = st.secrets["user_profiles"].get(user, {})
    
    page_bg_color = current_profile.get("primary_color", "#1F2937")
    side_bg = current_profile.get("sidebar_color", "#111827")
    chart_line_color = current_profile.get("line_color", "#34D399")

    st.markdown(f"""
        <style>
        .stApp {{ background-color: {page_bg_color}; color: white; }}
        [data-testid="stSidebar"] {{ background-color: {side_bg} !important; opacity: 1 !important; }}
        .stTabs [data-baseweb="tab"] {{ color: white !important; }}
        </style>
        """, unsafe_allow_html=True)
    
    if role == "developer":
        st.warning("🚧 DEV MODE ACTIVE: Connected to Workout Logs - DEV Sandbox")
        st.title(f"💪 Sandbox Environment: {user}'s Test Session")
    else:
        st.title(f"💪 Get Fit Together: {user}'s Session")

    # --- 4. DUAL-ENVIRONMENT GOOGLE SHEETS ROUTER ---
    if role == "developer":
        conn = st.connection("gsheets_dev", type=GSheetsConnection)
    else:
        conn = st.connection("gsheets_prod", type=GSheetsConnection)

    try:
        log_df = conn.read(ttl=600)
        if not log_df.empty:
            log_df['Date'] = log_df['Date'].astype(str)
    except:
        log_df = pd.DataFrame(columns=["User", "Date", "Activity", "Body Weight", "Details"])

    # 🤖 AUTOMATION ENGINE: Check-then-log helper function
    def check_and_autolog_garmin_weight(conn_history, df_history, user_name, today_date, garmin_weight_lbs):
        if not garmin_weight_lbs or float(garmin_weight_lbs) <= 0.0:
            return False
        try:
            if not df_history.empty:
                # Format checks to ensure zero comparison errors
                duplicate_check = df_history[
                    (df_history["User"] == user_name) & 
                    (df_history["Date"].astype(str) == str(today_date)) & 
                    (df_history["Activity"] == "Body Weight")
                ]
                if not duplicate_check.empty:
                    return False
            
            # Construct the passive log row
            new_row = pd.DataFrame([{
                "User": user_name,
                "Date": str(today_date),
                "Activity": "Body Weight",
                "Body Weight": float(garmin_weight_lbs),
                "Details": f"🤖 Automated Garmin Index Scale Sync ({garmin_weight_lbs} lbs)"
            }])
            
            updated_df = pd.concat([df_history, new_row], ignore_index=True)
            conn_history.update(data=updated_df)
            return True
        except Exception as e:
            print(f"Auto-weight sync skipped: {e}")
            return False

    if "current_workout_list" not in st.session_state:
        st.session_state["current_workout_list"] = []

    # --- 4.5 GARMIN INTEGRATION ---
    # 🤖 BULK AUTOMATION ENGINE: 30-Day Rolling Catch-up Sync
    def check_and_bulk_log_garmin_weight(conn_history, df_history, user_name, weight_history_list):
        if not weight_history_list or len(weight_history_list) == 0:
            return False
        try:
            existing_dates = set()
            if not df_history.empty:
                user_weights = df_history[(df_history["User"] == user_name) & (df_history["Activity"] == "Body Weight")]
                existing_dates = set(user_weights["Date"].astype(str).tolist())
                
            new_rows = []
            for entry in weight_history_list:
                g_date = str(entry["date"])
                g_weight = float(entry["weight"])
                if g_date not in existing_dates and g_weight > 0.0:
                    new_rows.append({
                        "User": user_name,
                        "Date": g_date,
                        "Activity": "Body Weight",
                        "Body Weight": g_weight,
                        "Details": f"🤖 Automated Garmin Index Scale Sync ({g_weight} lbs)"
                    })
            
            if new_rows:
                new_df = pd.DataFrame(new_rows)
                global log_df
                log_df = pd.concat([df_history, new_df], ignore_index=True)
                conn_history.update(data=log_df)
                return True
            return False
        except Exception as e:
            print(f"Auto-weight sync skipped: {e}")
            return False

    try:
        from garminconnect import Garmin
        import datetime
        from zoneinfo import ZoneInfo
        
        tz = ZoneInfo("America/Chicago")
        today = datetime.datetime.now(tz).date().isoformat()
        
        garmin_section = "garmin_dev" if role == "developer" else "garmin_prod"
        g_prefix = current_profile.get("garmin_prefix", "unknown")
        
        client_key = f"live_garmin_client_{g_prefix}"
        
        if client_key not in st.session_state:
            g_email = st.secrets[garmin_section].get(f"{g_prefix}_email", "")
            g_pass = st.secrets[garmin_section].get(f"{g_prefix}_pass", "")
            
            if g_email and g_pass:
                with st.spinner("Establishing secure link to Garmin..."):
                    client_instance = Garmin(g_email, g_pass)
                    client_instance.login()
                    st.session_state[client_key] = client_instance
        
        active_client = st.session_state.get(client_key, None)
        
        if active_client:
            @st.cache_data(ttl=1800, show_spinner=False)
            def fetch_garmin_data_layer(today_str, _client):
                try:
                    stats = _client.get_stats(today_str) or {}
                    
                    raw_steps = stats.get('totalSteps')
                    steps = f"{int(raw_steps):,}" if raw_steps else "0"
                    
                    raw_rhr = stats.get('restingHeartRate')
                    if not raw_rhr:
                        try:
                            rhr_data = _client.get_rhr_day(today_str)
                            raw_rhr = rhr_data.get('restingHeartRate') if rhr_data else None
                        except: pass
                    rhr = int(raw_rhr) if raw_rhr else 60

                    bb_max = 50
                    try:
                        bb_data = _client.get_body_battery(today_str)
                        if bb_data and isinstance(bb_data, list) and len(bb_data) > 0:
                            bb_max = bb_data[0].get('charged') or bb_data[0].get('highestBodyBatteryValue') or 50
                    except: pass

                    stress_val = stats.get('averageStressLevel', '--')
                    active_cal = stats.get('activeCalories', 0)
                    bmr_cal = stats.get('bmrCalories', 0)
                    total_calories = f"{int(active_cal + bmr_cal):,}" if (active_cal or bmr_cal) else "--"

                    hrv_val = "--"
                    try:
                        hrv_data = _client.get_hrv_data(today_str)
                        if hrv_data and 'hrvSummary' in hrv_data:
                            hrv_val = f"{hrv_data['hrvSummary'].get('lastNightAvg', '--')} ms"
                    except: pass

                    sleep_score = "--"
                    try:
                        sleep_data = _client.get_sleep_data(today_str)
                        if sleep_data and 'dailySleepDTO' in sleep_data and sleep_data['dailySleepDTO']:
                            sleep_score = sleep_data['dailySleepDTO'].get('sleepScore', '--')
                    except: pass

                    weight_lbs = 0.0
                    weight_goal = "--"
                    recent_weight_history = []
                    try:
                        start_date = (datetime.datetime.now(tz) - datetime.timedelta(days=30)).date().isoformat()
                        body_data = _client.get_body_composition(start_date, today_str)
                        if body_data:
                            if 'goals' in body_data and body_data['goals']:
                                g_w = body_data['goals'].get('weightGoal')
                                if g_w: weight_goal = f"{round((g_w / 1000) * 2.20462, 1)} lbs"

                            if 'dateWeightList' in body_data and len(body_data['dateWeightList']) > 0:
                                for entry in body_data['dateWeightList']:
                                    w_grams = entry.get('weight')
                                    c_date = entry.get('calendarDate')
                                    if w_grams and c_date:
                                        w_lbs = round((w_grams / 1000) * 2.20462, 1)
                                        recent_weight_history.append({"date": c_date, "weight": w_lbs})
                                if recent_weight_history:
                                    weight_lbs = recent_weight_history[-1]["weight"]
                    except: pass

                    debug_info = {"Date_Queried": today_str, "Main_Stats": stats}

                    return {
                        "Steps": steps, "RHR": rhr, "Body Battery": int(bb_max) if str(bb_max).isdigit() else 50, 
                        "Stress": stress_val, "Calories": total_calories, "HRV": hrv_val,
                        "Sleep Score": sleep_score, "Weight": weight_lbs, "Weight Goal": weight_goal,
                        "Weight_History": recent_weight_history, "Raw": str(debug_info)
                    }
                except Exception as inner_err:
                    return {"Steps": "0", "RHR": 60, "Body Battery": 50, "Stress": "--", "Calories": "--", "HRV": "--", "Sleep Score": "--", "Weight": 0.0, "Weight Goal": "--", "Weight_History": [], "Raw": f"Inner Error: {inner_err}"}

            daily_metrics = fetch_garmin_data_layer(today, active_client)
            garmin_status = "active"
            
            history_list = daily_metrics.get("Weight_History", [])
            check_and_bulk_log_garmin_weight(conn_history=conn, df_history=log_df, user_name=user, weight_history_list=history_list)
        else:
            garmin_status = "missing_secrets"
            daily_metrics = {"Steps": "0", "RHR": 60, "Body Battery": 50, "Stress": "--", "Calories": "--", "HRV": "--", "Sleep Score": "--", "Weight": 0.0, "Weight Goal": "--", "Weight_History": [], "Raw": "No active client"}

    except KeyError as e:
        garmin_status = "missing_secrets"
        daily_metrics = {"Steps": "0", "RHR": 60, "Body Battery": 50, "Stress": "--", "Calories": "--", "HRV": "--", "Sleep Score": "--", "Weight": 0.0, "Weight Goal": "--", "Weight_History": [], "Raw": f"Outer Error: {e}"}
    except Exception as outer_e:
        garmin_status = "unknown_error"
        daily_metrics = {"Steps": "0", "RHR": 60, "Body Battery": 50, "Stress": "--", "Calories": "--", "HRV": "--", "Sleep Score": "--", "Weight": 0.0, "Weight Goal": "--", "Weight_History": [], "Raw": f"Outer Error: {outer_e}"}

    # ==========================================
    # 📚 ANGELLE'S 12-MONTH MACROCYCLE DATABASE
    # ==========================================
    # (Defined here openly so both Section 5 Sidebar and Section 6 Tabs can see it)
    ROUTINES = {
        "Q1: Foundation & Endurance": {
            "Focus": "Building joint stability, mastering mechanics, aerobic base. Rest: 60-90s.",
            "Workouts": {
                "Workout A: Upper Body & Core": [
                    "Seated Cable Rows ( Low Pulley): 3 sets x 12 reps",
                    "Incline Smith Machine Press: 3 sets x 10 reps",
                    "Cable Tricep Pushdowns ( High Pulley): 3 sets x 15 reps",
                    "Dumbbell Bicep Curls (Free Weights): 3 sets x 12 reps",
                    "Kettlebell Russian Twists: 3 sets x 20 reps"
                ],
                "Workout B: Lower Body & Kettlebells": [
                    "Smith Machine Squats: 3 sets x 10-12 reps",
                    "Kettlebell Goblet Squats: 3 sets x 12 reps",
                    "Dumbbell Lunges (Free Weights): 3 sets x 10 reps/leg",
                    "Cable Pull-throughs ( Low Pulley): 3 sets x 15 reps"
                ],
                "Workout C: Full Body Circuit": [
                    "Kettlebell Swings: 4 sets x 15 reps",
                    "Lat Pulldowns ( High Pulley): 3 sets x 12 reps",
                    "Push-ups (or modified on knees): 3 sets to failure",
                    "Dumbbell Step-ups (using a bench/box): 3 sets x 10 reps/leg"
                ],
                "Outdoor Integration": [
                    "2 Days of cardio (30-45 mins)",
                    "Moderate-paced hiking",
                    "Beginner-level mountain biking",
                    "Focus on steady breathing"
                ]
            }
        },
        "Q2: Hypertrophy (Muscle Building)": {
            "Focus": "Increasing volume to build lean muscle and raise metabolic rate. Rest: 45-60s.",
            "Workouts": {
                "Workout A: Push Day (Chest/Shoulders/Triceps)": [
                    "Flat Smith Machine Press: 4 sets x 8-10 reps",
                    "Seated Dumbbell Shoulder Press: 3 sets x 10 reps",
                    "Cable Crossovers ( Dual Pulleys): 3 sets x 12 reps",
                    "Overhead Tricep Extensions: 3 sets x 12 reps"
                ],
                "Workout B: Pull Day (Back/Biceps/Rear Delts)": [
                    "Lat Pulldowns ( High Pulley): 4 sets x 8-10 reps",
                    "Single-Arm Dumbbell Rows: 3 sets x 10 reps/arm",
                    "Straight Arm Cable Pulldowns: 3 sets x 12 reps",
                    "Cable Face Pulls: 3 sets x 15 reps"
                ],
                "Workout C: Leg Day": [
                    "Kettlebell Romanian Deadlifts (RDLs): 4 sets x 10 reps",
                    "Smith Machine Reverse Lunges: 3 sets x 10 reps/leg",
                    "Dumbbell Calf Raises: 4 sets x 15 reps",
                    "Kettlebell Swings: 3 sets x 20 reps"
                ],
                "Outdoor Integration": [
                    "1 Day of long distance hiking (60+ mins)",
                    "1 Day of interval mountain biking:",
                    "- Pedal hard for 2 minutes",
                    "- Coast for 1 minute"
                ]
            }
        },
        "Q3: Strength & Power": {
            "Focus": "Lifting heavier weights for fewer reps paired with explosive movements. Rest: 90-120s.",
            "Workouts": {
                "Workout A: Heavy Upper": [
                    "Smith Machine Bench Press: 4 sets x 5-8 reps",
                    "Heavy Cable Rows ( Low Pulley): 4 sets x 6-8 reps",
                    "Dumbbell Incline Press: 3 sets x 8 reps",
                    "Kettlebell Upright Rows: 3 sets x 10 reps"
                ],
                "Workout B: Heavy Lower": [
                    "Smith Machine Squats: 4 sets x 6-8 reps",
                    "Heavy Dumbbell Romanian Deadlifts: 4 sets x 8 reps",
                    "Smith Machine Calf Raises: 4 sets x 12 reps",
                    "Weighted Planks (plate on back): 3 x 45s"
                ],
                "Workout C: Power & Kettlebell Flow": [
                    "Single-Arm KB Snatches/Cleans: 3 sets x 8/arm",
                    "Kettlebell Swings: 4 sets x 15 reps",
                    "Cable Woodchoppers (Pulley): 3 sets x 10/side",
                    "Explosive Push-ups: 3 sets x 8 reps"
                ],
                "Outdoor Integration": [
                    "Hill Training Focus:",
                    "Find steepest local hiking trails",
                    "Power up the inclines hard",
                    "Recover fully on the descents"
                ]
            }
        },
        "Q4: Metabolic Conditioning": {
            "Focus": "Maximum calorie burn using non-stop back-to-back Supersets.",
            "Workouts": {
                "Workout A: Upper Body Supersets": [
                    "Superset 1: Smith Machine Press (10r) + Cable Rows (12r) [4 Rounds]",
                    "Superset 2: DB Lateral Raises (12r) + Lat Pulldowns (12r) [3 Rounds]",
                    "Superset 3: Cable Curls (15r) + Tricep Pushdowns (15r) [3 Rounds]"
                ],
                "Workout B: Lower Body Supersets": [
                    "Superset 1: Smith Squats (10r) + KB Swings (15r) [4 Rounds]",
                    "Superset 2: Walking Lunges (10r/leg) + Goblet Squats (12r) [3 Rounds]",
                    "Superset 3: Cable Pull-throughs (15r) + Plank (60s) [3 Rounds]"
                ],
                "Workout C:  & Bell AMRAP": [
                    "⏱️ 20-Minute AMRAP Session",
                    "Cycle continuously through:",
                    "- 10 Kettlebell Swings",
                    "- 10 Push-ups",
                    "- 10 Cable Face Pulls",
                    "- 10 Dumbbell Goblet Squats"
                ],
                "Outdoor Integration": [
                    "Rucking Focus:",
                    "Hike with weighted vest or pack (45 mins)",
                    "1 Day of fast-paced continuous biking"
                ]
            }
        }
    }

    # --- 5. LOGGING SIDEBAR (Ultra-Clean Input Only) ---
    st.sidebar.header("🏋️ Log a Session")
    
    # 📅 CALENDAR ENGINE
    current_month = datetime.date.today().month
    if current_month in [1, 2, 3]: current_quarter_name = "Q1: Foundation & Endurance"
    elif current_month in [4, 5, 6]: current_quarter_name = "Q2: Hypertrophy (Muscle Building)"
    elif current_month in [7, 8, 9]: current_quarter_name = "Q3: Strength & Power"
    else: current_quarter_name = "Q4: Metabolic Conditioning"

    st.sidebar.markdown("### 🗓️ Current Training Phase")
    quarter_options = [current_quarter_name, "Custom"]
    selected_q = st.sidebar.selectbox("Current Phase", options=quarter_options, index=0)
    
    date_input = st.sidebar.date_input("Date", datetime.date.today())
    
    # 🔄 DATA ROUTING ENGINE
    details_prefix = ""
    show_weight_box = False
    
    if selected_q != "Custom":
        # 🟢 INFO IS GONE: No more captions or info boxes cluttering up the sidebar panel
        selected_w = st.sidebar.selectbox("Select Session", list(ROUTINES[selected_q]["Workouts"].keys()))
        
        if "Outdoor Integration" in selected_w:
            cardio_type = st.sidebar.selectbox("Cardio Activity Performed", ["Mountain Biking", "Hiking", "Walking"])
            activity_value = cardio_type
            details_prefix = f"📋 [{selected_q} - Outdoor Integration] "
        else:
            activity_value = "Full Body Circuit"
            short_w_name = selected_w.split(":")[0]
            details_prefix = f"🏋️ [{selected_q} - {short_w_name}] "
    else:
        # 1. Choose the custom activity
        activity_value = st.sidebar.selectbox("Activity Type", ["Full Body Circuit", "Mountain Biking", "Hiking", "Walking", "Mobility / Stretching", "Body Weight Only"])
        if activity_value == "Body Weight Only":
            show_weight_box = True

    # 2. ⚖️ DYNAMIC WEIGHT DISPLAY (Strictly ONE box here)
    if show_weight_box:
        weight_input = st.sidebar.number_input("Body Weight (lbs)", value=0.0, step=0.1, min_value=0.0, key="body_weight_scale_input")
    else:
        weight_input = 0.0

    # 3. 📝 STRUCTURED LIFT TRACKING
    non_lifting_activities = ["Body Weight Only", "Mountain Biking", "Hiking", "Walking", "Mobility / Stretching"]
    show_lift_stats = activity_value not in non_lifting_activities

    structured_log = ""
    
    if show_lift_stats:
        st.sidebar.markdown("### 📝 Lift Tracking Stats")
        col_sets, col_reps, col_weight = st.sidebar.columns(3)
        with col_sets:
            input_sets = st.number_input("Sets", min_value=0, value=0, step=1, key="lift_sets")
        with col_reps:
            input_reps = st.number_input("Reps", min_value=0, value=0, step=1, key="lift_reps")
        with col_weight:
            input_weight_lifted = st.number_input("Weight", min_value=0.0, value=0.0, step=2.5, key="lift_weight")
            
        if input_sets > 0 or input_reps > 0 or input_weight_lifted > 0.0:
            structured_log = f"{input_sets} Sets | {input_reps} Reps | {input_weight_lifted} lbs "

    # 4. 📝 UNIVERSAL NOTES BOX
    extra_notes = st.sidebar.text_input("Notes", placeholder="Optional: e.g., Felt heavy, 10 miles...", key="lift_notes")

    # 5. 🔄 STRING ASSEMBLY
    if extra_notes.strip():
        user_details = f"{structured_log}- {extra_notes.strip()}" if structured_log else extra_notes.strip()
    else:
        user_details = structured_log.strip()
        
    final_details = f"{details_prefix}{user_details}" if details_prefix else user_details

    if st.sidebar.button("💾 Submit & Log Workout", type="primary", width='stretch'):
        if not user_details.strip() and "Outdoor" not in final_details:
            st.sidebar.warning("Please add some workout details before submitting!")
        else:
            with st.spinner("Syncing to cloud master sheets..."):
                try:
                    new_log = {
                        "User": user,
                        "Date": str(date_input),
                        "Activity": activity_value,
                        "Body Weight": float(weight_input),
                        "Details": final_details
                    }
                    new_row_df = pd.DataFrame([new_log])
                    log_df = pd.concat([log_df, new_row_df], ignore_index=True)
                    conn.update(data=log_df)
                    st.cache_data.clear()
                    st.sidebar.success("🔥 Workout Successfully Logged!")
                    st.rerun()
                except Exception as log_err:
                    st.sidebar.error(f"Failed to log entry: {log_err}")
    
    # ==========================================
    # ⚙️ SIDEBAR UTILITY FOOTER 
    # ==========================================
    st.sidebar.markdown("---")
    
    # 🔄 1. Public Log Out Button (Visible to everyone)
    if st.sidebar.button("🚪 Switch User / Log Out", width='stretch'):
        for key in list(st.session_state.keys()):
            if "live_garmin_client" in key or "garmin_token" in key:
                del st.session_state[key]
        
        # Resets the password gatekeeper keys
        st.session_state["password_correct"] = False
        st.session_state["logged_in_user"] = None
        st.session_state["user_role"] = None
        st.rerun()

    # 🟢 THE LOCK: Only hide the backend debugging tools from your family
    if role == "developer":
        
        # 🛠️ 2. Garmin Debugger Expander (Dev Only)
        with st.sidebar.expander("🛠️ Garmin System Debugger"):
            st.caption(f"**Connection Status:** `{garmin_status.upper()}`")
            st.caption(f"**Target Profile Prefix:** `{g_prefix}`")
            
            if st.button("🧹 Clear Garmin Data Cache", width='stretch'):
                try:
                    fetch_garmin_data_layer.clear()
                    st.success("Garmin cache cleared!")
                    st.rerun()
                except Exception as cache_err:
                    st.error(f"Cache clear failed: {cache_err}")
                    
            if "Raw" in daily_metrics:
                st.text_area("Raw JSON Stream", value=daily_metrics["Raw"], height=150, disabled=True)
            else:
                st.info("No raw diagnostic payload found.")

    # 🏷️ 3. Application Version Tag (Public)
    st.sidebar.caption(f"<div style='text-align: center; color: gray; padding-top: 10px;'>Our Fitness App v{APP_VERSION}</div>", unsafe_allow_html=True)

    # ==========================================
    # 📋 6. MAIN DASHBOARD TABS (Routing Fix)
    # ==========================================
    # Base tabs visible to EVERYONE (Changelog is public)
    tab_titles = [
        "📚 Training Blueprint", 
        "⚡ Daily Vitals", 
        "📈 Progress Charts", 
        "📋 History Log",
        "📢 What's New" 
    ]
    
    # ONLY append the Admin tab if running locally as a developer
    if role == "developer":
        tab_titles.append("🛠️ Admin Panel")
        
    # Generate the tabs based on the current user's role
    tabs = st.tabs(tab_titles)
    
    # Assign the first 5 public tabs
    tab1 = tabs[0] 
    tab2 = tabs[1] 
    tab3 = tabs[2] 
    tab4 = tabs[3] 
    tab_changelog = tabs[4] # 🟢 Maps perfectly to your recovered code
    
    # Default tab_admin to None so it doesn't crash for regular users
    tab_admin = None 
    
    # If developer, assign the 6th tab to tab_admin
    if role == "developer":
        tab_admin = tabs[5] # 🟢 Maps perfectly to your recovered code

    # ------------------------------------------
    # 📚 TAB 1: TRAINING BLUEPRINT
    # ------------------------------------------
    with tab1:
        st.subheader("🗓️ 12-Month Periodized Roadmap")
        st.write("---")
        
        # Premium Active Notification Banner
        st.info(f"📆 **Active Calendar Phase Focus:** {current_quarter_name}")
        
        # Render the macrocycle accordion cards
        for q_key, q_data in ROUTINES.items():
            is_active = (q_key == current_quarter_name)
            title_prefix = "🔥 CURRENT PHASE: " if is_active else "📌 "
            
            with st.expander(f"{title_prefix}{q_key}", expanded=is_active):
                st.markdown(f"🎯 **Macro Target:** *{q_data['Focus']}*")
                st.write("---")
                
                # Responsive 4-Column Exercise Layout
                cols = st.columns(4)
                for idx, (w_name, exercises) in enumerate(q_data["Workouts"].items()):
                    with cols[idx]:
                        st.markdown(f"✨ **{w_name.split(':')[0]}**")
                        st.caption(w_name.split(":")[-1].strip() if ":" in w_name else "")
                        for ex in exercises:
                            st.markdown(f"<div style='font-size: 13px; line-height: 1.4; margin-bottom: 4px;'>• {ex}</div>", unsafe_allow_html=True)
                            
        # Weekly Baseline Calendar Flow Reference
        st.markdown("### 🌲 Weekly Cross-Training Architecture")
        col_sch1, col_sch2 = st.columns(2)
        with col_sch1:
            st.markdown("""
            * **Monday:** 🏋️ Workout A (Strength / Split Focus)
            * **Tuesday:** 🚲 Mountain Biking / Hiking / Walking (Cardio, 30-45 mins)
            * **Wednesday:** 🏋️ Workout B (Strength / Split Focus)
            """)
        with col_sch2:
            st.markdown("""
            * **Thursday:** 🧘 Walk / Low-Intensity Cardio & Mobility Stretch
            * **Friday:** 🏋️ Workout C (Full Body / Circuit Integration)
            * **Saturday / Sunday:** 👨‍👩‍👧‍👦 Family Active Recovery & Full System Rest
            """)

    # ------------------------------------------
    # ⚡ TAB 2: DAILY VITALS
    # ------------------------------------------
    with tab2:
        st.subheader("📊 Live Health & Readiness Dashboard")
        
        battery = daily_metrics.get("Body Battery", 50)
        stress = daily_metrics.get("Stress", 25)
        s_score = daily_metrics.get("Sleep Score", "--")
        
        # Dynamic Premium Background Coaching Banners
        if battery >= 75 and stress < 30:
            st.markdown("""
            <div style="background-color: #1E293B; border-left: 6px solid #10B981; padding: 15px; border-radius: 6px; margin-bottom: 20px;">
                <h4 style="margin: 0; color: #34D399; font-weight: 600;">⚡ Daily Focus: Peak Training Window</h4>
                <p style="margin: 5px 0 0 0; color: #E2E8F0; font-size: 14px;">Your energy capacity is exceptional and stress overhead is low. Today is an ideal window to increase intensity, push your heavy lifting progressions, or strive for a personal milestone.</p>
            </div>
            """, unsafe_allow_html=True)
        elif battery < 40 or stress > 50:
            st.markdown("""
            <div style="background-color: #1E293B; border-left: 6px solid #F59E0B; padding: 15px; border-radius: 6px; margin-bottom: 20px;">
                <h4 style="margin: 0; color: #FBBF24; font-weight: 600;">🧘 Daily Focus: Active Recovery & Deload</h4>
                <p style="margin: 5px 0 0 0; color: #E2E8F0; font-size: 14px;">Nervous system battery is on the lower side or systemic stress tracking is elevated. Consider adjusting today's focus toward mobility work, lighter recovery pacing, or an intentional rest day to bounce back strong.</p>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div style="background-color: #1E293B; border-left: 6px solid #3B82F6; padding: 15px; border-radius: 6px; margin-bottom: 20px;">
                <h4 style="margin: 0; color: #60A5FA; font-weight: 600;">🏋️ Daily Focus: Baseline Training Flow</h4>
                <p style="margin: 5px 0 0 0; color: #E2E8F0; font-size: 14px;">Your recovery profile is steady and stable. You have plenty of standard fuel to train—stick to your structured working sets, maintain great mechanical form, and execute your planned progression.</p>
            </div>
            """, unsafe_allow_html=True)

        # Clean 8-Metric Card Grid Layout
        col1, col2, col3, col4 = st.columns(4)
        col5, col6, col7, col8 = st.columns(4)

        col1.metric("Steps Tracked", daily_metrics.get("Steps", "0"))
        col2.metric("Resting Heart Rate", f"{daily_metrics.get('RHR', 60)} bpm")
        col3.metric("Body Battery", f"{battery}/100")
        col4.metric("Stress Index", f"{stress}/100")
        
        col5.metric("Sleep Score", f"{s_score} pts" if s_score != "--" else "—")
        col6.metric("Total Daily Burn", f"{daily_metrics.get('Calories', '--')} kcal" if daily_metrics.get('Calories') != "--" else "—")
        col7.metric("Current Weight Scale", f"{daily_metrics.get('Weight', 0.0)} lbs" if daily_metrics.get('Weight', 0.0) > 0 else "—")
        col8.metric("Garmin Weight Goal", daily_metrics.get("Weight Goal", "—"))

    # ------------------------------------------
    # 📈 TAB 3: PROGRESS CHARTS
    # ------------------------------------------
    with tab3:
        st.subheader("📈 Exercise Performance Progression")
        if log_df.empty:
            st.info("No training data found in the cloud logs to plot yet.")
        else:
            lift_df = log_df[log_df["Activity"] == "Full Body Circuit"].copy()
            if not lift_df.empty:
                st.line_chart(data=lift_df, x="Date", y="Body Weight")
                st.caption("Historical weight performance data indexed across circuit sessions.")
            else:
                st.info("Log a few 'Full Body Circuit' sessions to light up your chart metrics!")

    # ------------------------------------------
    # 📋 TAB 4: HISTORY LOG
    # ------------------------------------------
    with tab4:
        st.subheader(f"{user}'s Training History")
        if not log_df.empty:
            user_history_df = log_df[log_df["User"] == user].sort_values(by="Date", ascending=False)
            if not user_history_df.empty:
                edited_df = st.data_editor(user_history_df, num_rows="dynamic", width='stretch', disabled=["User", "Date", "Activity", "Body Weight", "Details"], key="log_editor")
                if len(edited_df) < len(user_history_df):
                    if st.button("🔴 Confirm Deletion and Update Sheet", type="primary", width="stretch"):
                        other_users_df = log_df[log_df["User"] != user]
                        final_df = pd.concat([other_users_df, edited_df], ignore_index=True)
                        conn.update(data=final_df)
                        st.cache_data.clear()
                        st.success("Google Sheet Updated!")
                        st.rerun()
            else:
                st.info("No history found for this user.")

   # ==========================================
    # TAB 5: 📢 WHAT'S NEW (CHANGELOG)
    # ==========================================
    with tab_changelog:
        st.subheader("📢 What's New: Release Notes")
        st.write("") 
        try:
            conn_changelog = st.connection("gsheets_backlog", type=GSheetsConnection)
            df_changelog = conn_changelog.read(ttl=3600)
            
            if "Status" in df_changelog.columns:
                done_items = df_changelog[df_changelog["Status"] == "Done"].copy()
                if not done_items.empty:
                    if "Release Date" not in done_items.columns: done_items["Release Date"] = "Unknown Date"
                    if "Version" not in done_items.columns: done_items["Version"] = ""
                    
                    done_items["Release Date"] = done_items["Release Date"].fillna("Unknown Date").replace("", "Unknown Date")
                    done_items["Version"] = done_items["Version"].fillna("").replace("nan", "")
                    done_items = done_items.sort_values(by="Release Date", ascending=False)
                    
                    unique_dates = done_items["Release Date"].unique()
                    recent_dates = unique_dates[:3]
                    older_dates = unique_dates[3:]
                    
                    def render_release_group(group_df, date_str):
                        v_string = group_df["Version"].iloc[0] if "Version" in group_df.columns and str(group_df["Version"].iloc[0]).strip() != "" else ""
                        header_ext = f" | v{v_string}" if v_string else ""
                        st.markdown(f"### 🚀 Update: {date_str}{header_ext}")
                        
                        for _, row in group_df.iterrows():
                            task = row.get("Task / Feature", row.get("Task", row.get("Feature", ""))) or "System Update"
                            category = str(row.get("Category", "General")).strip()
                            cat_lower = category.lower()
                            
                            if "bug" in cat_lower or "fix" in cat_lower: emoji = "🐛"
                            elif "ui" in cat_lower or "design" in cat_lower or "clean" in cat_lower: emoji = "🎨"
                            elif "integrat" in cat_lower or "api" in cat_lower or "garmin" in cat_lower: emoji = "🔌"
                            elif "feature" in cat_lower or "new" in cat_lower: emoji = "✨"
                            else: emoji = "📌"

                            public_msg = row.get("Public Message", "")
                            if pd.isna(public_msg) or str(public_msg).strip() == "":
                                public_msg = "Under-the-hood improvements and bug fixes."
                                
                            st.markdown(f"**{emoji} [{category}] {task}**")
                            st.caption(f"&emsp; *{public_msg}*")
                            st.write("") 
                        st.divider()

                    for r_date in recent_dates:
                        group = done_items[done_items["Release Date"] == r_date]
                        render_release_group(group, r_date)
                    
                    if len(older_dates) > 0:
                        with st.expander("🕰️ View Older Updates"):
                            for o_date in older_dates:
                                group = done_items[done_items["Release Date"] == o_date]
                                render_release_group(group, o_date)
                else:
                    st.info("No completed features in the backlog yet. Updates are coming soon!")
            else:
                st.warning("Could not find the 'Status' column in the backlog.")
        except Exception as e:
            st.error("Could not load the changelog at this time.")

    # ==========================================
    # TAB 6: 🛠️ ADMIN PANEL (DEVELOPERS ONLY)
    # ==========================================
    if tab_admin is not None:
        with tab_admin:
            st.subheader("🛠️ Developer Admin Panel")
            try:
                conn_backlog = st.connection("gsheets_backlog", type=GSheetsConnection)
                df_backlog = conn_backlog.read()
                
                for col in ["Public Message", "Release Date", "Version"]:
                    if col not in df_backlog.columns: df_backlog[col] = ""
                    df_backlog[col] = df_backlog[col].astype(str).replace("nan", "")
                
                if "Status" in df_backlog.columns:
                    cols = ["Status"] + [col for col in df_backlog.columns if col != "Status"]
                    df_backlog = df_backlog[cols]
                    df_display = df_backlog[df_backlog["Status"] != "Done"]
                else:
                    df_display = df_backlog
                
                st.write("Manage Active App Backlog & QoL Features:")
                edited_backlog = st.data_editor(
                    df_display, num_rows="dynamic", width="stretch", key="admin_backlog_editor",
                    column_config={
                        "Status": st.column_config.SelectboxColumn("Status", width="medium", options=["Backlog", "In Progress", "Blocked", "Done"], required=True),
                        "Public Message": st.column_config.TextColumn("Public Message", width="large"),
                        "Release Date": st.column_config.TextColumn("Release Date", disabled=True),
                        "Version": st.column_config.TextColumn("Version", disabled=True)
                    }
                )
                
                st.write("")
                col_btn1, col_btn2 = st.columns([1, 4])
                with col_btn1:
                    push_version = st.text_input("Release Version", value=APP_VERSION)
                with col_btn2:
                    st.write("") 
                    push_clicked = st.button("💾 Push Updates to Google Sheets", type="primary", width="stretch")
                
                if push_clicked:
                    today_str = str(datetime.date.today())
                    for col in ["Release Date", "Version"]:
                        if col not in edited_backlog.columns: edited_backlog[col] = ""
                    
                    mask_done = edited_backlog["Status"] == "Done"
                    edited_backlog.loc[mask_done & ((edited_backlog["Release Date"].isna()) | (edited_backlog["Release Date"] == "")), "Release Date"] = today_str
                    edited_backlog.loc[mask_done & ((edited_backlog["Version"].isna()) | (edited_backlog["Version"] == "")), "Version"] = push_version

                    if "Status" in df_backlog.columns:
                        df_done_archived = df_backlog[df_backlog["Status"] == "Done"]
                        final_df_to_push = pd.concat([edited_backlog, df_done_archived], ignore_index=True)
                    else:
                        final_df_to_push = edited_backlog
                        
                    conn_backlog.update(data=final_df_to_push)
                    st.success(f"✅ Version {push_version} successfully synced to the cloud!")
                    st.cache_data.clear()
                    st.rerun()
            except Exception as e:
                st.error(f"Failed to load the backlog. System Error: {e}")