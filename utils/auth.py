import bcrypt
from datetime import datetime
import re

import streamlit as st
from db import get_db

# Default user database with roles for initial access
users = {
    "admin": {"password": bcrypt.hashpw("password".encode(), bcrypt.gensalt()).decode(), "role": "admin"},
    "registrar": {"password": bcrypt.hashpw("regpass".encode(), bcrypt.gensalt()).decode(), "role": "registrar"},
    "faculty": {"password": bcrypt.hashpw("facpass".encode(), bcrypt.gensalt()).decode(), "role": "faculty"},
    "student": {"password": bcrypt.hashpw("stupass".encode(), bcrypt.gensalt()).decode(), "role": "student"},
}


def _normalize_role(role: str | None) -> str:
    normalized_role = str(role or "student").strip().lower()
    if normalized_role == "teacher":
        return "faculty"
    return normalized_role or "student"


def _normalize_identifier(value: str) -> str:
    return str(value or "").strip().lower()


def _doc_identifier(user_doc: dict) -> str:
    return _normalize_identifier(user_doc.get("email") or user_doc.get("username") or user_doc.get("name"))


def _doc_password_hash(user_doc: dict) -> str:
    password_hash = user_doc.get("password_hash") or user_doc.get("password") or ""
    if isinstance(password_hash, bytes):
        return password_hash.decode()
    return str(password_hash)


def _account_entry(identifier: str, name: str, role: str, active: bool):
    normalized_identifier = _normalize_identifier(identifier)
    return {
        "username": normalized_identifier,
        "name": str(name or normalized_identifier),
        "role": _normalize_role(role),
        "active": bool(active),
    }


def _student_link_fields(student_doc: dict | None):
    if not student_doc:
        return {}

    return {
        "student_id": str(student_doc.get("_id", "")).strip(),
        "student_no": str(student_doc.get("student_no", "")).strip(),
        "student_name": str(student_doc.get("name", "")).strip(),
        "student_email": str(student_doc.get("email", "")).strip().lower(),
        "program_code": str(student_doc.get("program_code", "")).strip(),
    }


def find_student_by_name(name: str):
    normalized_name = str(name or "").strip()
    if not normalized_name:
        return None

    try:
        return get_db().students.find_one(
            {"name": {"$regex": f"^{re.escape(normalized_name)}$", "$options": "i"}},
            {"_id": 1, "student_no": 1, "name": 1, "email": 1, "program_code": 1},
        )
    except Exception:
        return None


def search_students_by_name(name: str, limit: int = 8):
    normalized_name = str(name or "").strip()
    if not normalized_name:
        return []

    try:
        cursor = get_db().students.find(
            {"name": {"$regex": re.escape(normalized_name), "$options": "i"}},
            {"_id": 1, "student_no": 1, "name": 1, "email": 1, "program_code": 1},
        ).limit(limit)
        return list(cursor)
    except Exception:
        return []


def get_user(username: str):
    username = _normalize_identifier(username)
    if not username:
        return None

    try:
        db_user = get_db().users.find_one({"$or": [{"email": username}, {"username": username}]})
        if db_user:
            identifier = _doc_identifier(db_user)
            password_hash = _doc_password_hash(db_user)
            if identifier and password_hash:
                return {
                    "username": identifier,
                    "display_name": str(db_user.get("name") or identifier),
                    "password": password_hash,
                    "role": _normalize_role(db_user.get("role")),
                    "active": bool(db_user.get("active", True)),
                    "student_id": str(db_user.get("student_id") or "").strip(),
                    "student_no": str(db_user.get("student_no") or "").strip(),
                    "student_name": str(db_user.get("student_name") or db_user.get("name") or "").strip(),
                    "student_email": str(db_user.get("student_email") or db_user.get("email") or "").strip().lower(),
                    "program_code": str(db_user.get("program_code") or "").strip(),
                }
    except Exception:
        pass

    default_user = users.get(username)
    if default_user:
        return {
            "username": username,
            "display_name": username,
            "password": default_user["password"],
            "role": _normalize_role(default_user.get("role")),
            "active": True,
            "student_id": "",
            "student_no": "",
            "student_name": "",
            "student_email": "",
            "program_code": "",
        }
    return None


def save_user(
    username: str,
    password_hash: str,
    role: str,
    name: str | None = None,
    student_doc: dict | None = None,
    active: bool = True,
):
    username = _normalize_identifier(username)
    if not username:
        return False
    role = _normalize_role(role)

    now = datetime.utcnow()

    set_fields = {"role": role, "active": bool(active), "password_hash": password_hash}
    if "@" in username:
        set_fields["email"] = username
    else:
        set_fields["username"] = username
    set_fields["name"] = str(name or username)
    set_fields["updated_at"] = now
    set_fields.update(_student_link_fields(student_doc))

    try:
        get_db().users.update_one(
            {"$or": [{"email": username}, {"username": username}]},
            {
                "$set": set_fields,
                "$setOnInsert": {"created_at": now, "must_change_password": True, "last_login_at": None},
            },
            upsert=True,
        )
        return True
    except Exception:
        return False


def authenticate_user(username, password):
    username = _normalize_identifier(username)
    if not username or not password:
        return None

    user_record = get_user(username)
    if not user_record or not user_record.get("active", True):
        return None

    try:
        if bcrypt.checkpw(password.encode(), user_record["password"].encode()):
            return user_record
    except Exception:
        return None

    return None


def authenticate(username, password):
    user_record = authenticate_user(username, password)
    if user_record:
        return user_record.get("role")
    return False


def create_user(username: str, password: str, role: str, name: str | None = None) -> bool:
    role = _normalize_role(role)
    if not username or not password or role not in ["registrar", "faculty", "student"]:
        return False

    username = _normalize_identifier(username)
    if get_user(username):
        return False

    student_doc = None
    if role == "student":
        student_doc = find_student_by_name(name)
        if not student_doc:
            return False

    hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    users[username] = {"password": hashed_password, "role": role}
    return save_user(username, hashed_password, role, name or username, student_doc, active=True)


def update_user_role(username: str, role: str) -> bool:
    role = _normalize_role(role)
    if not username or role not in ["admin", "registrar", "faculty", "student"]:
        return False

    username = _normalize_identifier(username)
    user_record = get_user(username)
    if not user_record:
        return False

    password_hash = user_record["password"]
    users[username] = {"password": password_hash, "role": role}
    return save_user(
        username,
        password_hash,
        role,
        user_record.get("display_name") or username,
        active=user_record.get("active", True),
    )


def update_user_active(username: str, active: bool) -> bool:
    if not username:
        return False

    username = _normalize_identifier(username)
    user_record = get_user(username)
    if not user_record:
        return False

    password_hash = user_record["password"]
    users[username] = {"password": password_hash, "role": user_record.get("role")}
    return save_user(
        username,
        password_hash,
        user_record.get("role"),
        user_record.get("display_name") or username,
        active=active,
    )


def update_user_password(username: str, password: str) -> bool:
    if not username or not password:
        return False

    username = _normalize_identifier(username)
    user_record = get_user(username)
    if not user_record:
        return False

    hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    users[username] = {"password": hashed_password, "role": user_record.get("role")}
    return save_user(
        username,
        hashed_password,
        user_record.get("role"),
        user_record.get("display_name") or username,
        active=user_record.get("active", True),
    )


def delete_user(username: str) -> bool:
    if not username:
        return False

    username = _normalize_identifier(username)
    deleted = False

    if username in users:
        del users[username]
        deleted = True

    try:
        result = get_db().users.delete_one({"$or": [{"email": username}, {"username": username}]})
        deleted = result.deleted_count > 0 or deleted
    except Exception:
        pass

    return deleted


def list_user_accounts():
    accounts = []
    seen = set()
    try:
        for user in get_db().users.find({}, {"_id": 0, "username": 1, "email": 1, "name": 1, "role": 1, "active": 1}):
            identifier = _doc_identifier(user)
            if not identifier:
                continue
            accounts.append(_account_entry(identifier, user.get("name"), user.get("role"), user.get("active", True)))
            seen.add(identifier)
    except Exception:
        pass

    for username, data in users.items():
        if username not in seen:
            accounts.append(_account_entry(username, username, data.get("role"), True))
    return sorted(accounts, key=lambda account: account.get("username", ""))


def login():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.subheader("Login")
        username = st.text_input("Email or Username")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            user_record = authenticate_user(username, password)
            if user_record:
                st.session_state.logged_in = True
                st.session_state.role = user_record.get("role")
                st.session_state.username = user_record.get("username")
                st.session_state.display_name = user_record.get("display_name")
                st.session_state.student_id = user_record.get("student_id")
                st.session_state.student_no = user_record.get("student_no")
                st.session_state.student_name = user_record.get("student_name")
                st.session_state.student_email = user_record.get("student_email")
                st.session_state.program_code = user_record.get("program_code")
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
