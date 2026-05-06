import streamlit as st
from dotenv import load_dotenv
from pages.admin import show_admin_dashboard
from pages.registrar import show_registrar_dashboard
from pages.faculty import show_faculty_dashboard
from pages.students import show_students_dashboard
from utils.auth import logout, require_login

load_dotenv()

st.set_page_config(page_title="BSIT Dashboard Reports", layout="wide")

# Simple Session Management
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.role = None
    st.session_state.username = None
    st.session_state.display_name = None
    st.session_state.student_id = None
    st.session_state.student_no = None
    st.session_state.student_name = None
    st.session_state.student_email = None
    st.session_state.program_code = None

require_login()

role = st.session_state.role
username = st.session_state.get("username", "")
display_name = st.session_state.get("display_name") or username

st.sidebar.title("BSIT Dashboard")
st.sidebar.write(f"**User:** {display_name}")
st.sidebar.write(f"**Role:** {role}")

# Menu Filtering
menu_options = []
if role == "admin":
    menu_options = ["Admin Management", "Registrar Reports", "Faculty Reports", "Student Reports"]
elif role == "registrar":
    menu_options = ["Registrar Reports", "Faculty Reports", "Student Reports"]
elif role == "faculty":
    menu_options = ["Faculty Reports", "Student Reports"]
else:
    menu_options = ["Student Reports"]

menu = st.sidebar.radio("Select Dashboard", menu_options)

if logout():
    st.session_state.logged_in = False
    st.session_state.username = None
    st.session_state.display_name = None
    st.session_state.role = None
    st.session_state.student_id = None
    st.session_state.student_no = None
    st.session_state.student_name = None
    st.session_state.student_email = None
    st.session_state.program_code = None
    st.rerun()

# Routing to pages
if menu == "Admin Management":
    show_admin_dashboard()
elif menu == "Registrar Reports":
    show_registrar_dashboard()
elif menu == "Faculty Reports":
    show_faculty_dashboard()
elif menu == "Student Reports":
    show_students_dashboard()