# Quick Release Guide

## Швидкий старт (для цього репозиторію)

### ✅ Налаштовано

- GitHub секрет `PyPi` вже додано
- Release workflow готовий
- Публікація буде на PyPI (без TestPyPI)

### 🚀 Створення релізу

**1. Оновити версію в `pyproject.toml`:**
```toml
version = "0.1.0"  # ← Змінити тут
```

**2. Закомітити і створити тег:**
```bash
git add pyproject.toml
git commit -m "Bump version to 0.1.0"
git push

git tag v0.1.0
git push origin v0.1.0
```

**3. Створити GitHub Release:**
- Йдемо: https://github.com/ruslanlap/EasyEnv/releases/new
- Вибираємо тег: `v0.1.0`
- Title: `v0.1.0`
- Description: (копіюємо з CHANGELOG.md)
- Натискаємо **"Publish release"**

**4. Workflow автоматично:**
- Збере пакунок
- Опублікує на PyPI
- Готово! 🎉

### 📦 Перевірка

Після публікації:
```bash
pip install easyenv
easyenv --help
```

### 🔄 Workflow мануально

Якщо потрібно запустити вручну:
1. Йдемо: https://github.com/ruslanlap/EasyEnv/actions/workflows/release.yml
2. Натискаємо "Run workflow"
3. Вводимо версію (наприклад, `0.1.0`)
4. Натискаємо "Run workflow"

**Примітка:** Мануальний запуск тільки збере пакунок, але не опублікує (для публікації потрібен GitHub Release).

### 📝 Checklist перед релізом

- [ ] Оновити версію в `pyproject.toml`
- [ ] Оновити `CHANGELOG.md`
- [ ] Перевірити що всі тести проходять (`pytest`)
- [ ] Перевірити лінтинг (`ruff check .`)
- [ ] Закомітити і запушити зміни
- [ ] Створити тег
- [ ] Створити GitHub Release
- [ ] Дочекатись успішного workflow
- [ ] Перевірити встановлення: `pip install easyenv`

### 🆘 Troubleshooting

**Помилка: "File already exists"**
- Версія вже існує на PyPI
- Потрібно збільшити номер версії

**Помилка: "Invalid or non-existent authentication"**
- Перевірити що секрет `PyPi` правильно налаштований
- Перевірити що токен PyPI не застарів

**Workflow не запускається**
- Перевірити що GitHub Release створено (не Draft)
- Перевірити що тег починається з `v` (наприклад, `v0.1.0`)

### 📚 Детальна документація

Дивись `docs/RELEASE.md` для повної документації.
