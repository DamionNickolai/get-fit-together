import streamlit as st
from supabase import create_client, Client
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import pandas as pd

# 🟢 Initialize the connection to your cloud database
@st.cache_resource
def init_connection() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_SERVICE_KEY"]
    return create_client(url, key)

supabase = init_connection()

def get_target_table():
    """Checks the environment in secrets.toml and returns the correct table name."""
    try:
        # Check the new app_config dictionary in your secrets
        env = st.secrets["app_config"].get("environment", "production")
        return "history_dev" if env == "local" else "history"
    except Exception:
        # Defaults to 'history' (production) if something goes wrong
        return "history"

def get_user_history_df(user_name):
    """Fetches a user's history from the appropriate Supabase environment table."""
    target_table = get_target_table()
    try:
        response = supabase.table(target_table).select("*").eq("User", user_name).order("Date", desc=True).limit(50).execute()
        
        if response.data:
            df = pd.DataFrame(response.data)
            # Ensure we only rename if the column exists
            if "Body_Weight" in df.columns:
                df = df.rename(columns={"Body_Weight": "Body Weight"})
            return df
            
        # 🟢 THE FIX: If they have no data, return an empty table that STILL has the right column headers!
        return pd.DataFrame(columns=["id", "User", "Date", "Activity", "Body Weight", "Details"])
        
    except Exception as e:
        print(f"Error reading history from Supabase: {e}")
        # 🟢 Catch the error with the same blank template
        return pd.DataFrame(columns=["id", "User", "Date", "Activity", "Body Weight", "Details"])

def check_and_autolog_garmin_weight(user_name, today_date, garmin_weight_lbs):
    """Inserts a single Garmin weight entry safely without creating duplicates."""
    if not garmin_weight_lbs or float(garmin_weight_lbs) <= 0.0:
        return False
        
    target_table = get_target_table()
    try:
        # Check if this exact day is already synced from Garmin
        existing = supabase.table(target_table).select("id").eq("User", user_name).eq("Date", str(today_date)).eq("Activity", "Body Weight").ilike("Details", "%Automated Garmin%").execute()
        
        if existing.data and len(existing.data) > 0:
            return False # Skip: Already synced today!

        supabase.table(target_table).insert({
            "User": user_name,
            "Date": str(today_date),
            "Activity": "Body Weight",
            "Body_Weight": float(garmin_weight_lbs),
            "Details": f"🤖 Automated Garmin Index Scale Sync ({garmin_weight_lbs} lbs)"
        }).execute()
        return True
    except Exception as e:
        print(f"Auto-weight sync failed: {e}")
        return False

def check_and_bulk_log_garmin_weight(user_name, weight_history_list):
    """Bulk inserts 30-day Garmin weight entries without creating duplicates."""
    if not weight_history_list or len(weight_history_list) == 0:
        return False
        
    target_table = get_target_table()
    
    try:
        # 🟢 FIX #1: Convert to set for O(1) lookup instead of O(n) list search
        # Extract the dates we want to check FIRST
        dates_to_check = [str(entry["date"]) for entry in weight_history_list]
        
        # 1. Query Supabase ONLY for the dates we care about (not all dates)
        existing_response = supabase.table(target_table).select("Date").eq("User", user_name).eq("Activity", "Body Weight").ilike("Details", "%Automated Garmin%").in_("Date", dates_to_check).execute()
        
        # 🟢 Convert to SET for O(1) membership testing
        existing_dates = set(row["Date"] for row in (existing_response.data or []))

        rows_to_insert = []
        for entry in weight_history_list:
            g_weight = float(entry["weight"])
            entry_date = str(entry["date"])
            
            # 2. Only queue it for insert if the date is missing from the database
            if g_weight > 0.0 and entry_date not in existing_dates:
                rows_to_insert.append({
                    "User": user_name,
                    "Date": entry_date,
                    "Activity": "Body Weight",
                    "Body_Weight": g_weight,
                    "Details": f"🤖 Automated Garmin Index Scale Sync ({g_weight} lbs)"
                })
                
        if not rows_to_insert:
            return False # Nothing new to add, exit cleanly

        # 3. Execute the bulk insert for only the new dates
        supabase.table(target_table).insert(rows_to_insert).execute()
        return True
        
    except Exception as e:
        print(f"Bulk auto-weight sync error: {e}")
        return False
    
def log_manual_entry(user_name, log_date, activity, body_weight, details):
    """Inserts a manual workout or weight log into the appropriate Supabase environment table."""
    target_table = get_target_table()
    
    # Clean up the weight variable (Supabase wants a float or a null, not an empty string)
    weight_val = float(body_weight) if body_weight else None
    
    try:
        supabase.table(target_table).insert({
            "User": user_name,
            "Date": str(log_date),
            "Activity": activity,
            "Body_Weight": weight_val,
            "Details": details
        }).execute()
        return True
    except Exception as e:
        print(f"Manual log failed: {e}")
        return False
    
def get_garmin_target_table():
    """Returns the correct garmin metrics table based on environment."""
    try:
        env = st.secrets["app_config"].get("environment", "production")
        return "garmin_metrics_dev" if env == "local" else "garmin_metrics"
    except Exception:
        return "garmin_metrics"

def log_daily_garmin_metrics(user_name, log_date, metrics):
    """Saves today's Garmin metrics to the database to prevent re-fetching."""
    target_table = get_garmin_target_table()
    
    try:
        # Check if today is already logged
        existing = supabase.table(target_table).select("id").eq("User", user_name).eq("Date", str(log_date)).execute()
        
        payload = {
            "User": user_name,
            "Date": str(log_date),
            "Steps": metrics.get("Steps", "0"),
            "RHR": metrics.get("RHR", 60),
            "Body_Battery": metrics.get("Body Battery", 50),
            "Stress": metrics.get("Stress", "--"),
            "Calories": metrics.get("Calories", "--"),
            "HRV": metrics.get("HRV", "--"),
            "Sleep_Score": metrics.get("Sleep Score", "--")
        }
        
        if existing.data:
            # Update existing record
            supabase.table(target_table).update(payload).eq("id", existing.data[0]["id"]).execute()
        else:
            # Insert new record
            supabase.table(target_table).insert(payload).execute()
        return True
    except Exception as e:
        print(f"Failed to log Garmin metrics: {e}")
        return False

def get_recent_garmin_metrics(user_name, limit=7):
    """Fetches the last N days of Garmin metrics for the AI Coach."""
    target_table = get_garmin_target_table()
    try:
        response = supabase.table(target_table).select("*").eq("User", user_name).order("Date", desc=True).limit(limit).execute()
        if response.data:
            return pd.DataFrame(response.data)
        return pd.DataFrame()
    except Exception as e:
        print(f"Error reading Garmin metrics: {e}")
        return pd.DataFrame()
    
def get_all_time_prs(user_name):
    """
    Fetches the all-time max weight (PR) for EVERY exercise the user has ever logged.
    Uses a lightweight 'skinny query' to protect app performance.
    """
    target_table = get_target_table()
    try:
        # 🚀 SKINNY QUERY: We only pull the two columns we need.
        response = supabase.table(target_table).select("Activity, Details").eq("User", user_name).execute()
        
        if not response.data:
            return {}

        df = pd.DataFrame(response.data)

        # 1. Extract the weight using Regex. 
        # This perfectly catches both manual logs ("| 150 lbs") and AI logs ("🤖 3 Sets | 12 Reps | 150.0 lbs")
        df["Weight"] = df["Details"].str.extract(r'\|\s*([0-9.]+)\s*lbs').astype(float)

        # 2. Drop rows where no weight was found (e.g., Bodyweight exercises or Garmin syncs)
        df = df.dropna(subset=["Weight"])

        # 3. Calculate the absolute max weight for EVERY activity instantly
        pr_series = df.groupby("Activity")["Weight"].max()

        # Return a clean dictionary: e.g., {"Smith Machine Press": 150.0, "Squat": 225.0}
        return pr_series.to_dict()

    except Exception as e:
        print(f"Error calculating PRs: {e}")
        return {}

def get_user_profile(user_name):
    """Fetches the user's permanent dossier (phase, equipment, injuries) from Supabase."""
    try:
        # We always read from the main profile table, regardless of dev/prod environment
        response = supabase.table("gym_user_profiles").select("*").eq("username", user_name).execute()
        
        if response.data and len(response.data) > 0:
            return response.data[0] # Return the dictionary of their profile
        else:
            # Fallback default if they don't have a profile yet
            return {
                "current_phase": "Phase 1: Foundation & Endurance",
                "available_equipment": "Full Gym",
                "nagging_injuries": "None"
            }
    except Exception as e:
        print(f"Error fetching profile: {e}")
        return None

def get_chat_target_table():
    """Returns the correct coach chat table based on environment."""
    try:
        env = st.secrets["app_config"].get("environment", "production")
        return "coach_chat_history_dev" if env == "local" else "coach_chat_history"
    except Exception:
        return "coach_chat_history"

def save_coach_message(username, role, content, visuals=None, video_url=None):
    """Silently saves a single chat message to Supabase."""
    target_table = get_chat_target_table()
    try:
        data = {
            "username": username,
            "role": role,
            "content": content,
            "visuals": visuals,
            "video_url": video_url
        }
        supabase.table(target_table).insert(data).execute()
    except Exception as e:
        print(f"DB Save Error: {e}")

def get_todays_chat(username):
    """Fetches all chat messages for the user from exactly midnight Central Time to now."""
    target_table = get_chat_target_table()
    try:
        # Calculate midnight of today to ensure we only get "today's" amnesia-free chat
        today_start = datetime.now(ZoneInfo("America/Chicago")).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        
        response = supabase.table(target_table)\
            .select("*")\
            .eq("username", username)\
            .gte("created_at", today_start)\
            .order("created_at", desc=False)\
            .execute()
            
        return response.data
    except Exception as e:
        print(f"DB Fetch Error: {e}")
        return []
    
def clear_todays_chat(username):
    """Deletes only today's chat history so the user can start fresh."""
    target_table = get_chat_target_table()
    try:
        today_start = datetime.now(ZoneInfo("America/Chicago")).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        supabase.table(target_table)\
            .delete()\
            .eq("username", username)\
            .gte("created_at", today_start)\
            .execute()
    except Exception as e:
        print(f"DB Delete Error: {e}")

def ai_log_workout_set(user_name: str, exercise_name: str, sets: int, reps: int, weight_lbs: float, notes: str = "") -> str:
    """
    Logs a completed workout exercise to the user's fitness tracking database.
    Call this tool WHENEVER the user tells you they just finished a set, lifted a weight, or completed an exercise.
    
    Args:
        user_name: The name of the user (provided in the system prompt).
        exercise_name: The specific name of the exercise (e.g., 'Smith Machine Press', 'Kettlebell Swings').
        sets: The total number of sets completed.
        reps: The number of repetitions performed per set.
        weight_lbs: The weight lifted in pounds. Use 0.0 if it is a bodyweight exercise.
        notes: Any extra context, feelings, or modifications the user mentions (e.g., 'felt heavy', 'left knee popped', 'blah blah blah'). Leave blank if they don't mention anything.
    """
    try:
        # Format today's date exactly how your database expects it
        today_str = datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d")
        
        # Build a clean string that perfectly matches your historical manual logs!
        if weight_lbs > 0:
            details_str = f"🤖 {sets} Sets | {reps} Reps | {float(weight_lbs)} lbs"
        else:
            details_str = f"🤖 {sets} Sets | {reps} Reps | Bodyweight"
            
        # 🟢 THE NOTES UPGRADE: Append the custom notes if the AI extracted any!
        if notes:
            details_str += f" - {notes.strip()}"
            
        # Pass the extracted data into your existing manual log function!
        success = log_manual_entry(
            user_name=user_name, 
            log_date=today_str, 
            activity=exercise_name, 
            body_weight=None, 
            details=details_str
        )
        
        if success:
            return f"SUCCESS: Logged {exercise_name} ({details_str}) to the database."
        else:
            return "ERROR: Database insertion failed."
            
    except Exception as e:
        return f"ERROR: {str(e)}"
    
def ai_update_dossier(user_name: str, new_phase: str = None, new_equipment: str = None, new_injuries: str = None, new_goal_weight: float = None, new_primary_goal: str = None, new_age: int = None) -> str:
    """
    Updates the user's permanent fitness profile (Dossier) in the database.
    Call this tool WHENEVER the user mentions a new injury, a change in equipment, a new workout phase, or a change to their goal weight.
    
    Args:
        user_name: The name of the user.
        new_phase: Provide if the user explicitly changes their Phase (e.g., 'Phase 2: Hypertrophy').
        new_equipment: Provide if the user mentions new/different equipment.
        new_injuries: Provide if the user mentions a new injury or says an old one healed.
        new_goal_weight: Provide if the user explicitly states a new target or goal weight in pounds.
        new_primary_goal: Provide if the user explicitly states a new primary fitness goal.
        new_age: Provide if the user explicitly states a new age.
    """
    try:
        current_profile = get_user_profile(user_name)
        
        update_payload = {
            "username": user_name,
            "current_phase": new_phase if new_phase else current_profile.get("current_phase"),
            "available_equipment": new_equipment if new_equipment else current_profile.get("available_equipment"),
            "nagging_injuries": new_injuries if new_injuries else current_profile.get("nagging_injuries"),
            "goal_weight": new_goal_weight if new_goal_weight else current_profile.get("goal_weight"),
            "primary_goal": new_primary_goal if new_primary_goal else current_profile.get("primary_goal"),
            "age": new_age if new_age else current_profile.get("age"),
            "updated_at": datetime.now(ZoneInfo("America/Chicago")).isoformat()
        }
        
        supabase.table("gym_user_profiles").upsert(update_payload).execute()
        return "SUCCESS: User profile updated in the database."
    except Exception as e:
        return f"ERROR: Failed to update profile - {str(e)}"