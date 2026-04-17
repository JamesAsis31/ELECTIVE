from db import get_students, get_grades, get_subjects

for name, func in [('students', get_students), ('grades', get_grades), ('subjects', get_subjects)]:
    docs = list(func())
    print('---', name, 'count=', len(docs))
    for doc in docs[:2]:
        print('doc keys:', sorted(doc.keys()))
        print(doc)
    print()
