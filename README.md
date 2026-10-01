# EduHub

EduHub is a responsive course marketplace and self-paced learning demo built with FastAPI, SQLAlchemy, SQLite, Pydantic v2, JWT cookies, and plain HTML/CSS/JavaScript. No frontend framework or build process is used.

## Quick start

Python 3.11 or newer is required. In PowerShell, from the project root:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn main:app --reload
```

Open <http://127.0.0.1:8000>. FastAPI serves the frontend and API on the same origin. Interactive API documentation is available at <http://127.0.0.1:8000/docs>.

### Environment

| Variable | Default | Purpose |
| --- | --- | --- |
| `SECRET_KEY` | Development-only key in `auth.py` | JWT signing key. Set a unique, long random value outside local development. |
| `DATABASE_URL` | `sqlite:///./eduhub.db` | SQLAlchemy database URL. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | Cookie/JWT lifetime in minutes. |
| `COOKIE_SECURE` | `false` | Set `true` when serving over HTTPS. |
| `ADMIN_EMAIL` | `admin@eduhub.example.com` | Email for the initial admin account. |
| `ADMIN_PASSWORD` | `Admin123!` | Password for the initial admin account. Change it before any shared deployment. |

The configured admin is created on first startup if the address does not already exist. Admin credentials are not reset on subsequent starts. Courses, categories, course outlines, and the `WELCOME10` demo coupon are seeded automatically. Existing MVP SQLite tables receive additive, idempotent startup migrations; `create_all` alone is not relied on to alter those tables. Two legacy free placeholder courses are retained for existing enrollment history but unpublished from the new catalog.

All transactions are mock transactions. Card checkout accepts only the last four digits and never stores a full card number. UPI and PayPal are selection-only mock methods. No payment provider or mail service is connected. Password-reset links and mock contact/newsletter notifications are logged to the server console.

## Features

- Searchable, filterable course catalog with category, level, price, sort, and pagination.
- 14 paid course examples across six categories, three instructors, course outlines, and lessons.
- JWT authentication in an httpOnly, same-site cookie; rate-limited login, password reset, email verification demo, and profile/password management.
- Persistent cart, validated percentage/fixed coupons, mock multi-course checkout, generated order and printable receipt.
- Course reviews for enrolled learners, wishlist, lesson progress, course player, and printable completion certificates.
- Contact inbox, unique newsletter signup, admin metrics, course/category/coupon/user management, order CSV export, and message triage.
- Responsive design system, remembered light/dark theme, mobile navigation, inline API errors, and accessible page structures.

## Pages

`index.html` (home), `courses.html` (catalog), `course.html` (course detail), `login.html`, `register.html`, `forgot-password.html`, `reset-password.html`, `cart.html`, `checkout.html`, `order-success.html`, `invoice.html`, `dashboard.html`, `profile.html`, `orders.html` / legacy `enrollments.html`, `wishlist.html`, `player.html`, `certificate.html`, `about.html`, `contact.html`, `faq.html`, `pricing.html`, `terms.html`, `privacy.html`, `404.html`, and `admin.html`.

## API

All endpoints use the same origin; CORS is not enabled by default.

| Method | Endpoint | Access |
| --- | --- | --- |
| POST | `/api/auth/register`, `/api/auth/login`, `/api/auth/logout` | Public |
| POST | `/api/auth/forgot-password`, `/api/auth/reset-password` | Public |
| POST | `/api/auth/change-password`, `/api/auth/verify-email` | Signed in |
| GET / PUT | `/api/me` | Signed in |
| GET | `/api/categories`, `/api/courses`, `/api/courses/{id-or-slug}` | Public |
| GET | `/api/courses/{id}/reviews` | Public |
| POST | `/api/courses/{id}/reviews` | Enrolled learner |
| GET / POST / DELETE | `/api/cart`, `/api/cart/{course_id}` | Signed in |
| POST | `/api/coupons/validate` | Public |
| POST | `/api/checkout` | Signed in |
| GET | `/api/orders/me`, `/api/orders/{id}` | Order owner |
| GET / POST / DELETE | `/api/wishlist`, `/api/wishlist/{course_id}` | Signed in |
| GET | `/api/enrollments/me` | Signed in |
| POST / DELETE | `/api/enrollments`, `/api/enrollments/{id}` | Signed in |
| GET | `/api/learning/dashboard`, `/api/learning/courses/{id-or-slug}` | Signed in |
| POST | `/api/lessons/{id}/complete` | Enrolled learner |
| GET | `/api/certificates/{course_id}` | Enrolled learner with 100% progress |
| POST | `/api/contact`, `/api/newsletter/subscribe` | Public |
| GET | `/api/admin/stats`, `/api/admin/courses`, `/api/admin/categories`, `/api/admin/coupons`, `/api/admin/users`, `/api/admin/orders`, `/api/admin/enrollments`, `/api/admin/messages` | Admin |
| POST / PUT / DELETE | `/api/admin/courses`, `/api/admin/categories`, `/api/admin/coupons` | Admin |
| PATCH | `/api/admin/users/{id}/active`, `/api/admin/messages/{id}/read` | Admin |
| GET | `/api/admin/orders.csv` | Admin |

Validation failures return `{ "detail": "...", "errors": { "field": "message" } }`. Other API errors use the same envelope with an empty `errors` object.

## Project layout

```text
main.py, database.py, models.py, schemas.py, auth.py
routers/              API route modules
static/
  css/                Design tokens, components, and page layouts
  js/                 Shared header/footer and page interactions
  *.html              Plain static pages served by FastAPI
tests/                Pytest API and workflow tests
requirements.txt
.env.example
```

## Tests

```powershell
python -m pytest
```

The test suite uses an isolated in-memory SQLite database.

## Demo scope notes

No live payments, outgoing email, video hosting, or third-party analytics are integrated. Lesson content is a text-based demo player. Legal pages are placeholders and need review before commercial launch. The admin reports aggregate platform metrics and a simple CSS activity visualization rather than historical business intelligence charts.
