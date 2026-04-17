from db import get_students, get_grades, get_subjects
import pprint

for name, f in [('students', get_students), ('grades', get_grades), ('subjects', get_subjects)]:
    docs = f()
    print('===', name, 'count=', len(docs))
    for i, doc in enumerate(docs[:5]):
        print('doc', i, type(doc))
        pprint.pprint(doc)
    if docs:
        keys = set().union(*(d.keys() for d in docs))
        print('keys:', sorted(keys))
    print()
