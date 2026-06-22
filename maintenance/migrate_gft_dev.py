import streamlit as st
from supabase import create_client
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from security import encrypt_data

supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_SERVICE_KEY"])

# A dictionary mapping table names to the exact columns that need encryption
TABLES_TO_ENCRYPT = {
    "coach_chat_history_dev": ["content", "video_url", "visuals"],
    "garmin_metrics_dev": ["Body_Battery", "Calories", "HRV", "RHR", "Sleep_Score", "Steps", "Stress"],
    "history_dev": ["Activity", "Details", "Body_Weight"]
}

def migrate_table(table_name, columns):
    print(f"\n🚀 Starting migration for: {table_name}")
    response = supabase.table(table_name).select("*").execute()
    rows = response.data
    
    if not rows:
        print(f"No data found in {table_name}.")
        return

    success_count = 0
    for row in rows:
        update_payload = {}
        for col in columns:
            val = row.get(col)
            # Only encrypt if it's not empty and not already encrypted
            if val is not None and str(val).strip() != "" and not str(val).startswith("gAAAA"):
                update_payload[col] = encrypt_data(val)
                
        if update_payload:
            supabase.table(table_name).update(update_payload).eq("id", row["id"]).execute()
            success_count += 1
            
    print(f"✅ Migration complete for {table_name}! {success_count} rows encrypted.")

if __name__ == "__main__":
    for table, columns in TABLES_TO_ENCRYPT.items():
        migrate_table(table, columns)
    
    print("\n🎉 Get Fit Together Dev Sandbox is fully encrypted!")