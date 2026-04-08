# CollabNotes

Real-time collaborative notes application built with Django, Django Channels, HTML, and CSS.

## Project structure

```
collabnotes/
├── manage.py
├── requirements.txt
├── .env.example
│
├── core/                        ← Django project package
│   ├── settings.py
│   ├── urls.py
│   ├── asgi.py
│   └── wsgi.py
│
├── apps/
│   ├── accounts/                ← Auth: register, login, profile, password reset
│   ├── notes/                   ← Notes CRUD, sharing, version history, WS consumer
│   └── workspaces/              ← Workspace / folder organisation
│
├── templates/                   ← All templates in one folder
│   ├── base.html
│   ├── includes/
│   ├── accounts/
│   ├── notes/
│   ├── workspaces/
│   └── emails/
│
└── static/
    ├── css/style.css
    └── js/editor.js
```

## Local setup

### 1. Clone and create a virtual environment

```bash
git clone <repo>
cd collabnotes
python -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment variables

```bash
cp .env.example .env
# Edit .env with your values
```

Minimum required values for local development:
```
SECRET_KEY=any-random-string
DEBUG=True
DB_PASSWORD=your_postgres_password
```

### 3. Create the PostgreSQL database

```sql
CREATE DATABASE collabnotes_db;
CREATE USER collabnotes_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE collabnotes_db TO collabnotes_user;
```

### 4. Run migrations

```bash
python manage.py migrate
```

### 5. Create a superuser (optional)

```bash
python manage.py createsuperuser
```

### 6. Start Redis

```bash
redis-server
```

### 7. Run the development server

For WebSocket support you need Daphne (not `runserver`):

```bash
daphne -b 127.0.0.1 -p 8000 core.asgi:application
```

Or for HTTP-only development (no live collaboration):

```bash
python manage.py runserver
```

Open http://localhost:8000 — you'll be redirected to `/notes/` which redirects to `/accounts/login/`.

---

## Production deployment

### Gunicorn + Daphne + Nginx

```bash
# HTTP (REST, page views)
gunicorn core.wsgi:application --bind 127.0.0.1:8000 --workers 4

# WebSocket (Django Channels)
daphne -b 127.0.0.1 -p 8001 core.asgi:application
```

Nginx routes `/ws/` to Daphne (port 8001) and everything else to Gunicorn (port 8000).

```nginx
upstream gunicorn { server 127.0.0.1:8000; }
upstream daphne   { server 127.0.0.1:8001; }

server {
    listen 443 ssl;
    server_name yourdomain.com;

    location /ws/ {
        proxy_pass http://daphne;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }

    location /static/ { alias /srv/collabnotes/staticfiles/; }

    location / {
        proxy_pass http://gunicorn;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```

### Collect static files

```bash
python manage.py collectstatic --noinput
```

### Production environment variables

```
DEBUG=False
SECRET_KEY=<64-char random string>
ALLOWED_HOSTS=yourdomain.com
DB_PASSWORD=<strong password>
REDIS_URL=redis://127.0.0.1:6379
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.sendgrid.net
EMAIL_HOST_USER=apikey
EMAIL_HOST_PASSWORD=<sendgrid api key>
```

---

## Features

- **Register / login** with email verification
- **Password reset** via email (single-use, 1-hour tokens)
- **Create, edit, delete** notes with rich text formatting
- **Real-time collaboration** — multiple users see each other's edits live via WebSockets
- **Role-based access** — Owner / Editor / Viewer
- **Share notes** via invite link or by email address
- **Version history** — automatic snapshots on every save, manual snapshots, one-click restore
- **Workspaces** — organise notes into colour-coded folders
- **Responsive** — works on mobile

## Tech stack

| Layer | Technology |
|---|---|
| Framework | Django 5 |
| Real-time | Django Channels 4 + Redis |
| Database | PostgreSQL |
| Frontend | Django templates + HTML + CSS |
| JavaScript | Vanilla JS (editor.js — ~200 lines) |
| Auth security | Argon2 password hashing |
| HTML sanitisation | bleach |
| Static files | WhiteNoise |
