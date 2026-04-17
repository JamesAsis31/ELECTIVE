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
def build_faculty_dataframe():
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

    if "teacher" in df.columns:
        df["teacher"] = df["teacher"].fillna("").astype(str).str.strip()
    else:
        df["teacher"] = ""
    if "term" in df.columns:
        df["term"] = df["term"].fillna("").astype(str).str.strip().map(_normalize_term_label)
    else:
        df["term"] = ""
    if "status" in df.columns:
        df["status"] = df["status"].fillna("").astype(str).str.strip()
    else:
        df["status"] = ""

    df["student_name"] = df["student_name"].fillna("Unknown").replace("", "Unknown")
    df["program"] = df["program"].fillna("").astype(str).str.strip()
    df["pass_fail"] = df["grade"].apply(lambda value: "Pass" if pd.notna(value) and value >= 75 else "Fail")
    df["grade_submitted"] = df["grade"].notna()

    return df


def _filter_options(series: pd.Series):
    values = [value for value in series.dropna().astype(str).unique() if value.strip()]
    return ["All"] + sorted(values)


def _apply_filters(df: pd.DataFrame, teacher="All", subject_code="All", term="All", program="All") -> pd.DataFrame:
    filtered = df.copy()
    if teacher != "All":
        filtered = filtered[filtered["teacher"] == teacher]
    if subject_code != "All":
        filtered = filtered[filtered["subject_code"] == subject_code]
    if term != "All":
        filtered = filtered[filtered["term"] == term]
    if program != "All":
        filtered = filtered[filtered["program"] == program]
    return filtered


def _grade_bucket_series(grades: pd.Series) -> pd.Series:
    bins = [0, 74.99, 79.99, 84.99, 89.99, 94.99, 100]
    labels = ["Below 75", "75-79", "80-84", "85-89", "90-94", "95-100"]
    return pd.cut(grades, bins=bins, labels=labels, include_lowest=True)


def _difficulty_label(fail_rate: float, dropout_rate: float) -> str:
    score = max(fail_rate, dropout_rate)
    if score >= 40:
        return "High Difficulty"
    if score >= 20:
        return "Medium Difficulty"
    return "Low Difficulty"


def show_faculty_dashboard():
    st.title("Faculty Dashboard Reports")
    st.caption("Faculty analytics with linked filters and report tabs for faster navigation.")

    df = build_faculty_dataframe()
    if df.empty:
        st.warning("No grade data was loaded from MongoDB.")
        return

    teacher_options = _filter_options(df["teacher"])
    selected_teacher = st.session_state.get("faculty_teacher_filter", "All")
    if selected_teacher not in teacher_options:
        selected_teacher = "All"

    subject_source = _apply_filters(df, teacher=selected_teacher)
    subject_options = _filter_options(subject_source["subject_code"])
    selected_subject = st.session_state.get("faculty_subject_filter", "All")
    if selected_subject not in subject_options:
        selected_subject = "All"

    term_source = _apply_filters(df, teacher=selected_teacher, subject_code=selected_subject)
    term_options = _filter_options(term_source["term"])
    selected_term = st.session_state.get("faculty_term_filter", "All")
    if selected_term not in term_options:
        selected_term = "All"

    program_source = _apply_filters(df, teacher=selected_teacher, subject_code=selected_subject, term=selected_term)
    program_options = _filter_options(program_source["program"])
    selected_program = st.session_state.get("faculty_program_filter", "All")
    if selected_program not in program_options:
        selected_program = "All"

    filter_col1, filter_col2, filter_col3, filter_col4 = st.columns(4)
    with filter_col1:
        selected_teacher = st.selectbox("Teacher", teacher_options, key="faculty_teacher_filter")
    with filter_col2:
        selected_subject = st.selectbox("Subject", subject_options, key="faculty_subject_filter")
    with filter_col3:
        selected_term = st.selectbox("Term", term_options, key="faculty_term_filter")
    with filter_col4:
        selected_program = st.selectbox("Program", program_options, key="faculty_program_filter")

    filtered = _apply_filters(
        df,
        teacher=selected_teacher,
        subject_code=selected_subject,
        term=selected_term,
        program=selected_program,
    )
    if filtered.empty:
        st.warning("No matching grade records were found for the selected filters.")
        return

    summary_col1, summary_col2, summary_col3, summary_col4 = st.columns(4)
    summary_col1.metric("Filtered Records", len(filtered))
    summary_col2.metric("Students", filtered["student_id"].nunique())
    summary_col3.metric("Subjects", filtered["subject_code"].nunique())
    summary_col4.metric("Teachers", filtered["teacher"].nunique())

    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
        [
            "1. Grade Distribution",
            "2. Progress Tracker",
            "3. Difficulty",
            "4. Intervention",
            "5. Submission Status",
            "6. Custom Query",
            "7. Teacher Analytics",
        ]
    )

    with tab1:
        st.subheader("Class Grade Distribution")
        class_data = filtered.dropna(subset=["grade"]).copy()
        if class_data.empty:
            st.info("No numeric grades are available for the selected class.")
        else:
            class_data["Grade Range"] = _grade_bucket_series(class_data["grade"])
            distribution = class_data["Grade Range"].value_counts().reindex(
                ["Below 75", "75-79", "80-84", "85-89", "90-94", "95-100"]
            ).fillna(0)
            summary_table = distribution.reset_index()
            summary_table.columns = ["Grade Range", "Students"]
            total_students = int(summary_table["Students"].sum())
            summary_table["Percentage"] = summary_table["Students"].apply(
                lambda count: round((count / total_students) * 100, 1) if total_students else 0
            )
            st.dataframe(summary_table, use_container_width=True)

            fig, ax = plt.subplots()
            ax.hist(class_data["grade"], bins=[0, 75, 80, 85, 90, 95, 100], color="steelblue", edgecolor="black")
            ax.set_title("Grade Histogram")
            ax.set_xlabel("Grade Range")
            ax.set_ylabel("Number of Students")
            st.pyplot(fig)
            plt.close(fig)

    with tab2:
        st.subheader("Student Progress Tracker")
        progress_source = _apply_filters(df, teacher=selected_teacher, subject_code=selected_subject, program=selected_program)
        progress = (
            progress_source.groupby(["student_id", "student_name", "term"], dropna=False)
            .agg(GPA=("grade", "mean"))
            .reset_index()
        )
        progress["GPA"] = progress["GPA"].round(2)
        if progress.empty:
            st.info("No student progress records are available for the selected filters.")
        else:
            progress_pivot = progress.pivot(index="term", columns="student_name", values="GPA")
            st.line_chart(progress_pivot)
            st.dataframe(
                progress[["student_id", "student_name", "term", "GPA"]].rename(
                    columns={"student_id": "Student ID", "student_name": "Student Name", "term": "Term"}
                ),
                use_container_width=True,
            )

    with tab3:
        st.subheader("Subject Difficulty Heatmap")
        difficulty_source = _apply_filters(df, teacher=selected_teacher, term=selected_term, program=selected_program)
        difficulty = (
            difficulty_source.groupby(["subject_code", "subject_name"], dropna=False)
            .agg(
                Fail_Rate=("grade", lambda values: round((values < 75).sum() / len(values) * 100, 1) if len(values) else 0),
                Dropout_Rate=("status", lambda values: round(values.str.contains("drop", case=False, na=False).sum() / len(values) * 100, 1) if len(values) else 0),
                Students=("student_id", "nunique"),
            )
            .reset_index()
        )
        if difficulty.empty:
            st.info("No subject difficulty records are available for the selected filters.")
        else:
            difficulty["Difficulty"] = difficulty.apply(
                lambda row: _difficulty_label(row["Fail_Rate"], row["Dropout_Rate"]), axis=1
            )
            st.dataframe(
                difficulty.style.set_properties(**{"color": "white"}),
                use_container_width=True,
            )

            fig, ax = plt.subplots(figsize=(7, max(3, len(difficulty) * 0.45)))
            heatmap = difficulty[["Fail_Rate", "Dropout_Rate"]].to_numpy()
            image = ax.imshow(heatmap, cmap="YlOrRd", aspect="auto")
            ax.set_yticks(range(len(difficulty)))
            ax.set_yticklabels(difficulty["subject_code"])
            ax.set_xticks([0, 1])
            ax.set_xticklabels(["Fail Rate %", "Dropout Rate %"])
            ax.set_title("Subject Difficulty Heatmap")
            for row_index in range(len(difficulty)):
                for column_index in range(2):
                    ax.text(column_index, row_index, f"{heatmap[row_index, column_index]:.1f}%", ha="center", va="center")
            fig.colorbar(image, ax=ax)
            st.pyplot(fig)
            plt.close(fig)

    with tab4:
        st.subheader("Intervention Candidates List")
        candidates = filtered[filtered["grade"].isna() | (filtered["grade"] < 75)].copy()
        if candidates.empty:
            st.success("No intervention candidates were found for the selected filters.")
        else:
            candidates["Risk Flag"] = candidates["grade"].apply(
                lambda value: "Missing Grade" if pd.isna(value) else "Low Grade"
            )
            st.dataframe(
                candidates[["student_id", "student_name", "subject_code", "subject_name", "grade", "Risk Flag"]].rename(
                    columns={
                        "student_id": "Student ID",
                        "student_name": "Student Name",
                        "subject_code": "Subject",
                        "subject_name": "Subject Name",
                        "grade": "Current Grade",
                    }
                ),
                use_container_width=True,
            )

    with tab5:
        st.subheader("Grade Submission Status")
        submission_source = _apply_filters(df, teacher=selected_teacher, subject_code=selected_subject, term=selected_term, program=selected_program)
        submission = (
            submission_source.groupby(["subject_code", "teacher"], dropna=False)
            .agg(
                Number_of_Students=("student_id", "nunique"),
                Submitted_Grades=("grade_submitted", "sum"),
                Total_Records=("student_id", "count"),
            )
            .reset_index()
        )
        if submission.empty:
            st.info("No grade submission records are available for the selected filters.")
        else:
            submission["Submission Percentage"] = submission.apply(
                lambda row: round((row["Submitted_Grades"] / row["Total_Records"]) * 100, 1) if row["Total_Records"] else 0,
                axis=1,
            )
            submission["Submission Status"] = submission["Submission Percentage"].apply(
                lambda value: "Complete" if value >= 100 else ("Partial" if value > 0 else "Not Started")
            )
            st.dataframe(
                submission[["subject_code", "teacher", "Number_of_Students", "Submission Status", "Submission Percentage"]].rename(
                    columns={
                        "subject_code": "Subject",
                        "teacher": "Instructor",
                        "Number_of_Students": "Number of Students",
                        "Submission Percentage": "Submission %",
                    }
                ),
                use_container_width=True,
            )

    with tab6:
        st.subheader("Custom Query Builder")
        query_col1, query_col2 = st.columns(2)
        with query_col1:
            query_subject = st.selectbox("Subject", _filter_options(df["subject_code"]), key="faculty_query_subject")
            query_term = st.selectbox("Term", _filter_options(df["term"]), key="faculty_query_term")
        with query_col2:
            query_program = st.selectbox("Program", _filter_options(df["program"]), key="faculty_query_program")
            query_teacher = st.selectbox("Teacher", _filter_options(df["teacher"]), key="faculty_query_teacher")

        query_result = _apply_filters(
            df,
            teacher=query_teacher,
            subject_code=query_subject,
            term=query_term,
            program=query_program,
        )
        st.write(f"Matching records: {len(query_result)}")
        st.dataframe(
            query_result[["student_id", "student_name", "subject_code", "subject_name", "teacher", "term", "program", "grade", "pass_fail"]].rename(
                columns={
                    "student_id": "Student ID",
                    "student_name": "Student Name",
                    "subject_code": "Subject Code",
                    "subject_name": "Subject Name",
                    "teacher": "Teacher",
                    "term": "Term",
                    "program": "Program",
                    "grade": "Grade",
                    "pass_fail": "Pass/Fail",
                }
            ),
            use_container_width=True,
        )

    with tab7:
        st.subheader("Students Grade Analytics (Per Teacher)")
        analytics_teacher_options = _filter_options(df["teacher"])
        analytics_teacher = st.selectbox("Teacher for Analytics", analytics_teacher_options, key="faculty_analytics_teacher")
        analytics_subject_source = _apply_filters(df, teacher=analytics_teacher)
        analytics_subject_options = _filter_options(analytics_subject_source["subject_code"])
        analytics_subject = st.selectbox("Subject for Analytics", analytics_subject_options, key="faculty_analytics_subject")

        analytics_df = _apply_filters(df, teacher=analytics_teacher, subject_code=analytics_subject)
        if analytics_df.empty:
            st.info("No analytics records match the selected teacher and subject.")
        else:
            metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
            metric_col1.metric("Mean Grade", round(analytics_df["grade"].mean(), 2))
            metric_col2.metric("Median Grade", round(analytics_df["grade"].median(), 2))
            metric_col3.metric("Highest Grade", round(analytics_df["grade"].max(), 2))
            metric_col4.metric("Lowest Grade", round(analytics_df["grade"].min(), 2))

            analytics_chart = analytics_df.dropna(subset=["grade"]).copy()
            analytics_chart["Grade Range"] = _grade_bucket_series(analytics_chart["grade"])
            distribution = analytics_chart["Grade Range"].value_counts().reindex(
                ["Below 75", "75-79", "80-84", "85-89", "90-94", "95-100"]
            ).fillna(0)
            fig, ax = plt.subplots()
            distribution.plot(kind="bar", ax=ax, color="teal", edgecolor="black")
            ax.set_title("Grade Distribution")
            ax.set_xlabel("Grade Range")
            ax.set_ylabel("Number of Students")
            st.pyplot(fig)
            plt.close(fig)

            pass_count = int((analytics_df["grade"] >= 75).sum())
            fail_count = int((analytics_df["grade"] < 75).sum())
            fig, ax = plt.subplots()
            bars = ax.bar(["Pass", "Fail"], [pass_count, fail_count], color=["seagreen", "crimson"])
            ax.set_title("Pass vs Fail")
            ax.set_ylabel("Number of Students")
            for bar in bars:
                ax.text(bar.get_x() + (bar.get_width() / 2), bar.get_height(), str(int(bar.get_height())), ha="center", va="bottom")
            st.pyplot(fig)
            plt.close(fig)
            st.write(f"Pass: {pass_count} | Fail: {fail_count}")

            analytics_table = analytics_df.copy()
            analytics_table["Pass/Fail Status"] = analytics_table["grade"].apply(
                lambda value: "Pass" if pd.notna(value) and value >= 75 else "Fail"
            )
            analytics_table["Next Level"] = ""
            st.dataframe(
                analytics_table[["student_id", "student_name", "subject_code", "Next Level", "grade", "Pass/Fail Status"]].rename(
                    columns={
                        "student_id": "Student ID",
                        "student_name": "Student Name",
                        "subject_code": "Course",
                        "grade": "Grade",
                    }
                ),
                use_container_width=True,
            )
