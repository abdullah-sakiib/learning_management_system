# Learning Management System

A Django learning-management application organized by feature and layer.

## Local setup

1. Create and activate a virtual environment.
2. Install dependencies with `pip install -r requirements.txt`.
3. Copy `.env.example` to `.env` and set local values in your shell or environment loader.
4. Run `python manage.py migrate`.
5. Run `python manage.py runserver`.

The project uses development settings by default. Set `DJANGO_ENV=production`,
`DJANGO_SECRET_KEY`, and `DJANGO_ALLOWED_HOSTS` for a production deployment.

## Architecture

- `core/models/`: persistent domain entities grouped by feature.
- `core/views/`: HTTP request handlers grouped by user workflow.
- `core/forms/`: input parsing and validation.
- `core/services/`: state-changing business operations.
- `core/selectors/`: reusable read-only database queries.
- `core/urls/`: route definitions grouped by feature.
- `core/templates/core/`: namespaced Django templates.
- `core/static/core/`: page CSS and JavaScript.
- `core/tests/`: focused test modules and shared factories.
- `lms_project/settings/`: base, development, and production settings.

Views should remain thin: authorize the request, validate a form, call a service
or selector, and return a response. Business rules should not be duplicated in
templates or view functions.

## Verification

```text
python manage.py check
python manage.py makemigrations --check --dry-run
python -m pytest
python -m pytest core/tests/stqa --cov=core --cov-report=term-missing --cov-report=html
python -m pytest core/tests/e2e --run-selenium -q
```

The assessed STQA suite contains 150 pytest cases under `core/tests/stqa/`.
Five opt-in browser journeys are located under `core/tests/e2e/`.


