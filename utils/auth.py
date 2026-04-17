import bcrypt
import streamlit as st
from db import get_db

# Default user database with roles for initial access
users = {
    "admin": {"password": bcrypt.hashpw("password".encode(), bcrypt.gensalt()).decode(), "role": "admin"},
    "registrar": {"password": bcrypt.hashpw("regpass".encode(), bcrypt.gensalt()).decode(), "role": "registrar"},
    "faculty": {"password": bcrypt.hashpw("facpass".encode(), bcrypt.gensalt()).decode(), "role": "faculty"},
    "student": {"password": bcrypt.hashpw("stupass".encode(), bcrypt.gensalt()).decode(), "role": "student"},
}


def get_user(username: str):
    username = username.strip().lower()
    try:
        db_user = get_db().users.find_one({"username": username})
        if db_user:
            return {"username": db_user["username"], "password": db_user["password"], "role": db_user.get("role")}
    except Exception:
        pass
    return users.get(username)


def save_user(username: str, password_hash: str, role: str):
    try:
        get_db().users.update_one(
            {"username": username},
            {"$set": {"password": password_hash, "role": role}},
            upsert=True,
        )
    except Exception:
        pass


def authenticate(username, password):
    if not username or not password:
        return False

    user_record = get_user(username)
    if not user_record:
        return False

    try:
        if bcrypt.checkpw(password.encode(), user_record["password"].encode()):
            return user_record.get("role")
    except Exception:
        return False

    return False


def create_user(username: str, password: str, role: str) -> bool:
    if not username or not password or role not in ["registrar", "faculty", "student"]:
        return False

    username = username.strip().lower()
    if get_user(username):
        return False

    hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    users[username] = {"password": hashed_password, "role": role}
    save_user(username, hashed_password, role)
    return True


def update_user_role(username: str, role: str) -> bool:
    if not username or role not in ["admin", "registrar", "faculty", "student"]:
        return False

    username = username.strip().lower()
    user_record = get_user(username)
    if not user_record:
        return False

    password_hash = user_record["password"]
    users[username] = {"password": password_hash, "role": role}
    save_user(username, password_hash, role)
    return True


def update_user_password(username: str, password: str) -> bool:
    if not username or not password:
        return False

    username = username.strip().lower()
    user_record = get_user(username)
    if not user_record:
        return False

    hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    users[username] = {"password": hashed_password, "role": user_record.get("role")}
    save_user(username, hashed_password, user_record.get("role"))
    return True


def delete_user(username: str) -> bool:
    if not username:
        return False

    username = username.strip().lower()
    deleted = False

    if username in users:
        del users[username]
        deleted = True

    try:
        result = get_db().users.delete_one({"username": username})
        deleted = result.deleted_count > 0 or deleted
    except Exception:
        pass

    return deleted


def list_user_accounts():
    accounts = []
    seen = set()
    try:
        for user in get_db().users.find({}, {"_id": 0, "username": 1, "role": 1}):
            accounts.append(user)
            seen.add(user["username"])
    except Exception:
        pass

    for username, data in users.items():
        if username not in seen:
            accounts.append({"username": username, "role": data["role"]})
    return sorted(accounts, key=lambda account: account["username"])


def login():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.subheader("Login")
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            role = authenticate(username, password)
            if role:
                st.session_state.logged_in = True
                st.session_state.role = role
                st.session_state.username = username.strip().lower()
                st.success("Logged in successfully!")
                st.rerun()
            else:
                st.error("Invalid credentials")


def logout():
    if st.sidebar.button("Logout"):
        return True
    return False


def require_login():
    if not st.session_state.get("logged_in", False):
        login()
        st.stop()
