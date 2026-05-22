import pandas as pd

def check_and_autolog_garmin_weight(conn_history, df_history, user_name, today_date, garmin_weight_lbs):
    """Checks for existing entries and auto-logs a single Garmin weight entry."""
    if not garmin_weight_lbs or float(garmin_weight_lbs) <= 0.0:
        return False
    try:
        if not df_history.empty:
            duplicate_check = df_history[
                (df_history["User"] == user_name) & 
                (df_history["Date"].astype(str) == str(today_date)) & 
                (df_history["Activity"] == "Body Weight")
            ]
            if not duplicate_check.empty:
                return False
        
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

def check_and_bulk_log_garmin_weight(conn_history, df_history, user_name, weight_history_list):
    """Checks 30-day history and bulk logs any missing Garmin weight entries."""
    if not weight_history_list or len(weight_history_list) == 0:
        return False
    try:
        existing_dates = set()
        if not df_history.empty:
            user_weights = df_history[
                (df_history["User"] == user_name) & 
                (df_history["Activity"] == "Body Weight")
            ]
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
            updated_df = pd.concat([df_history, new_df], ignore_index=True)
            conn_history.update(data=updated_df)
            return True

        return False
    except Exception as e:
        print(f"Auto-weight sync skipped: {e}")
        return False