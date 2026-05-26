# 💪 Get Fit Together

A secure multi-user Streamlit app for tracking workouts, health metrics, and Garmin sync with a Supabase backend.

## 🚀 What it does
- Streamlit dashboard with login, user-specific views, and color theming
- Garmin Connect integration for Steps, Resting Heart Rate, Stress, Body Battery, and weight data
- Manual workout logging with structured training phases and custom session support
- Supabase PostgreSQL backend for history tracking and app version metadata
- Git-based deploy workflow using `deploy.py` for `dev` → `main` promotion

## 🧰 Tech stack
- Python
- Streamlit
- Supabase (PostgreSQL)
- Garmin Connect integration
- Plotly for charts

## 📦 Requirements
Install dependencies from `requirements.txt`:

```bash
pip install -r requirements.txt
```

## ⚙️ Configuration
Create a secrets file at `.streamlit/secrets.toml`.

> `.streamlit/secrets.toml` is already excluded by `.gitignore`.

Example configuration:

```toml
[database]
SUPABASE_URL = "your_supabase_project_url"
SUPABASE_KEY = "your_supabase_anon_key"
SUPABASE_SERVICE_KEY = "your_supabase_service_role_key"

[garmin_prod]
user1_email = "..."
user1_pass = "..."
user2_email = "..."
user2_pass = "..."

[garmin_dev]
user1_email = "..."
user1_pass = "..."
user2_email = "..."
user2_pass = "..."

[app_config]
default_dev_workspace = "your_local_path"
environment = "local" # change to "production" for live deployment
```

## ▶️ Run locally

```bash
streamlit run get_fit_together.py
```

## 🚀 Deploy workflow

This repository includes a helper script in `deploy.py`.

```bash
python deploy.py "Your deploy commit message"
```

The script:
1. commits and pushes changes to `dev`
2. waits for manual confirmation
3. merges `dev` into `main`
4. pushes `main`

## 📁 Project structure
- `get_fit_together.py` — main Streamlit app
- `auth.py` — login and password handling
- `database.py` — Supabase data helpers and logging
- `garmin_api.py` — Garmin Connect data fetcher
- `workouts.py` — training routines and session definitions
- `deploy.py` — simple git deployment helper
- `requirements.txt` — Python dependencies

## 📝 Notes
- Keep `.streamlit/secrets.toml` private and out of version control
- Use `app_config.environment = "local"` for development and `production` for live use
- Verify your Supabase keys and Garmin credentials before launching the app
