import streamlit as st
import datetime
from zoneinfo import ZoneInfo
from garminconnect import Garmin

@st.cache_data(ttl=1800, show_spinner=False)
def fetch_garmin_data_layer(today_str: str, cache_partition: str, _client):
    """Fetches and processes Garmin data, returning a clean dictionary."""
    try:
        stats = _client.get_stats(today_str) or {}

        # --- STEPS, RHR, BODY BATTERY, STRESS, CALORIES, HRV (Unchanged) ---
        raw_steps = stats.get("totalSteps")
        steps = f"{int(raw_steps):,}" if raw_steps else "0"

        raw_rhr = stats.get("restingHeartRate")
        if not raw_rhr:
            try:
                rhr_data = _client.get_rhr_day(today_str)
                raw_rhr = rhr_data.get("restingHeartRate") if rhr_data else None
            except Exception:
                raw_rhr = None
        rhr = int(raw_rhr) if raw_rhr else 60

        bb_max = 50
        try:
            bb_data = _client.get_body_battery(today_str)
            if bb_data and isinstance(bb_data, list) and len(bb_data) > 0:
                bb_max = bb_data[0].get("charged") or bb_data[0].get("highestBodyBatteryValue") or 50
        except Exception:
            bb_max = 50

        stress_val = stats.get("averageStressLevel", "--")
        
        total_cal_raw = stats.get("totalKilocalories")
        if total_cal_raw:
            total_calories = f"{int(total_cal_raw):,}"
        else:
            active_cal = stats.get("activeKilocalories", 0) or 0
            bmr_cal = stats.get("bmrKilocalories", 0) or 0
            total_calories = f"{int(active_cal + bmr_cal):,}" if (active_cal + bmr_cal) else "--"

        hrv_val = "--"
        try:
            hrv_data = _client.get_hrv_data(today_str)
            if hrv_data and "hrvSummary" in hrv_data:
                hrv_val = f"{hrv_data['hrvSummary'].get('lastNightAvg', '--')} ms"
        except Exception:
            hrv_val = "--"

        debug_info = {"Date_Queried": today_str, "Main_Stats": stats}

        # 🟢 1. FIX THE SLEEP SCORE API CHANGES
        sleep_score = "--"
        try:
            sleep_data = _client.get_sleep_data(today_str)
            debug_info["RAW_SLEEP"] = sleep_data 
            
            if sleep_data:
                # Garmin's new nested structure: dailySleepDTO -> sleepScores -> overall -> value
                sleep_score = sleep_data.get("dailySleepDTO", {}).get("sleepScores", {}).get("overall", {}).get("value", "--")
                
                # Fallback to the old structure just in case
                if sleep_score == "--":
                    sleep_score = sleep_data.get("dailySleepDTO", {}).get("sleepScore", "--")
        except Exception as sleep_err:
            debug_info["SLEEP_ERROR"] = str(sleep_err)

        weight_lbs = 0.0
        weight_goal = "--"
        recent_weight_history = []

        # 🟢 2. FIX THE WEIGHT SORTING & GOAL WEIGHT
        try:
            tz = ZoneInfo("America/Chicago")
            start_date = (datetime.datetime.now(tz) - datetime.timedelta(days=30)).date().isoformat()
            body_data = _client.get_body_composition(start_date, today_str)
            debug_info["RAW_BODY"] = body_data 

            if body_data:
                # Try getting goal from body composition first
                goals = body_data.get("goals")
                if isinstance(goals, dict) and goals.get("weightGoal"):
                    weight_goal = f"{round((goals.get('weightGoal') / 1000) * 2.20462, 1)} lbs"

                if "dateWeightList" in body_data and len(body_data["dateWeightList"]) > 0:
                    for entry in body_data["dateWeightList"]:
                        w_grams = entry.get("weight")
                        c_date = entry.get("calendarDate")
                        if w_grams and c_date:
                            w_lbs = round((w_grams / 1000) * 2.20462, 1)
                            recent_weight_history.append({"date": c_date, "weight": w_lbs})

                if recent_weight_history:
                    # 🟢 THE FIX: Force sort chronologically so [-1] is ALWAYS the newest weight!
                    recent_weight_history = sorted(recent_weight_history, key=lambda x: x["date"])
                    weight_lbs = recent_weight_history[-1]["weight"]

            # 🟢 3. HUNT FOR THE GOAL WEIGHT IN THE USER PROFILE
            if weight_goal == "--":
                try:
                    profile_data = _client.get_user_profile()
                    debug_info["RAW_PROFILE"] = profile_data
                    # Sometimes stored in grams, sometimes kg. Let's assume grams like body_comp
                    if profile_data and profile_data.get("weightGoal"):
                        weight_goal = f"{round((profile_data.get('weightGoal') / 1000) * 2.20462, 1)} lbs"
                except Exception as profile_err:
                    debug_info["PROFILE_ERROR"] = str(profile_err)

        except Exception as body_err:
            debug_info["BODY_ERROR"] = str(body_err)

        return {
            "Steps": steps,
            "RHR": rhr,
            "Body Battery": int(bb_max) if str(bb_max).isdigit() else 50,
            "Stress": stress_val,
            "Calories": total_calories,
            "HRV": hrv_val,
            "Sleep Score": sleep_score,
            "Weight": weight_lbs,
            "Weight Goal": weight_goal,
            "Weight_History": recent_weight_history,
            "Raw": str(debug_info),
        }

    except Exception as inner_err:
        return {
            "Steps": "0", "RHR": 60, "Body Battery": 50, "Stress": "--",
            "Calories": "--", "HRV": "--", "Sleep Score": "--",
            "Weight": 0.0, "Weight Goal": "--", "Weight_History": [],
            "Raw": f"Inner Error: {inner_err}"
        }