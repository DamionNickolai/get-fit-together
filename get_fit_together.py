# --- 1. APP CONFIGURATION & IMPORTS ---
import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import datetime
import plotly.express as px
import hashlib # 🟢 Added for secure mobile tokens
APP_VERSION = "1.1.0"

# Must be the very first Streamlit command
st.set_page_config(
    page_title="Get Fit Together",
    page_icon="💪",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 🟢 Bring in the login module!
from auth import check_password

# 🟢 Bring in the database automation helpers!
from database import check_and_bulk_log_garmin_weight, check_and_autolog_garmin_weight

# 🟢 Bring in the static workout database!
from workouts import ROUTINES

# --- 2. ENVIRONMENT DETECTION & PASSWORD SYSTEM ---
if check_password():
    # --- 3. DYNAMIC METADATA & COLOR THEMING ---
    user = st.session_state["logged_in_user"]
    role = st.session_state["user_role"]
    
    # 🟢 NEW: Pulls from the database dictionary we cached during login
    current_profile = st.session_state.get("profile_data", {})
    
    # Mapped directly to your exact Google Sheets headers
    page_bg_color = current_profile.get("Primary_Color", "#1F2937")
    side_bg = current_profile.get("Sidebar_Color", "#111827")
    chart_line_color = current_profile.get("Line_Color", "#34D399")

    st.markdown(f"""
        <style>
        .stApp {{ background-color: {page_bg_color}; color: white; }}
        [data-testid="stSidebar"] {{ background-color: {side_bg} !important; opacity: 1 !important; }}
        .stTabs [data-baseweb="tab"] {{ color: white !important; }}
        </style>
        """, unsafe_allow_html=True)

    # 📡 THE BUG RADAR (Only alerts if you are the developer)
    if role == "developer":
        try:
            # Quick read of the backlog to check for unresolved bugs
            conn_radar = st.connection("gsheets_backlog", type=GSheetsConnection)
            radar_df = conn_radar.read(ttl=600)
            
            if not radar_df.empty and "Category" in radar_df.columns and "Status" in radar_df.columns:
                # Count how many tickets are marked as Bug AND are still in the Backlog
                active_bugs = radar_df[(radar_df["Category"] == "Bug") & (radar_df["Status"] == "Backlog")]
                bug_count = len(active_bugs)
                
                if bug_count > 0:
                    st.warning(f"🐞 **Developer Alert:** You have {bug_count} unresolved bug report(s) waiting in the Admin Panel.")
        except Exception:
            pass # Fails silently so it doesn't interrupt your workout logging

    # --- 4. DUAL-ENVIRONMENT GOOGLE SHEETS ROUTER ---
    # 🟢 THE FIX: Routing is now tied to the environment, NOT your role.
    is_local_env = st.session_state.get("is_environment_local", False)
    if is_local_env:
        conn = st.connection("gsheets_dev", type=GSheetsConnection)
        st.warning("🚧 DEV MODE ACTIVE: Connected to Workout Logs - DEV Sandbox")
    else:
        conn = st.connection("gsheets_prod", type=GSheetsConnection)

    # 🟢 THE FIX: The Title UI now checks both your role AND your environment!
    is_local_env = st.session_state.get("is_environment_local", False)

    if role == "developer" and is_local_env:
        st.title(f"💪 Developer Sandbox: {user}")
    else:
        st.title(f"💪 Get Fit Together: {user}'s Session")

    # 🟢 THE READ-ONLY LOCK FLAG
    database_locked = False
    
    try:
        # 🟢 THE FIX: If we just wrote new data, bypass the 10-minute cache!
        if st.session_state.get("force_db_refresh", False):
            log_df = conn.read(ttl=0) 
            st.session_state["force_db_refresh"] = False # Reset the flag
        else:
            log_df = conn.read(ttl=600)
            
        if not log_df.empty:
            log_df['Date'] = log_df['Date'].astype(str)
    except Exception as db_err:
        print(f"⚠️ DATABASE READ FAILED: {db_err}")
        database_locked = True 
        log_df = pd.DataFrame(columns=["User", "Date", "Activity", "Body Weight", "Details"])
        st.error("⚠️ Cloud Database Sync Failed. The app is in Read-Only mode to protect your data. Please refresh.")
    
    # 🟢 THE FIX: Define g_prefix safely outside the try block so it always exists!
    g_prefix = current_profile.get("Garmin_Prefix", "unknown")

    try:
        from garminconnect import Garmin
        from zoneinfo import ZoneInfo
        import datetime

        tz = ZoneInfo("America/Chicago")
        today = datetime.datetime.now(tz).date().isoformat()

        if st.session_state.get("is_environment_local", False):
            garmin_section = "garmin_dev"
        else:
            garmin_section = "garmin_prod"

        # Build identity keys using the safely defined prefix
        g_email = st.secrets[garmin_section].get(f"{g_prefix}_email", "")
        g_pass  = st.secrets[garmin_section].get(f"{g_prefix}_pass", "")

        # Session key for Garmin client
        client_key = f"live_garmin_client_{g_prefix}"

        # Cache partition key (prevents cross-user data leaks)
        cache_id = f"{g_prefix}:{user}:{today}"

        # 🟢 RESTORED: Put Garmin in Standby Mode to prevent API rate-limiting
        is_dev_sandbox = (role == "developer" and st.session_state.get("is_environment_local", False))
        connect_garmin_clicked = False
        
        # Only show the button if they are a dev, local, and haven't connected yet!
        if is_dev_sandbox and client_key not in st.session_state:
            st.sidebar.info("🚧 Garmin API: Standby Mode")
            connect_garmin_clicked = st.sidebar.button("🚀 Connect to Garmin", use_container_width=True)

        # Determine if we should pull the trigger on the API
        run_login_sequence = False
        if client_key not in st.session_state:
            if not is_dev_sandbox:
                run_login_sequence = True # Auto-login for Production and normal Users
            elif connect_garmin_clicked:
                run_login_sequence = True # Manual override for the Developer

        # Create Garmin client if the trigger was pulled
        if run_login_sequence:
            if g_email and g_pass:
                with st.spinner("Establishing secure link to Garmin..."):
                    try:
                        # 🚨 THE ANTI-FREEZE FIX & TERMINAL DEBUGGER
                        print(f"Attempting Garmin login for: {g_email}")
                        client_instance = Garmin(g_email, g_pass)
                        client_instance.login()
                        st.session_state[client_key] = client_instance
                        print("✅ Garmin login successful!")
                    except Exception as garmin_err:
                        # Catches the freeze and forces the app to continue running
                        print(f"❌ GARMIN API ERROR: {garmin_err}")
                        st.session_state[client_key] = None 
                        st.sidebar.error(f"Garmin Sync Failed: {garmin_err}")

        active_client = st.session_state.get(client_key, None)
        
        # 🟢 NEW: Import the Garmin data fetcher from your new module
        from garmin_api import fetch_garmin_data_layer

        if active_client:
            daily_metrics = fetch_garmin_data_layer(today, cache_id, active_client)
            garmin_status = "active"

            history_list = daily_metrics.get("Weight_History", [])

            # 🟢 THE FIX: Lock the auto-sync so it only runs ONCE per session!
            if history_list and not database_locked:
                if not st.session_state.get("garmin_auto_synced", False):
                    check_and_bulk_log_garmin_weight(
                        conn_history=conn,
                        df_history=log_df,
                        user_name=user,
                        weight_history_list=history_list
                    )
                    st.session_state["garmin_auto_synced"] = True
                    st.session_state["force_db_refresh"] = True # Forces fresh read on next run
        else:
            # 🟢 NEW: Accurately reports Standby vs Missing status
            garmin_status = "dev_standby" if (is_dev_sandbox and client_key not in st.session_state) else "missing_secrets"
            daily_metrics = {
                "Steps": "0",
                "RHR": 60,
                "Body Battery": 50,
                "Stress": "--",
                "Calories": "--",
                "HRV": "--",
                "Sleep Score": "--",
                "Weight": 0.0,
                "Weight Goal": "--",
                "Weight_History": [],
                "Raw": "No active client"
            }

    except KeyError as e:
        garmin_status = "missing_secrets"
        daily_metrics = {
            "Steps": "0",
            "RHR": 60,
            "Body Battery": 50,
            "Stress": "--",
            "Calories": "--",
            "HRV": "--",
            "Sleep Score": "--",
            "Weight": 0.0,
            "Weight Goal": "--",
            "Weight_History": [],
            "Raw": f"Outer Error: {e}"
        }

    except Exception as outer_e:
        garmin_status = "unknown_error"
        daily_metrics = {
            "Steps": "0",
            "RHR": 60,
            "Body Battery": 50,
            "Stress": "--",
            "Calories": "--",
            "HRV": "--",
            "Sleep Score": "--",
            "Weight": 0.0,
            "Weight Goal": "--",
            "Weight_History": [],
            "Raw": f"Outer Error: {outer_e}"
        }

    # --- 5. LOGGING SIDEBAR (Ultra-Clean Input Only) ---
    st.sidebar.header("🏋️ Log a Session")
    
    # 🟢 NEW PHASE SELECTION MAPPER
    # The user sees the short name, but Python uses the long name for the database
    phase_options = ["Phase 1", "Phase 2", "Phase 3", "Phase 4", "Custom"]
    selected_short_phase = st.sidebar.selectbox("Phase", options=phase_options, index=0)
    
    phase_map = {
        "Phase 1": "Phase 1: Foundation & Endurance",
        "Phase 2": "Phase 2: Hypertrophy (Muscle Building)",
        "Phase 3": "Phase 3: Strength & Power",
        "Phase 4": "Phase 4: Metabolic Conditioning",
        "Custom": "Custom"
    }
    
    selected_q = phase_map[selected_short_phase]
    
    date_input = st.sidebar.date_input("Date", datetime.date.today())
    
    # 🔄 DATA ROUTING ENGINE
    details_prefix = ""
    show_weight_box = False
    
    if selected_q != "Custom":
        selected_w = st.sidebar.selectbox("Select Session", list(ROUTINES[selected_q]["Workouts"].keys()))
        
        if "Outdoor" in selected_w:
            # 🟢 QoL FIX: Skip the dropdown entirely and set a standard database entry
            activity_value = "Outdoor Activity" 
            details_prefix = f"🌲 [{selected_q} - Outdoor] "
        else:
            # 🟢 DYNAMIC EXERCISE GENERATOR
            raw_exercises = ROUTINES[selected_q]["Workouts"][selected_w]
            
            clean_exercises = []
            for ex in raw_exercises:
                clean_name = ex.split(":")[0].strip()
                if clean_name.startswith("- "): clean_name = clean_name[2:]
                clean_exercises.append(clean_name)
                
            activity_value = st.sidebar.selectbox("Exercise / Activity", clean_exercises)
            short_w_name = selected_w.split(":")[0]
            details_prefix = f"🏋️ [{selected_q} - {short_w_name}] "
            
    else:
        # 🟢 UPGRADED CUSTOM PHASE
        custom_session = st.sidebar.selectbox("Session Type", ["Full Body Circuit", "Mountain Biking", "Hiking", "Walking", "Mobility / Stretching", "Body Weight Only"])
        
        if custom_session == "Body Weight Only":
            show_weight_box = True
            activity_value = "Body Weight Only"
            details_prefix = ""
        elif custom_session in ["Mountain Biking", "Hiking", "Walking", "Mobility / Stretching"]:
            activity_value = custom_session
            details_prefix = f"📋 [Custom Phase] "
        else:
            master_exercises = []
            for q_key, q_data in ROUTINES.items():
                for w_key, ex_list in q_data["Workouts"].items():
                    if "Outdoor" not in w_key:
                        for ex in ex_list:
                            clean_name = ex.split(":")[0].strip()
                            if clean_name.startswith("- "): clean_name = clean_name[2:]
                            
                            if clean_name not in master_exercises and "AMRAP" not in clean_name and "Cycle continuously" not in clean_name and "⏱️" not in clean_name:
                                master_exercises.append(clean_name)
            
            master_exercises.sort()
            master_exercises.append("Other (Specify in Notes)")
            
            activity_value = st.sidebar.selectbox("Exercise / Activity", master_exercises)
            details_prefix = "🏋️ [Custom - Full Body Circuit] "

    # 🟢 THE GHOST WIDGET FIX: Create a resetting ID counter
    if "form_reset" not in st.session_state:
        st.session_state["form_reset"] = 0
    reset_id = st.session_state["form_reset"]

    # 2. ⚖️ DYNAMIC WEIGHT DISPLAY
    if show_weight_box:
        weight_input = st.sidebar.text_input("Body Weight (lbs)", key=f"bw_{reset_id}")
    else:
        weight_input = ""

    # 3. 📝 STRUCTURED LIFT TRACKING
    if selected_q == "Custom":
        non_lifting = ["Body Weight Only", "Mountain Biking", "Hiking", "Walking", "Mobility / Stretching"]
        show_lift_stats = custom_session not in non_lifting
    else:
        show_lift_stats = "Outdoor" not in selected_w and "Cycle continuously" not in activity_value
        
    structured_log = ""

    if show_lift_stats:
        st.sidebar.markdown("### 📝 Lift Tracking Stats")
        
        # The "Last Performed" Memory Query
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

        col_sets, col_reps, col_weight = st.sidebar.columns(3)
        with col_sets:
            input_sets = st.text_input("Sets", key=f"sets_{reset_id}")
        with col_reps:
            input_reps = st.text_input("Reps", key=f"reps_{reset_id}")
        with col_weight:
            input_weight_lifted = st.text_input("Weight", key=f"wgt_{reset_id}")

        if input_sets.strip() or input_reps.strip() or input_weight_lifted.strip():
            try:
                sets_val = int(input_sets) if input_sets.strip() else 0
                reps_val = int(input_reps) if input_reps.strip() else 0
                weight_val = float(input_weight_lifted) if input_weight_lifted.strip() else 0.0
                if sets_val > 0 or reps_val > 0 or weight_val > 0.0:
                    structured_log = f"{sets_val} Sets | {reps_val} Reps | {weight_val} lbs "
            except ValueError:
                pass

    elif selected_q != "Custom" and "Outdoor" in selected_w:
        # 🟢 THE NEW OUTDOOR DURATION TRACKER
        st.sidebar.markdown("### ⏱️ Session Duration")
        input_duration = st.sidebar.text_input("Duration (Minutes)", key=f"dur_{reset_id}")

        if input_duration.strip():
            try:
                duration_val = int(input_duration)
                if duration_val > 0:
                    structured_log = f"⏱️ {duration_val} mins "
            except ValueError:
                pass

    # 4. 📝 UNIVERSAL NOTES BOX
    extra_notes = st.sidebar.text_input("Notes / Explanation", placeholder="Optional: Provide any details...", key=f"notes_{reset_id}")

    # 5. 🔄 STRING ASSEMBLY
    if extra_notes.strip():
        user_details = f"{structured_log}- {extra_notes.strip()}" if structured_log else extra_notes.strip()
    else:
        user_details = structured_log.strip()
        
    final_details = f"{details_prefix}{user_details}" if details_prefix else user_details

    if st.sidebar.button("💾 Log Activity", type="primary", use_container_width=True):
        if database_locked:
            st.sidebar.error("Database connection is currently unstable. Please refresh the page so we don't overwrite your data.")
        elif not user_details.strip() and "Outdoor" not in final_details:
            st.sidebar.warning("Please add some workout details before submitting!")
        else:
            with st.spinner("Syncing to cloud master sheets..."):
                try:
                    # 🟢 BULLETPROOF FLOAT CONVERSION
                    # We check for empty strings, None values, and format errors
                    if weight_input == "" or weight_input is None:
                        final_weight = 0.0
                    else:
                        try:
                            final_weight = float(weight_input)
                        except:
                            final_weight = 0.0

                    new_log = {
                        "User": user,
                        "Date": str(date_input),
                        "Activity": activity_value,
                        "Body Weight": final_weight, # Guaranteed to be a safe number!
                        "Details": final_details
                    }
                    
                    new_row_df = pd.DataFrame([new_log])
                    log_df = pd.concat([log_df, new_row_df], ignore_index=True)
                    conn.update(data=log_df)
                    
                    # Trigger the cache bypass instead of a global wipe
                    st.session_state["force_db_refresh"] = True
                    
                    # Force the auto-clear ghost ID to cycle
                    st.session_state["form_reset"] += 1
                    
                    st.sidebar.success("🔥 Activity Successfully Logged!")
                    st.rerun()
                except Exception as log_err:
                    st.sidebar.error(f"Failed to log entry: {log_err}")
    
    # ==========================================
    # ⚙️ SIDEBAR UTILITY FOOTER 
    # ==========================================
    st.sidebar.markdown("---")
    
    # 🔄 1. Public Log Out Button (Visible to everyone)
    if st.sidebar.button("🚪 Switch User / Log Out", use_container_width=True):
        for key in list(st.session_state.keys()):
            if "live_garmin_client" in key or "garmin_token" in key:
                del st.session_state[key]
        
        st.session_state["password_correct"] = False
        st.session_state["logged_in_user"] = None
        st.session_state["user_role"] = None
        
        # 🟢 Wipes the magic URL tokens
        st.query_params.clear() 
        st.rerun()

    # 🟢 2. THE PANIC BUTTON (Public Bug Reporter)
    with st.sidebar.expander("🐛 Report an Issue"):
        # Wrap in a form so it clears instantly on submit
        with st.form(key=f"bug_report_{reset_id}", clear_on_submit=True):
            st.caption("Did something break? Tell the developer directly!")
            bug_text = st.text_area("What happened?", placeholder="e.g., The cardio duration box isn't showing up.")
            submit_bug = st.form_submit_button("📤 Send to Developer", type="secondary", use_container_width=True)
            
            if submit_bug:
                if not bug_text.strip():
                    st.warning("Please type a message first.")
                else:
                    with st.spinner("Sending..."):
                        try:
                            # Connect to your Admin Backlog sheet
                            conn_backlog = st.connection("gsheets_backlog", type=GSheetsConnection)
                            df_backlog = conn_backlog.read(ttl=0) # Force fresh read
                            
                            # Format it perfectly to match your Tab 6 Admin panel structure
                            new_ticket = {
                                "Status": "Backlog",
                                "Category": "Bug",
                                "Feature": f"User Report: {user}",
                                "Priority": "High", 
                                "Notes": bug_text.strip(), # Moves their complaint to the Notes column
                                "Public Message": "",
                                "Release Date": "",
                                "Version": ""
                            }
                            
                            new_ticket_df = pd.DataFrame([new_ticket])
                            updated_backlog = pd.concat([df_backlog, new_ticket_df], ignore_index=True)
                            
                            conn_backlog.update(data=updated_backlog)
                            st.success("✅ Sent! Thanks for the feedback.")
                        except Exception as bug_err:
                            st.error(f"Failed to send: {bug_err}")

    # 🔒 3. THE DEV LOCK: Only show the backend debugging tools to developers
    if role == "developer":
        
        # 🛠️ Garmin Debugger Expander (Dev Only)
        with st.sidebar.expander("🛠️ Garmin System Debugger"):
            st.caption(f"**Connection Status:** `{garmin_status.upper()}`")
            st.caption(f"**Target Profile Prefix:** `{g_prefix}`")
            
            if st.button("🧹 Clear Garmin Data Cache", use_container_width=True):
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

    # 🏷️ 4. Application Version Tag (Public)
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

    # 🟢 THE FIX: Only show What's New tab in production
    if not is_local_env:
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

    # Assign What's New tab only if it exists (production only)
    tab_idx = 4
    if not is_local_env:
        tab_changelog = tabs[tab_idx]
        tab_idx += 1

    # Assign Admin tab if developer and local
    if role == "developer" and is_local_env:
        tab_admin = tabs[tab_idx]

    # ------------------------------------------
    # 📚 TAB 1: TRAINING BLUEPRINT
    # ------------------------------------------
    with tab1:
        st.subheader("🗓️ 12-Month Periodized Roadmap")
        st.write("---")
        
        # 🟢 THE FIX: Removed the active banner, and forced expanded=False for all cards
        for q_key, q_data in ROUTINES.items():
            with st.expander(f"📌 {q_key}", expanded=False):
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
        
        # 1. Grab raw metrics
        battery_raw = daily_metrics.get("Body Battery", 50)
        stress_raw = daily_metrics.get("Stress", 25)
        s_score = daily_metrics.get("Sleep Score", "--")
        
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
                display_weight = float(valid_weights.iloc[-1]["Body Weight"]) # Grabs your newest entry
        
        # If no manual logs exist, fall back to the Garmin Scale API
        if display_weight == 0.0:
            display_weight = daily_metrics.get('Weight', 0.0)

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
        col7.metric("Current Weight Scale", f"{display_weight} lbs" if display_weight > 0 else "—")
        col8.metric("Garmin Weight Goal", daily_metrics.get("Weight Goal", "—"))

    # ------------------------------------------
    # 📈 TAB 3: PROGRESS CHARTS
    # ------------------------------------------
    with tab3:
        st.subheader("📈 Exercise Performance Progression")
        if log_df.empty:
            st.info("No training data found in the cloud logs to plot yet.")
        else:
            # 🟢 THE FIX: Force numbers, remove blanks, and plot all weight ins!
            chart_df = log_df[log_df["User"] == user].copy()
            chart_df["Body Weight"] = pd.to_numeric(chart_df["Body Weight"], errors="coerce")
            
            # Filter down to only rows where a valid weight was logged
            weight_trend_df = chart_df.dropna(subset=["Body Weight"])
            weight_trend_df = weight_trend_df[weight_trend_df["Body Weight"] > 0]
            
            if not weight_trend_df.empty:
                st.line_chart(data=weight_trend_df, x="Date", y="Body Weight")
                st.caption("Historical weight performance data tracked across your active sessions.")
            else:
                st.info("Log a few sessions with your body weight to light up your chart metrics!")

    # ------------------------------------------
    # 📋 TAB 4: HISTORY LOG
    # ------------------------------------------
    with tab4:
        st.subheader(f"{user}'s Training History")
        if not log_df.empty:
            user_history_df = log_df[log_df["User"] == user].sort_values(by="Date", ascending=False)
            if not user_history_df.empty:
                
                # 🟢 THE QoL FIX: Hides "User", and width commands removed to prevent crashes!
                edited_df = st.data_editor(
                    user_history_df, 
                    num_rows="dynamic", 
                    disabled=["Date", "Activity", "Body Weight", "Details"], 
                    column_config={
                        "User": None  
                    },
                    key="log_editor"
                )
                
                if len(edited_df) < len(user_history_df):
                    if st.button("🔴 Confirm Deletion and Update Sheet", type="primary"):
                        other_users_df = log_df[log_df["User"] != user]
                        final_df = pd.concat([other_users_df, edited_df], ignore_index=True)
                        conn.update(data=final_df)
                        st.success("Google Sheet Updated!")
                        st.rerun()
            else:
                st.info("No history found for this user.")

   # ==========================================
    # TAB 5: 📢 WHAT'S NEW (CHANGELOG) - PRODUCTION ONLY
    # ==========================================
    if tab_changelog is not None:
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

                        # 🟢 THE FIX: Only show items with Release Date today or in the past
                        today = str(datetime.date.today())
                        try:
                            done_items["Release Date"] = pd.to_datetime(done_items["Release Date"], errors="coerce")
                            today_date = pd.to_datetime(today)
                            done_items = done_items[done_items["Release Date"] <= today_date]
                            done_items["Release Date"] = done_items["Release Date"].dt.strftime("%Y-%m-%d")
                        except Exception:
                            pass

                        if not done_items.empty:
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
                            st.info("No released updates yet. Updates are coming soon!")
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
                
                # --- NEW CACHING LOGIC STARTS HERE ---
                col_head1, col_head2 = st.columns([4, 1])
                with col_head1:
                    st.write("Manage Active App Backlog & QoL Features:")
                with col_head2:
                    # Manual refresh button for the developer
                    if st.button("🔄 Refresh Data", use_container_width=True):
                        st.session_state["force_admin_refresh"] = True
                
                # Check if we need a fresh read, otherwise use the 10-minute cache
                if st.session_state.get("force_admin_refresh", False):
                    df_backlog = conn_backlog.read(ttl=0) 
                    st.session_state["force_admin_refresh"] = False # Reset flag
                else:
                    df_backlog = conn_backlog.read(ttl=600)
                # --- NEW CACHING LOGIC ENDS HERE ---
                
                # --- KEEP EVERYTHING BELOW EXACTLY AS YOU HAD IT ---
                for col in ["Public Message", "Release Date", "Version"]:
                    if col not in df_backlog.columns: df_backlog[col] = ""
                    df_backlog[col] = df_backlog[col].astype(str).replace("nan", "")
                
                if "Status" in df_backlog.columns:
                    cols = ["Status"] + [col for col in df_backlog.columns if col != "Status"]
                    df_backlog = df_backlog[cols]
                    df_display = df_backlog[df_backlog["Status"] != "Done"]
                else:
                    df_display = df_backlog
                
                # 🛑 KEEP THIS: This is your interactive table!
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
                                        
                    # 🟢 FIX 2: Wipe the editor's ghost memory before the rerun!
                    if "admin_backlog_editor" in st.session_state:
                        del st.session_state["admin_backlog_editor"]
                    
                    # --- NEW: Force a refresh so the UI updates ---
                    st.session_state["force_admin_refresh"] = True 
                        
                    st.rerun()

            except Exception as e:
                st.error(f"Failed to load the backlog. System Error: {e}")