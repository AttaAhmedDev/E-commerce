# E-Commerce Backend

A production-grade Django e-commerce backend, built feature-by-feature using a structured 13-step development methodology to ensure consistency, testability, and maintainability.

## Tech Stack

- **Language / Framework:** Python 3.14.3, Django 6.0.7
- **API:** Django REST Framework (DRF)
- **Database:** PostgreSQL
- **Auth:** SimpleJWT (with token blacklisting)
- **API Docs:** drf-spectacular
- **Filtering:** django-filter
- **Testing:** pytest-django, factory-boy

## Development Methodology

Every feature in this project is built through the same structured 13-step process, which keeps development consistent and ensures each piece is fully tested before moving to the next. (Fill in the exact 13 steps here if you want them documented explicitly.)

## Progress

### ✅ Completed

- **Project Setup** — base Django project configured with the stack above
- **Feature 1: Authentication** — JWT-based auth with token blacklisting
- **Feature 2: Profile / Password Management** — user profile updates and password change/reset flows

All tests are passing (green) through the completed work above.

### 🚧 In Progress

- **Feature 3.1: Category / Brand Models** — currently being built (models stage)

### 📋 Upcoming

- Remaining steps of Feature 3 (Category/Brand: serializers, views, filters, tests, docs)
- Future features TBD

## Running Tests

```bash
pytest
```

## API Documentation

Auto-generated via drf-spectacular. Once the server is running, check your configured schema/docs endpoint (e.g. `/api/schema/`, `/api/docs/`).

---