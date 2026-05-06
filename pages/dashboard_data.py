import pandas as pd
import streamlit as st

from db import (
    get_class_offerings,
    get_curriculum,
    get_grades,
    get_semesters,
    get_students,
    get_subjects,
    get_teachers,
)

PASSING_GRADE = 75


def _as_str(value):
    if value is None:
        return ""
    return str(value).strip()


def _to_int(value):
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None


def _to_float(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _semester_label(school_year, semester, semester_names):
    key = (school_year, semester)
    semester_name = semester_names.get(key, "")
    if semester_name:
        return f"{school_year} - {semester_name}"

    if semester == 1:
        return f"{school_year} - 1st Semester"
    if semester == 2:
        return f"{school_year} - 2nd Semester"
    if semester == 3:
        return f"{school_year} - Summer"
    if school_year:
        return school_year
    return "Unknown Term"


@st.cache_data
def _student_lookup():
    lookup = {}
    for student in get_students():
        student_key = _as_str(student.get("_id"))
        if not student_key:
            continue
        lookup[student_key] = {
            "student_number": _as_str(student.get("student_no") or student.get("student_id") or student.get("StudentID")),
            "student_name": _as_str(student.get("name") or student.get("student_name") or student.get("Name")) or "Unknown",
            "program_code": _as_str(student.get("program_code") or student.get("Course") or student.get("Program")),
            "status": _as_str(student.get("status")) or "unknown",
            "email": _as_str(student.get("email")),
        }
    return lookup


@st.cache_data
def _teacher_lookup():
    lookup = {}
    for teacher in get_teachers():
        teacher_key = _as_str(teacher.get("_id"))
        if not teacher_key:
            continue
        lookup[teacher_key] = {
            "teacher_name": _as_str(teacher.get("name")) or teacher_key,
            "department": _as_str(teacher.get("department")),
            "employment_type": _as_str(teacher.get("employment_type")),
        }
    return lookup


@st.cache_data
def _subject_lookup():
    lookup = {}
    for subject in get_subjects():
        subject_code = _as_str(subject.get("subjectCode") or subject.get("subject_code") or subject.get("_id"))
        if not subject_code:
            continue
        lookup[subject_code] = {
            "subject_name": _as_str(subject.get("subjectName") or subject.get("subject_name") or subject.get("Description")) or subject_code,
            "units": _to_float(subject.get("units")) or 0.0,
            "category": _as_str(subject.get("category")),
        }
    return lookup


@st.cache_data
def _offering_lookup():
    lookup = {}
    for offering in get_class_offerings():
        offering_key = _as_str(offering.get("_id"))
        if not offering_key:
            continue
        lookup[offering_key] = offering
    return lookup


@st.cache_data
def _semester_name_lookup():
    lookup = {}
    for semester in get_semesters():
        school_year = _as_str(semester.get("school_year"))
        semester_number = _to_int(semester.get("semester"))
        if not school_year or semester_number is None:
            continue
        lookup[(school_year, semester_number)] = _as_str(semester.get("semester_name"))
    return lookup


@st.cache_data
def get_term_filter_options(_existing_terms=None):
    options = set()

    if _existing_terms is not None:
        for term in pd.Series(_existing_terms).dropna().astype(str):
            cleaned_term = term.strip()
            if cleaned_term:
                options.add(cleaned_term)

    return ["All"] + sorted(options)


@st.cache_data
def _curriculum_subject_lookup():
    lookup = {}
    for curriculum in get_curriculum():
        if curriculum.get("is_active") is False:
            continue
        program_code = _as_str(curriculum.get("courseCode") or curriculum.get("program_code"))
        for subject in curriculum.get("subjects", []):
            subject_code = _as_str(subject.get("subjectCode"))
            if not program_code or not subject_code:
                continue
            lookup[(program_code, subject_code)] = {
                "subject_name": _as_str(subject.get("subjectName")) or subject_code,
                "units": _to_float(subject.get("units")) or 0.0,
                "year_level": _to_int(subject.get("yearLevel")),
                "semester": _to_int(subject.get("semester")),
                "prerequisites": ", ".join(subject.get("prerequisites", [])),
            }
    return lookup


@st.cache_data
def get_academic_records():
    students = _student_lookup()
    teachers = _teacher_lookup()
    subjects = _subject_lookup()
    offerings = _offering_lookup()
    semester_names = _semester_name_lookup()
    curriculum_subjects = _curriculum_subject_lookup()

    rows = []
    for grade_doc in get_grades():
        student_id = _as_str(grade_doc.get("student_id") or grade_doc.get("StudentID"))
        student = students.get(student_id, {})

        class_offering_id = _as_str(grade_doc.get("class_offering_id"))
        offering = offerings.get(class_offering_id, {})

        program_code = _as_str(
            grade_doc.get("program_code") or student.get("program_code") or offering.get("program")
        )
        subject_code = _as_str(grade_doc.get("subject_code") or offering.get("subjectCode"))
        curriculum_subject = curriculum_subjects.get((program_code, subject_code), {})
        subject = subjects.get(subject_code, {})

        teacher_id = _as_str(grade_doc.get("teacher_id") or offering.get("teacher_id"))
        teacher = teachers.get(teacher_id, {})

        school_year = _as_str(grade_doc.get("school_year") or offering.get("school_year"))
        semester = _to_int(grade_doc.get("semester") or offering.get("semester") or curriculum_subject.get("semester"))
        grade = _to_float(grade_doc.get("grade"))
        status = _as_str(grade_doc.get("status")) or "pending"
        remark = _as_str(grade_doc.get("remark"))
        section = _as_str(grade_doc.get("section") or offering.get("section"))
        year_level = _to_int(grade_doc.get("year_level") or offering.get("year_level") or curriculum_subject.get("year_level"))
        units = curriculum_subject.get("units") or subject.get("units") or 0.0
        subject_name = curriculum_subject.get("subject_name") or subject.get("subject_name") or subject_code

        rows.append(
            {
                "record_id": _as_str(grade_doc.get("_id")),
                "student_id": student_id,
                "student_number": student.get("student_number") or student_id,
                "student_name": student.get("student_name") or "Unknown",
                "student_email": student.get("email", ""),
                "program_code": program_code,
                "department": program_code,
                "student_status": student.get("status", ""),
                "subject_code": subject_code,
                "subject_name": subject_name,
                "units": units,
                "teacher_id": teacher_id,
                "teacher_name": teacher.get("teacher_name") or teacher_id or "Unassigned",
                "teacher_department": teacher.get("department", ""),
                "section": section,
                "school_year": school_year,
                "semester": semester,
                "term": _semester_label(school_year, semester, semester_names),
                "year_level": year_level,
                "grade": grade,
                "grade_submitted": grade is not None,
                "status": status,
                "remark": remark,
                "class_offering_id": class_offering_id,
                "pass_fail": "Pass" if grade is not None and grade >= PASSING_GRADE else (
                    "Fail" if grade is not None else "Missing"
                ),
                "dropout_flag": "drop" in status.lower() or "withdraw" in remark.lower(),
            }
        )

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df["units"] = pd.to_numeric(df["units"], errors="coerce").fillna(0.0)
    df["grade"] = pd.to_numeric(df["grade"], errors="coerce")
    df["semester"] = pd.to_numeric(df["semester"], errors="coerce")
    df["year_level"] = pd.to_numeric(df["year_level"], errors="coerce")
    df["term_order"] = df["school_year"].fillna("") + "-S" + df["semester"].fillna(0).astype(int).astype(str)
    return df


@st.cache_data
def get_curriculum_dataframe(program_code="BSIT"):
    rows = []
    for curriculum in get_curriculum():
        current_program = _as_str(curriculum.get("courseCode") or curriculum.get("program_code"))
        if program_code and current_program != program_code:
            continue
        for subject in curriculum.get("subjects", []):
            rows.append(
                {
                    "program_code": current_program,
                    "curriculum_year": _as_str(curriculum.get("curriculumYear")),
                    "course_name": _as_str(curriculum.get("courseName")),
                    "year_level": _to_int(subject.get("yearLevel")),
                    "semester": _to_int(subject.get("semester")),
                    "subject_code": _as_str(subject.get("subjectCode")),
                    "subject_name": _as_str(subject.get("subjectName")),
                    "units": _to_float(subject.get("units")) or 0.0,
                    "prerequisites": ", ".join(subject.get("prerequisites", [])),
                }
            )

    curriculum_df = pd.DataFrame(rows)
    if curriculum_df.empty:
        return curriculum_df

    return curriculum_df.sort_values(["year_level", "semester", "subject_code"]).reset_index(drop=True)


def build_curriculum_progress(student_id, program_code="BSIT"):
    curriculum_df = get_curriculum_dataframe(program_code)
    if curriculum_df.empty:
        return curriculum_df

    records = get_academic_records()
    student_rows = records[records["student_id"] == _as_str(student_id)].copy()

    progress_rows = []
    for _, subject in curriculum_df.iterrows():
        subject_attempts = student_rows[student_rows["subject_code"] == subject["subject_code"]].copy()
        completed_attempts = subject_attempts[subject_attempts["grade"] >= PASSING_GRADE]
        ongoing_attempts = subject_attempts[subject_attempts["grade"].isna() | (subject_attempts["status"].str.lower() != "final")]

        if not completed_attempts.empty:
            latest_attempt = completed_attempts.sort_values(["school_year", "semester"], ascending=[False, False]).iloc[0]
            subject_status = "Completed"
            display_grade = latest_attempt["grade"]
            term = latest_attempt["term"]
        elif not ongoing_attempts.empty:
            latest_attempt = ongoing_attempts.sort_values(["school_year", "semester"], ascending=[False, False]).iloc[0]
            subject_status = "Ongoing"
            display_grade = latest_attempt["grade"]
            term = latest_attempt["term"]
        elif not subject_attempts.empty:
            latest_attempt = subject_attempts.sort_values(["school_year", "semester"], ascending=[False, False]).iloc[0]
            subject_status = "Remaining"
            display_grade = latest_attempt["grade"]
            term = latest_attempt["term"]
        else:
            subject_status = "Remaining"
            display_grade = None
            term = ""

        progress_rows.append(
            {
                "year_level": subject["year_level"],
                "semester": subject["semester"],
                "subject_code": subject["subject_code"],
                "subject_name": subject["subject_name"],
                "units": subject["units"],
                "prerequisites": subject["prerequisites"],
                "term": term,
                "grade": display_grade,
                "subject_status": subject_status,
            }
        )

    return pd.DataFrame(progress_rows)