import streamlit as st
from supabase import create_client


def get_auth_client():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])


def get_user_data_client():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_SERVICE_KEY"])


def clear_auth_session():
    for key in [
        "password_correct",
        "auth_access_token",
        "auth_refresh_token",
        "auth_user_id",
        "logged_in_user",
        "username",
        "user_role",
        "primary_color",
        "sidebar_color",
        "line_color",
        "garmin_prefix",
    ]:
        st.session_state.pop(key, None)


def get_app_user_record(supabase, auth_user_id):
    if not auth_user_id:
        return None

    try:
        user_record = supabase.table("users").select("*").eq("auth_user_id", auth_user_id).limit(1).execute()
        if user_record.data:
            return user_record.data[0]
    except Exception:
        pass

    return None


def hydrate_user_session(db_user, auth_user_id=None):
    username = db_user["username"]

    st.session_state.pop("logout_in_progress", None)
    st.session_state["password_correct"] = True
    st.session_state["auth_user_id"] = auth_user_id or db_user.get("auth_user_id")
    st.session_state["logged_in_user"] = db_user["username"]
    st.session_state["username"] = db_user["username"]
    st.session_state["user_role"] = db_user.get("role", "user")
    st.session_state["primary_color"] = db_user.get("primary_color", "#1E3A8A")
    st.session_state["sidebar_color"] = db_user.get("sidebar_color", "#162A61")
    st.session_state["line_color"] = db_user.get("line_color", "#60A5FA")
    st.session_state["garmin_prefix"] = db_user.get("garmin_prefix", username.lower())
    return True

# ==========================================
# 🎨 LOGIN SCREEN STYLING
# ==========================================
def set_login_background(image_url):
    """
    Pulls an image securely from Supabase Storage and injects it as a 
    full-screen, mobile-friendly background with a dark readability overlay.
    """
    st.markdown(
        f"""
        <style>
        /* 🟢 1. THE BACKGROUND */
        .stApp {{
            background-image: linear-gradient(rgba(17, 24, 39, 0.5), rgba(17, 24, 39, 0.6)), 
                              url('{image_url}');
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
            background-repeat: no-repeat;
        }}
        
        /* 🟢 2. REMOVE INPUT BORDERS */
        div[data-baseweb="input"] {{
            border: none !important;
            background-color: rgba(30, 41, 59, 0.7) !important; 
        }}
        
        div[data-baseweb="input"]:focus-within {{
            box-shadow: none !important;
            border: none !important;
        }}

        /* 🟢 3. REMOVE OUTER FORM BORDER */
        [data-testid="stForm"] {{
            border: none !important;
            background-color: transparent !important;
        }}
        </style>
        """,
        unsafe_allow_html=True
    )

def check_password():
    """Returns `True` if the user has a valid Supabase Auth session."""
    auth_client = get_auth_client()
    user_data_client = get_user_data_client()
    
    if not st.session_state.get("logout_in_progress", False):
        if st.session_state.get("password_correct", False):
            return True

        access_token = st.session_state.get("auth_access_token")
        refresh_token = st.session_state.get("auth_refresh_token")

        if access_token and refresh_token:
            try:
                auth_client.auth.set_session(access_token, refresh_token)
                verified_user = auth_client.auth.get_user()
                auth_user = getattr(verified_user, "user", None)
                auth_user_id = getattr(auth_user, "id", None)
                db_user = get_app_user_record(user_data_client, auth_user_id)

                if db_user and hydrate_user_session(db_user, auth_user_id=auth_user_id):
                    return True
            except Exception:
                pass

            clear_auth_session()

    def perform_login(email, password):
        try:
            auth_response = auth_client.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if auth_response.user:
                auth_user_id = getattr(auth_response.user, "id", None)
                db_user = get_app_user_record(user_data_client, auth_user_id)

                if db_user and hydrate_user_session(db_user, auth_user_id=auth_user_id):
                    session = getattr(auth_response, "session", None)
                    st.session_state["auth_access_token"] = getattr(session, "access_token", None)
                    st.session_state["auth_refresh_token"] = getattr(session, "refresh_token", None)

                    st.query_params.clear()
                    return True

                st.warning("Authenticated user is not provisioned for this app. Missing auth_user_id mapping.")
                return False
        except Exception:
            st.error("Unable to sign in with the provided credentials.")
            return False

    # --- THE UI ---
    try:
        bg_url = st.secrets["app_config"]["bg_image_url"]
        set_login_background(image_url=bg_url)
    except Exception:
        pass
    
    st.markdown("<h2 style='text-align: center;'>🔒 Get Fit Together</h2>", unsafe_allow_html=True)
        
    col1, col2, col3 = st.columns([1, 2, 1]) 
    with col2:
        with st.form("login_form"):
            entered_email = st.text_input("Email", autocomplete="email")
            entered_password = st.text_input("Password", type="password", autocomplete="current-password")
            submitted = st.form_submit_button("Log In")

        if submitted:
            if perform_login(email=entered_email, password=entered_password):
                st.rerun() 
            else:
                st.error("😕 Email not recognized or password incorrect")
        
    return False