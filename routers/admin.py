import csv
import io
import re

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload
from auth import require_admin
from database import get_db
from models import Category, Course, Enrollment, Message, Order, OrderItem, User
from routers.enrollments import serialize_enrollment
from schemas import CategoryCreate, CouponCreate, CourseUpsert, MessagePublic

router = APIRouter(prefix="/api/admin", tags=["admin"])


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


@router.get("/enrollments")
def admin_enrollments(
    response: Response,
    page: int = Query(default=1, ge=1, le=10000),
    per_page: int = Query(default=100, ge=1, le=100),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    base = select(Enrollment)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    rows = db.scalars(
        select(Enrollment).options(joinedload(Enrollment.course), joinedload(Enrollment.user))
        .order_by(Enrollment.created_at.desc())
        .offset((page - 1) * per_page).limit(per_page)
    ).all()
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Page"] = str(page)
    return [
        {**serialize_enrollment(row), "user_email": row.user.email}
        for row in rows
    ]


@router.get("/messages", response_model=list[MessagePublic])
def admin_messages(
    response: Response,
    page: int = Query(default=1, ge=1, le=10000),
    per_page: int = Query(default=100, ge=1, le=100),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    total = db.scalar(select(func.count(Message.id))) or 0
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Page"] = str(page)
    return list(db.scalars(
        select(Message).order_by(Message.created_at.desc())
        .offset((page - 1) * per_page).limit(per_page)
    ))


@router.get("/stats")
def admin_stats(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return {
        "users": db.scalar(select(func.count(User.id))) or 0,
        "revenue": round(db.scalar(select(func.coalesce(func.sum(Order.total), 0))) or 0, 2),
        "enrollments": db.scalar(select(func.count(Enrollment.id)).where(Enrollment.status == "confirmed")) or 0,
        "new_messages": db.scalar(select(func.count(Message.id)).where(Message.is_read.is_(False))) or 0,
    }


@router.get("/courses")
def admin_courses(
    response: Response,
    page: int = Query(default=1, ge=1, le=10000),
    per_page: int = Query(default=100, ge=1, le=100),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    total = db.scalar(select(func.count(Course.id))) or 0
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Page"] = str(page)
    return list(db.scalars(
        select(Course).order_by(Course.id.desc()).offset((page - 1) * per_page).limit(per_page)
    ))


def course_values(payload: CourseUpsert) -> dict:
    slug = slugify(payload.title)
    return {**payload.model_dump(), "slug": slug}


@router.post("/courses", status_code=201)
def create_course(payload: CourseUpsert, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    course = Course(**course_values(payload))
    db.add(course)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A course with this title already exists.") from None
    db.refresh(course)
    return course


@router.put("/courses/{course_id}")
def update_course(course_id: int, payload: CourseUpsert, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found.")
    for key, value in course_values(payload).items():
        setattr(course, key, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A course with this title already exists.") from None
    db.refresh(course)
    return course


@router.delete("/courses/{course_id}")
def delete_course(course_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found.")
    if db.scalar(select(Enrollment.id).where(Enrollment.course_id == course_id)) or db.scalar(
        select(OrderItem.id).where(OrderItem.course_id == course_id)
    ):
        course.is_published = False
        db.commit()
        return {"message": "Course archived because it has learning or order history."}
    db.delete(course)
    db.commit()
    return {"message": "Course deleted."}


@router.get("/categories")
def admin_categories(
    response: Response,
    page: int = Query(default=1, ge=1, le=10000),
    per_page: int = Query(default=100, ge=1, le=100),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    total = db.scalar(select(func.count(Category.id))) or 0
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Page"] = str(page)
    return list(db.scalars(
        select(Category).order_by(Category.name).offset((page - 1) * per_page).limit(per_page)
    ))


@router.post("/categories", status_code=201)
def create_category(payload: CategoryCreate, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    category = Category(name=payload.name.strip(), slug=slugify(payload.name))
    db.add(category)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="This category already exists.") from None
    db.refresh(category)
    return category


@router.put("/categories/{category_id}")
def update_category(
    category_id: int,
    payload: CategoryCreate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found.")
    old_name = category.name
    category.name = payload.name.strip()
    category.slug = slugify(payload.name)
    try:
        db.flush()
        db.query(Course).filter(Course.category == old_name).update(
            {Course.category: category.name}, synchronize_session=False
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="This category already exists.") from None
    db.refresh(category)
    return category


@router.delete("/categories/{category_id}")
def delete_category(category_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    category = db.get(Category, category_id)
    if category is None:
        raise HTTPException(status_code=404, detail="Category not found.")
    if db.scalar(select(Course.id).where(Course.category == category.name).limit(1)):
        raise HTTPException(status_code=409, detail="Move or reassign courses before removing this category.")
    db.delete(category)
    db.commit()
    return {"message": "Category deleted."}


@router.get("/coupons")
def admin_coupons(
    response: Response,
    page: int = Query(default=1, ge=1, le=10000),
    per_page: int = Query(default=100, ge=1, le=100),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    from models import Coupon
    total = db.scalar(select(func.count(Coupon.id))) or 0
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Page"] = str(page)
    return list(db.scalars(
        select(Coupon).order_by(Coupon.id.desc()).offset((page - 1) * per_page).limit(per_page)
    ))


@router.post("/coupons", status_code=201)
def create_coupon(payload: CouponCreate, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    from models import Coupon
    if payload.kind == "percent" and payload.value > 100:
        raise HTTPException(status_code=422, detail="Percentage coupons cannot exceed 100.")
    coupon = Coupon(code=payload.code.strip().upper(), **payload.model_dump(exclude={"code"}))
    db.add(coupon)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A coupon with this code already exists.") from None
    db.refresh(coupon)
    return coupon


@router.put("/coupons/{coupon_id}")
def update_coupon(
    coupon_id: int,
    payload: CouponCreate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    from models import Coupon
    if payload.kind == "percent" and payload.value > 100:
        raise HTTPException(status_code=422, detail="Percentage coupons cannot exceed 100.")
    coupon = db.get(Coupon, coupon_id)
    if coupon is None:
        raise HTTPException(status_code=404, detail="Coupon not found.")
    coupon.code = payload.code.strip().upper()
    coupon.kind = payload.kind
    coupon.value = payload.value
    coupon.expires_at = payload.expires_at
    coupon.usage_limit = payload.usage_limit
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A coupon with this code already exists.") from None
    db.refresh(coupon)
    return coupon


@router.delete("/coupons/{coupon_id}")
def delete_coupon(coupon_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    from models import Coupon
    coupon = db.get(Coupon, coupon_id)
    if coupon is None:
        raise HTTPException(status_code=404, detail="Coupon not found.")
    db.delete(coupon)
    db.commit()
    return {"message": "Coupon deleted."}


@router.get("/users")
def admin_users(
    _: User = Depends(require_admin),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    total = db.scalar(select(func.count(User.id))) or 0
    rows = db.scalars(select(User).order_by(User.created_at.desc()).offset((page - 1) * per_page).limit(per_page))
    return {"items": [
        {"id": user.id, "name": user.name, "email": user.email, "is_active": user.is_active,
         "is_admin": user.is_admin, "created_at": user.created_at}
        for user in rows
    ], "total": total, "page": page, "per_page": per_page}


@router.patch("/users/{user_id}/active")
def set_user_active(user_id: int, enabled: bool, admin_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.id == admin_user.id and not enabled:
        raise HTTPException(status_code=409, detail="You cannot disable your own admin account.")
    user.is_active = enabled
    db.commit()
    return {"id": user.id, "is_active": user.is_active}


@router.get("/orders.csv")
def export_orders(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.scalars(select(Order).options(joinedload(Order.items)).order_by(Order.created_at.desc())).unique().all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["invoice", "user_id", "created_at", "subtotal", "discount", "total", "payment_method", "status", "courses"])

    def spreadsheet_text(value: str) -> str:
        return f"'{value}" if value.lstrip().startswith(("=", "+", "-", "@")) else value

    for order in rows:
        writer.writerow([order.invoice_number, order.user_id, order.created_at.isoformat(), order.subtotal,
                         order.discount, order.total, order.payment_method, order.status,
                         spreadsheet_text("; ".join(item.course_title for item in order.items))])
    return Response(
        output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="eduhub-orders.csv"'},
    )


@router.get("/orders")
def admin_orders(
    response: Response,
    page: int = Query(default=1, ge=1, le=10000),
    per_page: int = Query(default=100, ge=1, le=100),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    total = db.scalar(select(func.count(Order.id))) or 0
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Page"] = str(page)
    rows = db.scalars(
        select(Order).options(joinedload(Order.items)).order_by(Order.created_at.desc())
        .offset((page - 1) * per_page).limit(per_page)
    ).unique()
    return [{
        "id": order.id, "invoice_number": order.invoice_number, "user_id": order.user_id,
        "total": order.total, "created_at": order.created_at, "status": order.status,
        "items": [item.course_title for item in order.items]
    } for order in rows]


@router.patch("/messages/{message_id}/read")
def mark_message_read(message_id: int, is_read: bool = True, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    message = db.get(Message, message_id)
    if message is None:
        raise HTTPException(status_code=404, detail="Message not found.")
    message.is_read = is_read
    db.commit()
    return {"id": message.id, "is_read": message.is_read}
