import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from pages.dashboard_data import PASSING_GRADE, build_curriculum_progress, get_academic_records, get_term_filter_options

GRADE_LABELS = ["Below 60", "60-69", "70-79", "80-89", "90-100"]

STUDENT_FILTER_KEYS = [
    "students_student_search",
    "students_student_filter",
    "students_subject_filter",
    "students_section_filter",
    "students_term_filter",
]


def _filter_options(series: pd.Series):
    values = [value for value in series.dropna().astype(str).unique() if value.strip()]
    return ["All"] + sorted(values)


def _grade_ranges(grades: pd.Series):
    bins = [0, 59.99, 69.99, 79.99, 89.99, 100]
    return pd.cut(grades, bins=bins, labels=GRADE_LABELS, include_lowest=True)


def _student_display_map(df: pd.DataFrame):
    student_rows = (
        df[["student_id", "student_number", "student_name"]]
        .drop_duplicates()
        .sort_values(["student_name", "student_number"])
    )
    return {
        row["student_id"]: f"{row['student_name']} ({row['student_number']})"
        for _, row in student_rows.iterrows()
    }


def _student_options(student_map, search_text: str):
    normalized_search = search_text.strip().lower()
    student_ids = ["All"]
    for student_id, label in student_map.items():
        if not normalized_search or normalized_search in label.lower():
            student_ids.append(student_id)
    student_labels = {"All": "All Students"}
    student_labels.update(student_map)
    return student_ids, student_labels


def _reset_student_filters_for_user():
    current_scope = {
        "role": str(st.session_state.get("role") or "").strip().lower(),
        "username": str(st.session_state.get("username") or "").strip().lower(),
        "student_id": str(st.session_state.get("student_id") or "").strip(),
    }
    previous_scope = st.session_state.get("students_filter_scope")
    if previous_scope == current_scope:
        return

    for key in STUDENT_FILTER_KEYS:
        st.session_state.pop(key, None)
    st.session_state["students_filter_scope"] = current_scope


def _default_student_id(df: pd.DataFrame):
    linked_student_id = str(st.session_state.get("student_id") or "").strip()
    if linked_student_id:
        return linked_student_id

    username = str(st.session_state.get("username") or "").strip().lower()
    if not username:
        return "All"

    matches = df[
        (df["student_email"].fillna("").str.lower() == username) |
        (df["student_number"].fillna("").str.lower() == username)
    ]
    if matches.empty:
        return "All"
    return matches.iloc[0]["student_id"]


def _student_term_average(df: pd.DataFrame, student_id: str):
    student_rows = df[df["student_id"] == student_id]
    if student_rows.empty:
        return pd.DataFrame(columns=["Term", "GPA"])

    averages = (
        student_rows.groupby(["term", "school_year", "semester"], dropna=False)
        .agg(GPA=("grade", "mean"))
        .reset_index()
        .sort_values(["school_year", "semester"])
        .rename(columns={"term": "Term"})
    )
    averages["GPA"] = averages["GPA"].round(2)
    return averages[["Term", "GPA"]]


def _apply_filters(df: pd.DataFrame, student_id="All", subject_code="All", section="All", term="All"):
    filtered = df.copy()
    if student_id != "All":
        filtered = filtered[filtered["student_id"] == student_id]
    if subject_code != "All":
        filtered = filtered[filtered["subject_code"] == subject_code]
    if section != "All":
        filtered = filtered[filtered["section"] == section]
    if term != "All":
        filtered = filtered[filtered["term"] == term]
    return filtered


def _filter_progress_rows(
    progress_df: pd.DataFrame,
    subject_code="All",
    section="All",
    term="All",
    visible_subject_codes=None,
):
    filtered_progress = progress_df.copy()
    if subject_code != "All":
        filtered_progress = filtered_progress[filtered_progress["subject_code"] == subject_code]
    if term != "All":
        filtered_progress = filtered_progress[filtered_progress["term"] == term]
    if section != "All" and visible_subject_codes is not None:
        filtered_progress = filtered_progress[filtered_progress["subject_code"].isin(sorted(visible_subject_codes))]
    return filtered_progress


def show_students_dashboard():
    st.title("Students Dashboard Reports")
    st.caption("Student reports for subject performance, class comparison, and BSIT curriculum progress.")

    _reset_student_filters_for_user()

    df = get_academic_records()
    if df.empty:
        st.warning("No academic records were loaded from MongoDB Atlas.")
        return

    is_student_view = st.session_state.get("role") == "student"
    linked_student_id = str(st.session_state.get("student_id") or "").strip()
    if is_student_view:
        if not linked_student_id:
            st.error("This student account is not linked to a student record.")
            return
        df = df[df["student_id"].astype(str) == linked_student_id].copy()
        if df.empty:
            st.warning("No grade records were found for the linked student account.")
            return

    student_map = _student_display_map(df)
    default_student = (
        _default_student_id(df)
        if is_student_view
        else st.session_state.get("students_student_filter", "All")
    )
    search_value = st.session_state.get("students_student_search", "")
    student_ids, student_labels = _student_options(student_map, search_value)
    if default_student not in student_ids:
        default_student = "All"

    student_source = df if default_student == "All" else df[df["student_id"] == default_student]
    subject_options = _filter_options(student_source["subject_code"] if not student_source.empty else df["subject_code"])
    selected_subject = st.session_state.get("students_subject_filter", "All")
    if selected_subject not in subject_options:
        selected_subject = "All"

    section_source = student_source if selected_subject == "All" else student_source[student_source["subject_code"] == selected_subject]
    section_options = _filter_options(section_source["section"] if not section_source.empty else df["section"])
    selected_section = st.session_state.get("students_section_filter", "All")
    if selected_section not in section_options:
        selected_section = "All"

    term_source = section_source if selected_section == "All" else section_source[section_source["section"] == selected_section]
    term_options = get_term_filter_options(term_source["term"] if not term_source.empty else df["term"])
    selected_term = st.session_state.get("students_term_filter", "All")
    if selected_term not in term_options:
        selected_term = "All"

    with st.expander("Student Filters", expanded=True):
        filter_col1, filter_col2, filter_col3, filter_col4, filter_col5 = st.columns(5)
        if is_student_view:
            selected_student = linked_student_id
            student_label = student_map.get(selected_student, st.session_state.get("student_name") or selected_student)
            with filter_col1:
                st.text_input("Student", value=student_label, disabled=True)
        else:
            with filter_col1:
                search_value = st.text_input("Search Student", value=search_value, key="students_student_search")
            student_ids, student_labels = _student_options(student_map, search_value)
            if default_student not in student_ids:
                default_student = "All"
            with filter_col2:
                selected_student = st.selectbox(
                    "Student",
                    student_ids,
                    index=student_ids.index(default_student),
                    format_func=lambda value: student_labels[value],
                    key="students_student_filter",
                )

        student_source = df if selected_student == "All" else df[df["student_id"] == selected_student]
        subject_options = _filter_options(student_source["subject_code"] if not student_source.empty else df["subject_code"])
        if selected_subject not in subject_options:
            selected_subject = "All"
        with (filter_col2 if is_student_view else filter_col3):
            selected_subject = st.selectbox("Subject", subject_options, key="students_subject_filter")

        section_source = student_source if selected_subject == "All" else student_source[student_source["subject_code"] == selected_subject]
        section_options = _filter_options(section_source["section"] if not section_source.empty else df["section"])
        if selected_section not in section_options:
            selected_section = "All"
        with (filter_col3 if is_student_view else filter_col4):
            selected_section = st.selectbox("Section", section_options, key="students_section_filter")

        term_source = section_source if selected_section == "All" else section_source[section_source["section"] == selected_section]
        term_options = get_term_filter_options(term_source["term"] if not term_source.empty else df["term"])
        if selected_term not in term_options:
            selected_term = "All"
        with (filter_col4 if is_student_view else filter_col5):
            selected_term = st.selectbox("Term", term_options, key="students_term_filter")

    filtered = _apply_filters(
        df,
        student_id=selected_student,
        subject_code=selected_subject,
        section=selected_section,
        term=selected_term,
    )
    if filtered.empty:
        st.warning("No records match the selected student filters.")
        return

    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    metric_col1.metric("Grade Records", len(filtered))
    metric_col2.metric("Students", filtered["student_id"].nunique())
    metric_col3.metric("Subjects", filtered["subject_code"].nunique())
    metric_col4.metric("Sections", filtered["section"].nunique())

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
        [
            "1. Class Grade Distribution",
            "2. Performance Trend",
            "3. Subject Difficulty Ratings",
            "4. Class Average Comparison",
            "5. Passed vs Failed",
            "6. Curriculum Viewer",
        ]
    )

    with tab1:
        st.subheader("Class Grade Distribution (Histogram)")
        histogram_source = filtered.dropna(subset=["grade"]).copy()
        if selected_subject == "All" or selected_section == "All":
            st.info("Select a specific subject and section to view the class distribution.")
        elif histogram_source.empty:
            st.info("No grade data is available for the selected class.")
        else:
            histogram_source["Grade Range"] = _grade_ranges(histogram_source["grade"])
            distribution = histogram_source["Grade Range"].value_counts().reindex(GRADE_LABELS).fillna(0)
            fig, ax = plt.subplots()
            distribution.plot(kind="bar", ax=ax, color="#7fb3d5", edgecolor="black")
            ax.set_xlabel("Grade Range")
            ax.set_ylabel("Number of Students")
            ax.set_title("Grade Histogram")
            st.pyplot(fig)
            plt.close(fig)

    with tab2:
        st.subheader("Performance Trend Over Time")
        if selected_student == "All":
            st.info("Select a specific student to view GPA changes over time.")
        else:
            trend = _student_term_average(filtered, selected_student)
            if trend.empty:
                st.info("No GPA history is available for the selected student.")
            else:
                fig, ax = plt.subplots()
                ax.plot(trend["Term"], trend["GPA"], marker="o", linewidth=2, color="#117a65")
                ax.set_xlabel("Term")
                ax.set_ylabel("GPA")
                ax.set_title("GPA Trend Over Time")
                ax.tick_params(axis="x", rotation=25)
                st.pyplot(fig)
                plt.close(fig)
                st.dataframe(trend, use_container_width=True)

    with tab3:
        st.subheader("Subject Difficulty Ratings")
        if selected_subject == "All":
            st.info("Select a subject to analyze difficulty ratings.")
        else:
            difficulty_source = filtered.dropna(subset=["grade"]).copy()
            if difficulty_source.empty:
                st.info("No grade data is available for the selected subject.")
            else:
                difficulty_source["Grade Range"] = _grade_ranges(difficulty_source["grade"])
                percentages = difficulty_source["Grade Range"].value_counts(normalize=True).reindex(GRADE_LABELS).fillna(0).mul(100).round(1)
                difficulty_table = percentages.reset_index()
                difficulty_table.columns = ["Grade Range", "Percentage"]
                average_grade = round(difficulty_source["grade"].mean(), 2)
                if average_grade >= 85:
                    difficulty_level = "Low Difficulty"
                elif average_grade >= 70:
                    difficulty_level = "Medium Difficulty"
                else:
                    difficulty_level = "High Difficulty"

                info_col1, info_col2 = st.columns(2)
                info_col1.metric("Difficulty Level", difficulty_level)
                info_col2.metric("Average Grade", average_grade)
                st.dataframe(difficulty_table, use_container_width=True)

    with tab4:
        st.subheader("Comparison with Class Average")
        if selected_student == "All" or selected_subject == "All":
            st.info("Select a specific student and subject to compare against the class average.")
        else:
            class_rows = _apply_filters(
                df,
                subject_code=selected_subject,
                section=selected_section,
                term=selected_term,
            )

            student_subject_rows = class_rows[class_rows["student_id"] == selected_student].dropna(subset=["grade"])
            class_rows = class_rows.dropna(subset=["grade"])
            if student_subject_rows.empty or class_rows.empty:
                st.info("No comparison data is available for the selected student and subject.")
            else:
                student_grade = round(student_subject_rows["grade"].mean(), 2)
                student_rank_df = (
                    class_rows.groupby("student_id", dropna=False)
                    .agg(Student_Grade=("grade", "mean"))
                    .reset_index()
                    .sort_values("Student_Grade", ascending=False)
                    .reset_index(drop=True)
                )
                student_rank_df["Rank"] = student_rank_df.index + 1
                rank_row = student_rank_df[student_rank_df["student_id"] == selected_student].iloc[0]
                class_average = round(class_rows["grade"].mean(), 2)
                if student_grade > class_average:
                    remark = "Above Average"
                elif student_grade < class_average:
                    remark = "Below Average"
                else:
                    remark = "Average"

                compare_col1, compare_col2, compare_col3 = st.columns(3)
                compare_col1.metric("Student's Grade", student_grade)
                compare_col2.metric("Class Average", class_average)
                compare_col3.metric("Rank", f"{int(rank_row['Rank'])}/{len(student_rank_df)}")
                st.write(f"Remark: **{remark}**")

    with tab5:
        st.subheader("Passed vs Failed Summary")
        if selected_student == "All":
            st.info("Select a specific student to view the summary.")
        else:
            student_rows = filtered[filtered["student_id"] == selected_student].copy()
            program_code = student_rows["program_code"].iloc[0] if not student_rows.empty else "BSIT"
            progress_df = build_curriculum_progress(selected_student, program_code)
            progress_df = _filter_progress_rows(
                progress_df,
                subject_code=selected_subject,
                section=selected_section,
                term=selected_term,
                visible_subject_codes=set(student_rows["subject_code"].dropna().astype(str)),
            )
            passed_subjects = set(student_rows.loc[student_rows["grade"] >= PASSING_GRADE, "subject_code"])
            failed_subjects = set(student_rows.loc[student_rows["grade"] < PASSING_GRADE, "subject_code"]) - passed_subjects
            remaining = int((progress_df["subject_status"] == "Remaining").sum()) if not progress_df.empty else 0
            passed = len(passed_subjects)
            failed = len(failed_subjects)
            total = passed + failed + remaining

            if total == 0:
                st.info("No summary data is available for the selected student.")
            else:
                fig, ax = plt.subplots()
                ax.pie(
                    [passed, failed, remaining],
                    labels=["Passed", "Failed", "Remaining"],
                    autopct="%1.1f%%",
                    colors=["#239b56", "#cb4335", "#d4ac0d"],
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
            st.info("Select a specific student to view curriculum progress.")
        else:
            student_rows = filtered[filtered["student_id"] == selected_student].copy()
            if student_rows.empty:
                st.info("No curriculum data is available for the selected student.")
            else:
                program_code = student_rows["program_code"].iloc[0] or "BSIT"
                progress_df = build_curriculum_progress(selected_student, program_code)
                progress_df = _filter_progress_rows(
                    progress_df,
                    subject_code=selected_subject,
                    section=selected_section,
                    term=selected_term,
                    visible_subject_codes=set(student_rows["subject_code"].dropna().astype(str)),
                )
                if progress_df.empty:
                    st.info("No curriculum records are available for the selected program.")
                else:
                    completed = progress_df[progress_df["subject_status"] == "Completed"]
                    ongoing = progress_df[progress_df["subject_status"] == "Ongoing"]
                    remaining = progress_df[progress_df["subject_status"] == "Remaining"]
                    passed_subjects = int((student_rows["grade"] >= PASSING_GRADE).sum())
                    failed_subjects = int((student_rows["grade"] < PASSING_GRADE).sum())
                    completed_rows = student_rows[student_rows["grade"].notna()]
                    gpa = round(completed_rows["grade"].mean(), 2) if not completed_rows.empty else 0.0
                    units_earned = round(completed["units"].sum(), 1)

                    stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
                    stat_col1.metric("GPA", gpa)
                    stat_col2.metric("Units Earned", units_earned)
                    stat_col3.metric("Passed Subjects", passed_subjects)
                    stat_col4.metric("Failed Subjects", failed_subjects)

                    count_col1, count_col2, count_col3 = st.columns(3)
                    count_col1.metric("Completed", len(completed))
                    count_col2.metric("Ongoing", len(ongoing))
                    count_col3.metric("Remaining", len(remaining))

                    st.dataframe(
                        progress_df[["year_level", "semester", "subject_code", "subject_name", "units", "term", "grade", "subject_status"]].rename(
                            columns={
                                "year_level": "Year Level",
                                "semester": "Semester",
                                "subject_code": "Subject Code",
                                "subject_name": "Subject Name",
                                "units": "Units",
                                "term": "Term",
                                "grade": "Grade",
                                "subject_status": "Subject Status",
                            }
                        ),
                        use_container_width=True,
                    )