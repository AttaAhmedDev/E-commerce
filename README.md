# E-Commerce Backend

A Django REST API for an e-commerce catalog, authentication, cart, and wishlist. Features are added one at a time with tests before moving on.

## Tech Stack

- **Language / Framework:** Python 3.14.3, Django 6.0.7
- **API:** Django REST Framework
- **Database:** PostgreSQL
- **Auth:** SimpleJWT (rotating refresh tokens, blacklist)
- **API Docs:** drf-spectacular (Swagger UI)
- **Filtering:** django-filter
- **Images:** Pillow
- **Testing:** pytest-django, factory-boy

## Progress

### Completed

- **Project setup** — split settings (`local` / `production`), env-based config, custom exception shape
- **Authentication** — email-based users, JWT register/login/logout, token refresh
- **Profile / password** — view and update own profile; change password (blacklists outstanding tokens)
- **Catalog** — hierarchical categories, brands, products, variants, inventory
- **Product images** — gallery with a single primary image per product
- **Search, filter, sort** — product listing query params
- **Cart** — guest session cart, authenticated cart, merge on login/register
- **Wishlist** — login-required saved products (`Product`, not variant), unique per user, IDOR-safe list/add/remove

### Upcoming

- Orders / checkout (cart items reference `ProductVariant`; orders should snapshot price)

## Catalog design

Price and stock live on **`ProductVariant`**, not on `Product`. A product is the listing (name, category, brand, images). The sellable unit is a variant (SKU, size, color, price) with a separate `Inventory` row.

Cart lines also point at variants, and they read `variant.price` live — they do not store a snapshot until checkout.

Wishlist items point at **`Product`** instead — a general “I want this” signal, not a size/color commitment.

## Getting started

```bash
python -m venv venv
# Windows: .\venv\Scripts\Activate.ps1
# macOS/Linux: source venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

Create the PostgreSQL database named in `.env` (`DB_NAME`, default `corexion_ecommerce`), then:

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Local settings load from `config.settings.local` (see `.env.example`). Production settings live in `config.settings.production`.

## API

Base path: `/api/v1/`

Interactive docs: [http://127.0.0.1:8000/api/docs/](http://127.0.0.1:8000/api/docs/)  
OpenAPI schema: `/api/schema/`

Catalog **reads** are public. Catalog **writes** require an authenticated user with `role=admin`. List endpoints paginate (`page`, optional `page_size`, default 20, max 100).

### Auth

| Method | Path | Access |
|--------|------|--------|
| POST | `/api/v1/auth/register/` | Public — returns user + tokens; merges guest cart |
| POST | `/api/v1/auth/login/` | Public — returns user + tokens; merges guest cart |
| POST | `/api/v1/auth/refresh/` | Public — body: `{ "refresh": "..." }` |
| POST | `/api/v1/auth/logout/` | Authenticated — blacklists refresh token |
| GET / PATCH | `/api/v1/auth/profile/` | Authenticated — own profile only |
| POST | `/api/v1/auth/change-password/` | Authenticated — logs other sessions out |

Send `Authorization: Bearer <access>`. Access tokens last 15 minutes; refresh tokens last 7 days and rotate on use.

### Catalog

Resources are looked up by **slug** (`/products/{slug}/`, not numeric IDs).

| Resource | Path |
|----------|------|
| Categories | `/api/v1/categories/` |
| Brands | `/api/v1/brands/` |
| Products | `/api/v1/products/` |
| Variants | `/api/v1/products/{product_slug}/variants/` |
| Images | `/api/v1/products/{product_slug}/images/` |

Category **list** returns top-level categories only; children are nested on each item.

Product list query params:

| Param | Example | Notes |
|-------|---------|--------|
| `search` | `?search=Air+Max` | Name, description, category name, brand name |
| `category` | `?category=laptops` | Category slug |
| `brand` | `?brand=nike` | Brand slug |
| `min_price` / `max_price` | `?min_price=10&max_price=50` | Matches products with at least one active variant in range |
| `in_stock` | `?in_stock=true` | At least one active variant with quantity above 0 |
| `ordering` | `?ordering=price` or `-price` | Also `name`, `created_at` |

`price` ordering uses the lowest active variant price.

### Cart

Same endpoints for guests and logged-in users. Guests need the session cookie (`credentials: 'include'` from a browser). Authenticated requests use the JWT user cart.

| Method | Path | Behavior |
|--------|------|----------|
| GET | `/api/v1/cart/` | Current cart (`items`, `total_items`, `total_price`) |
| POST | `/api/v1/cart/items/` | `{ "variant_id": 1, "quantity": 2 }` — adding the same variant increases quantity |
| PATCH | `/api/v1/cart/items/{id}/` | Update quantity |
| DELETE | `/api/v1/cart/items/{id}/` | Remove line |

Quantity cannot exceed inventory. Login and register merge the session cart into the user cart (quantities add for the same variant) and delete the guest cart.

### Wishlist

Login required. Items are scoped to the current user only (no guest wishlist).

| Method | Path | Behavior |
|--------|------|----------|
| GET | `/api/v1/wishlist/` | Current user's wishlist (`product_detail`, `created_at`) |
| POST | `/api/v1/wishlist/items/` | `{ "product_id": 1 }` — rejects duplicates and inactive products |
| DELETE | `/api/v1/wishlist/items/{id}/` | Remove own item; other users' IDs return 404 |

## Project layout

```
config/                 # Django project (urls, split settings)
apps/
  common/               # timestamps, pagination, permissions, errors
  accounts/             # custom User (email + role)
  products/             # catalog models, filters, nested routes
  cart/                 # session/user carts and merge helper
  wishlist/             # login-required saved products
```

## Tests

```bash
pytest
```
