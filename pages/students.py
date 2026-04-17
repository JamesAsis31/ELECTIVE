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
def get_students_data():
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

    if "subject_code" in df.columns:
        df["subject_code"] = df["subject_code"].fillna("").astype(str).str.strip()
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

    df["section"] = ""
    df["units"] = 0.0
    df["student_name"] = df["student_name"].fillna("Unknown").replace("", "Unknown")
    df["program"] = df["program"].fillna("").astype(str).str.strip()
    df["pass_fail"] = df["grade"].apply(lambda value: "Pass" if pd.notna(value) and value >= 75 else "Fail")

    return df


def _filter_options(series: pd.Series):
    values = [value for value in series.dropna().astype(str).unique() if value.strip()]
    return ["All"] + sorted(values)


def _grade_ranges(grades: pd.Series) -> pd.Series:
    bins = [0, 59.99, 69.99, 79.99, 89.99, 100]
    labels = ["Below 60", "60-69", "70-79", "80-89", "90-100"]
    return pd.cut(grades, bins=bins, labels=labels, include_lowest=True)


def _student_display_map(df: pd.DataFrame):
    student_rows = df[["student_id", "student_name"]].drop_duplicates().sort_values(["student_name", "student_id"])
    return {row["student_id"]: f"{row['student_name']} ({row['student_id']})" for _, row in student_rows.iterrows()}


def _student_options(student_map, search_text: str):
    normalized_search = search_text.strip().lower()
    student_ids = ["All"]
    for student_id, label in student_map.items():
        if not normalized_search or normalized_search in label.lower():
            student_ids.append(student_id)
    student_labels = {"All": "All Students"}
    student_labels.update(student_map)
    return student_ids, student_labels


def _student_term_average(df: pd.DataFrame, student_id: str) -> pd.DataFrame:
    student_rows = df[df["student_id"] == student_id]
    if student_rows.empty:
        return pd.DataFrame(columns=["Term", "GPA"])

    averages = (
        student_rows.groupby("term", dropna=False)
        .agg(GPA=("grade", "mean"))
        .reset_index()
        .rename(columns={"term": "Term"})
    )
    averages["GPA"] = averages["GPA"].round(2)
    return averages.sort_values("Term")


def show_students_dashboard():
    st.title("Students Dashboard Reports")
    st.caption("Student-focused reports with simpler filters and tabbed navigation.")

    df = get_students_data()
    if df.empty:
        st.warning("No data available from the database.")
        return

    student_map = _student_display_map(df)
    student_search = st.session_state.get("students_student_search", "")
    student_ids, student_labels = _student_options(student_map, student_search)

    selected_student = st.session_state.get("students_student_filter", "All")
    if selected_student not in student_ids:
        selected_student = "All"

    student_source = df if selected_student == "All" else df[df["student_id"] == selected_student]
    subject_options = _filter_options(student_source["subject_code"])
    selected_subject = st.session_state.get("students_subject_filter", "All")
    if selected_subject not in subject_options:
        selected_subject = "All"

    term_source = student_source if selected_subject == "All" else student_source[student_source["subject_code"] == selected_subject]
    term_options = _filter_options(term_source["term"])
    selected_term = st.session_state.get("students_term_filter", "All")
    if selected_term not in term_options:
        selected_term = "All"

    with st.expander("Filters", expanded=True):
        filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)
        with filter_col1:
            student_search = st.text_input("Search Student Name", value=student_search, key="students_student_search")
        student_ids, student_labels = _student_options(student_map, student_search)
        if selected_student not in student_ids:
            selected_student = "All"
        with filter_col2:
            selected_student = st.selectbox(
                "Student",
                student_ids,
                index=student_ids.index(selected_student),
                format_func=lambda student_id: student_labels[student_id],
                key="students_student_filter",
            )
        student_source = df if selected_student == "All" else df[df["student_id"] == selected_student]
        subject_options = _filter_options(student_source["subject_code"])
        if selected_subject not in subject_options:
            selected_subject = "All"
        with filter_col3:
            selected_subject = st.selectbox("Subject", subject_options, key="students_subject_filter")
        term_source = student_source if selected_subject == "All" else student_source[student_source["subject_code"] == selected_subject]
        term_options = _filter_options(term_source["term"])
        if selected_term not in term_options:
            selected_term = "All"
        with filter_col4:
            selected_term = st.selectbox("Term", term_options, key="students_term_filter")

    st.caption("Use the search bar to quickly find a student by name.")

    filtered = df.copy()
    if selected_student != "All":
        filtered = filtered[filtered["student_id"] == selected_student]
    if selected_subject != "All":
        filtered = filtered[filtered["subject_code"] == selected_subject]
    if selected_term != "All":
        filtered = filtered[filtered["term"] == selected_term]

    if filtered.empty:
        st.warning("No records match the selected filters.")
        return

    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    metric_col1.metric("Records", len(filtered))
    metric_col2.metric("Students", filtered["student_id"].nunique())
    metric_col3.metric("Subjects", filtered["subject_code"].nunique())
    metric_col4.metric("Terms", filtered["term"].nunique())

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
        [
            "1. Grade Distribution",
            "2. Performance Trend",
            "3. Difficulty Ratings",
            "4. Class Comparison",
            "5. Passed vs Failed",
            "6. Curriculum Viewer",
        ]
    )

    with tab1:
        st.subheader("Class Grade Distribution (Histogram)")
        histogram_source = filtered.dropna(subset=["grade"]).copy()
        if histogram_source.empty:
            st.info("No grade data is available for the selected filters.")
        else:
            histogram_source["Grade Range"] = _grade_ranges(histogram_source["grade"])
            range_order = ["Below 60", "60-69", "70-79", "80-89", "90-100"]
            distribution = histogram_source["Grade Range"].value_counts().reindex(range_order).fillna(0)
            fig, ax = plt.subplots()
            distribution.plot(kind="bar", ax=ax, color="skyblue", edgecolor="black")
            ax.set_xlabel("Grade Range")
            ax.set_ylabel("Number of Students")
            ax.set_title("Grade Histogram")
            for index, value in enumerate(distribution.tolist()):
                ax.text(index, value + 0.2, str(int(value)), ha="center", va="bottom")
            st.pyplot(fig)
            plt.close(fig)

    with tab2:
        st.subheader("Performance Trend Over Time")
        if selected_student == "All":
            st.info("Select a specific student to view GPA changes over time.")
        else:
            trend = _student_term_average(df, selected_student)
            if trend.empty:
                st.info("No GPA history is available for the selected student.")
            else:
                fig, ax = plt.subplots()
                ax.plot(trend["Term"], trend["GPA"], marker="o", linewidth=2, color="teal")
                ax.set_xlabel("Term")
                ax.set_ylabel("GPA")
                ax.set_title("GPA Trend Over Time")
                for _, row in trend.iterrows():
                    ax.annotate(str(row["GPA"]), (row["Term"], row["GPA"]), textcoords="offset points", xytext=(0, 8), ha="center")
                st.pyplot(fig)
                plt.close(fig)
                st.dataframe(trend, use_container_width=True)

    with tab3:
        st.subheader("Subject Difficulty Ratings")
        if selected_subject == "All":
            st.info("Select a subject to analyze difficulty ratings.")
        else:
            subject_rows = df[df["subject_code"] == selected_subject].dropna(subset=["grade"]).copy()
            if subject_rows.empty:
                st.info("No grade data is available for the selected subject.")
            else:
                subject_rows["Grade Range"] = _grade_ranges(subject_rows["grade"])
                range_order = ["Below 60", "60-69", "70-79", "80-89", "90-100"]
                percentages = (
                    subject_rows["Grade Range"].value_counts(normalize=True).reindex(range_order).fillna(0).mul(100).round(1)
                )
                difficulty_table = percentages.reset_index()
                difficulty_table.columns = ["Grade Range", "Percentage"]
                average_grade = round(subject_rows["grade"].mean(), 2)
                if average_grade >= 85:
                    difficulty_level = "Low Difficulty"
                elif average_grade >= 70:
                    difficulty_level = "Medium Difficulty"
                else:
                    difficulty_level = "High Difficulty"

                metric_a, metric_b = st.columns(2)
                metric_a.metric("Difficulty Level", difficulty_level)
                metric_b.metric("Average Grade", average_grade)
                st.dataframe(difficulty_table, use_container_width=True)

    with tab4:
        st.subheader("Comparison with Class Average")
        if selected_student == "All" or selected_subject == "All":
            st.info("Select a specific student and subject to compare with the class average.")
        else:
            student_subject_rows = df[(df["student_id"] == selected_student) & (df["subject_code"] == selected_subject)].dropna(subset=["grade"])
            class_rows = df[df["subject_code"] == selected_subject].dropna(subset=["grade"])
            if student_subject_rows.empty or class_rows.empty:
                st.info("No comparison data is available for the selected student and subject.")
            else:
                student_grade = round(student_subject_rows["grade"].mean(), 2)
                class_average = round(class_rows["grade"].mean(), 2)
                higher_scores = int((class_rows["grade"] > student_grade).sum())
                rank = higher_scores + 1
                total_students = len(class_rows)
                if student_grade > class_average:
                    remark = "Above Average"
                elif student_grade < class_average:
                    remark = "Below Average"
                else:
                    remark = "Average"

                compare_col1, compare_col2, compare_col3 = st.columns(3)
                compare_col1.metric("Student Grade", student_grade)
                compare_col2.metric("Class Average", class_average)
                compare_col3.metric("Rank", f"{rank}/{total_students}")
                st.write(f"Remark: **{remark}**")

    with tab5:
        st.subheader("Passed vs Failed Summary")
        if selected_student == "All":
            st.info("Select a specific student to view the passed vs failed summary.")
        else:
            student_rows = df[df["student_id"] == selected_student]
            passed = int((student_rows["grade"] >= 75).sum())
            failed = int((student_rows["grade"] < 75).sum())
            remaining = int(student_rows["grade"].isna().sum())
            total = passed + failed + remaining
            if total == 0:
                st.info("No summary data is available for the selected student.")
            else:
                fig, ax = plt.subplots()
                ax.pie(
                    [passed, failed, remaining],
                    labels=["Passed", "Failed", "Remaining"],
                    autopct="%1.1f%%",
                    colors=["seagreen", "crimson", "gold"],
                    startangle=90,
                )
                ax.set_title("Passed vs Failed Summary")
                st.pyplot(fig)
                plt.close(fig)

                pass_col1, pass_col2, pass_col3 = st.columns(3)
                pass_col1.metric("Passed Subjects", passed)
                pass_col2.metric("Failed Subjects", failed)
                pass_col3.metric("Remaining Subjects", remaining)

    with tab6:
        st.subheader("Curriculum and Subject Viewer")
        if selected_student == "All":
            st.info("Select a specific student to view curriculum and subject progress.")
        else:
            student_rows = df[df["student_id"] == selected_student].copy()
            if student_rows.empty:
                st.info("No curriculum data is available for the selected student.")
            else:
                student_rows["Subject Status"] = student_rows["grade"].apply(
                    lambda value: "Completed" if pd.notna(value) and value >= 75 else (
                        "Ongoing" if pd.isna(value) else "Remaining"
                    )
                )

                completed = int((student_rows["Subject Status"] == "Completed").sum())
                ongoing = int((student_rows["Subject Status"] == "Ongoing").sum())
                remaining = int((student_rows["Subject Status"] == "Remaining").sum())
                passed_subjects = int((student_rows["grade"] >= 75).sum())
                failed_subjects = int((student_rows["grade"] < 75).sum())
                completed_rows = student_rows[student_rows["grade"].notna()]
                gpa = round(completed_rows["grade"].mean(), 2) if not completed_rows.empty else 0.0
                units_earned = 0

                curriculum_cols1, curriculum_cols2, curriculum_cols3, curriculum_cols4 = st.columns(4)
                curriculum_cols1.metric("GPA", gpa)
                curriculum_cols2.metric("Units Earned", units_earned)
                curriculum_cols3.metric("Passed Subjects", passed_subjects)
                curriculum_cols4.metric("Failed Subjects", failed_subjects)

                count_col1, count_col2, count_col3 = st.columns(3)
                count_col1.metric("Completed", completed)
                count_col2.metric("Ongoing", ongoing)
                count_col3.metric("Remaining", remaining)

                st.dataframe(
                    student_rows[["subject_code", "subject_name", "term", "grade", "Subject Status"]].rename(
                        columns={
                            "subject_code": "Subject Code",
                            "subject_name": "Subject Name",
                            "term": "Term",
                            "grade": "Grade",
                        }
                    ),
                    use_container_width=True,
                )

                st.caption("Units are shown as 0 because unit values are not present in the current database records.")
