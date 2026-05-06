import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from pages.dashboard_data import PASSING_GRADE, get_academic_records, get_term_filter_options

GRADE_RANGE_ORDER = ["Below 75", "75-79", "80-84", "85-89", "90-94", "95-100"]


def _filter_options(series: pd.Series):
    values = [value for value in series.dropna().astype(str).unique() if value.strip()]
    return ["All"] + sorted(values)


def _required_options(series: pd.Series):
    values = [value for value in series.dropna().astype(str).unique() if value.strip()]
    return sorted(values)


def _apply_filters(df: pd.DataFrame, teacher="All", subject_code="All", term="All", program="All"):
    filtered = df.copy()
    if teacher != "All":
        filtered = filtered[filtered["teacher_name"] == teacher]
    if subject_code != "All":
        filtered = filtered[filtered["subject_code"] == subject_code]
    if term != "All":
        filtered = filtered[filtered["term"] == term]
    if program != "All":
        filtered = filtered[filtered["program_code"] == program]
    return filtered


def _grade_bucket_series(grades: pd.Series):
    bins = [0, 74.99, 79.99, 84.99, 89.99, 94.99, 100]
    return pd.cut(grades, bins=bins, labels=GRADE_RANGE_ORDER, include_lowest=True)


def _difficulty_label(fail_rate: float, dropout_rate: float):
    score = max(fail_rate, dropout_rate)
    if score >= 40:
        return "High Difficulty"
    if score >= 20:
        return "Medium Difficulty"
    return "Low Difficulty"


def _difficulty_style(row):
    return ["background-color: transparent; color: #ffffff"] * len(row)


def _distribution_table(df: pd.DataFrame):
    if df.empty:
        return pd.DataFrame(columns=["Grade Range", "Students", "Percentage"])
    bucketed = df.copy()
    bucketed["Grade Range"] = _grade_bucket_series(bucketed["grade"])
    distribution = bucketed["Grade Range"].value_counts().reindex(GRADE_RANGE_ORDER).fillna(0)
    table = distribution.reset_index()
    table.columns = ["Grade Range", "Students"]
    total = int(table["Students"].sum())
    table["Percentage"] = table["Students"].apply(lambda value: round((value / total) * 100, 1) if total else 0.0)
    return table


def show_faculty_dashboard():
    st.title("Faculty Dashboard Reports")
    st.caption("BSIT grade analytics for class monitoring, intervention, and submission tracking.")

    df = get_academic_records()
    if df.empty:
        st.warning("No academic records were loaded from MongoDB Atlas.")
        return

    teacher_options = _filter_options(df["teacher_name"])
    selected_teacher = st.session_state.get("faculty_teacher_filter", "All")
    if selected_teacher not in teacher_options:
        selected_teacher = "All"

    subject_source = _apply_filters(df, teacher=selected_teacher)
    subject_options = _filter_options(subject_source["subject_code"])
    selected_subject = st.session_state.get("faculty_subject_filter", "All")
    if selected_subject not in subject_options:
        selected_subject = "All"

    term_source = _apply_filters(df, teacher=selected_teacher, subject_code=selected_subject)
    term_options = get_term_filter_options(term_source["term"])
    selected_term = st.session_state.get("faculty_term_filter", "All")
    if selected_term not in term_options:
        selected_term = "All"

    program_source = _apply_filters(df, teacher=selected_teacher, subject_code=selected_subject, term=selected_term)
    program_options = _filter_options(program_source["program_code"])
    selected_program = st.session_state.get("faculty_program_filter", "All")
    if selected_program not in program_options:
        selected_program = "All"

    with st.expander("Faculty Filters", expanded=True):
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
        st.warning("No records match the selected faculty filters.")
        return

    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    metric_col1.metric("Grade Records", len(filtered))
    metric_col2.metric("Students", filtered["student_id"].nunique())
    metric_col3.metric("Subjects", filtered["subject_code"].nunique())
    metric_col4.metric("Avg Grade", round(filtered["grade"].dropna().mean(), 2) if filtered["grade"].notna().any() else "N/A")

    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
        [
            "1. Class Grade Distribution",
            "2. Student Progress Tracker",
            "3. Subject Difficulty Heatmap",
            "4. Intervention Candidates",
            "5. Grade Submission Status",
            "6. Custom Query Builder",
            "7. Students Grade Analytics",
        ]
    )

    with tab1:
        st.subheader("Class Grade Distribution")
        class_data = filtered.dropna(subset=["grade"]).copy()
        if class_data.empty:
            st.info("No numeric grades are available for the selected class.")
        else:
            summary_table = _distribution_table(class_data)
            st.dataframe(summary_table, use_container_width=True)

            fig, ax = plt.subplots()
            ax.hist(class_data["grade"], bins=[0, 75, 80, 85, 90, 95, 100], color="#1f77b4", edgecolor="black")
            ax.set_xlabel("Grade Range")
            ax.set_ylabel("Number of Students")
            ax.set_title("Grade Histogram")
            st.pyplot(fig)
            plt.close(fig)

    with tab2:
        st.subheader("Student Progress Tracker")
        progress_source = _apply_filters(df, teacher=selected_teacher, subject_code=selected_subject, program=selected_program)
        progress = (
            progress_source.groupby(["student_id", "student_name", "term", "school_year", "semester"], dropna=False)
            .agg(GPA=("grade", "mean"))
            .reset_index()
            .sort_values(["school_year", "semester", "student_name"])
        )
        progress["GPA"] = progress["GPA"].round(2)
        if progress.empty:
            st.info("No student progress records are available for the selected filters.")
        else:
            chart_progress = progress.copy()
            student_count = chart_progress["student_name"].nunique()
            if student_count > 12:
                top_students = (
                    chart_progress.groupby("student_name", dropna=False)
                    .agg(Latest_GPA=("GPA", "last"))
                    .sort_values("Latest_GPA", ascending=False)
                    .head(12)
                    .index
                )
                chart_progress = chart_progress[chart_progress["student_name"].isin(top_students)]
                st.caption("Showing 12 student trend lines to keep the chart readable.")

            progress_pivot = chart_progress.pivot(index="term", columns="student_name", values="GPA")
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
                Fail_Rate=("grade", lambda values: round((values.dropna() < PASSING_GRADE).mean() * 100, 1) if len(values.dropna()) else 0.0),
                Dropout_Rate=("dropout_flag", lambda values: round(values.mean() * 100, 1) if len(values) else 0.0),
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
            st.dataframe(difficulty.style.apply(_difficulty_style, axis=1), use_container_width=True)

            fig, ax = plt.subplots(figsize=(7, max(3, len(difficulty) * 0.45)))
            heatmap = difficulty[["Fail_Rate", "Dropout_Rate"]].to_numpy()
            image = ax.imshow(heatmap, cmap="YlOrRd", aspect="auto")
            ax.set_yticks(range(len(difficulty)))
            ax.set_yticklabels(difficulty["subject_code"])
            ax.set_xticks([0, 1])
            ax.set_xticklabels(["Fail Rate %", "Dropout Rate %"])
            ax.set_title("Difficulty Heatmap")
            for row_index in range(len(difficulty)):
                for column_index in range(2):
                    ax.text(column_index, row_index, f"{heatmap[row_index, column_index]:.1f}%", ha="center", va="center")
            fig.colorbar(image, ax=ax)
            st.pyplot(fig)
            plt.close(fig)

    with tab4:
        st.subheader("Intervention Candidates List")
        candidates = filtered[filtered["grade"].isna() | (filtered["grade"] < PASSING_GRADE)].copy()
        if candidates.empty:
            st.success("No at-risk students were found for the selected filters.")
        else:
            candidates["Risk Flag"] = candidates["grade"].apply(
                lambda value: "Missing Grade" if pd.isna(value) else "Low Grade"
            )
            st.dataframe(
                candidates[["student_number", "student_name", "subject_code", "subject_name", "grade", "Risk Flag"]].rename(
                    columns={
                        "student_number": "Student ID",
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
            submission_source.groupby(["subject_code", "subject_name", "teacher_name"], dropna=False)
            .agg(
                Number_of_Students=("student_id", "nunique"),
                Submitted_Grades=("grade_submitted", "sum"),
                Total_Records=("record_id", "count"),
            )
            .reset_index()
        )
        if submission.empty:
            st.info("No grade submission records are available for the selected filters.")
        else:
            submission["Submission Percentage"] = submission.apply(
                lambda row: round((row["Submitted_Grades"] / row["Total_Records"]) * 100, 1) if row["Total_Records"] else 0.0,
                axis=1,
            )
            submission["Submission Status"] = submission["Submission Percentage"].apply(
                lambda value: "Complete" if value >= 100 else ("Partial" if value > 0 else "Not Started")
            )
            st.dataframe(
                submission[["subject_code", "teacher_name", "Number_of_Students", "Submission Status", "Submission Percentage"]].rename(
                    columns={
                        "subject_code": "Subject",
                        "teacher_name": "Instructor",
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
            query_term = st.selectbox("Term", get_term_filter_options(df["term"]), key="faculty_query_term")
        with query_col2:
            query_program = st.selectbox("Program", _filter_options(df["program_code"]), key="faculty_query_program")
            query_teacher = st.selectbox("Teacher", _filter_options(df["teacher_name"]), key="faculty_query_teacher")

        query_result = _apply_filters(
            df,
            teacher=query_teacher,
            subject_code=query_subject,
            term=query_term,
            program=query_program,
        )
        st.write(f"Matching records: {len(query_result)}")
        st.dataframe(
            query_result[["student_number", "student_name", "subject_code", "subject_name", "teacher_name", "term", "program_code", "grade", "pass_fail"]].rename(
                columns={
                    "student_number": "Student ID",
                    "student_name": "Student Name",
                    "subject_code": "Subject Code",
                    "subject_name": "Subject Name",
                    "teacher_name": "Teacher",
                    "term": "Term",
                    "program_code": "Program",
                    "grade": "Grade",
                    "pass_fail": "Pass/Fail",
                }
            ),
            use_container_width=True,
        )

    with tab7:
        st.subheader("Students Grade Analytics (Per Teacher)")
        analytics_teachers = _required_options(filtered["teacher_name"])
        if not analytics_teachers:
            st.info("No teacher records are available for analytics.")
        else:
            analytics_teacher = st.selectbox("Teacher for Analytics", analytics_teachers, key="faculty_analytics_teacher")
            analytics_subjects = _required_options(filtered[filtered["teacher_name"] == analytics_teacher]["subject_code"])
            if not analytics_subjects:
                st.info("No subjects are available for the selected teacher.")
            else:
                analytics_subject = st.selectbox("Subject for Analytics", analytics_subjects, key="faculty_analytics_subject")
                analytics_df = filtered[
                    (filtered["teacher_name"] == analytics_teacher) &
                    (filtered["subject_code"] == analytics_subject)
                ].dropna(subset=["grade"])

                if analytics_df.empty:
                    st.info("No analytics records match the selected teacher and subject.")
                else:
                    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
                    metric_col1.metric("Mean Grade", round(analytics_df["grade"].mean(), 2))
                    metric_col2.metric("Median Grade", round(analytics_df["grade"].median(), 2))
                    metric_col3.metric("Highest Grade", round(analytics_df["grade"].max(), 2))
                    metric_col4.metric("Lowest Grade", round(analytics_df["grade"].min(), 2))

                    distribution = _distribution_table(analytics_df)
                    chart_col1, chart_col2 = st.columns(2)
                    with chart_col1:
                        fig, ax = plt.subplots()
                        ax.bar(distribution["Grade Range"], distribution["Students"], color="#2a9d8f", edgecolor="black")
                        ax.set_title("Grade Distribution")
                        ax.set_xlabel("Grade Range")
                        ax.set_ylabel("Number of Students")
                        ax.tick_params(axis="x", rotation=35)
                        st.pyplot(fig)
                        plt.close(fig)
                    with chart_col2:
                        pass_count = int((analytics_df["grade"] >= PASSING_GRADE).sum())
                        fail_count = int((analytics_df["grade"] < PASSING_GRADE).sum())
                        fig, ax = plt.subplots()
                        bars = ax.bar(["Pass", "Fail"], [pass_count, fail_count], color=["#2e8b57", "#c0392b"])
                        ax.set_title("Pass vs Fail")
                        ax.set_ylabel("Number of Students")
                        for bar in bars:
                            ax.text(bar.get_x() + (bar.get_width() / 2), bar.get_height(), str(int(bar.get_height())), ha="center", va="bottom")
                        st.pyplot(fig)
                        plt.close(fig)

                    analytics_table = analytics_df.copy()
                    analytics_table["Next Level"] = ""
                    analytics_table["Pass/Fail Status"] = analytics_table["grade"].apply(
                        lambda value: "Pass" if value >= PASSING_GRADE else "Fail"
                    )
                    st.dataframe(
                        analytics_table[["student_number", "student_name", "subject_code", "Next Level", "grade", "Pass/Fail Status"]].rename(
                            columns={
                                "student_number": "Student ID",
                                "student_name": "Student Name",
                                "subject_code": "Course",
                                "grade": "Grade",
                            }
                        ),
                        use_container_width=True,
                    )