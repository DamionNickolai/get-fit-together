# 💪 Home Gym Tracker

A custom Streamlit web application designed to track strength progress, log daily health metrics, and visualize training data.

## 🚀 Features
* **Strength Dashboard:** Calculates Estimated 1RM and tracks progression on major lifts (Squats, Bench, Rows, etc.).
* **Wearable Integration:** Automatically pulls daily Steps, Resting Heart Rate, and Peak Body Battery from Garmin Connect.
* **Google Sheets Database:** Uses a cloud-hosted spreadsheet for easy data entry and historical logging.
* **Multi-User Support:** Separates data and customizes the UI for different users.

## 🛠️ Tech Stack
* **Frontend/Backend:** Python, Streamlit
* **Database:** `streamlit-gsheets`
* **Integrations:** `garminconnect`

## ⚙️ Setup & Configuration
To run this app securely, you must configure the Streamlit Secrets manager with the following structure. **Never commit these secrets to public code.**

```toml
# .streamlit/secrets.toml
password = "your_app_password"

[connections.gsheets]
# Google Service Account Credentials here...

[garmin]
user_email = "..."
user_pass = "..."
etc.
