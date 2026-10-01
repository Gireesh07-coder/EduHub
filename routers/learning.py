from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload, selectinload

from auth import get_current_user
from database import get_db
from models import Course, Enrollment, Lesson, LessonCompletion, Section, User
from schemas import LessonComplete

router = APIRouter(prefix="/api", tags=["learning"])


def progress_for(db: Session, user_id: int, course_id: int) -> tuple[int, int, int]:
    total = db.scalar(
        select(func.count(Lesson.id))
        .join(Section, Section.id == Lesson.section_id)
        .where(Section.course_id == course_id)
    ) or 0
    completed = db.scalar(
        select(func.count(LessonCompletion.id))
        .join(Lesson, Lesson.id == LessonCompletion.lesson_id)
        .join(Section, Section.id == Lesson.section_id)
        .where(LessonCompletion.user_id == user_id, Section.course_id == course_id)
    ) or 0
    return total, completed, round(completed * 100 / total) if total else 0


@router.get("/learning/dashboard")
def dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    enrollments = db.scalars(
        select(Enrollment).options(joinedload(Enrollment.course).selectinload(Course.sections).selectinload(Section.lessons))
        .where(Enrollment.user_id == user.id, Enrollment.status == "confirmed")
        .order_by(Enrollment.created_at.desc())
    ).unique().all()
    courses = []
    for enrollment in enrollments:
        total, completed, progress = progress_for(db, user.id, enrollment.course_id)
        first_incomplete = db.scalar(
            select(Lesson.id)
            .join(Section, Section.id == Lesson.section_id)
            .outerjoin(
                LessonCompletion,
                (LessonCompletion.lesson_id == Lesson.id) & (LessonCompletion.user_id == user.id),
            )
            .where(Section.course_id == enrollment.course_id, LessonCompletion.id.is_(None))
            .order_by(Section.position, Lesson.position)
            .limit(1)
        )
        courses.append({
            "course_id": enrollment.course_id,
            "title": enrollment.course.title,
            "slug": enrollment.course.slug,
            "category": enrollment.course.category,
            "instructor": enrollment.course.instructor,
            "progress": progress,
            "completed_lessons": completed,
            "total_lessons": total,
            "continue_lesson_id": first_incomplete,
            "enrolled_at": enrollment.created_at,
        })
    return {
        "courses": courses,
        "enrolled_count": len(courses),
        "completed_count": sum(course["progress"] == 100 for course in courses),
    }


@router.post("/lessons/{lesson_id}/complete")
def complete_lesson(
    lesson_id: int,
    payload: LessonComplete | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    lesson = db.scalar(select(Lesson).options(joinedload(Lesson.section)).where(Lesson.id == lesson_id))
    if lesson is None:
        raise HTTPException(status_code=404, detail="Lesson not found.")
    enrollment = db.scalar(select(Enrollment.id).where(
        Enrollment.user_id == user.id,
        Enrollment.course_id == lesson.section.course_id,
        Enrollment.status == "confirmed",
    ))
    if not enrollment:
        raise HTTPException(status_code=403, detail="Enroll in this course to track lesson progress.")
    completion = db.scalar(select(LessonCompletion).where(
        LessonCompletion.user_id == user.id, LessonCompletion.lesson_id == lesson.id
    ))
    completed_value = payload.completed if payload is not None else True
    if completed_value and completion is None:
        db.add(LessonCompletion(user_id=user.id, lesson_id=lesson.id))
    elif not completed_value and completion is not None:
        db.delete(completion)
    db.commit()
    total, completed, progress = progress_for(db, user.id, lesson.section.course_id)
    return {
        "lesson_id": lesson.id,
        "completed": completed_value,
        "progress": progress,
        "completed_lessons": completed,
        "total_lessons": total,
        "certificate_available": progress == 100,
    }


@router.get("/learning/courses/{course_key}")
def course_player(course_key: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    course_query = select(Course).options(selectinload(Course.sections).selectinload(Section.lessons))
    course_query = course_query.where(Course.id == int(course_key)) if course_key.isdigit() else course_query.where(Course.slug == course_key)
    course = db.scalar(course_query)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found.")
    enrollment = db.scalar(select(Enrollment).where(
        Enrollment.user_id == user.id, Enrollment.course_id == course.id, Enrollment.status == "confirmed"
    ))
    if not enrollment:
        raise HTTPException(status_code=403, detail="Enroll in this course to access the course player.")
    _, _, progress = progress_for(db, user.id, course.id)
    completed_ids = set(db.scalars(select(LessonCompletion.lesson_id).where(LessonCompletion.user_id == user.id)).all())
    return {
        "course_id": course.id,
        "title": course.title,
        "progress": progress,
        "sections": [
            {"id": section.id, "title": section.title, "lessons": [
                {"id": lesson.id, "title": lesson.title, "duration_minutes": lesson.duration_minutes,
                 "completed": lesson.id in completed_ids, "preview": lesson.preview}
                for lesson in sorted(section.lessons, key=lambda row: row.position)
            ]}
            for section in sorted(course.sections, key=lambda row: row.position)
        ],
    }


@router.get("/certificates/{course_id}")
def certificate(course_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found.")
    enrollment = db.scalar(select(Enrollment).where(
        Enrollment.user_id == user.id, Enrollment.course_id == course.id, Enrollment.status == "confirmed"
    ))
    if not enrollment:
        raise HTTPException(status_code=403, detail="Enroll in this course to access a certificate.")
    _, _, progress = progress_for(db, user.id, course.id)
    if progress < 100:
        raise HTTPException(status_code=409, detail="Complete all lessons to earn your certificate.")
    return {
        "learner": user.name,
        "course": course.title,
        "instructor": course.instructor,
        "issued_at": enrollment.created_at,
        "certificate_id": f"EDU-{user.id:05d}-{course.id:04d}",
    }
