import streamlit as st
from supabase import create_client, Client
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
        # 🟢 THE FIX: Change select(...) to select("*") so we pull the database 'id'
        response = supabase.table(target_table).select("*").eq("User", user_name).order("Date", desc=True).execute()
        
        if response.data:
            df = pd.DataFrame(response.data)
            # Ensure we only rename if the column exists
            if "Body_Weight" in df.columns:
                df = df.rename(columns={"Body_Weight": "Body Weight"})
            return df
        return pd.DataFrame()
    except Exception as e:
        print(f"Error reading history from Supabase: {e}")
        return pd.DataFrame()

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
        # 1. Ask Supabase for all dates this user already has an automated Garmin log
        existing_response = supabase.table(target_table).select("Date").eq("User", user_name).eq("Activity", "Body Weight").ilike("Details", "%Automated Garmin%").execute()
        
        existing_dates = []
        if existing_response.data:
            existing_dates = [row["Date"] for row in existing_response.data]

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