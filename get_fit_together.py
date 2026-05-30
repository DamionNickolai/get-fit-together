# --- 1. APP CONFIGURATION & IMPORTS ---
import streamlit as st
import pandas as pd
import datetime
import plotly.express as px
import hashlib 

# 🛑 1. PAGE CONFIG MUST BE FIRST
st.set_page_config(
    page_title="Get Fit Together",
    page_icon="💪",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 🟢 Add this near your other config variables
BODYWEIGHT_ONLY_EXERCISES = ["Push-ups", "Push-ups (or modified on knees)", "Plank", "Suspended Planks", "Atomic Push-ups"]

# 🛑 2. IMPORT CUSTOM MODULES
# 🟢 Bring in the login module!
from auth import check_password

# 🟢 Bring in the database automation helpers AND the Supabase client!
from database import check_and_bulk_log_garmin_weight, check_and_autolog_garmin_weight, get_user_history_df, log_manual_entry, supabase

# 🟢 Bring in the static workout database!
from workouts import ROUTINES

# 🟢 3. APP VERSIONING
APP_VERSION = "1.4.0"
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

    /* 🟢 WEBVIEW DROPDOWN SCROLL FIX 🟢 */
    /* Forces Android WebView to allow vertical scrolling inside Streamlit select boxes */
    div[data-baseweb="popover"] > div,
    ul[role="listbox"] {
        -webkit-overflow-scrolling: touch !important; /* Enables hardware momentum scrolling */
        overscroll-behavior-y: contain !important;    /* Traps the scroll inside the dropdown */
        touch-action: pan-y !important;               /* Tells the WebView to only expect vertical swipes here */
        max-height: 300px !important;                 /* Ensure dropdown doesn't expand too large */
        overflow-y: auto !important;                  /* Enable scrollbar if needed */
    }
    
    /* Additional Android/WebView specific fixes */
    [data-baseweb="select"] {
        -webkit-user-select: none !important;
        -webkit-touch-callout: none !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. ENVIRONMENT DETECTION & PASSWORD SYSTEM ---
# 🟢 THE BOUNCER: This function checks your URL, logs you in, AND fetches your colors!
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
    g_prefix = st.session_state.get("garmin_prefix", "").lower()

    # Notice we use the f-string (f""") and double brackets {{ }} here!
    st.markdown(f"""
        <style>
        .stApp {{ background-color: {page_bg_color} !important; color: white; }}
        [data-testid="stSidebar"] {{ background-color: {side_bg} !important; }}
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
            st.session_state["garmin_status"] = "Standby Mode"
            
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
    #  LOGGING SIDEBAR (Ultra-Clean Input Only)
    # ==========================================
    st.sidebar.header("🏋️ Log a Session")
    
    # 🟢 NEW PHASE SELECTION MAPPER
    # The user sees the short name, but Python uses the long name for the database
    phase_options = ["Phase 1", "Phase 2", "Phase 3", "Phase 4", "Daily Core", "TRX Suspension Mastery", "TRX Rip Trainer Power", "Open Gym"]
    selected_short_phase = st.sidebar.selectbox("Phase", options=phase_options, index=0)
    
    phase_map = {
        "Phase 1": "Phase 1: Foundation & Endurance",
        "Phase 2": "Phase 2: Hypertrophy (Muscle Building)",
        "Phase 3": "Phase 3: Strength & Power",
        "Phase 4": "Phase 4: Metabolic Conditioning",
        "Daily Core": "Daily Core",
        "TRX Suspension Mastery": "TRX Suspension Mastery",
        "TRX Rip Trainer Power": "TRX Rip Trainer Power",
        "Open Gym": "Open Gym"
    }
    
    selected_q = phase_map[selected_short_phase]
    
    # 🟢 THE TIMEZONE FIX
    # Force the app to calculate 'today' based on Central Time, ignoring the server's UTC clock
    from zoneinfo import ZoneInfo
    local_tz = ZoneInfo("America/Chicago")
    local_today = datetime.datetime.now(local_tz).date()
    
    date_input = st.sidebar.date_input("Date", local_today)
    
    # 🔄 DATA ROUTING ENGINE
    details_prefix = ""
    show_weight_box = False
    
    # 🟢 List of phrases to OMIT from the Exercise/Activity dropdown
    skip_phrases = [
        "Cycle continuously", 
        "20-Minute AMRAP Session", 
        "resting only as needed"
    ]
    
    if selected_q != "Open Gym":
        selected_w = st.sidebar.selectbox("Select Session", list(ROUTINES[selected_q]["Workouts"].keys()))
        
        if "Outdoor" in selected_w:
            activity_value = "Outdoor Activity" 
            details_prefix = f"🌲 [{selected_q} - Outdoor] "
        else:
            # 🟢 OPTIMIZED DYNAMIC EXERCISE GENERATOR
            raw_exercises = ROUTINES[selected_q]["Workouts"][selected_w]
            clean_exercises = []
            
            for ex in raw_exercises:
                # 🟢 FILTER: Check if this line is an instructional sentence, not an exercise
                if any(phrase in ex for phrase in skip_phrases):
                    continue
                
                clean_name = ex.split(":")[0].strip()
                if clean_name.startswith("- "): clean_name = clean_name[2:]
                clean_name = clean_name.lstrip("0123456789 ")
                
                if clean_name: # Only add if it's not an empty string
                    clean_exercises.append(clean_name)
                
            activity_value = st.sidebar.selectbox("Exercise / Activity", clean_exercises)
            short_w_name = selected_w.split(":")[0]
            details_prefix = f"🏋️ [{selected_q} - {short_w_name}] "
            
    else:
        # 🟢 UPGRADED OPEN GYM PHASE
        custom_session = st.sidebar.selectbox("Session Type", ["A La Carte", "Mountain Biking", "Hiking", "Walking", "Mobility / Stretching", "Body Weight Only"])
        
        if custom_session == "Body Weight Only":
            show_weight_box = True
            activity_value = "Body Weight Only"
            details_prefix = ""
        elif custom_session in ["Mountain Biking", "Hiking", "Walking", "Mobility / Stretching"]:
            activity_value = custom_session
            details_prefix = f"📋 [Open Gym] "
        else:
            master_exercises = []
            for q_key, q_data in ROUTINES.items():
                for w_key, ex_list in q_data["Workouts"].items():
                    if "Outdoor" not in w_key:
                        for ex in ex_list:
                            clean_name = ex.split(":")[0].strip()
                            
                            # The AMRAP / Bullet point cleaner
                            if clean_name.startswith("- "): 
                                clean_name = clean_name[2:]
                                # 🟢 NEW: Strip any leading numbers and spaces for the A La Carte menu
                                clean_name = clean_name.lstrip("0123456789 ")
                            
                            if clean_name not in master_exercises and "AMRAP" not in clean_name and "Cycle continuously" not in clean_name and "⏱️" not in clean_name:
                                master_exercises.append(clean_name)
            
            master_exercises.sort()
            
            # 🟢 THE DEADLIFT INJECTION
            if "Deadlift" not in master_exercises:
                master_exercises.append("Deadlift")
                
            master_exercises.append("Other (Specify in Notes)")
            
            activity_value = st.sidebar.selectbox("Exercise / Activity", master_exercises)
            details_prefix = "🏋️ [Open Gym - A La Carte] "

    # 🟢 THE GHOST WIDGET FIX: Create a resetting ID counter
    if "form_reset" not in st.session_state:
        st.session_state["form_reset"] = 0
    reset_id = st.session_state["form_reset"]

    # 2. ⚖️ DYNAMIC WEIGHT DISPLAY
    if show_weight_box:
        weight_input = st.sidebar.text_input("Body Weight (lbs)", key=f"bw_{reset_id}")
    else:
        weight_input = ""

    # 3. 📝 STRUCTURED LIFT TRACKING (Now with st.form!)
    if selected_q == "Open Gym":
        non_lifting = ["Body Weight Only", "Mountain Biking", "Hiking", "Walking", "Mobility / Stretching"]
        show_lift_stats = custom_session not in non_lifting
    else:
        show_lift_stats = "Outdoor" not in selected_w and "Cycle continuously" not in activity_value
        
    structured_log = ""

    # Keep the "Last Performed" memory outside the form so it displays dynamically
    if show_lift_stats:
        st.sidebar.markdown("### 📝 Lift Tracking Stats")
        
        if not log_df.empty and "User" in log_df.columns and "Activity" in log_df.columns:
            past_logs = log_df[(log_df["User"] == user) & (log_df["Activity"] == activity_value)].copy()
            if not past_logs.empty:
                past_logs = past_logs.sort_values(by="Date", ascending=False)
                last_log = past_logs.iloc[0]
                
                last_date = last_log["Date"]
                last_details = str(last_log.get("Details", ""))
                clean_details = last_details.split("]")[-1].strip() if "]" in last_details else last_details
                
                st.sidebar.markdown(f"""
                <div style="background-color: #1E293B; border: 1px solid #334155; padding: 12px; border-radius: 6px; margin-bottom: 15px;">
                    <div style="color: #94A3B8; font-size: 13px; margin-bottom: 5px;">💡 <b>Last Time ({last_date})</b></div>
                    <div style="color: #F8FAFC; font-size: 14px; font-weight: 500;">{clean_details}</div>
                </div>
                """, unsafe_allow_html=True)

    # 🚀 CREATE THE FORM HERE
    with st.sidebar.form(key=f"activity_log_form_{reset_id}"):
        
        # 🟢 DYNAMIC COLUMNS: Hide weight if it's bodyweight-only
        # It's bodyweight if it's in the specific list, OR if the whole phase is a TRX phase!
        is_trx_phase = selected_q in ["TRX Suspension Mastery", "TRX Rip Trainer Power"]
        is_bodyweight = (activity_value in BODYWEIGHT_ONLY_EXERCISES) or is_trx_phase
        
        if show_lift_stats:
            # Notice we use st.columns instead of st.sidebar.columns inside a form container
            cols = st.columns(2 if is_bodyweight else 3) 
            
            with cols[0]:
                input_sets = st.text_input("Sets", key=f"sets_{reset_id}")
            with cols[1]:
                input_reps = st.text_input("Reps", key=f"reps_{reset_id}")
                
            if not is_bodyweight:
                with cols[2]:
                    input_weight_lifted = st.text_input("Weight", key=f"wgt_{reset_id}")
            else:
                input_weight_lifted = "0" # Force 0 for bodyweight exercises
        else:
            # Set defaults if we aren't lifting
            input_sets, input_reps, input_weight_lifted = "", "", ""

        # 4. 📝 UNIVERSAL NOTES BOX (Inside the form)
        extra_notes = st.text_input("Notes / Explanation", placeholder="Optional: Provide any details...", key=f"notes_{reset_id}")

        # 5. SUBMIT BUTTON (This replaces your previous st.sidebar.button)
        submit_log = st.form_submit_button("💾 Log Activity", type="primary", width='stretch')


    # 🔄 6. DATABASE SYNC LOGIC (Triggers only when the form is submitted)
    if submit_log:
        
        # Build the structured string now that we have locked-in form data
        if input_sets.strip() or input_reps.strip() or (not is_bodyweight and input_weight_lifted.strip()):
            try:
                sets_val = int(input_sets) if input_sets.strip() else 0
                reps_val = int(input_reps) if input_reps.strip() else 0
                weight_val = float(input_weight_lifted) if input_weight_lifted.strip() else 0.0
                
                if is_bodyweight:
                    structured_log = f"{sets_val} Sets | {reps_val} Reps "
                else:
                    structured_log = f"{sets_val} Sets | {reps_val} Reps | {weight_val} lbs "
            except ValueError:
                pass

        if extra_notes.strip():
            user_details = f"{structured_log}- {extra_notes.strip()}" if structured_log else extra_notes.strip()
        else:
            user_details = structured_log.strip()
            
        final_details = f"{details_prefix}{user_details}" if details_prefix else user_details

        # Database Check & Submission
        if database_locked:
            st.sidebar.error("Database connection is currently unstable. Please refresh the page so we don't overwrite your data.")
        elif not user_details.strip() and "Outdoor" not in final_details:
            st.sidebar.warning("Please add some workout details before submitting!")
        else:
            with st.spinner("Syncing to Supabase Cloud..."):
                try:
                    if weight_input == "" or weight_input is None:
                        final_weight = 0.0
                    else:
                        try:
                            final_weight = float(weight_input)
                        except:
                            final_weight = 0.0

                    success = log_manual_entry(
                        user_name=user, 
                        log_date=date_input, 
                        activity=activity_value, 
                        body_weight=final_weight, 
                        details=final_details
                    )
                    
                    if success:
                        st.session_state["force_db_refresh"] = True
                        st.session_state["form_reset"] += 1
                        st.sidebar.success("🔥 Activity Successfully Logged to Cloud!")
                        st.rerun()
                    else:
                        st.sidebar.error("❌ Failed to log entry. Check terminal for errors.")

                except Exception as log_err:
                    st.sidebar.error(f"Failed to log entry: {log_err}")
    
    # ==========================================
    # ⚙️ SIDEBAR UTILITY FOOTER 
    # ==========================================
    st.sidebar.markdown("---")
    st.sidebar.divider()
    
    # GOAL WEIGHT SETTING EXPANDER
    with st.sidebar.expander("🎯 Set Goal Weight"):

        # 1. Fetch current goal
        current_goal_response = supabase.table("users").select("goal_weight").eq("username", user).execute()
        
        current_goal = 0.0
        if current_goal_response.data and current_goal_response.data[0].get("goal_weight"):
            current_goal = float(current_goal_response.data[0]["goal_weight"])
            
        # 2. THE FORM UPGRADE
        with st.form(key="goal_weight_form"):
            # 🟢 SET VALUE TO NONE AND ADD A PLACEHOLDER
            new_goal = st.number_input(
                "Target Weight (lbs)", 
                min_value=100.0, 
                max_value=400.0, 
                value=None, 
                placeholder=f"{current_goal}", # Shows as grey background text
                step=0.1
            )
            submit_goal = st.form_submit_button("💾 Save Goal", type="primary")
            
        # 3. TRIGGER AND ERROR CHECKING
        if submit_goal:
            # 🟢 NEW SAFETY CHECK: Don't save if they left it blank
            if new_goal is None:
                st.warning("Please enter a new goal weight before saving.")
            else:
                try:
                    # Attempt to update the database
                    update_response = supabase.table("users").update({"goal_weight": new_goal}).eq("username", user).execute()
                    
                    if not update_response.data:
                        st.error(f"⚠️ Supabase received the request, but couldn't update the row for '{user}'.")
                    else:
                        st.success(f"Goal updated to {new_goal} lbs!")
                        st.rerun() 
                        
                except Exception as e:
                    st.error(f"❌ Failed to connect to database: {e}")

    # 🟢 THE PANIC BUTTON (Public Bug Reporter)
    with st.sidebar.expander("🐛 Report an Issue"):
        # Wrap in a form so it clears instantly on submit
        with st.form(key=f"bug_report_{reset_id}", clear_on_submit=True):
            st.caption("Did something break? Tell the developer directly!")
            bug_text = st.text_area("What happened?", placeholder="e.g., The cardio duration box isn't showing up.")
            submit_bug = st.form_submit_button("📤 Send to Developer", type="secondary", width='stretch')
            
            if submit_bug:
                if not bug_text.strip():
                    st.warning("Please type a message first.")
                else:
                    with st.spinner("Sending..."):
                        try:
                            # 🟢 SUPABASE FIX: Instantly injects one row directly to the cloud
                            supabase.table("backlog").insert({
                                "status": "Backlog",
                                "category": "Bug",
                                "feature": f"User Report: {user}",
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
        
    # 🔄 Public Log Out Button (Visible to everyone)
    if st.sidebar.button("🚪 Switch User / Log Out", width='stretch'):
        for key in list(st.session_state.keys()):
            if "live_garmin_client" in key or "garmin_token" in key:
                del st.session_state[key]
        
        # 🟢 THE FIX: We completely delete the password memory instead of setting it to False!
        if "password_correct" in st.session_state:
            del st.session_state["password_correct"]
            
        st.session_state["logged_in_user"] = None
        st.session_state["user_role"] = None
        
        # 🟢 Wipes the magic URL tokens
        st.query_params.clear() 
        st.rerun()

    # 🏷️ Application Version Tag (Public)
    st.sidebar.caption(f"<div style='text-align: center; color: gray; padding-top: 10px;'>Get Fit Together v{APP_VERSION}</div>", unsafe_allow_html=True)

    # ==========================================
    # 📋 6. MAIN DASHBOARD TABS (Routing Fix)
    # ==========================================
    # Base tabs visible to EVERYONE
    tab_titles = [
        "📚 Training Blueprint",
        "⚡ Daily Vitals",
        "📈 Progress Charts",
        "📋 History Log"
    ]

    # 🟢 THE FIX: Always show What's New, so we can proofread in Dev
    tab_titles.append("📢 What's New")

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

    # Default to None
    tab_changelog = None
    tab_admin = None

    # Assign What's New tab (Always exists now)
    tab_changelog = tabs[4]
    tab_idx = 5

    # Assign Admin tab if developer and local
    if role == "developer" and is_local_env:
        tab_admin = tabs[tab_idx]

    # ------------------------------------------
    # 📚 TAB 1: TRAINING BLUEPRINT
    # ------------------------------------------
    with tab1:
        st.subheader("🗓️ 12-Month Periodized Roadmap")
        st.write("---")
        
        # 🟢 List the exact names of the routines you want at the BOTTOM of the page
        # (Make sure these strings match the keys in your workouts.py perfectly!)
        bottom_modules = [
            "Daily Core", 
            "TRX Suspension Mastery", 
            "TRX Rip Trainer Power"
        ]
        
        # 🟢 TOP SECTION: Render Phases 1-4
        for q_key, q_data in ROUTINES.items():
            # Skip the bottom modules so they don't render up here
            if q_key in bottom_modules:
                continue 
                
            with st.expander(f"📌 {q_key}", expanded=False):
                st.markdown(f"🎯 **Macro Target:** *{q_data['Focus']}*")
                st.write("---")
                
                # Responsive 4-Column Exercise Layout
                cols = st.columns(4)
                for idx, (w_name, exercises) in enumerate(q_data["Workouts"].items()):
                    with cols[idx]:
                        st.markdown(f"✨ **{w_name.split(':')[0]}**")
                        st.caption(w_name.split(":")[-1].strip() if ":" in w_name else "")
                        # Inside your rendering loop in Tab 1:
                        for ex in exercises:
                            # 🟢 Split the name from the reps (e.g., "Kettlebell Swings: 10 Reps")
                            name = ex.split(":")[0].strip()
                            reps = ex.split(":")[1].strip() if ":" in ex else ""
                            
                            st.markdown(f"<div style='font-size: 13px; line-height: 1.4; margin-bottom: 4px;'>• <b>{name}</b>: {reps}</div>", unsafe_allow_html=True)
                            
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

        # 🟢 BOTTOM SECTION: Render Core & TRX Systems
        st.markdown("---")
        st.subheader("🔄 Other Training Breakdowns")
        
        for module_key in bottom_modules:
            # Verify the module actually exists in workouts.py before trying to render it
            if module_key in ROUTINES:
                module_data = ROUTINES[module_key]
                with st.expander(f"📌 {module_key}", expanded=False):
                    st.markdown(f"🎯 **Macro Target:** *{module_data['Focus']}*")
                    st.write("---")
                    
                    # 🟢 Dynamically create the right amount of columns! 
                    # (Core has 1 workout, TRX has 3. This handles both automatically)
                    num_workouts = len(module_data["Workouts"])
                    cols = st.columns(num_workouts)
                    
                    for idx, (w_name, exercises) in enumerate(module_data["Workouts"].items()):
                        with cols[idx]:
                            st.markdown(f"✨ **{w_name.split(':')[0]}**")
                            for ex in exercises:
                                st.markdown(f"<div style='font-size: 13px; line-height: 1.4; margin-bottom: 4px;'>• {ex}</div>", unsafe_allow_html=True)

    # ------------------------------------------
    # ⚡ TAB 2: DAILY VITALS (ON DEMAND FIX)
    # ------------------------------------------    
    with tab2:
        st.subheader("📊 Live Health & Readiness Dashboard")
        
        # 🟢 THE MANUAL GARMIN TRIGGER
        with st.container(border=True):
            col_g1, col_g2 = st.columns([3, 1], vertical_alignment="center")
            
            with col_g1:
                status_color = "green" if st.session_state["garmin_status"] == "Active & Synced" else "orange"
                st.markdown(f"**Garmin Connection Status:** :{status_color}[{st.session_state['garmin_status']}]")
            
            with col_g2:
                if st.button("🚀 Fetch Latest Garmin Data", type="primary", width='stretch'):
                    with st.spinner("Establishing secure link to Garmin..."):
                        try:
                            # 1. Login
                            client_instance = Garmin(g_email, g_pass)
                            client_instance.login()
                            
                            # 2. Fetch Data
                            fresh_metrics = fetch_garmin_data_layer(today, cache_id, client_instance)
                            st.session_state["daily_metrics"] = fresh_metrics
                            st.session_state["garmin_status"] = "Active & Synced"
                            
                            # 3. Sync Weight to DB
                            history_list = fresh_metrics.get("Weight_History", [])
                            if history_list and not database_locked:
                                check_and_bulk_log_garmin_weight(
                                    user_name=user,
                                    weight_history_list=history_list
                                )
                                st.session_state["force_db_refresh"] = True 
                                
                            st.rerun() 
                            
                        except Exception as e:
                            st.session_state["garmin_status"] = f"Error: {e}"
                            st.rerun()

        st.write("") # Quick Spacer
        
        # 1. Grab raw metrics from session memory
        metrics = st.session_state["daily_metrics"]
        battery_raw = metrics.get("Body Battery", 50)
        stress_raw = metrics.get("Stress", 25)
        s_score = metrics.get("Sleep Score", "--")
        
        # 2. Math Safety Fix (Prevents crashes if Garmin is disconnected)
        battery = int(battery_raw) if str(battery_raw).isdigit() else 50
        stress = int(stress_raw) if str(stress_raw).isdigit() else 25
        
        # 🟢 3. SMART WEIGHT LOGIC: Check manual Google Sheets logs first!
        display_weight = 0.0
        if not log_df.empty and "User" in log_df.columns:
            user_weight_df = log_df[log_df["User"] == user].copy()
            # Force to numbers, skipping blanks
            user_weight_df["Body Weight"] = pd.to_numeric(user_weight_df["Body Weight"], errors="coerce")
            valid_weights = user_weight_df.dropna(subset=["Body Weight"])
            valid_weights = valid_weights[valid_weights["Body Weight"] > 0]
            
            if not valid_weights.empty:
                # 🟢 THE BUG FIX: Explicitly sort by Date!
                # ascending=True puts the newest date at the absolute bottom.
                valid_weights = valid_weights.sort_values(by="Date", ascending=True)
                
                # Now iloc[-1] guarantees we grab the true newest entry
                display_weight = float(valid_weights.iloc[-1]["Body Weight"])
        
        # If no manual logs exist, fall back to the Garmin Scale API
        if display_weight == 0.0:
            display_weight = metrics.get('Weight', 0.0)

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

        col1.metric("Steps Tracked", metrics.get("Steps", "0"))
        col2.metric("Resting Heart Rate", f"{metrics.get('RHR', 60)} bpm")
        col3.metric("Body Battery", f"{battery}/100")
        col4.metric("Stress Index", f"{stress}/100")
        
        col5.metric("Sleep Score", f"{s_score} pts" if s_score != "--" else "—")
        col6.metric("Total Daily Burn", f"{metrics.get('Calories', '--')} kcal" if metrics.get('Calories') != "--" else "—")
        col7.metric("Current Weight", f"{display_weight} lbs" if display_weight > 0 else "—")
        col8.metric("Weight Goal", f"{current_goal} lbs")

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
                    y=current_goal, # Now dynamically pulls from your sidebar variable!
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
    # 📋 TAB 4: HISTORY LOG
    # ------------------------------------------
    with tab4:
        st.subheader(f"{user}'s Training History")
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
                                    st.rerun()
                            except Exception as e:
                                st.error(f"Deletion failed. System Error: {e}")

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

                    # 🟢 SEMANTIC VERSIONING AUTO-CALCULATOR
                    def calculate_next_version(current_version, categories_in_release):
                        try:
                            major, minor, patch = map(int, current_version.replace('v', '').strip().split('.'))
                            
                            if "Core" in categories_in_release:
                                major += 1
                                minor = 0
                                patch = 0
                            elif "UI" in categories_in_release:
                                minor += 1
                                patch = 0
                            elif "Bug" in categories_in_release:
                                patch += 1
                            
                            return f"{major}.{minor}.{patch}"
                        except:
                            return current_version 

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
                        today_str = str(datetime.date.today())
                        
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