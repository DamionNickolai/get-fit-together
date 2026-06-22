import streamlit as st
from supabase import create_client
from streamlit_cookies_controller import CookieController
import uuid
from datetime import datetime, timedelta, timezone

from security import encrypt_data, decrypt_text


SESSION_COOKIE_NAME = "get_fit_session_v2"
LEGACY_SESSION_COOKIE_NAME = "get_fit_session"


def get_auth_client():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])


def get_user_data_client():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_SERVICE_KEY"])


def get_cookie_controller():
    """Return a single controller instance per browser session."""
    if "cookie_controller" not in st.session_state:
        st.session_state["cookie_controller"] = CookieController(key="get_fit_cookie_cache")
    return st.session_state["cookie_controller"]


def get_device_fingerprint():
    """Generate a basic device fingerprint for session tracking."""
    # Streamlit doesn't expose full device info, so we use a stable session identifier
    if "device_fingerprint" not in st.session_state:
        st.session_state["device_fingerprint"] = str(uuid.uuid4())
    return st.session_state["device_fingerprint"]


def utc_now():
    return datetime.now(timezone.utc)


def parse_iso_datetime(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def should_use_secure_cookie():
    env = st.secrets.get("app_config", {}).get("environment", "production")
    return env != "local"


def normalize_session_id(raw_value):
    if raw_value is None:
        return None
    value = str(raw_value).strip()
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        value = value[1:-1]
    return value


def write_session_cookie(controller, session_id):
    secure_cookie = should_use_secure_cookie()
    controller.set(
        SESSION_COOKIE_NAME,
        str(session_id),
        max_age=2592000,
        path="/",
        same_site="lax",
        secure=secure_cookie,
    )
    # The controller caches writes in memory immediately, so treat this as attempted success.
    return True


def ensure_session_cookie(controller):
    session_id = st.session_state.get("session_id")
    if not session_id:
        return
    existing_cookie = normalize_session_id(controller.get(SESSION_COOKIE_NAME))
    if existing_cookie != str(session_id):
        write_session_cookie(controller, session_id)


def remove_session_cookie(controller):
    if controller is None:
        return
    try:
        controller.remove(SESSION_COOKIE_NAME, path="/", same_site="lax", secure=True)
    except Exception:
        pass
    try:
        controller.remove(SESSION_COOKIE_NAME, path="/", same_site="lax", secure=False)
    except Exception:
        pass
    # Cleanup legacy cookie name from prior iterations.
    try:
        controller.remove(LEGACY_SESSION_COOKIE_NAME, path="/", same_site="lax", secure=True)
    except Exception:
        pass
    try:
        controller.remove(LEGACY_SESSION_COOKIE_NAME, path="/", same_site="lax", secure=False)
    except Exception:
        pass


def create_user_session(supabase, auth_user_id, refresh_token):
    """Create a new session record in the database and return session_id."""
    try:
        session_id = str(uuid.uuid4())
        session_record = {
            "session_id": session_id,
            "auth_user_id": auth_user_id,
            "refresh_token": encrypt_data(refresh_token),
            "device_fingerprint": get_device_fingerprint(),
            "created_at": utc_now().isoformat(),
            "last_accessed_at": utc_now().isoformat(),
            "expires_at": (utc_now() + timedelta(days=30)).isoformat(),
            "is_active": True
        }
        
        supabase.table("user_sessions").insert(session_record).execute()
        return session_id
    except Exception as e:
        print(f"Error creating session: {e}")
        return None


def get_session_from_database(supabase, session_id):
    """Retrieve a session record from the database."""
    try:
        result = supabase.table("user_sessions").select("*").eq("session_id", session_id).limit(1).execute()
        if result.data and len(result.data) > 0:
            session = result.data[0]
            session["refresh_token"] = decrypt_text(session.get("refresh_token"))
            # Check if session is still active and not expired
            if session.get("is_active"):
                expires_at = parse_iso_datetime(session.get("expires_at"))
                if expires_at and utc_now() < expires_at:
                    return session
            # Session is expired or inactive
            return None
        return None
    except Exception as e:
        print(f"Error retrieving session: {e}")
        return None


def refresh_session_access_time(supabase, session_id):
    """Update the last_accessed_at timestamp."""
    try:
        supabase.table("user_sessions").update(
            {"last_accessed_at": utc_now().isoformat()}
        ).eq("session_id", session_id).execute()
    except Exception as e:
        print(f"Error refreshing session: {e}")


def update_session_refresh_token(supabase, session_id, refresh_token):
    if not refresh_token:
        return
    try:
        supabase.table("user_sessions").update(
            {
                "refresh_token": encrypt_data(refresh_token),
                "last_accessed_at": utc_now().isoformat(),
            }
        ).eq("session_id", session_id).execute()
    except Exception as e:
        print(f"Error updating refresh token: {e}")


def invalidate_user_session(supabase, session_id):
    """Mark a session as inactive."""
    try:
        supabase.table("user_sessions").update(
            {"is_active": False}
        ).eq("session_id", session_id).execute()
    except Exception as e:
        print(f"Error invalidating session: {e}")


def clear_auth_session():
    """Clear session state and invalidate the database session."""
    user_data_client = get_user_data_client()
    session_id = st.session_state.get("session_id")
    
    # Invalidate the session in the database
    if session_id:
        invalidate_user_session(user_data_client, session_id)
    
    # Clear session state
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
        "session_id",
        "auth_bootstrap_attempts",
    ]:
        st.session_state.pop(key, None)
    
    # Also clear the cookie if the controller has already been initialized.
    controller = st.session_state.get("cookie_controller")
    remove_session_cookie(controller)


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
    """
    Returns `True` if the user has a valid session.
    Uses database-backed sessions for secure, auditable persistent login.
    """
    auth_client = get_auth_client()
    user_data_client = get_user_data_client()
    had_cookie_cache = "get_fit_cookie_cache" in st.session_state
    controller = get_cookie_controller()
    if had_cookie_cache:
        try:
            controller.refresh()
        except Exception:
            pass

    # Multi-pass bootstrap to avoid login-screen flash while cookie state hydrates.
    if (
        not st.session_state.get("logout_in_progress", False)
        and not st.session_state.get("password_correct", False)
    ):
        bootstrap_attempts = st.session_state.get("auth_bootstrap_attempts", 0)
        if bootstrap_attempts < 5:
            st.session_state["auth_bootstrap_attempts"] = bootstrap_attempts + 1
            st.rerun()
    
    # 🟢 STEP 1: Check if already authenticated in this session
    if not st.session_state.get("logout_in_progress", False):
        if st.session_state.get("password_correct", False):
            ensure_session_cookie(controller)
            return True
        
        # 🟢 STEP 2: Try to restore session from cookie
        stored_session_id = controller.get(SESSION_COOKIE_NAME)
        stored_session_id = normalize_session_id(stored_session_id)
        if stored_session_id:
            try:
                # Retrieve session from database
                session = get_session_from_database(user_data_client, stored_session_id)
                if session:
                    # Refresh the access time
                    refresh_session_access_time(user_data_client, stored_session_id)
                    
                    # Restore tokens from the session
                    refresh_token = session.get("refresh_token")
                    auth_user_id = session.get("auth_user_id")
                    
                    if refresh_token and auth_user_id:
                        try:
                            # Verify and refresh the auth session with refresh token
                            refreshed = auth_client.auth.refresh_session(refresh_token)
                            refreshed_session = getattr(refreshed, "session", None)
                            new_refresh_token = getattr(refreshed_session, "refresh_token", None)
                            if new_refresh_token:
                                update_session_refresh_token(user_data_client, stored_session_id, new_refresh_token)
                            auth_user = getattr(refreshed, "user", None)
                            if auth_user is None:
                                auth_user = getattr(getattr(refreshed, "session", None), "user", None)
                            verified_auth_user_id = getattr(auth_user, "id", None)
                            
                            # Get the user from our app database
                            db_user = get_app_user_record(user_data_client, verified_auth_user_id)
                            if db_user and hydrate_user_session(db_user, auth_user_id=verified_auth_user_id):
                                st.session_state["session_id"] = stored_session_id
                                st.session_state.pop("auth_bootstrap_attempts", None)
                                return True
                        except Exception:
                            pass
                
                # Session is invalid or expired - clear it
                remove_session_cookie(controller)
            except Exception:
                pass
    
    def perform_login(email, password):
        """Handle the login process and create a new session."""
        # User is explicitly logging in, so disable the logout gate.
        st.session_state.pop("logout_in_progress", None)
        try:
            auth_response = auth_client.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            if auth_response.user:
                auth_user_id = getattr(auth_response.user, "id", None)
                db_user = get_app_user_record(user_data_client, auth_user_id)

                if db_user and hydrate_user_session(db_user, auth_user_id=auth_user_id):
                    # 🟢 NEW: Create a session in the database
                    session = getattr(auth_response, "session", None)
                    refresh_token = getattr(session, "refresh_token", None)
                    
                    if refresh_token:
                        session_id = create_user_session(user_data_client, auth_user_id, refresh_token)
                        if session_id:
                            # Store only the session_id in the cookie (not the token!)
                            st.session_state["session_id"] = session_id
                            remove_session_cookie(controller)
                            write_ok = write_session_cookie(controller, session_id)
                            if not write_ok:
                                st.warning("Unable to persist browser session cookie. Persistent login will not work in this browser.")
                        else:
                            st.warning("Persistent login setup failed: could not create a session record.")
                    else:
                        st.warning("Persistent login setup failed: no refresh token returned by Supabase.")
                    
                    st.query_params.clear()
                    st.session_state.pop("auth_bootstrap_attempts", None)
                    st.session_state["post_login_clean_rerun"] = True
                    return True

                st.warning("Authenticated user is not provisioned for this app. Missing auth_user_id mapping.")
                return False
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
                return True
            else:
                st.error("😕 Email not recognized or password incorrect")
        
    return False