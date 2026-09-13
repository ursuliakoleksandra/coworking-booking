# Демонстрація роботи pre-commit хуків

Нижче — реальний лог із термінала під час розробки цього проєкту.

## Крок 1. Комітимо навмисно "поганий" код

Файл містив: невикористані імпорти, погане форматування (пробіли навколо
дужок, відсутність пробілів навколо `=`) і невикористану змінну.

```
$ git add app/routers/demo_bad.py
$ git commit -m "Demo: intentionally bad code"

black....................................................................Failed
- hook id: black
- files were modified by this hook

reformatted app/routers/demo_bad.py

ruff.....................................................................Failed
- hook id: ruff
- exit code: 1
- files were modified by this hook

F841 Local variable `unused_variable` is assigned to but never used
 --> app/routers/demo_bad.py:5:5
  |
3 | def badly_formatted_function(x, y):
4 |     z = x + y
5 |     unused_variable = 42
  |     ^^^^^^^^^^^^^^^
6 |     return z
  |
help: Remove assignment to unused variable `unused_variable`

flake8...................................................................Failed
- hook id: flake8
- exit code: 1

app/routers/demo_bad.py:5:5: F841 local variable 'unused_variable' is assigned to but never used
```

**Коміт заблоковано.** Git не створив коміт, поки не будуть виправлені
помилки — саме це і вимагається завданням.

## Крок 2. Виправляємо код (прибираємо невикористану змінну)

```
$ git add -A
$ git commit -m "Demo: fixed code passes pre-commit checks"

black....................................................................Passed
ruff.....................................................................Passed
flake8...................................................................Passed
fix end of files.........................................................Passed
trim trailing whitespace.................................................Passed
check yaml...............................................................Passed
check for merge conflicts................................................Passed

[master 3fb6311] Demo: fixed code passes pre-commit checks
```

**Коміт успішний** — усі перевірки пройдено.

## Висновок

Pre-commit налаштовано так, що жоден коміт із синтаксичними помилками чи
порушеннями стилю (`black`, `ruff`, `flake8`) не потрапить у репозиторій,
поки розробник їх не виправить.
