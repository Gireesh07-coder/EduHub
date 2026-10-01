from fastapi import APIRouter, Depends, status
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from database import get_db
from models import Message, NewsletterSubscriber
from schemas import ContactCreate, NewsletterCreate

router = APIRouter(prefix="/api", tags=["contact"])


@router.post("/contact", status_code=status.HTTP_201_CREATED)
def send_message(payload: ContactCreate, db: Session = Depends(get_db)):
    message = Message(email=str(payload.email).lower(), message=payload.message)
    db.add(message)
    db.commit()
    print(f"[EduHub contact inbox] New contact message #{message.id} from {message.email}")
    return {"message": "Thanks for reaching out. Your message has been sent."}


@router.post("/newsletter/subscribe", status_code=status.HTTP_201_CREATED)
def subscribe(payload: NewsletterCreate, db: Session = Depends(get_db)):
    email = str(payload.email).lower()
    if db.scalar(select(NewsletterSubscriber.id).where(NewsletterSubscriber.email == email)):
        raise HTTPException(status_code=409, detail="This email is already subscribed.")
    db.add(NewsletterSubscriber(email=email))
    db.commit()
    print(f"[EduHub mock newsletter confirmation] Confirmation requested for {email}")
    return {"message": "You're on the list. Look out for a welcome note from EduHub."}
