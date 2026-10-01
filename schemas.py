import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


PHONE_PATTERN = re.compile(r"^\+?[\d\s().-]{7,24}$")


def validate_phone(value: str) -> str:
    value = value.strip()
    digits = sum(character.isdigit() for character in value)
    if not PHONE_PATTERN.fullmatch(value) or not 7 <= digits <= 15:
        raise ValueError("Enter a valid phone number.")
    return value


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name is required.")
        return value

    @field_validator("password")
    @classmethod
    def password_byte_limit(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be no longer than 72 bytes.")
        return value


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=72)

    @field_validator("password")
    @classmethod
    def password_byte_limit(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be no longer than 72 bytes.")
        return value


class UserUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    age: int | None = Field(default=None, ge=5, le=100)
    phone: str | None = Field(default=None, max_length=30)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name is required.")
        return value

    @field_validator("phone")
    @classmethod
    def clean_phone(cls, value: str | None) -> str | None:
        return validate_phone(value) if value else value


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: EmailStr
    age: int | None
    phone: str | None
    is_admin: bool
    email_verified: bool = False


class CoursePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    description: str
    level: str
    price: float
    slug: str = ""
    category: str = "Learning"
    thumbnail_url: str = ""
    instructor: str = "EduHub Faculty"
    duration_hours: int = 1
    rating_avg: float = 0
    rating_count: int = 0
    language: str = "English"
    is_published: bool = True
    discounted_price: float | None = None
    created_at: datetime


class EnrollmentCreate(BaseModel):
    course_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=100)
    age: int = Field(ge=5, le=100)
    email: EmailStr
    phone: str = Field(min_length=7, max_length=30)
    payment_method: Literal["paypal", "credit", "debit"]

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name is required.")
        return value

    @field_validator("phone")
    @classmethod
    def clean_phone(cls, value: str) -> str:
        return validate_phone(value)


class EnrollmentPublic(BaseModel):
    id: int
    course_id: int
    course_title: str
    name: str
    age: int
    email: EmailStr
    phone: str
    payment_method: str
    status: str
    created_at: datetime


class ContactCreate(BaseModel):
    email: EmailStr
    message: str = Field(min_length=1, max_length=5000)

    @field_validator("message")
    @classmethod
    def clean_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message is required.")
        return value


class MessagePublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    message: str
    created_at: datetime
    is_read: bool = False


class ReviewCreate(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str = Field(default="", max_length=2000)

    @field_validator("comment")
    @classmethod
    def trim_comment(cls, value: str) -> str:
        return value.strip()


class CartAdd(BaseModel):
    course_id: int = Field(gt=0)


class CheckoutCreate(BaseModel):
    course_ids: list[int] = Field(min_length=1, max_length=20)
    coupon_code: str | None = Field(default=None, max_length=40)
    payment_method: Literal["card", "upi", "paypal"]
    last4: str | None = Field(default=None, pattern=r"^\d{4}$")

    @field_validator("course_ids")
    @classmethod
    def unique_courses(cls, value: list[int]) -> list[int]:
        if len(value) != len(set(value)):
            raise ValueError("Cart contains duplicate courses.")
        return value

    @field_validator("coupon_code")
    @classmethod
    def clean_coupon(cls, value: str | None) -> str | None:
        return value.strip().upper() if value else None


class CouponValidate(BaseModel):
    code: str = Field(min_length=1, max_length=40)
    subtotal: float = Field(ge=0, le=1000000)


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordReset(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    password: str = Field(min_length=8, max_length=72)

    @field_validator("password")
    @classmethod
    def password_byte_limit(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be no longer than 72 bytes.")
        return value


class ChangePassword(BaseModel):
    current_password: str = Field(min_length=1, max_length=72)
    new_password: str = Field(min_length=8, max_length=72)

    @field_validator("current_password")
    @classmethod
    def current_password_byte_limit(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be no longer than 72 bytes.")
        return value

    @field_validator("new_password")
    @classmethod
    def password_byte_limit(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be no longer than 72 bytes.")
        return value


class NewsletterCreate(BaseModel):
    email: EmailStr


class CourseUpsert(BaseModel):
    title: str = Field(min_length=3, max_length=150)
    description: str = Field(min_length=20, max_length=10000)
    level: str = Field(min_length=2, max_length=50)
    price: float = Field(ge=0, le=100000)
    category: str = Field(min_length=2, max_length=80)
    thumbnail_url: str = Field(default="", max_length=255)
    instructor: str = Field(min_length=2, max_length=120)
    duration_hours: int = Field(ge=1, le=1000)
    discounted_price: float | None = Field(default=None, ge=0, le=100000)
    language: str = Field(default="English", min_length=2, max_length=50)
    is_published: bool = True

    @field_validator("discounted_price")
    @classmethod
    def discounted_price_below_regular(cls, value: float | None, info):
        regular_price = info.data.get("price")
        if value is not None and regular_price is not None and value > regular_price:
            raise ValueError("Discounted price cannot exceed the regular price.")
        return value


class CategoryCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)


class CouponCreate(BaseModel):
    code: str = Field(min_length=3, max_length=40)
    kind: Literal["percent", "fixed"]
    value: float = Field(gt=0, le=100000)
    expires_at: datetime | None = None
    usage_limit: int | None = Field(default=None, gt=0)


class LessonComplete(BaseModel):
    completed: bool = True


class EnrollmentPublic(BaseModel):
    id: int
    course_id: int
    course_title: str
    name: str
    age: int
    email: EmailStr
    phone: str
    payment_method: str
    status: str
    created_at: datetime
    order_id: int | None = None
    progress: int = 0
