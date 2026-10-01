from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from auth import get_current_user
from database import get_db
from models import Course, Enrollment, Lesson, LessonCompletion, Section, User
from schemas import EnrollmentCreate, EnrollmentPublic

router = APIRouter(prefix="/api/enrollments", tags=["enrollments"])


def serialize_enrollment(enrollment: Enrollment) -> dict:
    return {
        "id": enrollment.id,
        "course_id": enrollment.course_id,
        "course_title": enrollment.course.title,
        "name": enrollment.name,
        "age": enrollment.age,
        "email": enrollment.email,
        "phone": enrollment.phone,
        "payment_method": enrollment.payment_method,
        "status": enrollment.status,
        "created_at": enrollment.created_at,
    }


@router.post("", response_model=EnrollmentPublic, status_code=status.HTTP_201_CREATED)
def enroll(
    payload: EnrollmentCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    course = db.get(Course, payload.course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found.")
    enrollment = db.scalar(
        select(Enrollment)
        .options(joinedload(Enrollment.course))
        .where(Enrollment.user_id == user.id, Enrollment.course_id == course.id)
    )
    if enrollment and enrollment.status != "canceled":
        raise HTTPException(status_code=409, detail="You are already enrolled in this course.")
    if enrollment:
        enrollment.name = payload.name
        enrollment.age = payload.age
        enrollment.email = str(payload.email).lower()
        enrollment.phone = payload.phone
        enrollment.payment_method = payload.payment_method
        enrollment.status = "confirmed"
    else:
        enrollment = Enrollment(
            user_id=user.id,
            course_id=course.id,
            name=payload.name,
            age=payload.age,
            email=str(payload.email).lower(),
            phone=payload.phone,
            payment_method=payload.payment_method,
            status="confirmed",
            course=course,
        )
        db.add(enrollment)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="You are already enrolled in this course.") from None
    db.refresh(enrollment)
    return serialize_enrollment(enrollment)


@router.get("/me", response_model=list[EnrollmentPublic])
def my_enrollments(
    response: Response,
    page: int = Query(default=1, ge=1, le=10000),
    per_page: int = Query(default=100, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = select(Enrollment).where(Enrollment.user_id == user.id)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    enrollments = db.scalars(
        select(Enrollment)
        .options(joinedload(Enrollment.course))
        .where(Enrollment.user_id == user.id)
        .order_by(Enrollment.created_at.desc())
        .offset((page - 1) * per_page).limit(per_page)
    ).all()
    response.headers["X-Total-Count"] = str(total)
    response.headers["X-Page"] = str(page)
    result = []
    for enrollment in enrollments:
        data = serialize_enrollment(enrollment)
        lessons_total = db.scalar(
            select(func.count(Lesson.id)).join(Section).where(Section.course_id == enrollment.course_id)
        ) or 0
        lessons_completed = db.scalar(
            select(func.count(LessonCompletion.id))
            .join(Lesson, Lesson.id == LessonCompletion.lesson_id)
            .join(Section, Section.id == Lesson.section_id)
            .where(Section.course_id == enrollment.course_id, LessonCompletion.user_id == user.id)
        ) or 0
        data["progress"] = round(lessons_completed * 100 / lessons_total) if lessons_total else 0
        data["order_id"] = enrollment.order_id
        result.append(data)
    return result


@router.delete("/{enrollment_id}")
def cancel_enrollment(
    enrollment_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    enrollment = db.scalar(
        select(Enrollment).where(Enrollment.id == enrollment_id, Enrollment.user_id == user.id)
    )
    if enrollment is None:
        raise HTTPException(status_code=404, detail="Enrollment not found.")
    if enrollment.status == "canceled":
        raise HTTPException(status_code=409, detail="This enrollment is already canceled.")
    enrollment.status = "canceled"
    db.commit()
    return {"message": "Enrollment canceled."}
