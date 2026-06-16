import streamlit as st
import datetime
from zoneinfo import ZoneInfo
import json
from workouts import ROUTINES

# 🟢 NEW: Import the updated SDK and its types
from google import genai
from google.genai import types

# 🟢 NEW: Import the AI logging tool from your database file!
from database import ai_log_workout_set, ai_update_dossier

def init_coach_chat(user_name, current_goal_weight, recent_workouts, recent_vitals, pr_text, current_phase, equipment, injuries, primary_goal, age):
    """
    Initializes a Gemini chat session using the new google-genai SDK, 
    giving it the system rules, today's date, and the user's data context.
    """
    try:
        api_key = st.secrets["ai"]["GEMINI_API_KEY"]
        if not api_key:
            return None, None, "⚠️ Gemini API key is blank."
            
        # 🟢 NEW: Initialize the Client object
        client = genai.Client(api_key=api_key)
        
    except KeyError:
        return None, "⚠️ Could not find the [ai] section or GEMINI_API_KEY in secrets.toml."
    except Exception as e:
        return None, f"⚠️ Failed to configure AI: {e}"

    # Get today's actual day of the week (Timezone Corrected!)
    local_tz = ZoneInfo("America/Chicago")
    today_name = datetime.datetime.now(local_tz).strftime("%A")

    # Your Weekly Architecture so the Coach knows what you should be doing
    weekly_schedule = """
    - Monday: Workout A (Strength / Split Focus)
    - Tuesday: Mountain Biking / Hiking / Walking (Cardio, 30-45 mins)
    - Wednesday: Workout B (Strength / Split Focus)
    - Thursday: Walk / Low-Intensity Cardio & Mobility Stretch
    - Friday: Workout C (Full Body / Circuit Integration)
    - Saturday / Sunday: Family Active Recovery & Full System Rest
    """

    # 🧠 The Coach's Brain (System Instructions)
    system_prompt = f"""
    You are an elite, highly empathetic, and motivating personal trainer for the app "Get Fit Together".
    Your client is {user_name}, who is {age} years old. Their target weight is {current_goal_weight} lbs. Their primary fitness goal(s) are: {primary_goal}.
    
    CRITICAL CONTEXT:
    Today is {today_name}. Here is their standard weekly schedule:
    {weekly_schedule}

    🟢 USER DOSSIER (Long-Term Memory):
    - Primary Focus/Goals: {primary_goal} (CRITICAL RULE: If the user states a new goal, you MUST combine it with these existing goals when calling the update tool. Never overwrite or delete existing goals unless explicitly asked).
    - Current Training Phase: {current_phase}
    - Available Equipment: {equipment} (CRITICAL RULE: If the user adds new equipment, you MUST combine it with this existing list when calling the update tool. Never overwrite or delete existing equipment unless explicitly asked).
    - Nagging Injuries / Limitations: {injuries}

    MASTER TRAINING BLUEPRINT (The 12-Month Roadmap):
    {json.dumps(ROUTINES, indent=2)}
    
    {pr_text}

    Recent Workout History:
    {recent_workouts.to_string() if not recent_workouts.empty else "No recent workouts logged."}

    Recent Garmin Vitals (Sleep, HRV, Stress, Body Battery):
    {recent_vitals.to_string() if not recent_vitals.empty else "No recent Garmin data available."}

    YOUR DIRECTIVES (Personality & Coaching Philosophy):
    1. Act as a supportive, knowledgeable, and highly interactive human coach. 
    2. Focus heavily on long-term consistency over short-term intensity.
    3. Always start the conversation by providing a concise daily briefing based on what today's schedule dictates ({today_name}) and how their recovery vitals look.
    4. Proactively protect the athlete. If their Garmin Stress is high, Body Battery is low, or sleep was poor, explicitly suggest swapping heavy lifts for active recovery, mobility, or a lighter variation. 
    5. Be an enthusiastic cheerleader. If you see a recent workout where they hit a PR or trained consistently, celebrate it!
    6. Keep responses punchy, highly actionable, and conversational. Do not output massive walls of text unless explicitly asked to explain a complex physiological concept.
    7. Be ready to adjust the workout plan on the fly. Reference the Master Training Blueprint to suggest specific exercises or alternative routines if they need a pivot today.
    8. HYBRID VISUALIZER TRIGGER: If the user explicitly asks how to perform an exercise, explain it briefly. Then, you MUST end your entire message with this exact secret tag on a new line: [EXERCISE: Exact Name of Exercise]. Example: [EXERCISE: Bulgarian Split Squat]
    9. 🛑 WORKOUT LOGGING CONCISENESS: When the user tells you they finished a set and you use your database logging tool, your verbal response MUST be extremely brief. Confirm the log in one short sentence, and then IMMEDIATELY tell them the exact next exercise on today's agenda. Do not give unsolicited advice about form unless they ask.
    10. 🛑 DOSSIER UPDATES: If the user explicitly mentions a new goal weight, their age, a new primary goal, a new injury, a change in available equipment, or moving to a new fitness phase, you MUST physically call the `ai_update_dossier` function to save it. DO NOT just verbally acknowledge the update—you must use the tool.
    11. 🛑 PHASE ADAPTATION & OPEN GYM: You MUST adapt all advice to their 'Current Training Phase' listed in the User Dossier. If their phase is "Open Gym: Free Form Training", drop all strict weekly schedules and act as a reactive, on-demand gym buddy. Give them exactly what they ask for without strictly enforcing the Master Training Blueprint.
    12. 🏠 HOME GYM ALIAS: If the user says they are working out 'at home', assume their current available equipment is: 'Major Fitness: B52 Pro Machine , Bench, Dumbbells, Kettlebells, Resistance Bands, TRX Suspension Trainer, TRX Rip Trainer, Bike with street or trail capability in the neighborhood.
    """

    try:
        # ==========================================
        # 🤖 THE MODEL SWITCHER
        # Uncomment the model you want to use. Keep the others commented out (#).
        # ==========================================
        
        # [PRIMARY] The smartest, fastest, high-volume model (1,000 Free Req/Day)
        ACTIVE_MODEL = "gemini-3.1-flash-lite"
        
        # [BACKUP 1] The standard, highly capable model (1,500 Free Req/Day - Rate limits apply)
        # ACTIVE_MODEL = "gemini-2.5-flash"
        
        # [BACKUP 2] The ultra-fast, older generation high-volume model
        # ACTIVE_MODEL = "gemini-2.5-flash-lite"
        
        # [BACKUP 3] The "Heavy Thinker" Pro model (Extremely strict limits - 50 Req/Day)
        # ACTIVE_MODEL = "gemini-2.5-pro"

        # Start the chat session with the selected model
        chat_session = client.chats.create(
            model=ACTIVE_MODEL,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                tools=[ai_log_workout_set, ai_update_dossier]
            )
        )
        return client, chat_session, None
    except Exception as e:
        return None, None, f"⚠️ Error starting chat: {e}"