import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from auth import get_current_user
from database import get_db
from models import (
    CartItem,
    Course,
    Coupon,
    Enrollment,
    Lesson,
    LessonCompletion,
    Order,
    OrderItem,
    Review,
    User,
    WishlistItem,
)
from schemas import CartAdd, CheckoutCreate, CouponValidate, ReviewCreate

router = APIRouter(prefix="/api", tags=["store"])


def course_price(course: Course) -> float:
    return float(course.discounted_price if course.discounted_price is not None else course.price)


def valid_coupon(db: Session, code: str, subtotal: float) -> tuple[Coupon, float]:
    coupon = db.scalar(select(Coupon).where(Coupon.code == code.upper()))
    if coupon is None or not coupon.is_active:
        raise HTTPException(status_code=400, detail="This coupon code is not valid.")
    expires = coupon.expires_at
    if expires and expires.tzinfo is None:
        expires = expires.replace(tzinfo=timezone.utc)
    if expires and expires <= datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="This coupon code has expired.")
    if coupon.usage_limit is not None and coupon.usage_count >= coupon.usage_limit:
        raise HTTPException(status_code=409, detail="This coupon has reached its usage limit.")
    discount = subtotal * coupon.value / 100 if coupon.kind == "percent" else coupon.value
    return coupon, round(min(discount, subtotal), 2)


def order_json(order: Order) -> dict:
    return {
        "id": order.id,
        "invoice_number": order.invoice_number,
        "subtotal": order.subtotal,
        "discount": order.discount,
        "total": order.total,
        "coupon_code": order.coupon_code,
        "payment_method": order.payment_method,
        "payment_last4": order.payment_last4,
        "status": order.status,
        "created_at": order.created_at,
        "items": [
            {"course_id": item.course_id, "title": item.course_title, "price": item.price}
            for item in order.items
        ],
    }


@router.get("/cart")
def get_cart(
    page: int = Query(default=1, ge=1, le=10000),
    per_page: int = Query(default=100, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    total = db.scalar(select(func.count(CartItem.id)).where(CartItem.user_id == user.id)) or 0
    items = db.scalars(
        select(CartItem).options(joinedload(CartItem.course))
        .where(CartItem.user_id == user.id)
        .order_by(CartItem.id)
        .offset((page - 1) * per_page).limit(per_page)
    ).all()
    return {
        "items": [
            {
                "course_id": item.course.id,
                "title": item.course.title,
                "slug": item.course.slug,
                "price": item.course.price,
                "discounted_price": item.course.discounted_price,
                "instructor": item.course.instructor,
            }
            for item in items
        ],
        "total": total,
        "page": page,
        "per_page": per_page,
    }


@router.post("/cart", status_code=status.HTTP_201_CREATED)
def add_to_cart(payload: CartAdd, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    course = db.get(Course, payload.course_id)
    if course is None or not course.is_published:
        raise HTTPException(status_code=404, detail="Course not found.")
    enrolled = db.scalar(
        select(Enrollment.id).where(
            Enrollment.user_id == user.id, Enrollment.course_id == course.id, Enrollment.status == "confirmed"
        )
    )
    if enrolled:
        raise HTTPException(status_code=409, detail="You already own this course.")
    if not db.scalar(select(CartItem.id).where(CartItem.user_id == user.id, CartItem.course_id == course.id)):
        db.add(CartItem(user_id=user.id, course_id=course.id))
        db.commit()
    return {"message": "Course added to your cart."}


@router.delete("/cart/{course_id}")
def remove_from_cart(course_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.scalar(select(CartItem).where(CartItem.user_id == user.id, CartItem.course_id == course_id))
    if item is None:
        raise HTTPException(status_code=404, detail="Cart item not found.")
    db.delete(item)
    db.commit()
    return {"message": "Course removed from your cart."}


@router.post("/coupons/validate")
def validate_coupon(payload: CouponValidate, db: Session = Depends(get_db)):
    coupon, discount = valid_coupon(db, payload.code.strip().upper(), payload.subtotal)
    return {
        "code": coupon.code,
        "kind": coupon.kind,
        "value": coupon.value,
        "discount": discount,
        "total": round(payload.subtotal - discount, 2),
    }


@router.post("/checkout", status_code=status.HTTP_201_CREATED)
def checkout(payload: CheckoutCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if payload.payment_method == "card" and not payload.last4:
        raise HTTPException(status_code=422, detail="Enter the last four digits for the mock card payment.")
    if payload.payment_method != "card" and payload.last4:
        raise HTTPException(status_code=422, detail="Card digits are only accepted for card payments.")
    courses = db.scalars(
        select(Course).where(Course.id.in_(payload.course_ids), Course.is_published.is_(True))
    ).all()
    by_id = {course.id: course for course in courses}
    if len(by_id) != len(payload.course_ids):
        raise HTTPException(status_code=404, detail="One or more courses are no longer available.")
    existing_ids = set(db.scalars(
        select(Enrollment.course_id).where(
            Enrollment.user_id == user.id,
            Enrollment.course_id.in_(payload.course_ids),
            Enrollment.status == "confirmed",
        )
    ).all())
    if existing_ids:
        raise HTTPException(status_code=409, detail="You already own one or more courses in this cart.")
    subtotal = round(sum(course_price(by_id[course_id]) for course_id in payload.course_ids), 2)
    coupon = None
    discount = 0.0
    if payload.coupon_code:
        coupon, discount = valid_coupon(db, payload.coupon_code, subtotal)
    order = Order(
        user_id=user.id,
        invoice_number=f"EH-{datetime.now(timezone.utc):%Y%m%d}-{secrets.token_hex(4).upper()}",
        subtotal=subtotal,
        discount=discount,
        total=round(subtotal - discount, 2),
        coupon_code=coupon.code if coupon else None,
        payment_method=payload.payment_method,
        payment_last4=payload.last4 if payload.payment_method == "card" else None,
        status="confirmed",
    )
    db.add(order)
    try:
        db.flush()
        for course in courses:
            order.items.append(OrderItem(course_id=course.id, course_title=course.title, price=course_price(course)))
            enrollment = db.scalar(select(Enrollment).where(
                Enrollment.user_id == user.id, Enrollment.course_id == course.id
            ))
            if enrollment:
                enrollment.name = user.name
                enrollment.age = user.age or 18
                enrollment.email = user.email
                enrollment.phone = user.phone or ""
                enrollment.payment_method = payload.payment_method
                enrollment.status = "confirmed"
                enrollment.order_id = order.id
            else:
                db.add(Enrollment(
                    user_id=user.id,
                    course_id=course.id,
                    name=user.name,
                    age=user.age or 18,
                    email=user.email,
                    phone=user.phone or "",
                    payment_method=payload.payment_method,
                    status="confirmed",
                    order_id=order.id,
                ))
            db.query(CartItem).filter(CartItem.user_id == user.id, CartItem.course_id == course.id).delete()
        if coupon:
            coupon.usage_count += 1
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A course was purchased in another checkout. Refresh your cart.") from None
    db.refresh(order)
    return order_json(order)


@router.get("/orders/me")
def get_my_orders(
    response: Response,
    page: int = Query(default=1, ge=1, le=10000),
    per_page: int = Query(default=100, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    total = db.scalar(select(func.count(Order.id)).where(Order.user_id == user.id)) or 0
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Page"] = str(page)
    orders = db.scalars(
        select(Order).options(joinedload(Order.items))
        .where(Order.user_id == user.id)
        .order_by(Order.created_at.desc())
        .offset((page - 1) * per_page).limit(per_page)
    ).unique().all()
    return [order_json(order) for order in orders]


@router.get("/orders/{order_id}")
def get_order(order_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    order = db.scalar(
        select(Order).options(joinedload(Order.items))
        .where(Order.id == order_id, Order.user_id == user.id)
    )
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found.")
    return order_json(order)


@router.get("/wishlist")
def get_wishlist(
    page: int = Query(default=1, ge=1, le=10000),
    per_page: int = Query(default=100, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    total = db.scalar(select(func.count(WishlistItem.id)).where(WishlistItem.user_id == user.id)) or 0
    items = db.scalars(
        select(WishlistItem).options(joinedload(WishlistItem.course))
        .where(WishlistItem.user_id == user.id)
        .offset((page - 1) * per_page).limit(per_page)
    ).all()
    return {"items": [
        {"course_id": item.course.id, "title": item.course.title, "slug": item.course.slug,
         "category": item.course.category, "instructor": item.course.instructor,
         "price": item.course.price, "discounted_price": item.course.discounted_price}
        for item in items
    ], "total": total, "page": page, "per_page": per_page}


@router.post("/wishlist", status_code=status.HTTP_201_CREATED)
def add_wishlist(payload: CartAdd, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    course = db.get(Course, payload.course_id)
    if course is None or not course.is_published:
        raise HTTPException(status_code=404, detail="Course not found.")
    if not db.scalar(select(WishlistItem.id).where(WishlistItem.user_id == user.id, WishlistItem.course_id == course.id)):
        db.add(WishlistItem(user_id=user.id, course_id=course.id))
        db.commit()
    return {"message": "Course saved to your wishlist."}


@router.delete("/wishlist/{course_id}")
def remove_wishlist(course_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = db.scalar(select(WishlistItem).where(WishlistItem.user_id == user.id, WishlistItem.course_id == course_id))
    if item is None:
        raise HTTPException(status_code=404, detail="Wishlist item not found.")
    db.delete(item)
    db.commit()
    return {"message": "Course removed from your wishlist."}


@router.get("/courses/{course_id}/reviews")
def list_reviews(
    course_id: int,
    response: Response,
    page: int = Query(default=1, ge=1, le=10000),
    per_page: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    if db.get(Course, course_id) is None:
        raise HTTPException(status_code=404, detail="Course not found.")
    total = db.scalar(select(func.count(Review.id)).where(Review.course_id == course_id)) or 0
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Page"] = str(page)
    rows = db.scalars(
        select(Review).options(joinedload(Review.user)).where(Review.course_id == course_id)
        .order_by(Review.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    ).all()
    return [{"id": row.id, "rating": row.rating, "comment": row.comment,
             "name": row.user.name, "created_at": row.created_at} for row in rows]


@router.post("/courses/{course_id}/reviews", status_code=status.HTTP_201_CREATED)
def create_review(
    course_id: int,
    payload: ReviewCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found.")
    enrollment = db.scalar(select(Enrollment.id).where(
        Enrollment.user_id == user.id, Enrollment.course_id == course_id, Enrollment.status == "confirmed"
    ))
    if not enrollment:
        raise HTTPException(status_code=403, detail="Enroll in this course before leaving a review.")
    if db.scalar(select(Review.id).where(Review.user_id == user.id, Review.course_id == course_id)):
        raise HTTPException(status_code=409, detail="You have already reviewed this course.")
    db.add(Review(user_id=user.id, course_id=course_id, rating=payload.rating, comment=payload.comment))
    db.flush()
    course.rating_avg = db.scalar(select(func.avg(Review.rating)).where(Review.course_id == course_id)) or payload.rating
    course.rating_count = db.scalar(select(func.count(Review.id)).where(Review.course_id == course_id)) or 1
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="You have already reviewed this course.") from None
    return {"message": "Thanks for sharing your review.", "rating_avg": course.rating_avg, "rating_count": course.rating_count}
