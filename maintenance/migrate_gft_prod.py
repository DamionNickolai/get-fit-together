import streamlit as st
from supabase import create_client
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from security import encrypt_data

supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_SERVICE_KEY"])

# 🟢 TARGETING ALL PRODUCTION TABLES
TABLES_TO_ENCRYPT = {
    "coach_chat_history": ["content", "video_url", "visuals"],
    "garmin_metrics": ["Body_Battery", "Calories", "HRV", "RHR", "Sleep_Score", "Steps", "Stress"],
    "history": ["Activity", "Details", "Body_Weight"],
    "gym_user_profiles": ["primary_goal", "available_equipment", "nagging_injuries", "current_phase", "goal_weight", "age"]
}

def migrate_table(table_name, columns):
    print(f"\n🚀 Starting production migration for: {table_name}")
    response = supabase.table(table_name).select("*").execute()
    rows = response.data
    
    if not rows:
        print(f"No data found in {table_name}.")
        return

    # 🟢 Dynamically determine the primary key for the update clause
    primary_key = "username" if table_name == "gym_user_profiles" else "id"

    success_count = 0
    for row in rows:
        update_payload = {}
        for col in columns:
            val = row.get(col)
            if val is not None and str(val).strip() != "" and not str(val).startswith("gAAAA"):
                update_payload[col] = encrypt_data(val)
                
        if update_payload:
            supabase.table(table_name).update(update_payload).eq(primary_key, row[primary_key]).execute()
            success_count += 1
            
    print(f"✅ Migration complete for {table_name}! {success_count} rows encrypted.")

if __name__ == "__main__":
    for table, columns in TABLES_TO_ENCRYPT.items():
        migrate_table(table, columns)
    
    print("\n🏆 Get Fit Together Production Data is FULLY SECURED!")