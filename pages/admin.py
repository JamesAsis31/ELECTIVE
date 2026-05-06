import pandas as pd
import streamlit as st
from utils.auth import create_user, delete_user, find_student_by_name, list_user_accounts, search_students_by_name, update_user_active, update_user_password, update_user_role
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
    current_admin = str(st.session_state.get("username") or "").strip().lower()

    stats = get_db_stats()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Students", stats["students"])
    col2.metric("Grades", stats["grades"])
    col3.metric("Subjects", stats["subjects"])
    col4.metric("User Accounts", stats["users"])

    st.markdown("---")
    pending_full_name = st.session_state.pop("admin_pending_full_name", None)
    if pending_full_name is not None:
        st.session_state["admin_full_name_input"] = pending_full_name
        st.session_state["admin_student_name_match"] = ""

    username = st.text_input("New email or username")
    full_name = st.text_input("Full name (optional)", key="admin_full_name_input")
    password = st.text_input("Password", type="password")
    password_confirm = st.text_input("Confirm password", type="password")
    role = st.selectbox("Role", ALLOWED_ROLES)

    if role == "student" and full_name.strip():
        matches = search_students_by_name(full_name)
        if matches:
            st.caption("Matching students from the database")
            match_options = [""] + [
                f"{student.get('name', '')} ({student.get('student_no', 'No Student No')})"
                for student in matches
            ]
            selected_match = st.selectbox(
                "Select matching student",
                match_options,
                key="admin_student_name_match",
            )
            if selected_match:
                selected_student = next(
                    (
                        student
                        for student in matches
                        if f"{student.get('name', '')} ({student.get('student_no', 'No Student No')})" == selected_match
                    ),
                    None,
                )
                if selected_student and st.session_state.get("admin_full_name_input") != selected_student.get("name", ""):
                    st.session_state["admin_pending_full_name"] = selected_student.get("name", "")
                    st.rerun()
        else:
            st.caption("No matching student names found.")

    if st.button("Create account"):
        if not username.strip():
            st.error("Username cannot be empty.")
        elif role == "student" and not full_name.strip():
            st.error("Student accounts require a full name that matches the students database.")
        elif role == "student" and not find_student_by_name(full_name):
            st.error("No matching student record was found for that full name.")
        elif password != password_confirm:
            st.error("Passwords do not match.")
        elif len(password) < 6:
            st.error("Password must be at least 6 characters.")
        else:
            if create_user(username, password, role, full_name):
                st.success(f"{role.title()} account '{username}' created successfully.")
            else:
                st.error("Failed to create account. The username may already exist.")

    st.markdown("---")
    st.subheader("Manage existing account")
    accounts = list_user_accounts()
    manage_role_options = ["All"] + sorted({account.get("role", "student") for account in accounts}) if accounts else ["All"]
    selected_manage_role = st.selectbox(
        "Filter users by role",
        manage_role_options,
        key="admin_manage_role_filter",
    )
    filtered_manage_accounts = accounts
    if selected_manage_role != "All":
        filtered_manage_accounts = [
            account for account in accounts if account.get("role", "student") == selected_manage_role
        ]

    usernames = [account.get("username", "") for account in filtered_manage_accounts if account.get("username")]

    if usernames:
        selected_username = st.selectbox(
            "Select user",
            usernames,
            format_func=lambda value: next(
                (
                    f"{account.get('name', value)} ({value})"
                    for account in filtered_manage_accounts
                    if account.get("username") == value
                ),
                value,
            ),
        )
        selected_account = next(
            (account for account in filtered_manage_accounts if account.get("username") == selected_username),
            {"username": selected_username, "role": "student"},
        )
        status_locked = selected_account.get("role") == "admin"

        new_role = st.selectbox(
            "Assigned role",
            MANAGEABLE_ROLES,
            index=MANAGEABLE_ROLES.index(selected_account.get("role", "student"))
            if selected_account.get("role", "student") in MANAGEABLE_ROLES
            else MANAGEABLE_ROLES.index("student"),
            key=f"manage_role_{selected_username}",
        )
        requested_active = st.checkbox(
            "Account is active",
            value=bool(selected_account.get("active", True)),
            key=f"manage_status_{selected_username}",
            disabled=status_locked,
        )
        if status_locked:
            st.caption("Admin account status is protected and cannot be changed.")
        new_password = st.text_input("New password", type="password", key=f"manage_password_{selected_username}")
        confirm_password = st.text_input(
            "Confirm new password",
            type="password",
            key=f"manage_confirm_password_{selected_username}",
        )
        update_submitted = st.button("Save account changes", key=f"manage_update_{selected_username}")

        if update_submitted:
            changed = False
            if selected_username == current_admin and new_role != "admin":
                st.error("You cannot change your own admin role.")
            elif status_locked and requested_active != bool(selected_account.get("active", True)):
                st.error("Admin account status cannot be changed.")
            elif selected_username == current_admin and not requested_active:
                st.error("You cannot deactivate the account you are currently using.")
            else:
                if new_role != selected_account.get("role"):
                    if update_user_role(selected_username, new_role):
                        changed = True
                    else:
                        st.error("Failed to update the user role.")

                if requested_active != bool(selected_account.get("active", True)):
                    if update_user_active(selected_username, requested_active):
                        changed = True
                    else:
                        st.error("Failed to update the account status.")

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
                else:
                    st.info("No changes to save.")

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
        st.info("No accounts match the selected role filter.")

    st.markdown("---")
    st.subheader("Existing Accounts")
    accounts = list_user_accounts()
    if accounts:
        role_options = ["All"] + sorted({account.get("role", "student") for account in accounts})
        selected_role_filter = st.selectbox("Filter by role", role_options, key="admin_accounts_role_filter")
        filtered_accounts = accounts
        if selected_role_filter != "All":
            filtered_accounts = [
                account for account in accounts if account.get("role", "student") == selected_role_filter
            ]

        if filtered_accounts:
            protected_accounts = [account for account in filtered_accounts if account.get("role") == "admin"]
            editable_accounts = [account for account in filtered_accounts if account.get("role") != "admin"]

            if protected_accounts:
                st.caption("Admin accounts are protected. Their active status cannot be modified.")
                st.dataframe(pd.DataFrame(protected_accounts), hide_index=True, use_container_width=True)

            if editable_accounts:
                editable_accounts_df = pd.DataFrame(editable_accounts)
                edited_accounts_df = st.data_editor(
                    editable_accounts_df,
                    hide_index=True,
                    use_container_width=True,
                    disabled=["username", "name", "role"],
                    column_config={
                        "username": st.column_config.TextColumn("Username"),
                        "name": st.column_config.TextColumn("Name"),
                        "role": st.column_config.TextColumn("Role"),
                        "active": st.column_config.CheckboxColumn("Active"),
                    },
                    key="admin_accounts_editor",
                )

            if editable_accounts and st.button("Apply table status changes", key="admin_apply_status_changes"):
                changed_accounts = []
                for original_account, edited_account in zip(editable_accounts, edited_accounts_df.to_dict("records")):
                    original_active = bool(original_account.get("active", True))
                    edited_active = bool(edited_account.get("active", True))
                    if original_active != edited_active:
                        changed_accounts.append((original_account.get("username", ""), edited_active))

                if not changed_accounts:
                    st.info("No status changes to apply.")
                else:
                    failed_updates = []
                    for account_username, account_active in changed_accounts:
                        if account_username == current_admin and not account_active:
                            failed_updates.append(account_username)
                            st.error("You cannot deactivate the account you are currently using.")
                            continue

                        if not update_user_active(account_username, account_active):
                            failed_updates.append(account_username)

                    if failed_updates:
                        st.error(
                            "Failed to update these accounts: " + ", ".join(sorted(set(filter(None, failed_updates))))
                        )
                    else:
                        st.success("Account statuses updated successfully.")
                        st.rerun()
            elif not editable_accounts:
                st.info("No non-admin accounts are available for status editing in the current filter.")
        else:
            st.info("No accounts match the selected role filter.")
    else:
        st.write("No accounts available.")

    st.markdown("---")
    st.info("Note: When MongoDB is available, accounts are persisted to the BSIT users collection.")
