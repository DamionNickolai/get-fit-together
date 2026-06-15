import streamlit as st
from supabase import create_client

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
    
    # Return True if the user is already actively logged in
    if st.session_state.get("password_correct", False):
        return True

    def perform_login(email, password):
        """Core login logic handling password verification using Supabase Auth."""
        try:
            # Connect using the safe ANON key 
            supabase = create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
            
            # Authenticate securely through Supabase Auth
            auth_response = supabase.auth.sign_in_with_password({
                "email": email,
                "password": password
            })
            
            # If successful, link their metadata to the app settings
            if auth_response.user:
                metadata = auth_response.user.user_metadata
                username = metadata.get("username")
                
                # DEBUG CHECK 1: Did we get the metadata?
                if not username:
                    st.warning("⚠️ DEBUG: Login successful, but no 'username' found in Auth metadata!")
                    return False
                
                # Query your public table (Changed .eq to .ilike to ignore capitalization!)
                user_record = supabase.table("users").select("*").ilike("username", username).execute()
                
                if user_record.data:
                    db_user = user_record.data[0]
                    st.session_state["password_correct"] = True
                    st.session_state["logged_in_user"] = db_user["username"]
                    
                    # 🟢 THE AUTHENTICATION BRIDGE
                    st.session_state["username"] = db_user["username"]
                    
                    st.session_state["user_role"] = metadata.get("role", "user") 
                    st.session_state["primary_color"] = db_user.get("primary_color", "#1E3A8A")
                    st.session_state["sidebar_color"] = db_user.get("sidebar_color", "#162A61")
                    st.session_state["line_color"] = db_user.get("line_color", "#60A5FA")
                    st.session_state["garmin_prefix"] = metadata.get("garmin_prefix", username.lower())
                    
                    st.query_params.clear()
                    return True
                else:
                    # DEBUG CHECK 2: Did the table lookup fail?
                    st.warning(f"⚠️ DEBUG: Login successful, but couldn't find '{username}' in the public.users table!")
                    return False
                    
        except Exception as e:
            # DEBUG CHECK 3: Did Supabase reject the password/email?
            st.error(f"⚠️ DEBUG: Supabase Auth Error: {e}")
        return False

    # --- THE UI ---
    bg_url = st.secrets["app_config"]["bg_image_url"]
    set_login_background(image_url=bg_url)
    
    st.markdown("<h2 style='text-align: center;'>🔒 Home Sync Login</h2>", unsafe_allow_html=True)
    
    def password_entered():
        # Triggered when the user clicks 'Log In'
        entered_email = st.session_state.get("email", "").strip() 
        entered_password = st.session_state.get("password", "")
        
        if perform_login(email=entered_email, password=entered_password):
            if "password" in st.session_state:
                del st.session_state["password"] # Clear the password from memory for security
        else:
            st.session_state["password_correct"] = False
            
    col1, col2, col3 = st.columns([1, 2, 1]) 
    with col2:
        with st.form("login_form"):
            # Notice we are asking for an Email now!
            st.text_input("Email", key="email", autocomplete="email")
            st.text_input("Password", type="password", key="password", autocomplete="current-password")
            
            st.form_submit_button("Log In", on_click=password_entered)

        if "password_correct" in st.session_state and st.session_state["password_correct"] is False:
            st.error("😕 Email not recognized or password incorrect")
        
    return False