# --- 1. APP CONFIGURATION & IMPORTS ---
import streamlit as st
import pandas as pd
import datetime
import plotly.express as px
import hashlib 
import re

# 🟢 NEW: Put the Google GenAI types right here!
from google.genai import types

# 🛑 1. PAGE CONFIG MUST BE FIRST
st.set_page_config(
    page_title="Get Fit Together",
    page_icon="💪",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 🟢 Add this near your other config variables
BODYWEIGHT_ONLY_EXERCISES = [
    "Push-ups", "Push-ups (or modified on knees)", "Plank", "Suspended Planks", "Atomic Push-ups",
    # TRX Suspension Mastery
    "TRX Chest Press (Straps Fully Lengthened)", "TRX Low Rows (Straps Fully Shortened)", "TRX Tricep Extensions (Mid-Length)", 
    "TRX Bicep Curls (Mid-Length)", "TRX Y-Flys (Mid-Length)", "TRX Pistol Squats (Mid-Length)", 
    "TRX Bulgarian Split Squats (Mid-Calf)", "TRX Suspended Hamstring Curls (Mid-Calf)", "TRX Glute Bridges (Mid-Calf)", 
    "TRX Jump Squats (Mid-Length)", "TRX Atomic Push-ups (Mid-Calf)", "TRX Suspended Pikes (Mid-Calf)", 
    "TRX Mountain Climbers (Mid-Calf)", "TRX Suspended Planks (Mid-Calf)", "TRX Side Planks (Feet in Cradles)",
    # TRX Rip Trainer Power
    "TRX Rip Strike (Zone 1 Anchor)", "TRX Rip Pitchfork (Zone 1 Anchor)", "TRX Rip Sweep (Zone 1 Anchor)", 
    "TRX Rip Torso Rotation (Zone 2 Anchor)", "TRX Rip Kayak (Zone 2 Anchor)", "TRX Rip Chest Press (Zone 2 Anchor)", 
    "TRX Rip Row (Zone 2 Anchor)", "TRX Rip Tricep Extension (Zone 2 Anchor)", "TRX Rip Bicep Curl (Zone 2 Anchor)", 
    "TRX Rip Overhead Press (Zone 1 Anchor)", "TRX Rip Squat Row (Zone 2 Anchor)", "TRX Rip Lunge Chest Press (Zone 2 Anchor)", 
    "TRX Rip Jump Squat (Zone 2 Anchor)", "TRX Rip Windmill (Zone 1 Anchor)", "TRX Rip Drag (Zone 1 Anchor)"
]

# 🛑 2. IMPORT CUSTOM MODULES
# 🟢 Bring in central time
from zoneinfo import ZoneInfo
# 🟢 Bring in the login module!
from auth import check_password
# 🟢 Bring in the database automation helpers AND the Supabase client!
from database import check_and_bulk_log_garmin_weight, check_and_autolog_garmin_weight, get_user_history_df, log_manual_entry, supabase, log_daily_garmin_metrics, get_recent_garmin_metrics, save_coach_message, get_todays_chat, clear_todays_chat, ai_log_workout_set, ai_update_dossier, get_all_time_prs, get_user_profile
# 🟢 Put in the AI COACH!
from ai_coach import init_coach_chat
# 🟢 Bring in the static workout database!
from workouts import ROUTINES
# 🟢 Bring in the utility functions!
from utils import calculate_next_version, get_youtube_embed_url, safe_int_convert

# 🟢 3. APP VERSIONING
APP_VERSION = "2.1.0"
st.session_state["APP_VERSION"] = APP_VERSION

# ==========================================
# 🛠️ STATIC UI STYLESHEET (Runs instantly)
# ==========================================
st.markdown("""
    <style>
    /* Hides the "Press Enter to submit form" text globally */
    div[data-testid="InputInstructions"] { display: none !important; }

    /* Hides the standard web browser number arrows */
    input[type=number]::-webkit-inner-spin-button,
    input[type=number]::-webkit-outer-spin-button { -webkit-appearance: none; margin: 0; }

    /* Hides Streamlit's custom +/- buttons */
    [data-testid="stNumberInputStepUp"] { display: none !important; }
    [data-testid="stNumberInputStepDown"] { display: none !important; }

    /* Hide toolbar buttons: Share, Edit, GitHub, Favorite, Hamburger menu */
    header [data-testid="stToolbarActionButton"] { display: none !important; }
    header button[kind="secondary"] { display: none !important; }
    header button[aria-label*="menu"] { display: none !important; }

    /* Make the header bar transparent */
    header { background-color: transparent !important; }
    header > div { background-color: transparent !important; }

    /* Ensure sidebar toggle remains visible */
    [data-testid="stSidebarCollapsedControl"] { display: block !important; visibility: visible !important; }
    button[aria-label*="collapse"] { display: block !important; visibility: visible !important; }
    button[aria-label*="expand"] { display: block !important; visibility: visible !important; }
    </style>
""", unsafe_allow_html=True)

# --- 2. ENVIRONMENT DETECTION & PASSWORD SYSTEM ---
if check_password():

    # --- 3. DYNAMIC METADATA & COLOR THEMING ---
    user = st.session_state["logged_in_user"]
    role = st.session_state["user_role"]
    
    # ==========================================
    # 🎨 DYNAMIC THEME STYLESHEET (Runs AFTER login)
    # ==========================================
    # Now that check_password() has run, these variables will successfully find your database colors!
    page_bg_color = st.session_state.get("primary_color", "#1F2937")
    side_bg = st.session_state.get("sidebar_color", "#111827")
    chart_line_color = st.session_state.get("line_color", "#34D399")
    g_prefix = (st.session_state.get("garmin_prefix") or "").lower()

    # Notice we use the f-string (f""") and double brackets {{ }} here!
    st.markdown(f"""
        <style>
        .stApp {{ background-color: {page_bg_color} !important; color: white; }}
        [data-testid="stSidebar"] {{ background-color: {side_bg} !important; opacity: 1 !important; }}
        .stTabs [data-baseweb="tab"] {{ color: white !important; }}
        </style>
    """, unsafe_allow_html=True)
    
    # 📡 THE BUG RADAR (Only alerts if you are the developer)
    if role == "developer":
        try:
            # 🟢 SUPABASE FIX: Direct query, no dataframes needed
            radar_response = supabase.table("backlog").select("*").eq("category", "Bug").eq("status", "Backlog").execute()
            bug_count = len(radar_response.data) if radar_response.data else 0
            
            if bug_count > 0:
                # 🟢 CUSTOM ALERT STYLING (Yellow text, No background)
                st.markdown(
                    f"""
                    <div style='background-color: transparent; margin-bottom: 15px;'>
                        <h4 style='color: #facc15; margin: 0px;'>
                            🐞 Developer Alert: You have {bug_count} unresolved bug report(s) waiting in the Admin Panel.
                        </h4>
                    </div>
                    """, 
                    unsafe_allow_html=True
                )
        except Exception:
            pass # Fails silently so it doesn't interrupt your workout logging

    # --- 4. ENVIRONMENT & SUPABASE CONNECTION ---
    # 🟢 THE FIX: We now pull the environment directly from your secrets.toml
    env = st.secrets.get("app_config", {}).get("environment", "production")
    is_local_env = (env == "local")

    if is_local_env:
        # 🟢 CUSTOM ALERT STYLING
        st.markdown(
            """
            <div style="background-color: #fef08a; padding: 12px; border-radius: 8px; margin-bottom: 20px; border: 1px solid #facc15;">
                <h3 style="color: #b91c1c; margin: 0px; text-align: center;">
                    🚧 DEV MODE ACTIVE: Connected to Supabase DEV Database
                </h3>
            </div>
            """, 
            unsafe_allow_html=True
        )

    if role == "developer" and is_local_env:
        st.title(f"💪 Developer Sandbox: {user}")
    else:
        st.title(f"💪 Get Fit Together: {user}'s Session")

    # 🟢 THE READ-ONLY LOCK FLAG
    database_locked = False
    
    try:
        # 🟢 THE FIX: Fetch directly from Supabase! No more Google Sheets here.
        log_df = get_user_history_df(user)
        
        if not log_df.empty:
            log_df['Date'] = log_df['Date'].astype(str)
            # Ensure the User column exists for your downstream pandas logic
            if 'User' not in log_df.columns:
                log_df['User'] = user 
    except Exception as db_err:
        print(f"⚠️ DATABASE READ FAILED: {db_err}")
        database_locked = True 
        log_df = pd.DataFrame(columns=["User", "Date", "Activity", "Body Weight", "Details"])
        st.error("⚠️ Cloud Database Sync Failed. The app is in Read-Only mode to protect your data. Please refresh.")
        
    # ==========================================
    # 🟢 NEW GARMIN INITIALIZATION (STANDBY MODE)
    # ==========================================
    try:
        from garminconnect import Garmin 
        from garmin_api import fetch_garmin_data_layer
        from zoneinfo import ZoneInfo
        import datetime
        
        tz = ZoneInfo("America/Chicago")
        today = datetime.datetime.now(tz).date().isoformat()

        garmin_section = "garmin_dev" if is_local_env else "garmin_prod"

        # Build identity keys using the safely defined prefix
        g_email = st.secrets[garmin_section].get(f"{g_prefix}_email", "")
        g_pass  = st.secrets[garmin_section].get(f"{g_prefix}_pass", "")

        cache_id = f"{g_prefix}:{user}:{today}"
        
        # Initialize default standby data (Fast Boot!)
        if "garmin_status" not in st.session_state:
            # 🟢 Check the database for today's data first!
            recent_db_metrics = get_recent_garmin_metrics(user, limit=1)
            
            if not recent_db_metrics.empty and str(recent_db_metrics.iloc[0]["Date"]) == today:
                db_row = recent_db_metrics.iloc[0]
                st.session_state["garmin_status"] = "Loaded from Cloud"
                st.session_state["daily_metrics"] = {
                    "Steps": db_row.get("Steps", "0"),
                    "RHR": db_row.get("RHR", 60),
                    "Body Battery": db_row.get("Body_Battery", 50),
                    "Stress": db_row.get("Stress", "--"),
                    "Calories": db_row.get("Calories", "--"),
                    "HRV": db_row.get("HRV", "--"),
                    "Sleep Score": db_row.get("Sleep_Score", "--"),
                    "Weight": 0.0, # Your existing smart weight logic handles this below
                    "Weight Goal": "--",
                    "Weight_History": [],
                    "Raw": "Loaded from Database"
                }
            else:
                st.session_state["garmin_status"] = "Standby Mode"
                st.session_state["daily_metrics"] = {
                    "Steps": "0", "RHR": 60, "Body Battery": 50, "Stress": "--",
                    "Calories": "--", "HRV": "--", "Sleep Score": "--",
                    "Weight": 0.0, "Weight Goal": "--", "Weight_History": [],
                    "Raw": "Standby Mode Active"
                }
            
        if "daily_metrics" not in st.session_state:
            st.session_state["daily_metrics"] = {
                "Steps": "0", "RHR": 60, "Body Battery": 50, "Stress": "--",
                "Calories": "--", "HRV": "--", "Sleep Score": "--",
                "Weight": 0.0, "Weight Goal": "--", "Weight_History": [],
                "Raw": "Standby Mode Active"
            }
            
        garmin_status = st.session_state["garmin_status"]
        daily_metrics = st.session_state["daily_metrics"]

    except Exception as init_err:
        garmin_status = "missing_secrets"
        daily_metrics = {
            "Steps": "0", "RHR": 60, "Body Battery": 50, "Stress": "--",
            "Calories": "--", "HRV": "--", "Sleep Score": "--",
            "Weight": 0.0, "Weight Goal": "--", "Weight_History": [],
            "Raw": f"Init Error: {init_err}"
        }

    # ==========================================
    #  ⚡ SIDEBAR: Vitals
    # ==========================================
    st.sidebar.header("⚡ Vitals")
    
    # 🟢 THE VARIABLE FIX: Fetch the goal weight EARLY so the metrics can use it
    # 1. Fetch from our new Long-Term Memory table instead of the old users table!
    early_profile = get_user_profile(user)
    db_goal = float(early_profile.get("goal_weight", 0) or 0)
    
    # 2. Check if the AI or UI just updated the global state. If not, set it using the DB.
    if "global_goal_weight" not in st.session_state:
        st.session_state["global_goal_weight"] = db_goal
        
    # 3. Lock in the current goal for the metrics to use!
    current_goal = st.session_state["global_goal_weight"]

    # 🟢 GARMIN AUTO-FETCH & MANUAL TRIGGER
    with st.sidebar.container(border=True):
        status_color = "green" if st.session_state["garmin_status"] == "Active & Synced" else "orange"
        st.markdown(f"**Garmin:** :{status_color}[{st.session_state['garmin_status']}]")
        
        # Check if we have today's metrics in the DB to avoid unnecessary daily fetching
        needs_auto_fetch = False
        
        # ONLY calculate auto-fetch if we are in Production! 
        # In DEV (is_local_env), this stays False, forcing you to use the manual button
        if not is_local_env and st.session_state["garmin_status"] == "Standby Mode":
            recent_db_metrics = get_recent_garmin_metrics(user, limit=1)
            if recent_db_metrics.empty or str(recent_db_metrics.iloc[0]["Date"]) != today:
                needs_auto_fetch = True

        fetch_clicked = st.button("🚀 Fetch Latest Garmin Data", type="primary", use_container_width=True)
        
        if fetch_clicked or needs_auto_fetch:
            with st.spinner("Syncing Garmin Data..." if fetch_clicked else "Auto-syncing Daily Garmin..."):
                try:
                    client_instance = Garmin(g_email, g_pass)
                    client_instance.login()
                    fresh_metrics = fetch_garmin_data_layer(today, cache_id, client_instance)
                    st.session_state["daily_metrics"] = fresh_metrics
                    st.session_state["garmin_status"] = "Active & Synced"
                    
                    # Log the daily metrics to the database
                    log_daily_garmin_metrics(user, today, fresh_metrics)
                    
                    history_list = fresh_metrics.get("Weight_History", [])
                    if history_list and not database_locked:
                        check_and_bulk_log_garmin_weight(user_name=user, weight_history_list=history_list)
                        st.session_state["force_db_refresh"] = True 
                    st.rerun() 
                except Exception as e:
                    st.session_state["garmin_status"] = f"Error: {e}"
                    if fetch_clicked: # Only rerun on error if they manually clicked it
                        st.rerun()

    st.sidebar.write("") # Quick Spacer
    
    # 🟢 SIDEBAR METRICS - SAFE CONVERSION
    # 1. Grab raw metrics
    metrics = st.session_state["daily_metrics"]
    battery_raw = metrics.get("Body Battery", 50)
    stress_raw = metrics.get("Stress", 25)
    s_score = metrics.get("Sleep Score", "--")
    
    # 🟢 FIX #2: Use safe conversion that handles "60.5", "--", None, etc.
    battery = safe_int_convert(battery_raw, default=50)
    stress = safe_int_convert(stress_raw, default=25)
    
    # 2. SMART WEIGHT LOGIC
    display_weight = 0.0
    if not log_df.empty and "User" in log_df.columns:
        user_weight_df = log_df[log_df["User"] == user].copy()
        user_weight_df["Body Weight"] = pd.to_numeric(user_weight_df["Body Weight"], errors="coerce")
        valid_weights = user_weight_df.dropna(subset=["Body Weight"])
        valid_weights = valid_weights[valid_weights["Body Weight"] > 0]
        
        if not valid_weights.empty:
            valid_weights = valid_weights.sort_values(by="Date", ascending=True)
            display_weight = float(valid_weights.iloc[-1]["Body Weight"])
    
    if display_weight == 0.0:
        display_weight = metrics.get('Weight', 0.0)

    # 3. SIDEBAR METRICS GRID (Sleek 2-column layout)
    col1, col2 = st.sidebar.columns(2)
    col1.metric("Steps", metrics.get("Steps", "0"))
    col2.metric("Burn (kcal)", metrics.get("Calories", "--"))
    
    col3, col4 = st.sidebar.columns(2)
    col3.metric("Battery", f"{battery}/100")
    col4.metric("Stress", f"{stress}/100")
    
    col5, col6 = st.sidebar.columns(2)
    col5.metric("Sleep (pts)", s_score if s_score != "--" else "—")
    col6.metric("RHR (bpm)", metrics.get("RHR", 60))
    
    col7, col8 = st.sidebar.columns(2)
    col7.metric("Weight (lbs)", display_weight if display_weight > 0 else "—")
    col8.metric("Goal (lbs)", current_goal)
    
    # 🟢 THE FIX: Define the reset_id globally BEFORE the bug reporter needs it!
    if "form_reset" not in st.session_state:
        st.session_state["form_reset"] = 0
    reset_id = st.session_state["form_reset"]

    # ==========================================
    # ⚙️ PERSONAL SETTINGS 
    # ==========================================
    st.sidebar.divider()

    # --- SIDEBAR: UNIFIED USER DOSSIER ---
    with st.sidebar.expander("⚙️ My Fitness Profile", expanded=False):
        # 🟢 THE FIX: We explicitly define the user and fetch the data right here!
        active_user = st.session_state["username"] 
        user_profile = get_user_profile(active_user)
        
        # Safely extract the variables
        current_goal_weight = float(user_profile.get("goal_weight", 0) or 0)        
        primary_goal = user_profile.get("primary_goal", "General Fitness")
        current_age = int(user_profile.get("age", 30) or 30)
        current_phase = user_profile.get("current_phase", "Phase 1: Foundation & Endurance")
        equipment = user_profile.get("available_equipment", "Full Gym")
        injuries = user_profile.get("nagging_injuries", "None")

        # 🟢 GLOBAL SYNC: Broadcast this weight so Tab 3 and Garmin Vitals can see it!
        st.session_state["global_goal_weight"] = current_goal_weight
        
        # The UI Elements
        col1, col2 = st.columns(2)
        with col1:
            new_age = st.number_input("Age", min_value=10, max_value=120, value=current_age, step=1)
        with col2:
            new_goal = st.number_input("Goal Weight (lbs)", min_value=0.0, value=current_goal_weight, step=1.0)

        new_primary_goal = st.text_area("Primary Focus / Goals", value=primary_goal, height=68)
        
        # 🟢 NEW: The expanded, bulletproof phase selector
        phase_options = [
            "Phase 1: Foundation & Endurance", 
            "Phase 2: Hypertrophy (Muscle Building for Fat Loss)", 
            "Phase 3: Strength & Power", 
            "Phase 4: Metabolic Conditioning",
            "Open Gym: Free Form Training"
        ]
        
        phase_prefix = current_phase.split(":")[0] if current_phase else "Phase 1"
        try:
            default_index = ["Phase 1", "Phase 2", "Phase 3", "Phase 4", "Open Gym"].index(phase_prefix)
        except ValueError:
            default_index = 0

        new_phase = st.selectbox("Current Phase", phase_options, index=default_index)
        
        new_equip = st.text_area("Available Equipment", value=equipment, height=68)
        new_injuries = st.text_area("Nagging Injuries", value=injuries, height=68)
        
        if st.button("Save Profile", use_container_width=True):
            try:
                supabase.table("gym_user_profiles").upsert({
                    "username": active_user,
                        "age": new_age,
                        "primary_goal": new_primary_goal,
                        "current_phase": new_phase,
                        "available_equipment": new_equip,
                        "nagging_injuries": new_injuries,
                        "goal_weight": new_goal,
                        "updated_at": datetime.datetime.now(ZoneInfo("America/Chicago")).isoformat()
                }).execute()
                st.success("Profile Updated!")
                st.rerun() 
            except Exception as e:
                st.error(f"Failed to update: {e}")

    st.sidebar.divider() 

    # ==========================================
    # ⚙️ SIDEBAR UTILITY FOOTER 
    # ==========================================

    # 🟢 THE PANIC BUTTON (Now with Role-Based Categories!)
    with st.sidebar.expander("🐛 Report an Issue"):
        # Wrap in a form so it clears instantly on submit
        with st.form(key=f"bug_report_{reset_id}", clear_on_submit=True):
            st.caption("Did something break or do you have an idea? Tell the developer!")
            
            # 1. DYNAMIC CATEGORY LOGIC
            if role == "developer":
                issue_categories = ["Bug", "UI", "Core", "Ops"]
            else:
                issue_categories = ["Bug", "UI"]
                
            selected_category = st.selectbox("Type of Issue", options=issue_categories)
            
            # 2. THE TEXT INPUT
            bug_text = st.text_area("What happened?", placeholder="e.g., The cardio duration box isn't showing up.")
            submit_bug = st.form_submit_button("📤 Send to Developer", type="secondary", use_container_width=True)
            
            # 3. SUBMISSION ENGINE
            if submit_bug:
                if not bug_text.strip():
                    st.warning("Please type a message first.")
                else:
                    with st.spinner("Sending..."):
                        try:
                            # We inject your selected_category right into the payload
                            supabase.table("backlog").insert({
                                "status": "Backlog",
                                "category": selected_category,
                                "feature": f"User Reported: {user}",
                                "priority": "High",
                                "notes": bug_text.strip()
                            }).execute()
                            
                            st.success("✅ Sent! Thanks for the feedback.")
                        except Exception as bug_err:
                            st.error(f"Failed to send: {bug_err}")

    # 🔒 THE DEV LOCK: Only show the backend debugging tools to developers
    if role == "developer":
        
        # 🛠️ Garmin Debugger Expander (Dev Only)
        with st.sidebar.expander("🛠️ Garmin System Debugger"):
            st.caption(f"**Connection Status:** `{garmin_status.upper()}`")
            st.caption(f"**Target Profile Prefix:** `{g_prefix}`")
            
            if st.button("🧹 Reset Garmin Session", width='stretch'):
                st.session_state["garmin_status"] = "Standby Mode"
                st.session_state["daily_metrics"] = {
                    "Steps": "0", "RHR": 60, "Body Battery": 50, "Stress": "--",
                    "Calories": "--", "HRV": "--", "Sleep Score": "--",
                    "Weight": 0.0, "Weight Goal": "--", "Weight_History": [],
                    "Raw": "Session Reset"
                }
                
                # Nuke the API cache if it's currently stored in memory
                if "fetch_garmin_data_layer" in globals():
                    try:
                        fetch_garmin_data_layer.clear()
                    except:
                        pass
                        
                st.success("Session & Cache reset!")
                st.rerun()
                
            if "Raw" in daily_metrics:
                st.text_area("Raw JSON Stream", value=daily_metrics["Raw"], height=150, disabled=True)
            else:
                st.info("No raw diagnostic payload found.")
        
    # 🔄 Public Log Out Button
    if st.sidebar.button("🚪 Switch User / Log Out", use_container_width=True):
        
        # Completely nuke the session state
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        
        st.query_params.clear() 
        st.rerun()

    # 🏷️ Application Version Tag (Public)
    st.sidebar.caption(f"<div style='text-align: center; color: gray; padding-top: 10px;'>Get Fit Together v{APP_VERSION}</div>", unsafe_allow_html=True)

    # ==========================================
    # 📋 6. MAIN DASHBOARD TABS (Routing Fix)
    # ==========================================
    # Base tabs visible to EVERYONE
    tab_titles = [
        "🤖 AI Coach", 
        "🏋️ Log a Session",
        "📈 Progress Charts",
        "📚 Training Blueprint",
        "📢 What's New"
    ]

    # ONLY append the Admin tab if running locally AND you are a developer
    if role == "developer" and is_local_env:
        tab_titles.append("🛠️ Admin Panel")
        
    # Generate the tabs based on the current user's role/location
    tabs = st.tabs(tab_titles)

    # Assign the first 4 public tabs
    tab1 = tabs[0]
    tab2 = tabs[1]
    tab3 = tabs[2]
    tab4 = tabs[3]

    # Assign What's New tab
    tab_changelog = tabs[4]
    tab_idx = 5

    # Assign Admin tab if developer and local
    tab_admin = None
    if role == "developer" and is_local_env:
        tab_admin = tabs[tab_idx]

    # ------------------------------------------
    # 🤖 TAB 1: AI COACH
    # ------------------------------------------
    with tab1:
        # 🛑 THE STRICT GATEKEEPER
        # This must be the absolute first thing in the tab, outside of any other loops!
        if "username" not in st.session_state:
            st.error("Authentication required. Please log in.")
            st.stop() # Halts the entire app right here!
            
        # Grab the verified name once to use everywhere below
        active_user = st.session_state["username"]

        col_c1, col_c2 = st.columns([4, 1], vertical_alignment="bottom")
        with col_c1:
            st.subheader(f"🧠 Coach's Corner")
        with col_c2:
            # A quick way to wipe the memory and start over!
            if st.button("🧹 Clear Chat", use_container_width=True): 
                active_user = st.session_state["username"]
                clear_todays_chat(active_user)
                if "coach_chat" in st.session_state:
                    del st.session_state["coach_chat"]
                if "chat_messages" in st.session_state:
                    del st.session_state["chat_messages"]
                st.rerun()

        # ==========================================
        # 🚀 THE UNIFIED WAKE UP SEQUENCE
        # ==========================================
        if "coach_chat" not in st.session_state or "chat_messages" not in st.session_state:
            with st.spinner("Waking up Coach"):
                
                # --- 1. INITIALIZE THE AI BRAIN ---
                recent_workouts = log_df[log_df["User"] == user].sort_values(by="Date", ascending=False).head(14) if not log_df.empty else pd.DataFrame()
                recent_vitals = get_recent_garmin_metrics(user, limit=14)
                if not recent_vitals.empty:
                    recent_vitals = recent_vitals.drop(columns=["id", "User"], errors="ignore")
                
                # --- NEW: Fetch All-Time PRs dynamically ---
                all_prs = get_all_time_prs(user)
                
                # Format the top heavy lifts for the AI to know about
                pr_text = "All-Time PRs: "
                if all_prs:
                    # Let's hand the AI your Big 3. If you have them, it will help it calibrate your strength level and make better workout suggestions!
                    for lift_name, max_weight in all_prs.items():
                        if any(key in lift_name for key in ["Press", "Squat", "Deadlift"]):
                            pr_text += f"{lift_name}: {max_weight} lbs | "
                else:
                    pr_text += "No PRs established yet."
                
                # ==========================================
                # 🟢 NEW: Fetch the User Dossier (Long Term Memory)
                # ==========================================
                user_profile = get_user_profile(user)
                current_phase = user_profile.get("current_phase", "Phase 1: Foundation & Endurance")
                equipment = user_profile.get("available_equipment", "Full Gym")
                injuries = user_profile.get("nagging_injuries", "None")
                
                # Catch the new telephone line (Now with Dossier!)
                coach_client, chat_session, error = init_coach_chat(
                    user, 
                    current_goal, 
                    recent_workouts, 
                    recent_vitals, 
                    pr_text,
                    current_phase, 
                    equipment,     
                    injuries,      
                    primary_goal,  
                    current_age
                )
                
                if error:
                    st.error(error)
                else:
                    st.session_state["coach_client"] = coach_client 
                    st.session_state["coach_chat"] = chat_session
                    
                    # --- 2. CHECK THE DATABASE ---
                    active_user = st.session_state["username"]
                    db_history = get_todays_chat(active_user)
                    
                    if db_history and len(db_history) > 0:
                        # A. Load the visual UI memory
                        st.session_state["chat_messages"] = [
                            {
                                "role": msg["role"],
                                "content": msg["content"],
                                "visuals": msg.get("visuals"),
                                "video_url": msg.get("video_url")
                            } for msg in db_history
                        ]
                        
                        # 🟢 PYLANCE FIX: Grab the phase locally so your IDE stops showing red text!
                        active_user = st.session_state["username"]
                        local_profile = get_user_profile(active_user)
                        active_phase = local_profile.get("current_phase", "Phase 1: Foundation & Endurance")
                        
                        # B. Inject the memories into the AI's internal brain!
                        ai_history = []
                        for msg in db_history:
                            ai_role = "user" if msg["role"] == "user" else "model"
                            
                            # 🟢 THE GOOGLE API FIX: Remind it of the phase!
                            if len(ai_history) == 0 and ai_role == "model":
                                ai_history.append({"role": "user", "parts": [f"Analyze my Garmin vitals and generate my Daily Briefing. My current training phase is: {active_phase}."]})
                                
                            ai_history.append({"role": ai_role, "parts": [msg["content"]]})
                        
                        try:
                            # Safely load the history into the AI's context window
                            st.session_state["coach_chat"].history = ai_history
                        except Exception as e:
                            print(f"History Injection Warning: {e}")
                            
                    else:
                        # --- 3. BRAND NEW DAY ---
                        st.session_state["chat_messages"] = []
                        
                        # Trigger the Epic Daily Briefing on the first boot!
                        try:
                            # 🟢 PYLANCE FIX: Grab the phase locally here too!
                            active_user = st.session_state["username"]
                            local_profile = get_user_profile(active_user)
                            active_phase = local_profile.get("current_phase", "Phase 1: Foundation & Endurance")
                            
                            # 🟢 WAKE UP PROMPT FIX: Both lines safely bound together!
                            wake_up_prompt = f"Analyze my Garmin vitals and generate my personalized Daily Briefing. My current training phase is: {active_phase}."
                            briefing_response = st.session_state["coach_chat"].send_message(wake_up_prompt)
                            
                            epic_greeting = briefing_response.text
                            
                            st.session_state["chat_messages"].append({"role": "assistant", "content": epic_greeting})
                            save_coach_message(active_user, "assistant", epic_greeting)
                        except Exception as e:
                            fallback = "Good morning! Ready to crush today's workout?"
                            st.session_state["chat_messages"].append({"role": "assistant", "content": fallback})
                            save_coach_message(active_user, "assistant", fallback)
                                                
        # 🟢 THE ELONGATED VIDEO MODAL
        @st.dialog("🎥 Form Tutorial", width="large")
        def play_video_modal(url):
            # YouTube requires "embed" links for iframes, not "watch" links. We swap it here!
            embed_url = url.replace("watch?v=", "embed/")
            
            # We use raw HTML to force a specific height
            st.markdown(
                f"""
                <iframe width="100%" height="800" src="{embed_url}" 
                frameborder="0" allow="fullscreen; accelerometer; autoplay; encrypted-media; picture-in-picture" 
                style="border-radius: 8px;"></iframe>
                """, 
                unsafe_allow_html=True
            )

        # 2. RENDER THE CHAT UI
        if "chat_messages" in st.session_state:
            with st.container(border=True):
                # We use 'enumerate' here to give every link a mathematically unique ID!
                for idx, msg in enumerate(st.session_state["chat_messages"]):
                    avatar = "👤" if msg["role"] == "user" else "🤖"
                    with st.chat_message(msg["role"], avatar=avatar):
                        st.markdown(msg["content"])
                        
                        # RENDER THE HYBRID VISUALIZER IF ATTACHED
                        # 🟢 THE FIX: Check if visuals has actual text, not just if the key exists!
                        if msg.get("visuals"):
                            ex_name = msg["visuals"]
                            video_url = msg.get("video_url")
                            
                            if video_url:
                                # 🎬 Direct text-link button! No expander required.
                                if st.button(f"🎥 View Demonstration: {ex_name}", key=f"modal_link_{idx}", type="tertiary"):
                                    play_video_modal(video_url)
                            else:
                                st.caption(f"⚠️ *Could not fetch video tutorial for {ex_name}.*")

        # 3. HANDLE USER INPUT
        prompt = st.chat_input("Ask Coach...")
        if prompt:
            # 1. Save user prompt to screen and DB
            st.session_state["chat_messages"].append({"role": "user", "content": prompt})
            save_coach_message(active_user, "user", prompt)
            
            # Instantly draw the user's message so the UI feels snappy
            with st.chat_message("user", avatar="👤"):
                st.markdown(prompt)

            # 2. Open the Coach's chat bubble
            with st.chat_message("assistant", avatar="🤖"):
                with st.spinner("Coach is holding the clipboard..."):
                    try:
                        # Send the user's message to the AI
                        response = st.session_state["coach_chat"].send_message(prompt)
                        
                        # ==========================================
                        # 🛠️ THE TOOL INTERCEPTOR & ROUTER
                        # ==========================================
                        if response.function_calls:
                            # The AI wants to use a tool! Grab the request.
                            fc = response.function_calls[0]
                            args = dict(fc.args)
                            
                            # Force the active_user into the arguments
                            args["user_name"] = active_user 
                            
                            # 🟢 THE ROUTER: Check WHICH tool the AI wants to use!
                            if fc.name == "ai_log_workout_set":
                                tool_result_string = ai_log_workout_set(**args)
                                
                            elif fc.name == "ai_update_dossier":
                                tool_result_string = ai_update_dossier(**args)
                                
                            else:
                                tool_result_string = f"Error: Unknown tool called: {fc.name}"
                            
                            # Hand the database success/error message BACK to the AI 
                            response = st.session_state["coach_chat"].send_message(
                                types.Part.from_function_response(
                                    name=fc.name,
                                    response={"result": tool_result_string}
                                )
                            )
                        # ==========================================

                        # 3. Handle the final text response
                        raw_text = response.text
                        
                        # (Your existing video extraction logic)
                        import re
                        exercise_match = re.search(r'\[EXERCISE:\s*(.*?)\]', raw_text, re.IGNORECASE)
                        
                        if exercise_match:
                            exercise_name = exercise_match.group(1).strip()
                            clean_text = re.sub(r'\[EXERCISE:\s*.*?\]', '', raw_text, flags=re.IGNORECASE).strip()
                            real_video_url = get_youtube_embed_url(exercise_name)
                            
                            st.markdown(clean_text) # Print to screen
                            st.session_state["chat_messages"].append({"role": "assistant", "content": clean_text, "visuals": exercise_name, "video_url": real_video_url})
                            save_coach_message(active_user, "assistant", clean_text, exercise_name, real_video_url)
                        else:
                            st.markdown(raw_text) # Print to screen
                            st.session_state["chat_messages"].append({"role": "assistant", "content": raw_text})
                            save_coach_message(active_user, "assistant", raw_text)
                            
                        # Refresh the app to lock everything in!
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"Coach hit a snag: {e}")

        # 4. HANDLE THE AI GENERATION 
        if "chat_messages" in st.session_state and len(st.session_state["chat_messages"]) > 0:
            last_message = st.session_state["chat_messages"][-1]
            
            if last_message["role"] == "user":
                with st.spinner("Coach is typing..."):
                    try:
                        response = st.session_state["coach_chat"].send_message(last_message["content"])
                        raw_text = response.text
                        
                        exercise_match = re.search(r'\[EXERCISE:\s*(.*?)\]', raw_text, re.IGNORECASE)
                        
                        if exercise_match:
                            exercise_name = exercise_match.group(1).strip()
                            clean_text = re.sub(r'\[EXERCISE:\s*.*?\]', '', raw_text, flags=re.IGNORECASE).strip()
                            
                            real_video_url = get_youtube_embed_url(exercise_name)
                            
                            st.session_state["chat_messages"].append({
                                "role": "assistant", 
                                "content": clean_text,
                                "visuals": exercise_name,
                                "video_url": real_video_url  
                            })
                            
                            # Use active_user!
                            save_coach_message(active_user, "assistant", clean_text, exercise_name, real_video_url)
                            
                        else:
                            st.session_state["chat_messages"].append({"role": "assistant", "content": raw_text})
                            
                            # Use active_user!
                            save_coach_message(active_user, "assistant", raw_text)
                            
                        st.rerun()
                    except Exception as e:
                        st.error(f"Coach hit a snag: {e}")

    # ------------------------------------------
    # 🏋️ TAB 2: LOG A SESSION (FLATTENED UI)
    # ------------------------------------------    
    with tab2:
        st.subheader("🏋️ Log Your Workout")
        
        # 🟢 THE TIMEZONE FIX
        from zoneinfo import ZoneInfo
        local_tz = ZoneInfo("America/Chicago")
        local_today = datetime.datetime.now(local_tz).date()
        date_input = st.date_input("Date", local_today)
        
        # 🟢 BUILD THE ULTIMATE MASTER ACTIVITY LIST
        master_exercises = []
        skip_phrases = ["Cycle continuously", "20-Minute AMRAP Session", "resting only as needed"]
        
        # 1. Extract every unique lifting exercise from your ROUTINES dictionary
        for q_key, q_data in ROUTINES.items():
            for w_key, ex_list in q_data["Workouts"].items():
                if "Outdoor" not in w_key:
                    for ex in ex_list:
                        if any(phrase in ex for phrase in skip_phrases): continue
                        clean_name = ex.split(":")[0].strip()
                        if clean_name.startswith("- "): clean_name = clean_name[2:]
                        clean_name = clean_name.lstrip("0123456789 ")
                        
                        # Only add it if it's not already in the list
                        if clean_name and clean_name not in master_exercises and "AMRAP" not in clean_name and "⏱️" not in clean_name:
                            master_exercises.append(clean_name)
        
        if "Deadlift" not in master_exercises: master_exercises.append("Deadlift")
        
        # 2. THE FIX: Alphabetize the standard lifting exercises FIRST
        master_exercises.sort()
        
        # 3. Append custom/lifestyle options to the very bottom
        extra_options = [
            "Mountain Biking", 
            "Hiking", 
            "Walking", 
            "Mobility / Stretching", 
            "Body Weight Only", 
            "Other (Specify in Notes)"
        ]
        for opt in extra_options:
            if opt not in master_exercises:
                master_exercises.append(opt)
        
        # 🟢 THE CONTAINED MASTER LIST
        st.markdown("**Select Activity**")
        with st.container(height=250):
            activity_value = st.radio(
                "Select Activity", 
                options=master_exercises,
                label_visibility="collapsed"
            )
        
        # 🔄 FORM ROUTING LOGIC
        # 🟢 UPGRADED SMART CHECK: Looks for the exercise name even if it is hidden inside a longer string
        is_bodyweight = any(bw_ex in activity_value for bw_ex in BODYWEIGHT_ONLY_EXERCISES) or (activity_value in ["Body Weight Only", "Mobility / Stretching"])
        
        # Determine if we show sets/reps at all
        non_lifting = ["Body Weight Only", "Mountain Biking", "Hiking", "Walking", "Mobility / Stretching", "Other (Specify in Notes)"]
        show_lift_stats = activity_value not in non_lifting
        
        # Ask for Body Weight if they specifically chose a bodyweight session
        if activity_value == "Body Weight Only":
            weight_input = st.text_input("Current Body Weight (lbs)", key=f"bw_{reset_id}")
        else:
            weight_input = ""

        # 📝 HISTORICAL STATS (Last Time they did this specific exercise)
        if show_lift_stats:
            st.markdown("### 📝 Lift Tracking")
            if not log_df.empty and "User" in log_df.columns and "Activity" in log_df.columns:
                past_logs = log_df[(log_df["User"] == user) & (log_df["Activity"] == activity_value)].copy()
                if not past_logs.empty:
                    past_logs = past_logs.sort_values(by="Date", ascending=False)
                    last_log = past_logs.iloc[0]
                    last_date = last_log["Date"]
                    last_details = str(last_log.get("Details", ""))
                    clean_details = last_details.split("]")[-1].strip() if "]" in last_details else last_details
                    
                    st.markdown(f"""
                    <div style="background-color: #1E293B; border: 1px solid #334155; padding: 12px; border-radius: 6px; margin-bottom: 15px;">
                        <div style="color: #94A3B8; font-size: 13px; margin-bottom: 5px;">💡 <b>Last Time ({last_date})</b></div>
                        <div style="color: #F8FAFC; font-size: 14px; font-weight: 500;">{clean_details}</div>
                    </div>
                    """, unsafe_allow_html=True)

        # 💾 THE SUBMIT FORM
        with st.form(key=f"activity_log_form_{reset_id}"):
            if show_lift_stats:
                cols = st.columns(2 if is_bodyweight else 3) 
                with cols[0]: input_sets = st.text_input("Sets", key=f"sets_{reset_id}")
                with cols[1]: input_reps = st.text_input("Reps", key=f"reps_{reset_id}")
                if not is_bodyweight:
                    with cols[2]: input_weight_lifted = st.text_input("Weight", key=f"wgt_{reset_id}")
                else:
                    input_weight_lifted = "0"
            else:
                input_sets, input_reps, input_weight_lifted = "", "", ""

            extra_notes = st.text_input("Notes / Explanation", placeholder="Optional: Provide any details...", key=f"notes_{reset_id}")
            submit_log = st.form_submit_button("💾 Log Activity", type="primary", use_container_width=True)

        # 📤 DATABASE SYNC
        if submit_log:
            structured_log = ""
            if input_sets.strip() or input_reps.strip() or (not is_bodyweight and input_weight_lifted.strip()):
                try:
                    sets_val = int(input_sets) if input_sets.strip() else 0
                    reps_val = int(input_reps) if input_reps.strip() else 0
                    weight_val = float(input_weight_lifted) if input_weight_lifted.strip() else 0.0
                    
                    # 🟢 THE UNIFIED FORMATTING UPGRADE
                    if is_bodyweight:
                        structured_log = f"{sets_val} Sets | {reps_val} Reps | Bodyweight "
                    else:
                        structured_log = f"{sets_val} Sets | {reps_val} Reps | {weight_val} lbs "
                except ValueError:
                    pass

            if extra_notes.strip():
                final_details = f"{structured_log}- {extra_notes.strip()}" if structured_log else extra_notes.strip()
            else:
                final_details = structured_log.strip()

            if database_locked:
                st.error("Database connection is currently unstable. Please refresh the page so we don't overwrite your data.")
            elif not final_details.strip() and activity_value not in non_lifting:
                st.warning("Please add some workout details before submitting!")
            else:
                with st.spinner("Syncing to Supabase Cloud..."):
                    try:
                        final_weight = float(weight_input) if weight_input else 0.0
                    except:
                        final_weight = 0.0

                    success = log_manual_entry(
                        user_name=user, log_date=date_input, activity=activity_value, 
                        body_weight=final_weight, details=final_details
                    )
                    
                    if success:
                        st.session_state["force_db_refresh"] = True
                        st.session_state["form_reset"] += 1
                        st.success("🔥 Activity Successfully Logged to Cloud!")
                        # 🟢 FIX #3: Remove st.rerun() - let Streamlit handle the update
                        # st.rerun() causes cascading re-renders and unnecessary Garmin API calls
                    else:
                        st.error("❌ Failed to log entry.")

        # ==========================================
        # 🟢 HISTORY & DELETION ENGINE
        # ==========================================
        st.write("---")
        with st.expander("📝 Edit / Delete Past Logs"):
            if not log_df.empty:
                user_history_df = log_df[log_df["User"] == user].sort_values(by="Date", ascending=False)
                if not user_history_df.empty:
                    
                    # 🟢 THE FIX: Re-enable the editor, but lock the text fields
                    edited_df = st.data_editor(
                        user_history_df, 
                        num_rows="dynamic", 
                        disabled=["id", "Date", "Activity", "Body Weight", "Details"], 
                        column_config={
                            "id": None,    # Keep the ID hidden from the UI
                            "User": None   # Keep the User hidden
                        },
                        key="log_editor"
                    )
                    
                    # 🟢 THE SUPABASE DELETION ENGINE
                    if len(edited_df) < len(user_history_df):
                        if st.button("🔴 Confirm Deletion from Cloud Database", type="primary"):
                            with st.spinner("Deleting..."):
                                try:
                                    # 1. Figure out exactly which IDs were deleted from the UI
                                    original_ids = set(user_history_df['id'].dropna())
                                    remaining_ids = set(edited_df['id'].dropna())
                                    
                                    # 🟢 THE BULLETPROOF FIX: Force NumPy data types into standard Python Integers
                                    raw_deleted_ids = original_ids - remaining_ids
                                    deleted_ids = [int(float(x)) for x in raw_deleted_ids]
                                    
                                    if deleted_ids:
                                        # 2. Grab the exact table name using the logic you already built
                                        from database import get_target_table
                                        target_table = get_target_table()
                                        
                                        # 3. Execute the delete command via Supabase API
                                        response = supabase.table(target_table).delete().in_("id", deleted_ids).execute()
                                        
                                        # 4. Trigger the refresh loop
                                        st.session_state["force_db_refresh"] = True
                                        st.success(f"✅ {len(deleted_ids)} log(s) successfully deleted!")
                                        # 🟢 FIX #3: Remove st.rerun() - state update alone will refresh the UI
                                        # st.rerun() causes full app reset + cascading Garmin fetches
                                except Exception as e:
                                    st.error(f"Deletion failed. System Error: {e}")

    # ------------------------------------------
    # 📈 TAB 3: PROGRESS CHARTS
    # ------------------------------------------
    with tab3:
        # 🟢 CENTERED MAIN HEADER
        st.markdown("<h3 style='text-align: center; margin-bottom: 20px;'>📈 Exercise Performance Progression</h3>", unsafe_allow_html=True)
        if log_df.empty:
            st.info("No training data found in the cloud logs to plot yet.")
        else:
            chart_df = log_df[log_df["User"] == user].copy()
            chart_df["Body Weight"] = pd.to_numeric(chart_df["Body Weight"], errors="coerce")
            
            # Filter down to only rows where a valid weight was logged
            weight_trend_df = chart_df.dropna(subset=["Body Weight"])
            weight_trend_df = weight_trend_df[weight_trend_df["Body Weight"] > 0]
            
            if not weight_trend_df.empty:
                
                # 🟢 HOW TO DISABLE CODE
                # By putting a '#' in front of these lines, Python ignores them!
                # We also removed the st.caption completely as requested.
                
                # col_c1, col_c2 = st.columns([3, 2], vertical_alignment="center")
                # with col_c1:
                #     pass 
                # with col_c2:
                #     enable_zoom = st.toggle("🔍 Allow Zooming", value=False)
                
                # We hardcode enable_zoom to False so the chart knows to stay locked!
                enable_zoom = False 
                
                # 🟢 CALCULATE THE 7-DAY TREND
                weight_trend_df = weight_trend_df.sort_values(by="Date")
                weight_trend_df["7-Day Trend"] = weight_trend_df["Body Weight"].rolling(window=7, min_periods=1).mean()

                # 🟢 THE FOOLPROOF TITLE
                # We use Streamlit to draw the title outside the chart area!
                # The negative bottom margin pulls it snug against the timeframe buttons.
                st.markdown("<h4 style='text-align: center; margin-bottom: -15px;'>Body Weight Trend</h4>", unsafe_allow_html=True)

                # 1. Create the base line chart
                # (Notice we completely removed the title from inside Plotly)
                fig = px.line(
                    weight_trend_df, 
                    x="Date", 
                    y=["Body Weight", "7-Day Trend"]
                )
                
                # 2. CHANGE DAILY WEIGH-IN TO A LINE & FIX HOVER TEXT 🟢
                # The hovertemplate="%{y:.1f} lbs" is the magic wand that cleans up the pop-out!
                fig.data[0].update(
                    mode='lines', 
                    line=dict(color='red', width=3), 
                    opacity=0.4, 
                    name="Weigh-in",
                    hovertemplate="%{y:.1f} lbs"
                )
                fig.data[1].update(
                    line=dict(color=chart_line_color, width=6), 
                    name="Trend",
                    hovertemplate="%{y:.1f} lbs"
                )

                # 3. ADD A HORIZONTAL GOAL LINE
                fig.add_hline(
                    y=st.session_state.get("global_goal_weight", 0), # Now dynamically pulls from your sidebar variable!
                    line_dash="dash", 
                    line_color="green", 
                    opacity=0.8,
                    annotation_text="Goal", 
                    annotation_position="right"
                )

                # 4. Apply Mobile-Friendly Styling & Layout
                fig.update_layout(
                    
                    xaxis=dict(
                        title="",
                        rangeselector=dict(
                            buttons=list([
                                dict(count=1, label="1M", step="month", stepmode="backward"),
                                dict(count=3, label="3M", step="month", stepmode="backward"),
                                dict(count=6, label="6M", step="month", stepmode="backward"),
                                dict(label="All", step="all")
                            ]),
                            bgcolor="rgba(0,0,0,0.5)" 
                        ),
                        type="date"
                    ),
                    yaxis_title="Weight (lbs)",
                    # 🟢 ADJUST TOP MARGIN
                    # You guessed it! Dropping this from 60 to 45 pulls everything slightly closer together.
                    margin=dict(l=10, r=10, t=45, b=10), 
                    hovermode="x unified",       
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    dragmode=False, # Removed the dynamic zoom check since you are keeping it locked
                    
                    # 5. THE LEGEND LAYOUT
                    legend=dict(
                        title_text="",       
                        orientation="h",     
                        yanchor="bottom",
                        y=1.02,              # Dropped slightly to sit closer to the timeframe buttons
                        xanchor="right",
                        x=1                  
                    )
                )

                # Render in Streamlit
                st.plotly_chart(
                    fig, 
                    config={'displayModeBar': False} # Hardcoded to False since we dropped the zoom toggle
                )
                
            else:
                st.info("Log a few sessions with your body weight to light up your chart metrics!")

            # ==========================================
        # 🟢 NEW: THE BIG 3 STRENGTH TRACKER
        # ==========================================
        st.write("---") # Visual separator from the bodyweight chart
        st.markdown("<h3 style='text-align: center; margin-bottom: 20px;'>💪 Big 3 Strength Tracker</h3>", unsafe_allow_html=True)
        
        col_s1, col_s2, col_s3 = st.columns([1, 2, 1])
        with col_s2:
            # You can easily add "Overhead Press" or "Barbell Row" to this list later!
            target_lift = st.selectbox("Select Core Lift", ["Bench Press", "Squat", "Deadlift"], label_visibility="collapsed")

            # --- PR CALCULATOR ---
            # We filter the whole history (not just the chart) to find your all-time best
            all_time_max = log_df[(log_df["User"] == user) & (log_df["Activity"].str.contains(target_lift, case=False, na=False))].copy()
            all_time_max["Weight"] = all_time_max["Details"].str.extract(r'\|\s*([0-9.]+)\s*lbs').astype(float)
            
            pr_val = all_time_max["Weight"].max()
            pr_display = f"{pr_val:.1f}" if pd.notna(pr_val) else "--"
            
            st.markdown(f"<p style='text-align: center; color: #34D399; font-weight: bold;'>PR: {pr_display} lbs</p>", unsafe_allow_html=True)
        
        if log_df.empty:
            st.info("No training data found to track strength metrics.")
        else:
            # 1. Filter the entire database for the selected lift
            lift_df = log_df[(log_df["User"] == user) & (log_df["Activity"].str.contains(target_lift, case=False, na=False))].copy()
            
            if not lift_df.empty:
                # 2. THE REGEX EXTRACTION ENGINE
                # This hunts through the "Details" string (e.g., "3 Sets | 5 Reps | 315.0 lbs") 
                # and isolates the exact number sitting right before "lbs".
                lift_df["Weight Lifted"] = lift_df["Details"].str.extract(r'\|\s*([0-9.]+)\s*lbs').astype(float)
                
                # 3. Clean up the data (Drop rows where you didn't log a weight)
                lift_df = lift_df.dropna(subset=["Weight Lifted"])
                lift_df = lift_df[lift_df["Weight Lifted"] > 0]
                
                if not lift_df.empty:
                    # 4. Find the Daily Max 
                    # (If you log 3 warmup sets and 1 working set on the same day, this isolates your heaviest lift!)
                    daily_max_df = lift_df.groupby("Date")["Weight Lifted"].max().reset_index()
                    daily_max_df = daily_max_df.sort_values(by="Date")
                    
                    # 5. Calculate a 3-Session Rolling Trend Line
                    daily_max_df["Trend"] = daily_max_df["Weight Lifted"].rolling(window=3, min_periods=1).mean()
                    
                    # 6. Build the Chart
                    fig_lift = px.line(
                        daily_max_df, 
                        x="Date", 
                        y=["Weight Lifted", "Trend"]
                    )
                    
                    # 7. Match the Styling to your Body Weight Chart perfectly
                    fig_lift.data[0].update(
                        mode='lines+markers', # Added markers so individual workout days pop
                        line=dict(color='red', width=3), # Amber color for the raw heavy lift
                        opacity=0.5, 
                        name="Max Lift",
                        hovertemplate="%{y:.1f} lbs"
                    )
                    fig_lift.data[1].update(
                        line=dict(color=chart_line_color, width=6), 
                        name="Trend",
                        hovertemplate="%{y:.1f} lbs"
                    )
                    
                    fig_lift.update_layout(
                        xaxis=dict(
                            title="",
                            rangeselector=dict(
                                buttons=list([
                                    dict(count=1, label="1M", step="month", stepmode="backward"),
                                    dict(count=3, label="3M", step="month", stepmode="backward"),
                                    dict(count=6, label="6M", step="month", stepmode="backward"),
                                    dict(label="All", step="all")
                                ]),
                                bgcolor="rgba(0,0,0,0.5)" 
                            ),
                            type="date"
                        ),
                        yaxis_title="Weight (lbs)",
                        margin=dict(l=10, r=10, t=10, b=10), 
                        hovermode="x unified",       
                        plot_bgcolor="rgba(0,0,0,0)",
                        paper_bgcolor="rgba(0,0,0,0)",
                        dragmode=False,
                        legend=dict(
                            title_text="",       
                            orientation="h",     
                            yanchor="bottom",
                            y=1.02,              
                            xanchor="right",
                            x=1                  
                        )
                    )
                    
                    st.plotly_chart(fig_lift, config={'displayModeBar': False})
                else:
                    st.info(f"You have logged {target_lift}, but we couldn't detect the weight. Ensure you use the structured sidebar logger!")
            else:
                st.info(f"No {target_lift} sessions found in your history yet. Time to hit the iron!")

    # ------------------------------------------
    # 📚 TAB 4: TRAINING BLUEPRINT
    # ------------------------------------------
    with tab4:        
        st.subheader("🧠 Coaching Philosophy & Blueprint")
        st.write("---")
        
        # Pull in your logic from blueprint.py
        from blueprint import WORKOUT_FRAMEWORKS
        
        # Helper function to clean citations from text
        def clean_citations(text):
            """Remove [cite: ...] markers for cleaner display"""
            import re
            return re.sub(r'\[cite:.*?\]', '', text).strip()
        
        # Introduction to the 4-phase system
        st.markdown("""
        Your training program is structured around **4 progressive phases**, each designed with a specific purpose to build strength, 
        muscle, endurance, and conditioning. The Coach adapts workouts daily based on your current phase's rules, equipment, and weekly structure.
        
        **Phase progression** is based on your training readiness and goals. Phases typically last 4-6 weeks before advancing.
        """)
        st.divider()
        
        # Phase Overview - Show all phases at a glance
        st.markdown("### 📋 Training Phases Overview")
        
        phase_list = list(WORKOUT_FRAMEWORKS.items())
        for idx, (phase_name, framework) in enumerate(phase_list, 1):
            is_active = phase_name.split(":")[0] in current_phase
            phase_emoji = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "🔓"][idx - 1]
            current_indicator = " ⭐ **CURRENT**" if is_active else ""
            focus_summary = clean_citations(framework.get('focus', ''))
            
            st.markdown(f"**{phase_emoji} {phase_name}**{current_indicator}")
            st.caption(focus_summary)
        
        st.divider()
        
        # Render each Phase as a detailed expander with structured callouts
        st.markdown("### 🎯 Phase Details")
        for idx, (phase_name, framework) in enumerate(phase_list, 1):
            is_active = phase_name.split(":")[0] in current_phase
            phase_emoji = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "🔓"][idx - 1]
            expander_title = f"{phase_emoji} {phase_name} (CURRENT)" if is_active else f"{phase_emoji} {phase_name}"
            
            with st.expander(expander_title, expanded=is_active):
                # Extract the focus (remove citations for clean display)
                focus_text = clean_citations(framework.get('focus', ''))
                st.markdown(f"**🎯 Purpose:** {focus_text}")
                
                # Extract rep ranges and rest from lifting_rules
                lifting_rules = clean_citations(framework.get('lifting_rules', ''))
                st.markdown(f"**💪 Lifting Guidelines:** {lifting_rules}")
                
                # Weekly structure from weekly_cadence
                weekly_structure = clean_citations(framework.get('weekly_cadence', ''))
                st.markdown(f"**📅 Weekly Structure:** {weekly_structure}")
                
                # AI coaching approach
                st.markdown("---")
                ai_approach = clean_citations(framework.get('ai_instructions', ''))
                st.markdown(f"**🤖 Coaching Focus:** {ai_approach}")
        
        st.divider()
        
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
        st.divider()
        
        # Enhanced: How to use your Coach
        st.markdown("""
        ### 🤖 How to Use Your Coach
        
        The Coach **adapts all workouts to your current phase's rules**, equipment availability, and weekly structure. 
        Your daily workouts follow the phase's rep ranges, rest periods, and coaching approach.
        
        **Example Prompts to Try:**
        """)
        
        col_ex1, col_ex2 = st.columns(2)
        with col_ex1:
            st.markdown("""
            * *"I'm at the home gym—build me a workout using the current Phase's rules."*
            * *"I'm feeling sore today; adjust for more mobility and active recovery."*
            * *"Build me a quick 20-minute session before work."*
            * *"I have access to heavy weights today—maximize this!"*
            """)
        with col_ex2:
            st.markdown("""
            * *"Build me an intense metabolic circuit—push the cardio."*
            * *"I'm in Phase 3—focus on strength and heavy lifts."*
            * *"Can you do a lower-body AMRAP session?"*
            * *"Design a workout for TRX and bodyweight only."*
            """)                         
           
    # ==========================================
    # TAB 5: 📢 WHAT'S NEW (CHANGELOG)
    # ==========================================
    if tab_changelog is not None:
        with tab_changelog:
            st.subheader("📢 What's New: Release Notes")
            try:
                # 🟢 1. GLOBAL DICTIONARY (Used by both Dev and Prod feeds)
                cat_display = {"Core": "Core Features", "UI": "User Interface / Experience", "Bug": "Bug Fixes", "Ops": "Operations"}
                
                # ==========================================
                # 2. DEV ONLY: DRAFT RELEASE PREVIEW
                # ==========================================
                if role == "developer" and is_local_env:
                    staged_response = supabase.table("backlog").select("*").eq("status", "Staged").execute()
                    
                    if staged_response.data:
                        categories = [r.get("category", "") for r in staged_response.data]
                        current_v = st.session_state.get("APP_VERSION", APP_VERSION)
                        
                        try:
                            major, minor, patch = map(int, current_v.replace('v', '').strip().split('.'))
                            if "Core" in categories:
                                major += 1; minor = 0; patch = 0
                            elif "UI" in categories:
                                minor += 1; patch = 0
                            elif "Bug" in categories:
                                patch += 1
                            proposed_v = f"{major}.{minor}.{patch}"
                        except:
                            proposed_v = current_v
                            
                        st.markdown(f"""
                        <div style="background-color: #fef08a; padding: 12px; border-radius: 8px; margin-bottom: 20px; border: 1px solid #facc15;">
                            <h4 style="color: #b91c1c; margin: 0px; text-align: center;">
                                🚧 DRAFT PREVIEW: Proposed Release v{proposed_v}
                            </h4>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # 🟢 SAFE SORTING (The 'else 99' prevents crashes from old/weird tags!)
                        batch_cats = sorted(set(categories), key=lambda x: ["Core", "UI", "Bug", "Ops"].index(x) if x in ["Core", "UI", "Bug", "Ops"] else 99)

                        for cat in batch_cats:
                            st.markdown(f"#### {cat_display.get(cat, cat)}")
                            cat_items = [r for r in staged_response.data if r.get("category") == cat]
                            
                            for item in cat_items:
                                task = item.get("feature", "System Update")
                                pub_msg = item.get("public_message", "")
                                
                                st.markdown(f"**• {task}**")
                                if pub_msg and str(pub_msg).strip() not in ["", "None"]:
                                    st.caption(f"&emsp; *{pub_msg}*")
                            st.write("")
                        st.divider()

                # ==========================================
                # 3. PROD FEED (The Formal History)
                # ==========================================
                response = supabase.table("backlog").select("*").eq("status", "Done").execute()
                
                if response.data:
                    df = pd.DataFrame(response.data)
                    
                    df = df.rename(columns={
                        "feature": "Feature", "category": "Category", 
                        "public_message": "Public Message", "release_date": "Release Date", 
                        "version": "Version"
                    })
                    
                    for col in ["Release Date", "Version", "Public Message"]:
                        if col not in df.columns: df[col] = ""
                        df[col] = df[col].fillna("").astype(str)

                    df["Release Date"] = pd.to_datetime(df["Release Date"], errors="coerce").fillna(pd.Timestamp("2000-01-01"))
                    
                    def parse_version(v_str):
                        try:
                            clean_v = str(v_str).lower().replace('v', '').strip()
                            return tuple(map(int, clean_v.split('.')))
                        except:
                            return (0, 0, 0)

                    current_app_v = parse_version(APP_VERSION)
                    df = df[df["Version"].apply(parse_version) <= current_app_v]
                    
                    df = df.sort_values(by=["Release Date", "Version"], ascending=[False, False])
                    unique_versions = [v for v in df["Version"].unique() if v.strip() != ""]
                    
                    recent_versions = unique_versions[:3]
                    older_versions = unique_versions[3:]
                   
                    # --- RENDER RECENT RELEASES ---
                    for v_val in recent_versions:
                        group = df[df["Version"] == v_val]
                        date_val = group["Release Date"].iloc[0]
                        date_str = pd.to_datetime(date_val).strftime("%Y-%m-%d") if date_val > pd.Timestamp("2000-01-01") else "Archive"
                        
                        st.markdown(f"### 🚀 Update: {date_str} | v{v_val}")
                        
                        # Apply the clean bundling to Production!
                        version_cats = group["Category"].fillna("Ops").unique().tolist()
                        batch_cats = sorted(version_cats, key=lambda x: ["Core", "UI", "Bug", "Ops"].index(x) if x in ["Core", "UI", "Bug", "Ops"] else 99)
                        
                        for cat in batch_cats:
                            st.markdown(f"#### {cat_display.get(cat, cat)}")
                            cat_df = group[group["Category"] == cat]
                            
                            for _, row in cat_df.iterrows():
                                task = row.get("Feature", "System Update")
                                pub_msg = row.get("Public Message", "")
                                st.markdown(f"**• {task}**")
                                if pd.notna(pub_msg) and str(pub_msg).strip() not in ["", "None"]:
                                    st.caption(f"&emsp; *{pub_msg}*")
                            st.write("")
                        st.divider()

                    # --- RENDER ARCHIVED RELEASES ---
                    if len(older_versions) > 0:
                        with st.expander("🕰️ View Older Updates"):
                            for v_val in older_versions:
                                group = df[df["Version"] == v_val]
                                date_val = group["Release Date"].iloc[0]
                                date_str = pd.to_datetime(date_val).strftime("%Y-%m-%d") if date_val > pd.Timestamp("2000-01-01") else "Archive"
                                
                                st.markdown(f"### 🚀 Update: {date_str} | v{v_val}")
                                
                                version_cats = group["Category"].fillna("Ops").unique().tolist()
                                batch_cats = sorted(version_cats, key=lambda x: ["Core", "UI", "Bug", "Ops"].index(x) if x in ["Core", "UI", "Bug", "Ops"] else 99)
                                
                                for cat in batch_cats:
                                    st.markdown(f"#### {cat_display.get(cat, cat)}")
                                    cat_df = group[group["Category"] == cat]
                                    
                                    for _, row in cat_df.iterrows():
                                        task = row.get("Feature", "System Update")
                                        pub_msg = row.get("Public Message", "")
                                        st.markdown(f"**• {task}**")
                                        if pd.notna(pub_msg) and str(pub_msg).strip() not in ["", "None"]:
                                            st.caption(f"&emsp; *{pub_msg}*")
                                    st.write("")
                                st.divider()
                else:
                    st.info("No released updates yet.")
                    
            except Exception as e:
                st.error(f"Could not load the changelog: {e}")

    # ==========================================
    # TAB 6: 🛠️ ADMIN PANEL (DEVELOPERS ONLY)
    # ==========================================
    if tab_admin is not None:
        with tab_admin:
            st.subheader("🛠️ Developer Admin Panel")
            try:
                col_head1, col_head2 = st.columns([4, 1])
                with col_head1:
                    st.write("Manage Active App Backlog & QoL Features:")
                with col_head2:
                    if st.button("🔄 Refresh Data", width='stretch'):
                        st.session_state["force_admin_refresh"] = True

                # Read the active backlog table directly from Supabase
                response = supabase.table("backlog").select("*").neq("status", "Done").order("id").execute()
                
                if response.data:
                    df_backlog = pd.DataFrame(response.data)
                    df_backlog = df_backlog.fillna("")
                    
                    df_backlog = df_backlog.rename(columns={
                        "status": "Status", "category": "Category", "feature": "Feature", 
                        "priority": "Priority", "notes": "Notes", "public_message": "Public Message", 
                        "release_date": "Release Date", "version": "Version"
                    })

                    # 🟢 THE MULTI-LEVEL SORTING FIX (Status -> Category -> Priority)
                    # Clean up old/blank Priority data
                    df_backlog["Priority"] = df_backlog["Priority"].replace("", "Low").fillna("Low")
                    df_backlog["Priority"] = df_backlog["Priority"].astype(str).str.title()
                    
                    # 🟢 1. UPDATE THE STATUS HIERARCHY
                    # Add "Staged" right before Done
                    status_order = ["In Progress", "Backlog", "Blocked", "Staged", "Done"]
                    df_backlog["Status"] = pd.Categorical(df_backlog["Status"], categories=status_order, ordered=True)

                    category_order = ["Core", "UI", "Bug", "Ops"]
                    df_backlog["Category"] = pd.Categorical(df_backlog["Category"], categories=category_order, ordered=True)

                    priority_order = ["High", "Medium", "Low"]
                    df_backlog["Priority"] = pd.Categorical(df_backlog["Priority"], categories=priority_order, ordered=True)
                    
                    df_backlog = df_backlog.sort_values(["Status", "Category", "Priority"])
                    df_backlog = df_backlog.reset_index(drop=True)

                    # 🛑 Interactive Table
                    edited_backlog = st.data_editor(
                        df_backlog, 
                        num_rows="dynamic", 
                        width="stretch", 
                        key="admin_backlog_editor",
                        hide_index=True,  
                        column_config={
                            "id": None, 
                            # 🟢 2. ADD STAGED TO THE UI DROPDOWN
                            "Status": st.column_config.SelectboxColumn("Status", options=["Backlog", "In Progress", "Blocked", "Staged", "Done"], required=True),
                            "Category": st.column_config.SelectboxColumn("Category", options=["Core", "UI", "Bug", "Ops"], required=True),
                            "Priority": st.column_config.SelectboxColumn("Priority", options=["High", "Medium", "Low"], required=True),
                            "Public Message": st.column_config.TextColumn("Public Message", width="large"),
                            "Release Date": st.column_config.TextColumn("Release Date", disabled=True),
                            "Version": st.column_config.TextColumn("Version", disabled=True)
                        }
                    )
            
                    # 🟢 3. THE MAGIC BATCHING LOGIC
                    # The calculator ONLY looks at things currently sitting in "Staged"
                    mask_staged = (edited_backlog["Status"] == "Staged")
                    categories_being_released = edited_backlog.loc[mask_staged, "Category"].tolist()
                    
                    active_version = st.session_state.get("APP_VERSION", APP_VERSION)
                    
                    # Only propose a new version if there are actually things sitting in Staged!
                    if categories_being_released:
                        proposed_version = calculate_next_version(active_version, categories_being_released)
                    else:
                        proposed_version = active_version

                    st.write("")
                    col_btn1, col_btn2 = st.columns([1, 4])
                    with col_btn1:
                        st.markdown(
                            f"""
                            <div style="font-size: 13px; color: #94A3B8; margin-bottom: 4px;">Proposed Release</div>
                            <div style="background-color: #1E293B; border: 1px solid #334155; padding: 6px; border-radius: 6px; text-align: center; color: #34D399; font-weight: 600; font-size: 16px;">
                                v{proposed_version}
                            </div>
                            """, 
                            unsafe_allow_html=True
                        )
                        push_version = proposed_version 
                        
                    with col_btn2:
                        st.write("") 
                        # 🟢 4. THE SPLIT BUTTONS
                        col_save, col_deploy = st.columns([1, 1])
                        with col_save:
                            # This button just saves notes/statuses without touching the version number
                            save_clicked = st.button("💾 Save Daily Work (Keep Staged)", width="stretch")
                        with col_deploy:
                            # This button actually cuts the production release!
                            deploy_clicked = st.button("🚀 Cut Release & Move Staged to Done", type="primary", width="stretch")

                    # 🟢 5. THE NEW PUSH ROUTER
                    if save_clicked or deploy_clicked:
                        today_str = datetime.datetime.now(ZoneInfo("America/Chicago")).date().isoformat()
                        # 🟢 THE DELETE FIX: Find IDs that exist in the original DB but are missing from the UI
                        original_ids = set(df_backlog["id"].dropna().astype(int).tolist())
                        current_ids = set(edited_backlog["id"].dropna().astype(int).tolist())
                        deleted_ids = list(original_ids - current_ids)

                        if deleted_ids:
                            try:
                                supabase.table("backlog").delete().in_("id", deleted_ids).execute()
                            except Exception as e:
                                st.error(f"❌ Failed to delete items from database: {e}")
                        
                        if deploy_clicked and categories_being_released:
                            # ONLY if they click Deploy do we stamp the dates, versions, and move to Done!
                            edited_backlog.loc[mask_staged, "Release Date"] = today_str
                            edited_backlog.loc[mask_staged, "Version"] = push_version
                            edited_backlog.loc[mask_staged, "Status"] = "Done"

                        # Prepare the full payload for Supabase
                        upload_df = edited_backlog.rename(columns={
                            "Status": "status", "Category": "category", "Feature": "feature", 
                            "Priority": "priority", "Notes": "notes", "Public Message": "public_message", 
                            "Release Date": "release_date", "Version": "version"
                        })
                        
                        raw_records = upload_df.to_dict(orient="records")
                        records_to_update = []
                        records_to_insert = []
                        
                        for record in raw_records:
                            clean_row = {}
                            has_valid_id = False
                            
                            for key, value in record.items():
                                if key == "id":
                                    try:
                                        clean_row[key] = int(float(value))
                                        has_valid_id = True
                                    except (ValueError, TypeError):
                                        continue 
                                else:
                                    if pd.isna(value) or value is None or str(value).strip() in ["None", "nan"]:
                                        clean_row[key] = ""
                                    else:
                                        clean_row[key] = value
                                        
                            if has_valid_id:
                                records_to_update.append(clean_row)
                            else:
                                if clean_row.get("feature"): 
                                    records_to_insert.append(clean_row)
                        
                        try:
                            if records_to_update:
                                supabase.table("backlog").upsert(records_to_update).execute()
                            if records_to_insert:
                                supabase.table("backlog").insert(records_to_insert).execute()
                                
                            if deploy_clicked:
                                st.success(f"✅ Release {push_version} Cut! Run your deploy.py script now.")
                                st.session_state["APP_VERSION"] = push_version
                            else:
                                st.success("✅ Daily progress saved!")
                                
                            if "admin_backlog_editor" in st.session_state:
                                del st.session_state["admin_backlog_editor"]
                            
                            st.session_state["force_admin_refresh"] = True 
                            st.rerun()
                            
                        except Exception as e:
                            st.error(f"❌ Supabase rejected the payload: {e}")
                else:
                    st.info("Backlog is empty. Add a ticket to get started!")

            except Exception as e:
                st.error(f"Failed to load the backlog. System Error: {e}")