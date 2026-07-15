# E-commerce API

A Django REST Framework project for an e-commerce backend with authentication, product management, and API documentation.

## Features
- JWT authentication
- User profile management
- Product CRUD endpoints
- API schema generation with drf-spectacular

## Tech Stack
- Python 3.12+
- Django
- Django REST Framework
- PostgreSQL

## Setup
1. Create and activate a virtual environment
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and update the values
4. Run migrations:
   ```bash
   python manage.py migrate
   ```
5. Start the development server:
   ```bash
   python manage.py runserver
   ```

## Testing
```bash
pytest
```
