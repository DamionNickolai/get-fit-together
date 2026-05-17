# --- 1. APP CONFIGURATION & IMPORTS ---
import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import datetime
import plotly.express as px

# Must be the very first Streamlit command
st.set_page_config(
    page_title="Our Fitness App",
    page_icon="💪",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 2. PASSWORD & USER ACCOUNT SYSTEM ---
def check_password():
    # If already verified in this session, don't show the login screen
    if st.session_state.get("password_correct", False):
        return True

    # Main login form container
    with st.container():
        st.subheader("🔒 Gym Access Portal")
        
        # Text input box - works with Enter key
        entered_pass = st.text_input("Enter Password", type="password", key="login_password")
        
        # Dedicated Login Button
        login_clicked = st.button("🚀 Log In", use_container_width=True, type="primary")
        
        # Trigger validation if they press Enter OR click the button
        if login_clicked or (entered_pass and st.session_state.get("last_pass") != entered_pass):
            st.session_state["last_pass"] = entered_pass # track to prevent double-firing
            
            credentials = st.secrets["passwords"]
            
            if entered_pass == credentials.get("jason"):
                st.session_state["password_correct"] = True
                st.session_state["logged_in_user"] = "Jason"
                st.session_state["user_role"] = "user"
                st.rerun()
            elif entered_pass == credentials.get("angelle"):
                st.session_state["password_correct"] = True
                st.session_state["logged_in_user"] = "Angelle"
                st.session_state["user_role"] = "user"
                st.rerun()
            elif entered_pass == credentials.get("dev_mode"):
                st.session_state["password_correct"] = True
                st.session_state["logged_in_user"] = "Jason"  # Default dev view to Jason
                st.session_state["user_role"] = "developer"   # Master flag for sandbox database
                st.rerun()
            elif entered_pass:
                st.error("😕 Password incorrect")
                return False
                
        return False
    return True

if check_password():
    # --- 3. MULTI-USER & COLOR THEMING ---
    user = st.session_state["logged_in_user"]
    role = st.session_state.get("user_role", "user")
    
    # Define theme colors based on the user session
    page_bg_color = "#1E3A8A" if user == "Jason" else "#0D9488"
    side_bg = "#162A61" if user == "Jason" else "#0A6E65"

    st.markdown(f"""
        <style>
        .stApp {{ background-color: {page_bg_color}; color: white; }}
        [data-testid="stSidebar"] {{ background-color: {side_bg} !important; opacity: 1 !important; }}
        .stTabs [data-baseweb="tab"] {{ color: white !important; }}
        </style>
        """, unsafe_allow_html=True)
    
    # Giant warning banner if logged into the Dev database environment
    if role == "developer":
        st.warning("🚧 DEV MODE ACTIVE: Connected to Workout Logs - DEV Sandbox")
        st.title(f"💪 Sandbox Environment: {user}'s Test Session")
    else:
        st.title(f"💪 Get Fit Together: {user}'s Session")

    # --- 4. DUAL-ENVIRONMENT GOOGLE SHEETS ROUTER ---
    if role == "developer":  # (Or "dev_mode", whichever your app uses)
        # Connect to the Sandbox database
        conn = st.connection("gsheets_dev", type=GSheetsConnection)
        
        # Connect to the Backlog database (DEV ONLY)
        conn_backlog = st.connection("gsheets_backlog", type=GSheetsConnection)
        
    else:
        # Connect to the Live Production database
        conn = st.connection("gsheets_prod", type=GSheetsConnection)

    try:
        log_df = conn.read(ttl=600)
        if not log_df.empty:
            log_df['Date'] = log_df['Date'].astype(str)
    except:
        log_df = pd.DataFrame(columns=["User", "Date", "Activity", "Body Weight", "Details"])

    if "current_workout_list" not in st.session_state:
        st.session_state["current_workout_list"] = []

    # --- 4.5 GARMIN INTEGRATION (SAFEGUARDED & ENVIRONMENT AWARE) ---
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
                
                tz = ZoneInfo("America/Chicago")
                today = datetime.datetime.now(tz).date().isoformat()
                
                stats = client.get_stats(today) or {}
                
                try:
                    steps_data = client.get_steps_data(today)
                except:
                    steps_data = "Endpoint unavailable"
                
                raw_steps = stats.get('totalSteps')
                steps = f"{int(raw_steps):,}" if raw_steps else "0"
                
                raw_rhr = stats.get('restingHeartRate')
                if not raw_rhr:
                    try:
                        rhr_data = client.get_rhr_day(today)
                        raw_rhr = rhr_data.get('restingHeartRate') if rhr_data else None
                    except: pass
                rhr = int(raw_rhr) if raw_rhr else "--"
                
                bb_max = "--"
                try:
                    bb_data = client.get_body_battery(today)
                    if bb_data and isinstance(bb_data, list) and len(bb_data) > 0:
                        bb_max = bb_data[0].get('charged') or bb_data[0].get('highestBodyBatteryValue') or "--"
                except: pass

                debug_info = {
                    "Date_Queried": today,
                    "Main_Stats": stats
                }

                return {"Steps": steps, "RHR": rhr, "Body Battery": bb_max, "Raw": str(debug_info)}
                
            except Exception as e:
                return {"Steps": "0", "RHR": "--", "Body Battery": "--", "Raw": f"Garmin Server Error: {str(e)}"}

        # Route Garmin API parameters dynamically based on role and active profile
        garmin_section = "garmin_dev" if role == "developer" else "garmin_prod"
        
        if user == "Jason":
            g_email = st.secrets[garmin_section]["jason_email"]
            g_pass = st.secrets[garmin_section]["jason_pass"]
        else:
            g_email = st.secrets[garmin_section]["angelle_email"]
            g_pass = st.secrets[garmin_section]["angelle_pass"]

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
    
    # Sandbox profile switcher toggle (Only appears to you if logged in via dev_mode)
    if role == "developer":
        st.sidebar.subheader("⚙️ Sandbox Controls")
        sim_user = st.sidebar.radio("Simulate User Profile:", ["Jason", "Angelle"])
        if sim_user != st.session_state["logged_in_user"]:
            st.session_state["logged_in_user"] = sim_user
            st.rerun()

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
        st.toast("Saved Successfully!")
        st.rerun()

    # --- USER LOGOUT/SWITCH & DEBUGGER ---
    st.sidebar.markdown("<br>" * 10, unsafe_allow_html=True) 
    st.sidebar.markdown("---")
    
    if st.sidebar.button("🔄 Switch User / Logout", use_container_width=True):
        st.session_state.clear()
        st.rerun()
        
    with st.sidebar.expander("🛠️ Garmin Debugger"):
        st.write(daily_metrics.get("Raw", "No raw data found"))
    
    # --- 6. MAIN DASHBOARD TABS ---
    if role == "developer":
        tab1, tab2, tab3, tab_admin = st.tabs(["📈 Progress Charts", "📅 Training History", "📚 Reference Library", "🛠️ Admin Panel"])
    else:
        tab1, tab2, tab3 = st.tabs(["📈 Progress Charts", "📅 Training History", "📚 Reference Library"])
        tab_admin = None  # Keeps the code from breaking for regular users

    with tab1:
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
       
        st.divider()

        # --- SECTION B: WEIGHT JOURNEY ---
        user_df = log_df[(log_df["User"] == user) & (log_df["Body Weight"] > 0)] if not log_df.empty else pd.DataFrame()
        if not user_df.empty:
            st.subheader(f"⚖️ {user}'s Weight Journey")
            fig_weight = px.line(user_df, x="Date", y="Body Weight", markers=True, text="Body Weight")
            fig_weight.update_traces(textposition="top center", line_color="#34D399") 
            fig_weight.update_layout(
                xaxis_title="", 
                yaxis_title="Lbs", 
                margin=dict(l=0, r=0, t=20, b=0),
                paper_bgcolor='rgba(0,0,0,0)',
                plot_bgcolor='rgba(0,0,0,0)',
                font=dict(color="white")
            )
            st.plotly_chart(fig_weight, use_container_width=True, config={'displayModeBar': False})
        
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
                                        s, w, r = float(stats[0]), float(stats[1]), float(stats[2])
                                        est_1rm = w * (36 / (37 - r)) if r < 37 else w
                                        vol = s * w * r
                                        
                                        records.append({
                                            "Date": row["Date"], 
                                            "Est 1RM": round(est_1rm, 1),
                                            "Weight (lbs)": w,
                                            "Reps": r,
                                            "Sets": s, 
                                            "Volume": vol
                                        })
                            except: continue
                    return pd.DataFrame(records).sort_values("Date") if records else pd.DataFrame()

                def draw_strength_chart(df, title):
                    if not df.empty:
                        fig = px.line(df, x="Date", y="Est 1RM", markers=True, 
                                      hover_data=["Sets", "Reps", "Weight (lbs)", "Volume"])
                        fig.update_traces(line_color="#60A5FA" if user == "Jason" else "#2DD4BF")
                        fig.update_layout(
                            xaxis_title="", 
                            yaxis_title="Est. 1RM (lbs)", 
                            margin=dict(l=0, r=0, t=10, b=0),
                            paper_bgcolor='rgba(0,0,0,0)',
                            plot_bgcolor='rgba(0,0,0,0)',
                            font=dict(color="white")
                        )
                        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
                    else:
                        st.info(f"No data for {title}.")

                st.markdown("### The Big Three")
                col1, col2 = st.columns(2)
                
                with col1:
                    st.caption("Smith Machine Squats")
                    draw_strength_chart(get_lift_df("Smith Machine Squats"), "Squats")

                with col2:
                    st.caption("Smith Machine Bench Press")
                    draw_strength_chart(get_lift_df("Smith Machine Bench Press"), "Bench Press")

                st.markdown("---")
                st.markdown("### Specialized Tracking")
                other_ex = st.selectbox("Select other exercise", ["Cable Lat Pulldowns", "Cable Rows", "Cable Woodchoppers", "Smith Machine RDLs"])
                draw_strength_chart(get_lift_df(other_ex), other_ex)

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

    # ==========================================
    # 🛠️ ADMIN PANEL: LIVE BACKLOG (DEV ONLY)
    # ==========================================
    if tab_admin:
        with tab_admin:
            st.subheader("📋 Project Backlog")
            st.caption("Live sync from Google Sheets: 'Workout Logs - Backlog'")
            
            try:
                # Securely pull the URL from secrets
                backlog_url = st.secrets["app_config"]["backlog_sheet_url"]
                backlog_df = conn.read(spreadsheet=backlog_url)
                
                # 1. Split the data to protect historical "Done" items
                active_df = backlog_df[backlog_df["Status"] != "Done"]
                done_df = backlog_df[backlog_df["Status"] == "Done"]
                
                # 2. Render an interactive data editor
                edited_df = st.data_editor(
                    active_df,
                    # NEW: Force the visual order of columns left-to-right
                    column_order=["Status", "ID", "Category", "Feature", "Priority", "Notes"],
                    column_config={
                        "Status": st.column_config.SelectboxColumn(
                            "Status",
                            help="Click to update task status",
                            options=["Not Started", "In Progress", "Done"],
                            required=True
                        )
                    },
                    # Lock all other columns so you don't accidentally edit the feature name
                    disabled=["ID", "Category", "Feature", "Priority", "Notes"], 
                    use_container_width=True,
                    hide_index=True,
                    key="backlog_editor"
                )
                
                # 3. Secure Save Mechanism
                if st.button("💾 Save Backlog Updates", type="primary"):
                    # Recombine the edited active items with the hidden Done items
                    final_df = pd.concat([edited_df, done_df], ignore_index=True).sort_values("ID")
                    
                    # Push the complete dataset back to Google Sheets
                    conn.update(data=final_df, spreadsheet=backlog_url)
                    st.cache_data.clear()  # Force Streamlit to forget the old cached data
                    st.success("Backlog successfully updated in Google Sheets!")
                    st.rerun()
                    
            except Exception as e:
                st.error(f"Failed to load the backlog. Check your connection: {e}")

