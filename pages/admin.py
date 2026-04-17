import streamlit as st
from utils.auth import create_user, delete_user, list_user_accounts, update_user_password, update_user_role
from db import get_db

ALLOWED_ROLES = ["registrar", "faculty", "student"]
MANAGEABLE_ROLES = ["admin", "registrar", "faculty", "student"]


def get_db_stats():
    try:
        db = get_db()
        return {
            "students": db.students.count_documents({}),
            "grades": db.grades.count_documents({}),
            "subjects": db.subjects.count_documents({}),
            "users": db.users.count_documents({}),
        }
    except Exception:
        return {"students": 0, "grades": 0, "subjects": 0, "users": 0}


def show_admin_dashboard():
    st.title("Admin Account Management")
    st.write("Create new accounts for registrar, faculty, and student users.")
    current_admin = st.session_state.get("username", "").strip().lower()

    stats = get_db_stats()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Students", stats["students"])
    col2.metric("Grades", stats["grades"])
    col3.metric("Subjects", stats["subjects"])
    col4.metric("User Accounts", stats["users"])

    st.markdown("---")
    col_left, col_right = st.columns([2, 1])

    with col_left:
        username = st.text_input("New username")
        password = st.text_input("Password", type="password")
        password_confirm = st.text_input("Confirm password", type="password")
        role = st.selectbox("Role", ALLOWED_ROLES)

        if st.button("Create account"):
            if not username.strip():
                st.error("Username cannot be empty.")
            elif password != password_confirm:
                st.error("Passwords do not match.")
            elif len(password) < 6:
                st.error("Password must be at least 6 characters.")
            else:
                if create_user(username, password, role):
                    st.success(f"{role.title()} account '{username}' created successfully.")
                else:
                    st.error("Failed to create account. The username may already exist.")

    with col_right:
        st.subheader("Existing accounts")
        accounts = list_user_accounts()
        if accounts:
            st.table(accounts)
        else:
            st.write("No accounts available.")

    st.markdown("---")
    st.subheader("Manage existing account")
    accounts = list_user_accounts()
    usernames = [account["username"] for account in accounts]

    if usernames:
        selected_username = st.selectbox("Select user", usernames)
        selected_account = next(
            (account for account in accounts if account["username"] == selected_username),
            {"username": selected_username, "role": "student"},
        )

        with st.form("manage_account_form"):
            new_role = st.selectbox(
                "Role",
                MANAGEABLE_ROLES,
                index=MANAGEABLE_ROLES.index(selected_account.get("role", "student"))
                if selected_account.get("role", "student") in MANAGEABLE_ROLES
                else MANAGEABLE_ROLES.index("student"),
            )
            new_password = st.text_input("New password", type="password")
            confirm_password = st.text_input("Confirm new password", type="password")
            update_submitted = st.form_submit_button("Save changes")

        if update_submitted:
            changed = False
            if selected_username == current_admin and new_role != "admin":
                st.error("You cannot change your own admin role.")
            else:
                if new_role != selected_account.get("role"):
                    if update_user_role(selected_username, new_role):
                        changed = True
                    else:
                        st.error("Failed to update the user role.")

                if new_password or confirm_password:
                    if new_password != confirm_password:
                        st.error("Passwords do not match.")
                    elif len(new_password) < 6:
                        st.error("Password must be at least 6 characters.")
                    elif update_user_password(selected_username, new_password):
                        changed = True
                    else:
                        st.error("Failed to update the password.")

                if changed:
                    st.success(f"Account '{selected_username}' updated successfully.")
                    st.rerun()

        delete_disabled = selected_username == current_admin
        if delete_disabled:
            st.caption("You cannot delete the account you are currently using.")

        if st.button("Delete account", type="secondary", disabled=delete_disabled):
            if delete_user(selected_username):
                st.success(f"Account '{selected_username}' deleted successfully.")
                st.rerun()
            else:
                st.error("Failed to delete account.")
    else:
        st.write("No accounts available.")

    st.markdown("---")
    st.info("Note: When MongoDB is available, new accounts are persisted to the BSIT3 database.")
