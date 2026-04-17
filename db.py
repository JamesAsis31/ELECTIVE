import os
from functools import lru_cache
from dotenv import load_dotenv
from bson import ObjectId
from pymongo import MongoClient
from pymongo.errors import PyMongoError

load_dotenv()

_client = None


def _to_str(value):
    if isinstance(value, ObjectId):
        return str(value)
    return value


def ensure_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def normalize_documents(documents):
    normalized = []
    for doc in documents:
        row = dict(doc)
        if "_id" in row:
            row["_id"] = str(row["_id"])
        if "StudentID" in row and not row.get("student_id"):
            row["student_id"] = str(row["StudentID"])
        if "StudentNumber" in row and not row.get("student_id"):
            row["student_id"] = str(row["StudentNumber"])
        if "SubjectCode" in row and not row.get("subject_code"):
            row["subject_code"] = str(row["SubjectCode"])
        if "SubjectName" in row and not row.get("subject_name"):
            row["subject_name"] = str(row["SubjectName"])
        if "StudentName" in row and not row.get("student_name"):
            row["student_name"] = str(row["StudentName"])
        if "Name" in row and not row.get("student_name"):
            row["student_name"] = str(row["Name"])
        if "Term" in row and not row.get("term"):
            row["term"] = str(row["Term"])
        if "SemesterID" in row and not row.get("term"):
            row["term"] = str(row["SemesterID"])

        for field in ["student_id", "subject_id", "program", "department", "teacher", "status", "term"]:
            if field in row and isinstance(row[field], ObjectId):
                row[field] = str(row[field])

        if isinstance(row.get("student"), dict) and "_id" in row["student"]:
            row["student_id"] = str(row["student"]["_id"])
        if isinstance(row.get("subject"), dict) and "_id" in row["subject"]:
            row["subject_id"] = str(row["subject"]["_id"])
        normalized.append(row)
    return normalized


def get_client():
    global _client
    if _client is None:
        uri = os.getenv("MONGO_URI")
        if not uri:
            raise ValueError("MONGO_URI is not set in .env")
        _client = MongoClient(uri, serverSelectionTimeoutMS=10000)
    return _client


def get_db():
    db_name = os.getenv("DB_NAME", "BSIT3")
    return get_client()[db_name]


@lru_cache(maxsize=None)
def get_collection_data(collection_name):
    try:
        return normalize_documents(get_db()[collection_name].find())
    except PyMongoError as error:
        print(f"MongoDB error reading {collection_name}: {error}")
        return []


def get_students():
    return get_collection_data("students")


def get_grades():
    return get_collection_data("grades")


def get_subjects():
    return get_collection_data("subjects")


def get_users():
    return get_collection_data("users")


def get_grade_rows():
    documents = get_grades()
    rows = []
    for doc in documents:
        student_id = doc.get("student_id") or doc.get("StudentID") or doc.get("StudentNumber")
        student_name = doc.get("student_name") or doc.get("StudentName") or doc.get("Name")
        term = doc.get("term") or doc.get("SemesterID") or doc.get("Term")
        subject_codes = ensure_list(doc.get("SubjectCodes") or doc.get("subject_code") or doc.get("SubjectCode"))
        grades = ensure_list(doc.get("Grades") or doc.get("grade") or doc.get("Grade"))
        teachers = ensure_list(doc.get("Teachers") or doc.get("teacher") or doc.get("Teacher"))
        if term is not None and not isinstance(term, str):
            term = str(term)

        length = max(len(subject_codes), len(grades), len(teachers), 1)
        if len(subject_codes) == 0:
            subject_codes = ["Unknown"] * length
        if len(grades) == 0:
            grades = [None] * length
        if len(teachers) == 0:
            teachers = [""] * length

        subject_codes = (subject_codes + ["Unknown"] * length)[:length]
        grades = (grades + [None] * length)[:length]
        teachers = (teachers + [""] * length)[:length]

        for index in range(length):
            rows.append(
                {
                    "_id": str(doc.get("_id", "")),
                    "student_id": str(student_id) if student_id is not None else "",
                    "student_name": str(student_name) if student_name is not None else "",
                    "subject_code": str(subject_codes[index]) if subject_codes[index] is not None else "Unknown",
                    "grade": grades[index],
                    "teacher": str(teachers[index]) if teachers[index] is not None else "",
                    "term": term or "",
                    "status": str(doc.get("status", "")),
                    "program": str(doc.get("Program", doc.get("program", ""))) if doc.get("Program", doc.get("program", "")) is not None else "",
                    "department": str(doc.get("Department", doc.get("department", ""))) if doc.get("Department", doc.get("department", "")) is not None else "",
                    "subject_name": str(doc.get("SubjectName", doc.get("subject_name", ""))) if doc.get("SubjectName", doc.get("subject_name", "")) is not None else "",
                }
            )
    return normalize_documents(rows)
