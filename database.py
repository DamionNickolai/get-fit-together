import streamlit as st
from supabase import create_client, Client
import pandas as pd
from timezone_utils import app_midnight_iso, app_now, app_today_iso

# 🟢 IMPORT THE SECURITY ENGINE
from security import encrypt_data, decrypt_text, decrypt_float

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
        env = st.secrets["app_config"].get("environment", "production")
        return "history_dev" if env == "local" else "history"
    except Exception:
        return "history"

def get_user_history_df(user_name):
    """Fetches a user's history from the appropriate Supabase environment table."""
    target_table = get_target_table()
    try:
        response = supabase.table(target_table).select("*").eq("User", user_name).order("Date", desc=True).limit(50).execute()
        
        if response.data:
            # 🟢 DECRYPT DATA BEFORE PANDAS SEES IT
            for row in response.data:
                row["Activity"] = decrypt_text(row.get("Activity"))
                row["Details"] = decrypt_text(row.get("Details"))
                row["Body_Weight"] = decrypt_float(row.get("Body_Weight"))

            df = pd.DataFrame(response.data)
            if "Body_Weight" in df.columns:
                df = df.rename(columns={"Body_Weight": "Body Weight"})
            return df
            
        return pd.DataFrame(columns=["id", "User", "Date", "Activity", "Body Weight", "Details"])
        
    except Exception as e:
        print(f"Error reading history from Supabase: {e}")
        return pd.DataFrame(columns=["id", "User", "Date", "Activity", "Body Weight", "Details"])

def check_and_autolog_garmin_weight(user_name, today_date, garmin_weight_lbs):
    """Inserts a single Garmin weight entry safely without creating duplicates."""
    if not garmin_weight_lbs or float(garmin_weight_lbs) <= 0.0:
        return False
        
    target_table = get_target_table()
    try:
        # Note: Since Details and Activity are encrypted, we can't reliably use .ilike() on the database side anymore.
        # We fetch today's records and check them in Python.
        existing = supabase.table(target_table).select("Activity, Details").eq("User", user_name).eq("Date", str(today_date)).execute()
        
        for row in (existing.data or []):
            activity = decrypt_text(row.get("Activity"))
            details = decrypt_text(row.get("Details"))
            if activity == "Body Weight" and "Automated Garmin" in details:
                return False # Skip: Already synced today!

        supabase.table(target_table).insert({
            "User": user_name,
            "Date": str(today_date),
            # 🟢 ENCRYPT SENSITIVE DATA
            "Activity": encrypt_data("Body Weight"),
            "Body_Weight": encrypt_data(float(garmin_weight_lbs)),
            "Details": encrypt_data(f"🤖 Automated Garmin Index Scale Sync ({garmin_weight_lbs} lbs)")
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
        dates_to_check = [str(entry["date"]) for entry in weight_history_list]
        
        # Fetch the potential duplicates
        existing_response = supabase.table(target_table).select("Date, Activity, Details").eq("User", user_name).in_("Date", dates_to_check).execute()
        
        # 🟢 Decrypt in Python to check for duplicates safely
        existing_dates = set()
        for row in (existing_response.data or []):
            activity = decrypt_text(row.get("Activity"))
            details = decrypt_text(row.get("Details"))
            if activity == "Body Weight" and "Automated Garmin" in details:
                existing_dates.add(row["Date"])

        rows_to_insert = []
        for entry in weight_history_list:
            g_weight = float(entry["weight"])
            entry_date = str(entry["date"])
            
            if g_weight > 0.0 and entry_date not in existing_dates:
                rows_to_insert.append({
                    "User": user_name,
                    "Date": entry_date,
                    # 🟢 ENCRYPT
                    "Activity": encrypt_data("Body Weight"),
                    "Body_Weight": encrypt_data(g_weight),
                    "Details": encrypt_data(f"🤖 Automated Garmin Index Scale Sync ({g_weight} lbs)")
                })
                
        if not rows_to_insert:
            return False 

        supabase.table(target_table).insert(rows_to_insert).execute()
        return True
        
    except Exception as e:
        print(f"Bulk auto-weight sync error: {e}")
        return False
    
def log_manual_entry(user_name, log_date, activity, body_weight, details):
    """Inserts a manual workout or weight log into the appropriate Supabase environment table."""
    target_table = get_target_table()
    weight_val = float(body_weight) if body_weight else None
    
    try:
        supabase.table(target_table).insert({
            "User": user_name,
            "Date": str(log_date),
            # 🟢 ENCRYPT
            "Activity": encrypt_data(activity),
            "Body_Weight": encrypt_data(weight_val) if weight_val else None,
            "Details": encrypt_data(details)
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
        existing = supabase.table(target_table).select("id").eq("User", user_name).eq("Date", str(log_date)).execute()
        
        # 🟢 ENCRYPT ALL METRICS
        payload = {
            "User": user_name,
            "Date": str(log_date),
            "Steps": encrypt_data(metrics.get("Steps", "0")),
            "RHR": encrypt_data(metrics.get("RHR", 60)),
            "Body_Battery": encrypt_data(metrics.get("Body Battery", 50)),
            "Stress": encrypt_data(metrics.get("Stress", "--")),
            "Calories": encrypt_data(metrics.get("Calories", "--")),
            "HRV": encrypt_data(metrics.get("HRV", "--")),
            "Sleep_Score": encrypt_data(metrics.get("Sleep Score", "--"))
        }
        
        if existing.data:
            supabase.table(target_table).update(payload).eq("id", existing.data[0]["id"]).execute()
        else:
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
            # 🟢 DECRYPT METRICS BEFORE DATAFRAME
            for row in response.data:
                row["Steps"] = decrypt_text(row.get("Steps"))
                row["RHR"] = decrypt_float(row.get("RHR"))
                row["Body_Battery"] = decrypt_float(row.get("Body_Battery"))
                row["Stress"] = decrypt_text(row.get("Stress"))
                row["Calories"] = decrypt_text(row.get("Calories"))
                row["HRV"] = decrypt_text(row.get("HRV"))
                row["Sleep_Score"] = decrypt_text(row.get("Sleep_Score"))
                
            return pd.DataFrame(response.data)
        return pd.DataFrame()
    except Exception as e:
        print(f"Error reading Garmin metrics: {e}")
        return pd.DataFrame()
    
def get_all_time_prs(user_name):
    """Fetches the all-time max weight (PR) for EVERY exercise the user has ever logged."""
    target_table = get_target_table()
    try:
        response = supabase.table(target_table).select("Activity, Details").eq("User", user_name).execute()
        
        if not response.data:
            return {}

        # 🟢 DECRYPT BEFORE PANDAS SEARCHES FOR PATTERNS
        for row in response.data:
            row["Activity"] = decrypt_text(row.get("Activity"))
            row["Details"] = decrypt_text(row.get("Details"))

        df = pd.DataFrame(response.data)

        df["Weight"] = df["Details"].str.extract(r'\|\s*([0-9.]+)\s*lbs').astype(float)
        df = df.dropna(subset=["Weight"])
        pr_series = df.groupby("Activity")["Weight"].max()
        return pr_series.to_dict()

    except Exception as e:
        print(f"Error calculating PRs: {e}")
        return {}

def get_user_profile(user_name):
    """Fetches and decrypts the user's permanent dossier."""
    try:
        response = supabase.table("gym_user_profiles").select("*").eq("username", user_name).execute()
        
        if response.data and len(response.data) > 0:
            data = response.data[0]
            # 🟢 DECRYPT PROFILE DATA
            data["current_phase"] = decrypt_text(data.get("current_phase"))
            data["available_equipment"] = decrypt_text(data.get("available_equipment"))
            data["nagging_injuries"] = decrypt_text(data.get("nagging_injuries"))
            data["primary_goal"] = decrypt_text(data.get("primary_goal"))
            data["goal_weight"] = decrypt_float(data.get("goal_weight"))
            data["age"] = decrypt_float(data.get("age"))
            
            # Clean up floats that are actually integers (like Age)
            if data["age"]:
                data["age"] = int(data["age"])
                
            return data
        else:
            return {
                "current_phase": "Phase 1: Foundation & Endurance",
                "available_equipment": "Full Gym",
                "nagging_injuries": "None",
                "goal_weight": None,
                "primary_goal": "General Fitness",
                "age": None
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
        # 🟢 ENCRYPT PAYLOAD
        data = {
            "username": username,
            "role": role, # Leaving role plain text for UI logic
            "content": encrypt_data(content),
            "visuals": encrypt_data(visuals) if visuals else None,
            "video_url": encrypt_data(video_url) if video_url else None
        }
        supabase.table(target_table).insert(data).execute()
    except Exception as e:
        print(f"DB Save Error: {e}")

def get_todays_chat(username):
    """Fetches all chat messages for the user from exactly midnight Central Time to now."""
    target_table = get_chat_target_table()
    try:
        today_start = app_midnight_iso()
        
        response = supabase.table(target_table)\
            .select("*")\
            .eq("username", username)\
            .gte("created_at", today_start)\
            .order("created_at", desc=False)\
            .execute()
            
        # 🟢 DECRYPT CHAT
        if response.data:
            for row in response.data:
                row["content"] = decrypt_text(row.get("content"))
                row["visuals"] = decrypt_text(row.get("visuals"))
                row["video_url"] = decrypt_text(row.get("video_url"))
                
        return response.data
    except Exception as e:
        print(f"DB Fetch Error: {e}")
        return []
    
def clear_todays_chat(username):
    """Deletes only today's chat history so the user can start fresh."""
    target_table = get_chat_target_table()
    try:
        today_start = app_midnight_iso()
        supabase.table(target_table)\
            .delete()\
            .eq("username", username)\
            .gte("created_at", today_start)\
            .execute()
    except Exception as e:
        print(f"DB Delete Error: {e}")

def ai_log_workout_set(user_name: str, exercise_name: str, sets: int, reps: int, weight_lbs: float, notes: str = "") -> str:
    """Logs a completed workout exercise to the user's fitness tracking database."""
    try:
        today_str = app_today_iso()
        
        if weight_lbs > 0:
            details_str = f"🤖 {sets} Sets | {reps} Reps | {float(weight_lbs)} lbs"
        else:
            details_str = f"🤖 {sets} Sets | {reps} Reps | Bodyweight"
            
        if notes:
            details_str += f" - {notes.strip()}"
            
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
    """Encrypts and updates the user's permanent fitness profile."""
    try:
        current_profile = get_user_profile(user_name)
        
        # 🟢 ENCRYPT BEFORE UPSERTING
        update_payload = {
            "username": user_name,
            "current_phase": encrypt_data(new_phase) if new_phase else encrypt_data(current_profile.get("current_phase")),
            "available_equipment": encrypt_data(new_equipment) if new_equipment else encrypt_data(current_profile.get("available_equipment")),
            "nagging_injuries": encrypt_data(new_injuries) if new_injuries else encrypt_data(current_profile.get("nagging_injuries")),
            "primary_goal": encrypt_data(new_primary_goal) if new_primary_goal else encrypt_data(current_profile.get("primary_goal")),
            "updated_at": app_now().isoformat()
        }
        
        # Handle numerics
        gw = new_goal_weight if new_goal_weight else current_profile.get("goal_weight")
        if gw:
            update_payload["goal_weight"] = encrypt_data(gw)
            
        user_age = new_age if new_age else current_profile.get("age")
        if user_age:
            update_payload["age"] = encrypt_data(user_age)
        
        supabase.table("gym_user_profiles").upsert(update_payload).execute()
        return "SUCCESS: User profile updated in the database."
    except Exception as e:
        return f"ERROR: Failed to update profile - {str(e)}"