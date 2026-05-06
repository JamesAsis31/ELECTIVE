import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from pages.dashboard_data import PASSING_GRADE, get_academic_records, get_term_filter_options


def _filter_options(series: pd.Series):
    values = [value for value in series.dropna().astype(str).unique() if value.strip()]
    return ["All"] + sorted(values)


def _required_options(series: pd.Series):
    values = [value for value in series.dropna().astype(str).unique() if value.strip()]
    return sorted(values)


def _apply_filters(df: pd.DataFrame, term="All", subject_code="All", department="All"):
    filtered = df.copy()
    if term != "All":
        filtered = filtered[filtered["term"] == term]
    if subject_code != "All":
        filtered = filtered[filtered["subject_code"] == subject_code]
    if department != "All":
        filtered = filtered[filtered["program_code"] == department]
    return filtered


def _grade_distribution_histogram(values: pd.Series, title: str, x_label: str):
    fig, ax = plt.subplots()
    ax.hist(values.dropna(), bins=10, color="#5dade2", edgecolor="black")
    ax.set_xlabel(x_label)
    ax.set_ylabel("Number of Students")
    ax.set_title(title)
    st.pyplot(fig)
    plt.close(fig)


def _enrollment_trend(df: pd.DataFrame):
    rows = []
    previous_students = set()

    ordered_terms = (
        df[["term", "school_year", "semester"]]
        .drop_duplicates()
        .sort_values(["school_year", "semester"])
    )
    for _, term_row in ordered_terms.iterrows():
        term = term_row["term"]
        current_students = set(df.loc[df["term"] == term, "student_id"].dropna().unique())
        total_enrollment = len(current_students)
        new_enrollees = len(current_students - previous_students)
        dropouts = len(previous_students - current_students) if previous_students else 0
        retained = len(current_students & previous_students)
        retention_rate = round((retained / len(previous_students)) * 100, 1) if previous_students else 0.0
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


def show_registrar_dashboard():
    st.title("Registrar Dashboard Reports")
    st.caption("Registrar analytics for academic standing, term trends, and program performance.")

    df = get_academic_records()
    if df.empty:
        st.error("No academic records were loaded from MongoDB Atlas.")
        return

    term_options = get_term_filter_options(df["term"])
    selected_term = st.session_state.get("registrar_term_filter", "All")
    if selected_term not in term_options:
        selected_term = "All"

    subject_source = _apply_filters(df, term=selected_term)
    subject_options = _filter_options(subject_source["subject_code"])
    selected_subject = st.session_state.get("registrar_subject_filter", "All")
    if selected_subject not in subject_options:
        selected_subject = "All"

    department_source = _apply_filters(df, term=selected_term, subject_code=selected_subject)
    department_options = _filter_options(department_source["program_code"])
    selected_department = st.session_state.get("registrar_department_filter", "All")
    if selected_department not in department_options:
        selected_department = "All"

    with st.expander("Registrar Filters", expanded=True):
        filter_col1, filter_col2, filter_col3 = st.columns(3)
        with filter_col1:
            selected_term = st.selectbox("Term", term_options, key="registrar_term_filter")
        with filter_col2:
            selected_subject = st.selectbox("Subject Code", subject_options, key="registrar_subject_filter")
        with filter_col3:
            selected_department = st.selectbox("Department / Program", department_options, key="registrar_department_filter")

    filtered = _apply_filters(df, term=selected_term, subject_code=selected_subject, department=selected_department)
    if filtered.empty:
        st.warning("No records match the selected registrar filters.")
        return

    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    metric_col1.metric("Grade Records", len(filtered))
    metric_col2.metric("Students", filtered["student_id"].nunique())
    metric_col3.metric("Programs", filtered["program_code"].nunique())
    metric_col4.metric("Subjects", filtered["subject_code"].nunique())

    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
        [
            "1. Academic Standing",
            "2. Dean's List",
            "3. Probation",
            "4. Pass/Fail Distribution",
            "5. Enrollment Trend",
            "6. Top Performers",
            "7. Advising Analytics",
        ]
    )

    with tab1:
        st.subheader("Student Academic Standing Report")
        standing = (
            filtered.groupby(["student_number", "student_name"], dropna=False)
            .agg(GPA=("grade", "mean"), Total_Subjects=("subject_code", "count"))
            .reset_index()
        )
        standing["GPA"] = standing["GPA"].round(2)
        _grade_distribution_histogram(standing["GPA"], "GPA Distribution", "GPA Range")
        st.dataframe(
            standing.rename(columns={"student_number": "Student Number", "student_name": "Student Name"}),
            use_container_width=True,
        )

    with tab2:
        st.subheader("Dean's List Report")
        deans_list = (
            filtered.groupby(["student_number", "student_name", "term", "school_year", "semester"], dropna=False)
            .agg(GPA=("grade", "mean"), Total_Subjects=("subject_code", "count"))
            .reset_index()
            .sort_values(["school_year", "semester", "student_name"])
        )
        deans_list["GPA"] = deans_list["GPA"].round(2)
        deans_list = deans_list[deans_list["GPA"] >= 90]
        if deans_list.empty:
            st.info("No students meet the Dean's List threshold for the selected filters.")
        else:
            st.dataframe(
                deans_list[["student_number", "student_name", "term", "GPA", "Total_Subjects"]].rename(
                    columns={"student_number": "Student Number", "student_name": "Student Name", "term": "Term"}
                ),
                use_container_width=True,
            )

    with tab3:
        st.subheader("Probation Report")
        probation = (
            filtered.groupby(["student_number", "student_name", "term", "school_year", "semester"], dropna=False)
            .agg(
                GPA=("grade", "mean"),
                Total_Subjects=("subject_code", "count"),
                Fail_Count=("grade", lambda values: (values.dropna() < PASSING_GRADE).sum()),
            )
            .reset_index()
            .sort_values(["school_year", "semester", "student_name"])
        )
        probation["GPA"] = probation["GPA"].round(2)
        probation["Fail Percentage"] = probation.apply(
            lambda row: round((row["Fail_Count"] / row["Total_Subjects"]) * 100, 1) if row["Total_Subjects"] else 0.0,
            axis=1,
        )
        probation = probation[(probation["GPA"] <= PASSING_GRADE) | (probation["Fail Percentage"] >= 30)]
        if probation.empty:
            st.info("No students are on probation for the selected filters.")
        else:
            st.dataframe(
                probation[["student_number", "student_name", "term", "GPA", "Fail Percentage", "Total_Subjects"]].rename(
                    columns={"student_number": "Student Number", "student_name": "Student Name", "term": "Term"}
                ),
                use_container_width=True,
            )

    with tab4:
        st.subheader("Subject Pass/Fail Distribution")
        pass_fail = (
            filtered.groupby(["subject_code", "subject_name", "term"], dropna=False)
            .agg(
                Pass_Count=("grade", lambda values: (values.dropna() >= PASSING_GRADE).sum()),
                Fail_Count=("grade", lambda values: (values.dropna() < PASSING_GRADE).sum()),
                Total=("record_id", "count"),
            )
            .reset_index()
        )
        pass_fail["Pass %"] = pass_fail.apply(
            lambda row: round((row["Pass_Count"] / row["Total"]) * 100, 1) if row["Total"] else 0.0,
            axis=1,
        )
        pass_fail["Fail %"] = pass_fail.apply(
            lambda row: round((row["Fail_Count"] / row["Total"]) * 100, 1) if row["Total"] else 0.0,
            axis=1,
        )
        st.dataframe(
            pass_fail.rename(
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

    with tab5:
        st.subheader("Enrollment Trend Analysis")
        enrollment_trend = _enrollment_trend(filtered)
        if enrollment_trend.empty:
            st.info("Unable to compute enrollment trends from the selected data.")
        else:
            st.dataframe(enrollment_trend, use_container_width=True)
            st.line_chart(enrollment_trend.set_index("Semester")[["Total Enrollment"]])

    with tab6:
        st.subheader("Top Performers per Program")
        performers = filtered[filtered["program_code"].str.strip() != ""]
        if performers.empty:
            st.info("Program data is not available for top performer analysis.")
        else:
            top_performers = (
                performers.groupby(["program_code", "student_number", "student_name"], dropna=False)
                .agg(GPA=("grade", "mean"), Total_Subjects=("subject_code", "count"))
                .reset_index()
            )
            top_performers["GPA"] = top_performers["GPA"].round(2)
            top_performers = top_performers.sort_values(["program_code", "GPA"], ascending=[True, False])
            top_per_program = top_performers.groupby("program_code", as_index=False).head(10)
            st.dataframe(
                top_per_program.rename(
                    columns={
                        "program_code": "Program",
                        "student_number": "Student Number",
                        "student_name": "Student Name",
                    }
                ),
                use_container_width=True,
            )

    with tab7:
        st.subheader("Curriculum Progress and Advising")
        teacher_options = _required_options(filtered["teacher_name"])
        if not teacher_options:
            st.info("No teacher records are available for advising analytics.")
        else:
            advising_col1, advising_col2 = st.columns(2)
            with advising_col1:
                selected_teacher = st.selectbox("Selected Teacher", teacher_options, key="registrar_advising_teacher")
            subject_options = _required_options(filtered[filtered["teacher_name"] == selected_teacher]["subject_code"])
            if not subject_options:
                st.info("No subjects are available for the selected teacher.")
            else:
                with advising_col2:
                    selected_advising_subject = st.selectbox("Selected Subject", subject_options, key="registrar_advising_subject")

                advising = filtered[
                    (filtered["teacher_name"] == selected_teacher) &
                    (filtered["subject_code"] == selected_advising_subject)
                ].dropna(subset=["grade"])
                if advising.empty:
                    st.info("No advising records match the selected teacher and subject.")
                else:
                    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
                    metric_col1.metric("Mean Grade", round(advising["grade"].mean(), 2))
                    metric_col2.metric("Median Grade", round(advising["grade"].median(), 2))
                    metric_col3.metric("Highest Grade", round(advising["grade"].max(), 2))
                    metric_col4.metric("Lowest Grade", round(advising["grade"].min(), 2))

                    chart_col1, chart_col2 = st.columns(2)
                    with chart_col1:
                        fig, ax = plt.subplots()
                        ax.hist(advising["grade"], bins=[0, 75, 80, 85, 90, 95, 100], color="#2874a6", edgecolor="black")
                        ax.set_title("Grade Distribution")
                        ax.set_xlabel("Grade Range")
                        ax.set_ylabel("Number of Students")
                        st.pyplot(fig)
                        plt.close(fig)
                    with chart_col2:
                        pass_count = int((advising["grade"] >= PASSING_GRADE).sum())
                        fail_count = int((advising["grade"] < PASSING_GRADE).sum())
                        fig, ax = plt.subplots()
                        bars = ax.bar(["Pass", "Fail"], [pass_count, fail_count], color=["#239b56", "#cb4335"])
                        ax.set_title("Pass vs Fail")
                        ax.set_ylabel("Number of Students")
                        for bar in bars:
                            ax.text(bar.get_x() + (bar.get_width() / 2), bar.get_height(), str(int(bar.get_height())), ha="center", va="bottom")
                        st.pyplot(fig)
                        plt.close(fig)

                    advising_table = advising.copy()
                    advising_table["Next Level"] = ""
                    advising_table["Pass/Fail Status"] = advising_table["grade"].apply(
                        lambda value: "Pass" if value >= PASSING_GRADE else "Fail"
                    )
                    st.dataframe(
                        advising_table[["student_number", "student_name", "program_code", "Next Level", "grade", "Pass/Fail Status"]].rename(
                            columns={
                                "student_number": "Student ID",
                                "student_name": "Student Name",
                                "program_code": "Course",
                                "grade": "Grade",
                            }
                        ),
                        use_container_width=True,
                    )