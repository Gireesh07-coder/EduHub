from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from database import get_db
from models import Category, Course, Lesson, Review, Section
from schemas import CoursePublic

router = APIRouter(prefix="/api", tags=["courses"])


@router.get("/categories")
def categories(
    response: Response,
    page: int = Query(default=1, ge=1, le=10000),
    per_page: int = Query(default=100, ge=1, le=100),
    db: Session = Depends(get_db),
):
    total = db.scalar(select(func.count(Category.id))) or 0
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Page"] = str(page)
    return [
        {"name": name, "slug": slug}
        for name, slug in db.execute(
            select(Category.name, Category.slug).order_by(Category.name)
            .offset((page - 1) * per_page).limit(per_page)
        ).all()
    ]


@router.get("/courses", response_model=list[CoursePublic])
def list_courses(
    response: Response,
    q: str | None = Query(default=None, max_length=100),
    category: str | None = Query(default=None, max_length=80),
    level: str | None = Query(default=None, max_length=50),
    min_price: float | None = Query(default=None, ge=0, le=100000),
    max_price: float | None = Query(default=None, ge=0, le=100000),
    sort: str = Query(default="popular", pattern="^(popular|newest|price|rating)$"),
    page: int = Query(default=1, ge=1, le=10000),
    per_page: int = Query(default=24, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = select(Course).where(Course.is_published.is_(True))
    if q:
        term = f"%{q.strip()}%"
        query = query.where(or_(Course.title.ilike(term), Course.description.ilike(term), Course.instructor.ilike(term)))
    if category:
        query = query.where(func.lower(Course.category) == category.strip().lower())
    if level:
        query = query.where(func.lower(Course.level) == level.strip().lower())
    if min_price is not None:
        query = query.where(func.coalesce(Course.discounted_price, Course.price) >= min_price)
    if max_price is not None:
        query = query.where(func.coalesce(Course.discounted_price, Course.price) <= max_price)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    if sort == "newest":
        query = query.order_by(Course.created_at.desc())
    elif sort == "price":
        query = query.order_by(func.coalesce(Course.discounted_price, Course.price), Course.id)
    elif sort == "rating":
        query = query.order_by(Course.rating_avg.desc(), Course.rating_count.desc())
    else:
        query = query.order_by(Course.rating_count.desc(), Course.rating_avg.desc())
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Page"] = str(page)
    response.headers["X-Per-Page"] = str(per_page)
    return list(db.scalars(query.offset((page - 1) * per_page).limit(per_page)))


@router.get("/courses/{course_key}")
def get_course(course_key: str, db: Session = Depends(get_db)):
    query = select(Course).options(selectinload(Course.sections).selectinload(Section.lessons))
    if course_key.isdigit():
        query = query.where(Course.id == int(course_key))
    else:
        query = query.where(Course.slug == course_key)
    course = db.scalar(query.where(Course.is_published.is_(True)))
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found.")
    reviews = db.scalars(select(Review).where(Review.course_id == course.id).order_by(Review.created_at.desc()).limit(12)).all()
    return {
        "id": course.id,
        "title": course.title,
        "slug": course.slug,
        "description": course.description,
        "level": course.level,
        "price": course.price,
        "discounted_price": course.discounted_price,
        "category": course.category,
        "thumbnail_url": course.thumbnail_url,
        "instructor": course.instructor,
        "duration_hours": course.duration_hours,
        "rating_avg": course.rating_avg,
        "rating_count": course.rating_count,
        "language": course.language,
        "created_at": course.created_at,
        "sections": [
            {
                "id": section.id,
                "title": section.title,
                "position": section.position,
                "lessons": [
                    {
                        "id": lesson.id,
                        "title": lesson.title,
                        "duration_minutes": lesson.duration_minutes,
                        "position": lesson.position,
                        "preview": lesson.preview,
                    }
                    for lesson in sorted(section.lessons, key=lambda item: item.position)
                ],
            }
            for section in sorted(course.sections, key=lambda item: item.position)
        ],
        "reviews": [
            {
                "id": review.id,
                "rating": review.rating,
                "comment": review.comment,
                "name": review.user.name,
                "created_at": review.created_at,
            }
            for review in reviews
        ],
    }
