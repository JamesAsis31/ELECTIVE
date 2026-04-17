import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from db import get_grade_rows, get_students, get_subjects


def _normalize_term_label(value):
    text = str(value).strip()
    if not text:
        return ""

    lowered = text.lower()
    if "1st" in lowered or "first" in lowered:
        return "1st Semester"
    if "2nd" in lowered or "second" in lowered:
        return "2nd Semester"
    if "summer" in lowered or "3rd" in lowered or "third" in lowered:
        return "Summer"

    try:
        numeric_value = int(float(text))
    except ValueError:
        return text

    semester_position = numeric_value % 3
    if semester_position == 1:
        return "1st Semester"
    if semester_position == 2:
        return "2nd Semester"
    return "Summer"


@st.cache_data
def _student_lookup():
    lookup = {}
    for student in get_students():
        student_id = str(student.get("_id", "")).strip()
        if not student_id:
            continue
        student_name = student.get("student_name") or student.get("Name") or "Unknown"
        program = student.get("Course") or student.get("Program") or student.get("program") or ""
        lookup[student_id] = {
            "student_name": str(student_name).strip() or "Unknown",
            "program": str(program).strip(),
        }
    return lookup


@st.cache_data
def _subject_lookup():
    lookup = {}
    for subject in get_subjects():
        subject_code = str(subject.get("subject_code") or subject.get("SubjectCode") or subject.get("_id") or "").strip()
        if not subject_code:
            continue
        subject_name = subject.get("subject_name") or subject.get("SubjectName") or subject.get("Description") or subject.get("Name") or ""
        lookup[subject_code] = str(subject_name).strip()
    return lookup


@st.cache_data
def build_registrar_dataframe():
    grade_rows = get_grade_rows()
    if not grade_rows:
        return pd.DataFrame()

    df = pd.DataFrame(grade_rows)
    if df.empty or "student_id" not in df.columns:
        return pd.DataFrame()

    df["student_id"] = df["student_id"].astype(str).str.strip()
    if "grade" in df.columns:
        df["grade"] = pd.to_numeric(df["grade"], errors="coerce")
    else:
        df["grade"] = pd.Series(dtype="float64")

    students = _student_lookup()
    subjects = _subject_lookup()

    df["student_name"] = df["student_id"].map(
        lambda student_id: students.get(student_id, {}).get("student_name", "Unknown")
    )
    df["program"] = df["student_id"].map(
        lambda student_id: students.get(student_id, {}).get("program", "")
    )
    df["department"] = df["program"]

    if "subject_code" in df.columns:
        df["subject_code"] = df["subject_code"].astype(str).str.strip()
    else:
        df["subject_code"] = ""
    df["subject_name"] = df["subject_code"].map(lambda code: subjects.get(code, ""))

    if "term" in df.columns:
        df["term"] = df["term"].fillna("").astype(str).str.strip().map(_normalize_term_label)
    else:
        df["term"] = ""
    if "teacher" in df.columns:
        df["teacher"] = df["teacher"].fillna("").astype(str).str.strip()
    else:
        df["teacher"] = ""
    if "status" in df.columns:
        df["status"] = df["status"].fillna("").astype(str).str.strip()
    else:
        df["status"] = ""

    df["student_name"] = df["student_name"].fillna("Unknown").replace("", "Unknown")
    df["program"] = df["program"].fillna("").astype(str).str.strip()
    df["department"] = df["department"].fillna("").astype(str).str.strip()
    df["pass_fail"] = df["grade"].apply(lambda value: "Pass" if pd.notna(value) and value >= 75 else "Fail")

    return df


def _enrollment_trend(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "term" not in df.columns or "student_id" not in df.columns:
        return pd.DataFrame()

    rows = []
    previous_students = set()
    for term in sorted(df["term"].dropna().unique()):
        current_students = set(df.loc[df["term"] == term, "student_id"].dropna().unique())
        total_enrollment = len(current_students)
        new_enrollees = len(current_students - previous_students)
        dropouts = len(previous_students - current_students) if previous_students else 0
        retention_rate = round((len(current_students & previous_students) / len(previous_students)) * 100, 1) if previous_students else 0.0
        rows.append(
            {
                "Semester": term,
                "Total Enrollment": total_enrollment,
                "New Enrollees": new_enrollees,
                "Dropouts": dropouts,
                "Retention Rate": retention_rate,
            }
        )
        previous_students = current_students

    return pd.DataFrame(rows)


def _filter_options(series: pd.Series):
    values = [value for value in series.dropna().astype(str).unique() if value.strip()]
    return ["All"] + sorted(values)


def _apply_filters(df: pd.DataFrame, term="All", subject_code="All", department="All") -> pd.DataFrame:
    filtered = df.copy()
    if term != "All":
        filtered = filtered[filtered["term"] == term]
    if subject_code != "All":
        filtered = filtered[filtered["subject_code"] == subject_code]
    if department != "All":
        filtered = filtered[filtered["department"] == department]
    return filtered


def show_registrar_dashboard():
    st.title("Registrar's Office Dashboard Reports")

    df = build_registrar_dataframe()
    if df.empty:
        st.error("No grade or student records found in MongoDB.")
        return

    term_options = _filter_options(df["term"])
    selected_term = st.session_state.get("registrar_term_filter", "All")
    if selected_term not in term_options:
        selected_term = "All"

    subject_source = _apply_filters(df, term=selected_term)
    subject_options = _filter_options(subject_source["subject_code"])
    selected_subject = st.session_state.get("registrar_subject_filter", "All")
    if selected_subject not in subject_options:
        selected_subject = "All"

    department_source = _apply_filters(df, term=selected_term, subject_code=selected_subject)
    department_options = _filter_options(department_source["department"])
    selected_department = st.session_state.get("registrar_department_filter", "All")
    if selected_department not in department_options:
        selected_department = "All"

    filter_col1, filter_col2, filter_col3 = st.columns(3)
    with filter_col1:
        selected_term = st.selectbox("Filter by Term", term_options, key="registrar_term_filter")
    with filter_col2:
        selected_subject = st.selectbox("Filter by Subject Code", subject_options, key="registrar_subject_filter")
    with filter_col3:
        selected_department = st.selectbox("Filter by Department / Program", department_options, key="registrar_department_filter")

    filtered = _apply_filters(df, term=selected_term, subject_code=selected_subject, department=selected_department)

    if filtered.empty:
        st.warning("No records match the selected filters.")
        return

    metrics_col1, metrics_col2, metrics_col3 = st.columns(3)
    metrics_col1.metric("Filtered Records", len(filtered))
    metrics_col2.metric("Students", filtered["student_id"].nunique())
    metrics_col3.metric("Subjects", filtered["subject_code"].nunique())

    st.header("1: Student Academic Standing Report")
    standing = (
        filtered.groupby(["student_id", "student_name"], dropna=False)
        .agg(GPA=("grade", "mean"), Total_Subjects=("subject_code", "count"))
        .reset_index()
    )
    standing["GPA"] = standing["GPA"].round(2)

    fig, ax = plt.subplots()
    ax.hist(standing["GPA"].dropna(), bins=10, color="skyblue", edgecolor="black")
    ax.set_xlabel("GPA Range")
    ax.set_ylabel("Number of Students")
    ax.set_title("GPA Distribution")
    st.pyplot(fig)
    plt.close(fig)

    st.dataframe(
        standing[["student_id", "student_name", "GPA", "Total_Subjects"]].rename(
            columns={"student_id": "Student Number", "student_name": "Student Name"}
        ),
        use_container_width=True,
    )

    st.header("2: Dean's List Report")
    deans_list = (
        filtered.groupby(["student_id", "student_name", "term"], dropna=False)
        .agg(GPA=("grade", "mean"), Total_Subjects=("subject_code", "count"))
        .reset_index()
    )
    deans_list["GPA"] = deans_list["GPA"].round(2)
    deans_list = deans_list[deans_list["GPA"] >= 90]
    if deans_list.empty:
        st.info("No students qualify for the Dean's List with the current filters. Showing the highest GPAs in the filtered data instead.")
        top_candidates = (
            filtered.groupby(["student_id", "student_name", "term"], dropna=False)
            .agg(GPA=("grade", "mean"), Total_Subjects=("subject_code", "count"))
            .reset_index()
            .sort_values("GPA", ascending=False)
            .head(10)
        )
        top_candidates["GPA"] = top_candidates["GPA"].round(2)
        st.dataframe(
            top_candidates[["student_id", "student_name", "term", "GPA", "Total_Subjects"]].rename(
                columns={"student_id": "Student Number", "student_name": "Student Name", "term": "Term"}
            ),
            use_container_width=True,
        )
    else:
        st.dataframe(
            deans_list[["student_id", "student_name", "term", "GPA", "Total_Subjects"]].rename(
                columns={"student_id": "Student Number", "student_name": "Student Name", "term": "Term"}
            ),
            use_container_width=True,
        )

    st.header("3: Probation Report")
    probation = (
        filtered.groupby(["student_id", "student_name", "term"], dropna=False)
        .agg(
            GPA=("grade", "mean"),
            Total_Subjects=("subject_code", "count"),
            Fail_Count=("pass_fail", lambda values: (values == "Fail").sum()),
        )
        .reset_index()
    )
    probation["GPA"] = probation["GPA"].round(2)
    probation["Fail Percentage"] = probation.apply(
        lambda row: round((row["Fail_Count"] / row["Total_Subjects"]) * 100, 1) if row["Total_Subjects"] else 0,
        axis=1,
    )
    probation = probation[(probation["GPA"] <= 75) | (probation["Fail Percentage"] >= 30)]
    if probation.empty:
        st.info("No students are on academic probation with the current filters.")
    else:
        st.dataframe(
            probation[["student_id", "student_name", "term", "GPA", "Fail Percentage", "Total_Subjects"]].rename(
                columns={"student_id": "Student Number", "student_name": "Student Name", "term": "Term"}
            ),
            use_container_width=True,
        )

    st.header("4: Subject Pass/Fail Distribution")
    pass_fail = (
        filtered.groupby(["subject_code", "subject_name", "term"], dropna=False)
        .agg(
            Pass_Count=("pass_fail", lambda values: (values == "Pass").sum()),
            Fail_Count=("pass_fail", lambda values: (values == "Fail").sum()),
            Total=("pass_fail", "count"),
        )
        .reset_index()
    )
    pass_fail["Pass %"] = pass_fail.apply(
        lambda row: round((row["Pass_Count"] / row["Total"]) * 100, 1) if row["Total"] else 0,
        axis=1,
    )
    pass_fail["Fail %"] = pass_fail.apply(
        lambda row: round((row["Fail_Count"] / row["Total"]) * 100, 1) if row["Total"] else 0,
        axis=1,
    )
    st.dataframe(
        pass_fail[["subject_code", "subject_name", "term", "Pass_Count", "Fail_Count", "Pass %", "Fail %"]].rename(
            columns={
                "subject_code": "Subject Code",
                "subject_name": "Subject Name",
                "term": "Term",
                "Pass_Count": "Pass Count",
                "Fail_Count": "Fail Count",
            }
        ),
        use_container_width=True,
    )

    st.header("5: Enrollment Trend Analysis")
    enrollment_trend = _enrollment_trend(filtered)
    if enrollment_trend.empty:
        st.write("Unable to compute enrollment trends from the available fields.")
    else:
        st.dataframe(enrollment_trend, use_container_width=True)
        st.line_chart(enrollment_trend.set_index("Semester")[["Total Enrollment"]])

    st.header("6: Top Performers per Program")
    performers = filtered[filtered["program"].str.strip() != ""]
    if performers.empty:
        st.write("Program data is not available for top performer analysis.")
    else:
        performers = (
            performers.groupby(["program", "student_id", "student_name"], dropna=False)
            .agg(GPA=("grade", "mean"), Total_Subjects=("subject_code", "count"))
            .reset_index()
        )
        performers["GPA"] = performers["GPA"].round(2)
        performers = performers.sort_values(["program", "GPA"], ascending=[True, False])
        top_per_program = performers.groupby("program", as_index=False).head(10)
        st.dataframe(
            top_per_program[["program", "student_id", "student_name", "GPA", "Total_Subjects"]].rename(
                columns={"program": "Program", "student_id": "Student Number", "student_name": "Student Name"}
            ),
            use_container_width=True,
        )

    st.header("7: Curriculum Progress and Advising")
    advising_col1, advising_col2 = st.columns(2)
    with advising_col1:
        selected_teacher = st.selectbox("Select Teacher", _filter_options(filtered["teacher"]))
    with advising_col2:
        selected_advising_subject = st.selectbox("Select Subject", _filter_options(filtered["subject_code"]))

    advising = filtered.copy()
    if selected_teacher != "All":
        advising = advising[advising["teacher"] == selected_teacher]
    if selected_advising_subject != "All":
        advising = advising[advising["subject_code"] == selected_advising_subject]

    if advising.empty:
        st.warning("No advising records match the selected teacher and subject.")
        return

    st.subheader("Subject Performance Summary")
    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    metric_col1.metric("Mean Grade", round(advising["grade"].mean(), 2))
    metric_col2.metric("Median Grade", round(advising["grade"].median(), 2))
    metric_col3.metric("Highest Grade", round(advising["grade"].max(), 2))
    metric_col4.metric("Lowest Grade", round(advising["grade"].min(), 2))

    st.subheader("Grade Distribution")
    bins = [0, 60, 70, 80, 90, 100]
    labels = ["0-59", "60-69", "70-79", "80-89", "90-100"]
    advising_chart = advising.copy()
    advising_chart["Grade Range"] = pd.cut(advising_chart["grade"], bins=bins, labels=labels, include_lowest=True)
    distribution = advising_chart["Grade Range"].value_counts().reindex(labels).fillna(0)
    fig, ax = plt.subplots()
    distribution.plot(kind="bar", ax=ax, color="teal", edgecolor="black")
    ax.set_title("Grade Distribution")
    ax.set_xlabel("Grade Range")
    ax.set_ylabel("Number of Students")
    st.pyplot(fig)
    plt.close(fig)

    st.subheader("Pass vs Fail")
    pass_count = int((advising["grade"] >= 75).sum())
    fail_count = int((advising["grade"] < 75).sum())
    fig, ax = plt.subplots()
    bars = ax.bar(["Pass", "Fail"], [pass_count, fail_count], color=["seagreen", "crimson"])
    ax.set_title("Pass vs Fail")
    ax.set_ylabel("Number of Students")
    for bar in bars:
        ax.text(
            bar.get_x() + (bar.get_width() / 2),
            bar.get_height(),
            str(int(bar.get_height())),
            ha="center",
            va="bottom",
            fontweight="bold",
        )
    st.pyplot(fig)
    plt.close(fig)
    st.write(f"**Pass:** {pass_count} | **Fail:** {fail_count}")

    st.subheader("Student Performance Table")
    advising_table = advising.copy()
    advising_table["Pass/Fail Status"] = advising_table["grade"].apply(
        lambda value: "Pass" if pd.notna(value) and value >= 75 else "Fail"
    )
    advising_table["Next Level"] = ""
    st.dataframe(
        advising_table[["student_id", "student_name", "subject_code", "Next Level", "grade", "Pass/Fail Status"]].rename(
            columns={
                "student_id": "Student ID",
                "student_name": "Student Name",
                "subject_code": "Course",
                "grade": "Grade",
            }
        ),
        use_container_width=True,
    )
