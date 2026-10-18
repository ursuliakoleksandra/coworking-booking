# Демонстрація роботи pre-commit хуків (лабораторна №2)

Реальний лог із термінала під час розробки коду ролей/авторизації.

## Крок 1. Комітимо навмисно "поганий" код

```
$ git commit -m "Lab 2: users, roles, RBAC, JWT auth, IDOR protection, tests"

black....................................................................Failed
- hook id: black
- files were modified by this hook

reformatted app/routers/demo_bad.py

ruff.....................................................................Failed
- hook id: ruff
- exit code: 1

app/routers/demo_bad.py:2:5: F841 Local variable `x` is assigned to but never used
  |
1 | def badly_formatted_role_check(role, user):
2 |     x = 1
  |     ^ F841
3 |     if role == user.role:
4 |         return True
  |
  = help: Remove assignment to unused variable `x`

flake8...................................................................Failed
- hook id: flake8
- exit code: 1

app/routers/demo_bad.py:2:5: F841 local variable 'x' is assigned to but never used

fix end of files.........................................................Passed
trim trailing whitespace.................................................Passed
check for merge conflicts................................................Passed
```

**Коміт заблоковано.**

## Крок 2. Прибираємо невикористану змінну і комітимо знову

```
$ git add -A
$ git commit -m "Lab 2: users, roles, RBAC, JWT auth, IDOR protection, tests"

black....................................................................Passed
ruff.....................................................................Passed
flake8...................................................................Passed
fix end of files.........................................................Passed
trim trailing whitespace.................................................Passed
check for merge conflicts................................................Passed

[master 6e305e7] Lab 2: users, roles, RBAC, JWT auth, IDOR protection, tests
```

**Коміт успішний.**
