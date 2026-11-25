# Employee Trip Management Portal

A simple base project: employees request business trips, managers approve or reject them.

**Stack:** Python 3, Flask, SQLite (no extra setup), plain HTML/CSS.

## Features
- Login / registration (hashed passwords), roles: `employee` and `manager`
- Employees: submit, edit, and cancel pending trip requests; dashboard with status counts
- Managers: view all requests, filter by status, approve/reject with a comment
- Input validation (dates, cost, required fields)

## Run
```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
Open http://127.0.0.1:5000

## Demo accounts (created on first run)
| Role     | Email                | Password    |
|----------|----------------------|-------------|
| Manager  | manager@example.com  | manager123  |
| Employee | employee@example.com | employee123 |

## Structure
```
app.py            routes, auth, database (portal.db is created automatically)
templates/        Jinja2 pages
static/style.css  styling
```

## Next steps
Email notifications, trip expense reports, department-based approval chains, CSRF protection (Flask-WTF), and a production WSGI server. Set `SECRET_KEY` as an environment variable before deploying.
