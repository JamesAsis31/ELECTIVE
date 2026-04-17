import pandas as pd
import numpy as np

np.random.seed(42)
teachers = ['Teacher A', 'Teacher B', 'Teacher C']
subjects = ['MATH101', 'ENG102', 'SCI103', 'HIST104', 'ART105']
terms = ['2023-1', '2023-2', '2024-1', '2024-2']
programs = ['Computer Science', 'Engineering', 'Business', 'Arts']

rows = []
for i in range(200):
    student_num = f'STUD{i:03d}'
    name = f'Student {i+1}'
    program = np.random.choice(programs)
    for term in terms:
        teacher = np.random.choice(teachers)
        subject = np.random.choice(subjects)
        grade = np.random.normal(80, 15)
        grade = max(40, min(100, grade))
        if np.random.rand() < 0.05:
            grade = np.nan
        dropped = np.random.rand() < 0.05
        rows.append({
            'Student ID': student_num,
            'Student Name': name,
            'Program': program,
            'Teacher': teacher,
            'Subject Code': subject,
            'Term': term,
            'Grade': grade,
            'Dropped': dropped
        })


df = pd.DataFrame(rows)

filtered = df.copy()

# 1. Grade distribution summary

grade_data = filtered.dropna(subset=['Grade'])
bins = [0, 75, 80, 85, 90, 95, 100]
labels = ['Below 75', '75–79', '80–84', '85–89', '90–94', '95–100']

grade_data['Range'] = pd.cut(grade_data['Grade'], bins=bins, labels=labels, include_lowest=True)
summary = grade_data['Range'].value_counts(normalize=True).reindex(labels).fillna(0) * 100
print('summary type:', type(summary))
print(summary.head())

summary = summary.reset_index().rename(columns={'index': 'Grade Range', 'Range': 'Percent'})
print('after reset:', summary.head())
print('cols:', summary.columns)

summary['Percent'] = pd.to_numeric(summary['Percent'], errors='coerce').fillna(0)
summary['Percent Display'] = summary['Percent'].map(lambda x: f"{x:.1f}%")
print('after formatting:', summary.head())
print('cols now:', summary.columns)
