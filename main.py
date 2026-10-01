import os
import re
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, select, text

from auth import hash_password
from database import Base, SessionLocal, engine
from models import Category, Course, Coupon, Lesson, Section, User
from routers import admin, auth, contact, courses, enrollments, learning, store

STATIC_DIR = Path(__file__).resolve().parent / "static"

SEED_COURSES = (
    ("Physics 101", "Build an intuitive foundation in mechanics, energy, waves, and the physics of everyday life.", "Beginner", "Science", "Dr. Maya Chen", 18, 89, 59),
    ("Mathematics for JEE", "Master calculus, algebra, and problem-solving strategies for competitive exams.", "Advanced", "Mathematics", "Arjun Mehta", 32, 129, 89),
    ("Chemistry: The Essentials", "Understand atoms, reactions, and the patterns that make chemistry click.", "Beginner", "Science", "Dr. Maya Chen", 16, 79, 49),
    ("Python for Curious Minds", "Write practical Python programs from your first line of code to useful projects.", "Beginner", "Technology", "Elena Rivera", 24, 99, 69),
    ("Modern Web Development", "Build accessible, responsive websites with HTML, CSS, and JavaScript.", "Intermediate", "Technology", "Elena Rivera", 28, 149, 99),
    ("Data Science Foundations", "Explore data analysis, visualization, and the ideas behind machine learning.", "Intermediate", "Technology", "Elena Rivera", 30, 169, 119),
    ("Product Design Studio", "Turn user insights into clear flows, thoughtful interfaces, and prototypes.", "Beginner", "Design", "Elena Rivera", 20, 119, 79),
    ("Visual Storytelling", "Create memorable visual narratives with composition, color, and typography.", "Intermediate", "Design", "Elena Rivera", 14, 89, 59),
    ("Financial Confidence", "Build a practical personal finance toolkit for real-world decisions.", "Beginner", "Business", "Arjun Mehta", 12, 69, 45),
    ("Leadership in Practice", "Lead teams with clarity, empathy, and confident communication.", "Intermediate", "Business", "Arjun Mehta", 15, 109, 75),
    ("Creative Writing Lab", "Find your voice and shape compelling stories with guided weekly exercises.", "Beginner", "Creative", "Dr. Maya Chen", 10, 59, 39),
    ("Introduction to Astronomy", "Journey from our solar system to distant galaxies with a curious eye.", "Beginner", "Science", "Dr. Maya Chen", 13, 75, 49),
    ("Excel to Insight", "Use spreadsheets to organize, analyze, and present business information.", "Intermediate", "Business", "Arjun Mehta", 11, 85, 55),
    ("JavaScript: Beyond Basics", "Level up with modern JavaScript patterns, APIs, and interactive projects.", "Advanced", "Technology", "Elena Rivera", 22, 129, 89),
)


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def migrate_legacy_columns() -> None:
    additions = {
        "users": {
            "is_active": "BOOLEAN NOT NULL DEFAULT 1",
            "email_verified": "BOOLEAN NOT NULL DEFAULT 0",
            "reset_token_hash": "VARCHAR(64)",
            "reset_token_expires": "DATETIME",
        },
        "courses": {
            "slug": "VARCHAR(180) NOT NULL DEFAULT ''",
            "category": "VARCHAR(80) NOT NULL DEFAULT 'Learning'",
            "thumbnail_url": "VARCHAR(255) NOT NULL DEFAULT ''",
            "instructor": "VARCHAR(120) NOT NULL DEFAULT 'EduHub Faculty'",
            "duration_hours": "INTEGER NOT NULL DEFAULT 1",
            "rating_avg": "FLOAT NOT NULL DEFAULT 0",
            "rating_count": "INTEGER NOT NULL DEFAULT 0",
            "language": "VARCHAR(50) NOT NULL DEFAULT 'English'",
            "is_published": "BOOLEAN NOT NULL DEFAULT 1",
            "discounted_price": "FLOAT",
        },
        "enrollments": {"order_id": "INTEGER"},
        "messages": {"is_read": "BOOLEAN NOT NULL DEFAULT 0"},
    }
    with engine.begin() as connection:
        inspector = inspect(connection)
        for table, columns in additions.items():
            if not inspector.has_table(table):
                continue
            existing = {column["name"] for column in inspector.get_columns(table)}
            for column, definition in columns.items():
                if column not in existing:
                    connection.execute(text(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {definition}'))
        if inspect(connection).has_table("courses"):
            rows = connection.execute(text("SELECT id, title, slug FROM courses")).all()
            taken: set[str] = set()
            for course_id, title, existing_slug in rows:
                base_slug = existing_slug or slugify(title) or f"course-{course_id}"
                slug = base_slug
                suffix = 2
                while slug in taken:
                    slug = f"{base_slug}-{suffix}"
                    suffix += 1
                taken.add(slug)
                if existing_slug != slug:
                    connection.execute(text("UPDATE courses SET slug = :slug WHERE id = :id"), {"slug": slug, "id": course_id})
            connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_courses_slug ON courses (slug)"))


def initialize_database() -> None:
    migrate_legacy_columns()
    Base.metadata.create_all(bind=engine)
    migrate_legacy_columns()
    with SessionLocal() as db:
        category_names = {name for (name,) in db.execute(select(Category.name)).all()}
        categories = sorted({course[3] for course in SEED_COURSES})
        for name in categories:
            if name not in category_names:
                db.add(Category(name=name, slug=slugify(name)))
        existing_slugs = set(db.scalars(select(Course.slug)).all())
        for title, description, level, category, instructor, hours, price, discounted in SEED_COURSES:
            slug = slugify(title)
            course = db.scalar(select(Course).where(Course.slug == slug))
            if course is None:
                course = Course(
                    title=title, slug=slug, description=description, level=level, category=category,
                    instructor=instructor, duration_hours=hours, price=price,
                    discounted_price=discounted, thumbnail_url="", rating_avg=4.8, rating_count=120,
                    language="English", is_published=True,
                )
                db.add(course)
                db.flush()
            else:
                course.category = category
                course.instructor = instructor
                course.duration_hours = hours
                course.price = price
                course.discounted_price = discounted
                course.rating_avg = course.rating_avg or 4.8
                course.rating_count = course.rating_count or 120
            if not course.sections:
                for section_position in range(1, 4):
                    section = Section(title=f"Part {section_position}: {('The foundations', 'Build your skills', 'Put it into practice')[section_position - 1]}", position=section_position)
                    course.sections.append(section)
                    for lesson_position in range(1, 4):
                        section.lessons.append(Lesson(
                            title=f"Lesson {section_position}.{lesson_position} — {('A fresh perspective', 'Core concepts', 'Practice together')[lesson_position - 1]}",
                            duration_minutes=8 + lesson_position * 3,
                            position=lesson_position,
                            preview=section_position == 1 and lesson_position == 1,
                        ))
        for legacy_slug in ("chemistry-basics", "computer-science"):
            legacy_course = db.scalar(select(Course).where(Course.slug == legacy_slug))
            if (
                legacy_course is not None
                and legacy_course.instructor == "EduHub Faculty"
                and legacy_course.price == 0
            ):
                legacy_course.is_published = False
        for course in db.scalars(select(Course)).all():
            if not course.slug:
                course.slug = slugify(course.title) or f"course-{course.id}"
        if db.scalar(select(Coupon.id).where(Coupon.code == "WELCOME10")) is None:
            db.add(Coupon(code="WELCOME10", kind="percent", value=10, is_active=True))
        admin_email = os.getenv("ADMIN_EMAIL", "admin@eduhub.example.com").strip().lower()
        admin_password = os.getenv("ADMIN_PASSWORD", "Admin123!")
        admin_user = db.scalar(select(User).where(User.email == admin_email))
        if admin_user is None:
            db.add(
                User(
                    name="EduHub Admin",
                    email=admin_email,
                    hashed_password=hash_password(admin_password),
                    is_admin=True,
                )
            )
        elif not admin_user.is_admin:
            raise RuntimeError(
                "ADMIN_EMAIL belongs to a non-admin account. Choose a separate admin email or promote the account explicitly."
            )
        db.commit()


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_database()
    yield


app = FastAPI(title="EduHub API", version="1.0.0", lifespan=lifespan)
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; script-src 'self'; connect-src 'self'; frame-ancestors 'none'"
    return response


@app.exception_handler(RequestValidationError)
async def validation_error_handler(_: Request, exc: RequestValidationError):
    errors = {}
    for item in exc.errors():
        field = ".".join(str(part) for part in item["loc"] if part not in ("body", "query", "path"))
        errors[field or "request"] = item["msg"].replace("Value error, ", "")
    return JSONResponse(status_code=422, content={"detail": "Input validation failed.", "errors": errors})


@app.exception_handler(HTTPException)
async def http_error_handler(_: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail if isinstance(exc.detail, str) else str(exc.detail), "errors": {}},
        headers=exc.headers,
    )


@app.exception_handler(404)
async def page_not_found(request: Request, exc):
    if request.url.path.startswith("/api/"):
        return JSONResponse(status_code=404, content={"detail": "Not found.", "errors": {}})
    return FileResponse(STATIC_DIR / "404.html", status_code=404)


app.include_router(auth.router)
app.include_router(courses.router)
app.include_router(enrollments.router)
app.include_router(contact.router)
app.include_router(admin.router)
app.include_router(store.router)
app.include_router(learning.router)


@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(STATIC_DIR / "favicon.svg", media_type="image/svg+xml")


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="frontend")
