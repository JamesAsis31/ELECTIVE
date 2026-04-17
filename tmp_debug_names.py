from db import get_students, get_grade_rows
import pandas as pd

students = get_students()
grades = get_grade_rows()

# Build lookup
lookup = {}
for s in students:
    sid = str(s.get("_id", ""))
    name = s.get("student_name", "") or s.get("Name", "") or ""
    program = s.get("Course", "") or s.get("Program", "") or ""
    lookup[sid] = {"student_name": name, "program": program}

# Check IDs 1-10
for i in range(1, 11):
    entry = lookup.get(str(i))
    if entry:
        print(f"  _id={i} -> {entry}")
    else:
        print(f"  _id={i} -> NOT FOUND")

print(f"Total lookup entries: {len(lookup)}")

# Test with grade rows
df = pd.DataFrame(grades)
df["student_id"] = df["student_id"].astype(str)
df["resolved_name"] = df["student_id"].map(
    lambda sid: lookup.get(sid, {}).get("student_name", "") or "Unknown"
)
print("\nFirst 10 resolved names:")
print(df[["student_id", "student_name", "resolved_name", "subject_code", "grade"]].head(10).to_string())

unknown_count = (df["resolved_name"] == "Unknown").sum()
print(f"\nUnknown count: {unknown_count} / {len(df)}")
