from db import get_students, get_grades

students = list(get_students())
grades = list(get_grades())
print('students count', len(students))
print('students keys sample', sorted(students[0].keys()) if students else [])
print('students sample', students[0] if students else 'none')
print('grades count', len(grades))
print('grades keys sample', sorted(grades[0].keys()) if grades else [])
print('grades sample', grades[0] if grades else 'none')
