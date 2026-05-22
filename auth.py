import streamlit as st
from streamlit_gsheets import GSheetsConnection
import hashlib

def check_password():
    """Returns `True` if the user had a correct password or magic link."""
    if st.session_state.get("password_correct", False):
        return True

    # Pull the user database from the 'Users' tab of the Backlog sheet
    try:
        conn_admin = st.connection("gsheets_backlog", type=GSheetsConnection)
        users_df = conn_admin.read(worksheet="Users", ttl=600) 
    except Exception as e:
        st.error("⚠️ Unable to connect to the User Database.")
        return False

    url_token = st.query_params.get("auth", None)
    url_user = st.query_params.get("user", None)

    # 1. Check for the Magic URL Token (Mobile Bypass)
    if url_token and url_user and not users_df.empty:
        user_match = users_df[users_df["Username"] == url_user]
        if not user_match.empty:
            user_data = user_match.iloc[0]
            correct_password = str(user_data["Password"])
            expected_token = hashlib.sha256(f"{url_user}{correct_password}".encode()).hexdigest()[:20]
            
            if url_token == expected_token:
                st.session_state["password_correct"] = True
                st.session_state["logged_in_user"] = url_user
                st.session_state["profile_data"] = user_data.to_dict() 
                
                host_header = st.context.headers.get("Host", "")
                is_local = "streamlit" not in host_header.lower()
                st.session_state["is_environment_local"] = is_local
                
                if user_data["Role"] == "developer" and is_local:
                    st.session_state["user_role"] = "developer"
                    st.session_state["logged_in_user"] = st.secrets["app_config"]["default_dev_workspace"]
                else:
                    st.session_state["user_role"] = user_data["Role"]
                return True

    # 2. Show the standard Login Form
    with st.container():
        st.subheader("🔒 Gym Access Portal")
        
        with st.form("login_form", clear_on_submit=False):
            typed_user = st.text_input("Profile Name", key="login_username", autocomplete="username").strip()
            entered_pass = st.text_input("Password", type="password", key="login_password", autocomplete="current-password")
            login_clicked = st.form_submit_button("🚀 Log In", type="primary", use_container_width=True)
        
        if login_clicked:
            if not typed_user or not entered_pass:
                st.warning("⚠️ Please fill in both fields.")
                return False
                
            if users_df.empty:
                st.error("Database is empty or failed to load.")
                return False

            user_match = users_df[users_df["Username"] == typed_user]
            
            if not user_match.empty:
                user_data = user_match.iloc[0]
                correct_password = str(user_data["Password"])
                
                if entered_pass == correct_password:
                    st.session_state["password_correct"] = True
                    st.session_state["profile_data"] = user_data.to_dict() 
                    
                    secure_token = hashlib.sha256(f"{typed_user}{correct_password}".encode()).hexdigest()[:20]
                    st.query_params["user"] = typed_user
                    st.query_params["auth"] = secure_token
                    
                    host_header = st.context.headers.get("Host", "")
                    is_local = "streamlit" not in host_header.lower()
                    st.session_state["is_environment_local"] = is_local
                    
                    if user_data["Role"] == "developer" and is_local:
                        st.session_state["user_role"] = "developer"
                        st.session_state["logged_in_user"] = st.secrets["app_config"]["default_dev_workspace"]
                    else:
                        st.session_state["user_role"] = user_data["Role"]
                        st.session_state["logged_in_user"] = typed_user
                        
                    st.rerun()
                else:
                    st.error("😕 Access denied. Check your credentials.")
                    return False
            else:
                st.error("😕 Access denied. Check your credentials.")
                return False
                
        return False