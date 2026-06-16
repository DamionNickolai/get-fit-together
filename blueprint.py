# blueprint.py - The AI Coach's Master Playbook

WORKOUT_FRAMEWORKS = {
    "Phase 1: Foundation & Endurance": {
        "focus": "Building joint stability, mastering B52 machine mechanics, and establishing an aerobic base on the trails[cite: 10].",
        "lifting_rules": "3 sets per exercise. 10-15 reps per set. Keep rest periods around 60–90 seconds[cite: 11, 13, 15].",
        "weekly_cadence": "3 Lifting Days (Upper & Core, Lower, Full Body Circuit), 2 Cardio/Outdoor Days (30-45 mins), 1 Active Recovery Day, 1 Full Rest[cite: 2, 3, 4, 5, 6, 7, 8, 12, 18, 23, 28].",
        "ai_instructions": "Design workouts using the user's available equipment. Prioritize foundational compound movements and safety. Always include 1-2 dedicated core movements (e.g., planks, Russian twists) on Upper Body days[cite: 17, 60]. For cardio days, suggest moderate-paced hiking, walking, or beginner mountain biking focusing on steady breathing[cite: 28]."
    },
    "Phase 2: Hypertrophy (Muscle Building for Fat Loss)": {
        "focus": "Increasing the volume (more sets/reps) to build lean muscle, raising resting metabolic rate to burn fat[cite: 30].",
        "lifting_rules": "3 to 4 sets per exercise. 8-12 reps per set. Rest periods drop to 45–60 seconds[cite: 31, 33, 35, 38].",
        "weekly_cadence": "3 Lifting Days (Push, Pull, Legs), 2 Intense Outdoor Days, 1 Active Recovery, 1 Full Rest[cite: 32, 37, 42, 47].",
        "ai_instructions": "Design workouts strictly for hypertrophy. Group muscles by Push (Chest/Shoulders/Triceps), Pull (Back/Biceps/Rear Delts), and Legs[cite: 32, 37, 42]. If the user has TRX, integrate it for bodyweight pulls or core stability. For cardio, suggest longer distance hiking (60+ mins) or interval mountain biking (pedal hard 2 mins, coast 1 min)[cite: 47]."
    },
    "Phase 3: Strength & Power": {
        "focus": "Lifting slightly heavier weights for fewer reps to build true strength, paired with explosive movements[cite: 49].",
        "lifting_rules": "4 sets per heavy exercise. 5-8 reps per set. Rest periods increase to 90–120 seconds for heavy lifts[cite: 50, 52, 57].",
        "weekly_cadence": "3 Lifting Days (Heavy Upper, Heavy Lower, Power & Flow), 2 Outdoor Days, 1 Active Recovery, 1 Rest[cite: 51, 56, 61, 66].",
        "ai_instructions": "Focus on progressive overload. Heavy Upper and Heavy Lower days should rely on the B52 Smith Machine and heavy free weights[cite: 52, 58]. The Power & Flow day should utilize Kettlebells for explosive movements (cleans, snatches, heavy swings) and plyometrics (explosive push-ups)[cite: 62, 63, 65]. For outdoor days, suggest hill training: powering up steep inclines and recovering on descents[cite: 66, 67]."
    },
    "Phase 4: Metabolic Conditioning": {
        "focus": "Maximum calorie burn and cardiovascular health using 'Supersets' (two exercises back-to-back with no rest)[cite: 69].",
        "lifting_rules": "Minimal rest. Cycle through supersets or AMRAPs (As Many Rounds As Possible)[cite: 69, 78].",
        "weekly_cadence": "3 Lifting Days (Upper Supersets, Lower Supersets, Full Body AMRAP), 2 Intense Outdoor Days, 1 Active Recovery, 1 Rest[cite: 70, 74, 78, 84].",
        "ai_instructions": "Workouts must be intense and keep the heart rate elevated. Pair opposing muscle groups in supersets (e.g., Push + Pull, or Quads + Hamstrings)[cite: 71, 75]. The Full Body day should be structured as a 20-minute AMRAP using Kettlebells, B52, and Bodyweight[cite: 78, 79]. For outdoor days, suggest 'Rucking' (hiking with a weighted vest/pack for 45 mins) or fast-paced continuous mountain biking[cite: 84]."

    },
    "Open Gym: Free Form Training": {
        "focus": "Total flexibility and on-demand adaptation. The AI Coach acts as a reactive personal trainer, building whatever the user requests without enforcing strict weekly progression rules.",
        "lifting_rules": "Adaptable to the user's specific request. Reps, sets, and rest periods should match the user's stated goal for that session (e.g., strength, hypertrophy, endurance). If the user doesn't specify, default to standard hypertrophy (3 sets of 8-12 reps).",
        "weekly_cadence": "No strict schedule. Train based on feel, life schedule, and immediate goals.",
        "ai_instructions": "DO NOT enforce a specific phase or strict progression. Listen entirely to the user's prompt. If they ask for a leg day, give them a leg day. If they ask for 20 minutes of HIIT, give them exactly that. Only provide constraints or corrections if their requested workout is physically dangerous."
    }
}