import datetime
from zoneinfo import ZoneInfo

import streamlit as st

try:
    from streamlit_js_eval import streamlit_js_eval
except Exception:
    streamlit_js_eval = None


FALLBACK_TIMEZONE = "America/Chicago"


def get_app_timezone_name() -> str:
    tz_name = st.session_state.get("user_timezone", FALLBACK_TIMEZONE)
    if isinstance(tz_name, str) and tz_name.strip():
        return tz_name.strip()
    return FALLBACK_TIMEZONE


def get_app_timezone() -> ZoneInfo:
    try:
        return ZoneInfo(get_app_timezone_name())
    except Exception:
        return ZoneInfo(FALLBACK_TIMEZONE)


def app_now() -> datetime.datetime:
    return datetime.datetime.now(get_app_timezone())


def app_today() -> datetime.date:
    return app_now().date()


def app_today_iso() -> str:
    return app_today().isoformat()


def app_midnight_iso() -> str:
    return app_now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()


def initialize_user_timezone():
    if "user_timezone" not in st.session_state:
        st.session_state["user_timezone"] = FALLBACK_TIMEZONE

    if streamlit_js_eval is None:
        return

    detected_tz = streamlit_js_eval(
        js_expressions="Intl.DateTimeFormat().resolvedOptions().timeZone",
        key="user_timezone_detector",
    )

    if isinstance(detected_tz, str) and detected_tz.strip():
        detected_tz = detected_tz.strip()
        try:
            ZoneInfo(detected_tz)
        except Exception:
            return

        if st.session_state.get("user_timezone") != detected_tz:
            st.session_state["user_timezone"] = detected_tz
            st.rerun()