import os
import re

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["ADMIN_EMAIL"] = "test-admin@eduhub.example.com"
os.environ["ADMIN_PASSWORD"] = "TestAdmin123!"

import pytest
from fastapi.testclient import TestClient

from database import Base, engine
from main import app

LEARNER_EMAIL = "learner@example.com"
LEARNER_PASSWORD = "securePass123"
ADMIN_EMAIL = "test-admin@eduhub.example.com"


@pytest.fixture()
def client():
    Base.metadata.drop_all(bind=engine)
    with TestClient(app) as test_client:
        yield test_client
    Base.metadata.drop_all(bind=engine)


def register(client: TestClient, email: str = LEARNER_EMAIL):
    return client.post(
        "/api/auth/register",
        json={"name": "Test Learner", "email": email, "password": LEARNER_PASSWORD},
    )


def admin_login(client: TestClient):
    return client.post(
        "/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": "TestAdmin123!"},
    )


def checkout_course(client: TestClient, course_id: int, **kwargs):
    return client.post(
        "/api/checkout",
        json={
            "course_ids": [course_id],
            "payment_method": "card",
            "last4": "4242",
            **kwargs,
        },
    )


def test_auth_profile_validation_and_security_headers(client: TestClient):
    response = register(client)
    assert response.status_code == 201
    assert response.json()["email_verified"] is False
    assert "httponly" in response.headers["set-cookie"].lower()
    assert response.headers["x-content-type-options"] == "nosniff"
    assert client.get("/api/me").json()["name"] == "Test Learner"
    assert client.put("/api/me", json={"name": "Updated", "age": 22, "phone": "+1 212 555 0100"}).status_code == 200
    assert client.post("/api/auth/verify-email").json()["message"]
    assert client.get("/api/me").json()["email_verified"] is True
    client.post("/api/auth/logout")
    login = client.post("/api/auth/login", json={"email": LEARNER_EMAIL, "password": LEARNER_PASSWORD})
    assert login.status_code == 200
    invalid = client.post(
        "/api/auth/register",
        json={"name": "Learner", "email": "not-an-email", "password": "short"},
    )
    assert invalid.status_code == 422
    assert invalid.json()["detail"] == "Input validation failed."
    assert "errors" in invalid.json()
    assert client.post("/api/auth/login", json={"email": LEARNER_EMAIL, "password": "wrong-password"}).status_code == 401


def test_catalog_search_filters_sort_and_pagination(client: TestClient):
    courses = client.get("/api/courses")
    assert courses.status_code == 200
    assert len(courses.json()) >= 12
    assert courses.headers["x-total-count"] == str(len(courses.json()))
    page = client.get("/api/courses?category=Technology&level=Beginner&max_price=100&page=1&per_page=2")
    assert page.status_code == 200
    assert 1 <= len(page.json()) <= 2
    assert all(row["category"] == "Technology" and row["level"] == "Beginner" for row in page.json())
    search = client.get("/api/courses?q=python")
    assert search.status_code == 200 and "Python" in search.json()[0]["title"]
    sorted_by_price = client.get("/api/courses?sort=price").json()
    prices = [row["discounted_price"] or row["price"] for row in sorted_by_price]
    assert prices == sorted(prices)
    assert len(client.get("/api/categories").json()) >= 4
    course = courses.json()[0]
    assert client.get(f"/api/courses/{course['slug']}").json()["sections"]
    assert client.get("/api/courses/not-a-course").status_code == 404
    assert client.get("/api/courses?sort=invalid").status_code == 422


def test_cart_coupon_checkout_duplicates_and_receipt(client: TestClient):
    assert register(client).status_code == 201
    courses = client.get("/api/courses").json()
    assert client.post("/api/cart", json={"course_id": courses[0]["id"]}).status_code == 201
    assert client.post("/api/cart", json={"course_id": courses[1]["id"]}).status_code == 201
    assert len(client.get("/api/cart").json()["items"]) == 2
    subtotal = sum(item["discounted_price"] or item["price"] for item in courses[:2])
    coupon = client.post("/api/coupons/validate", json={"code": "WELCOME10", "subtotal": subtotal})
    assert coupon.status_code == 200
    assert coupon.json()["discount"] > 0
    assert client.post("/api/coupons/validate", json={"code": "NOPE", "subtotal": 100}).status_code == 400
    order = client.post("/api/checkout", json={
        "course_ids": [courses[0]["id"], courses[1]["id"]],
        "coupon_code": "WELCOME10",
        "payment_method": "card",
        "last4": "4242",
    })
    assert order.status_code == 201, order.text
    data = order.json()
    assert data["invoice_number"].startswith("EH-")
    assert data["total"] < data["subtotal"]
    assert data["payment_last4"] == "4242"
    assert len(data["items"]) == 2
    assert len(client.get("/api/enrollments/me").json()) == 2
    assert client.get("/api/orders/me").json()[0]["id"] == data["id"]
    assert client.get(f"/api/orders/{data['id']}").status_code == 200
    assert client.get("/api/orders/99999").status_code == 404
    assert client.post("/api/checkout", json={
        "course_ids": [courses[0]["id"]], "payment_method": "upi"
    }).status_code == 409
    assert client.get("/api/cart").json()["items"] == []
    assert client.post("/api/cart", json={"course_id": courses[0]["id"]}).status_code == 409
    assert client.post("/api/checkout", json={
        "course_ids": [courses[2]["id"]], "payment_method": "card", "last4": "4111 1111"
    }).status_code == 422


def test_coupon_usage_limit_and_admin_crud(client: TestClient):
    assert admin_login(client).status_code == 200
    coupon = client.post("/api/admin/coupons", json={
        "code": "ONEUSE", "kind": "fixed", "value": 10, "usage_limit": 1
    })
    assert coupon.status_code == 201, coupon.text
    course = client.get("/api/courses").json()[0]
    assert register(client).status_code == 201
    result = checkout_course(client, course["id"], coupon_code="ONEUSE")
    assert result.status_code == 201, result.text
    validate = client.post("/api/coupons/validate", json={"code": "ONEUSE", "subtotal": 90})
    assert validate.status_code == 409
    assert admin_login(client).status_code == 200
    assert client.get("/api/admin/courses").status_code == 200
    created = client.post("/api/admin/courses", json={
        "title": "A New Practical Course",
        "description": "A thoughtful description long enough for the API validation rules.",
        "level": "Beginner",
        "price": 50,
        "category": "Design",
        "instructor": "Nina Kapoor",
        "duration_hours": 5,
        "discounted_price": 40,
        "language": "English",
    })
    assert created.status_code == 201, created.text
    changed = client.put(f"/api/admin/courses/{created.json()['id']}", json={
        "title": "A New Practical Course Updated",
        "description": "A refreshed thoughtful description long enough for the API validation rules.",
        "level": "Intermediate",
        "price": 60,
        "category": "Design",
        "instructor": "Nina Kapoor",
        "duration_hours": 6,
        "language": "English",
    })
    assert changed.status_code == 200
    category = client.post("/api/admin/categories", json={"name": "Wellbeing"})
    assert category.status_code == 201
    assert client.delete(f"/api/admin/categories/{category.json()['id']}").status_code == 200


def test_review_permissions_wishlist_and_lesson_progress(client: TestClient):
    courses = client.get("/api/courses").json()
    course = courses[0]
    assert register(client).status_code == 201
    assert client.post(f"/api/courses/{course['id']}/reviews", json={"rating": 5, "comment": "Great"}).status_code == 403
    assert client.post("/api/wishlist", json={"course_id": course["id"]}).status_code == 201
    assert client.get("/api/wishlist").json()["items"][0]["course_id"] == course["id"]
    assert client.delete(f"/api/wishlist/{course['id']}").status_code == 200
    order = checkout_course(client, course["id"])
    assert order.status_code == 201, order.text
    review = client.post(f"/api/courses/{course['id']}/reviews", json={"rating": 5, "comment": "<script>hello</script>"})
    assert review.status_code == 201
    assert client.post(f"/api/courses/{course['id']}/reviews", json={"rating": 4}).status_code == 409
    player = client.get(f"/api/learning/courses/{course['slug']}")
    assert player.status_code == 200
    lessons = [lesson for section in player.json()["sections"] for lesson in section["lessons"]]
    assert len(lessons) >= 3
    assert client.get(f"/api/certificates/{course['id']}").status_code == 409
    for lesson in lessons:
        result = client.post(f"/api/lessons/{lesson['id']}/complete", json={})
        assert result.status_code == 200, result.text
    assert result.json()["progress"] == 100
    assert client.get(f"/api/certificates/{course['id']}").status_code == 200
    assert client.get("/api/learning/dashboard").json()["completed_count"] == 1


def test_password_reset_is_one_time_and_profile_account_features(client: TestClient, capsys):
    assert register(client).status_code == 201
    assert client.post("/api/auth/forgot-password", json={"email": LEARNER_EMAIL}).status_code == 200
    output = capsys.readouterr().out
    token = re.search(r"reset-password\.html\?token=([A-Za-z0-9_-]+)", output).group(1)
    reset = client.post("/api/auth/reset-password", json={"token": token, "password": "replacement123"})
    assert reset.status_code == 200
    assert client.post("/api/auth/reset-password", json={"token": token, "password": "anotherPass123"}).status_code == 400
    client.post("/api/auth/logout")
    assert client.post("/api/auth/login", json={"email": LEARNER_EMAIL, "password": LEARNER_PASSWORD}).status_code == 401
    assert client.post("/api/auth/login", json={"email": LEARNER_EMAIL, "password": "replacement123"}).status_code == 200
    assert client.post("/api/auth/change-password", json={
        "current_password": "replacement123", "new_password": "anotherPass123"
    }).status_code == 200
    assert client.post("/api/newsletter/subscribe", json={"email": "news@example.com"}).status_code == 201
    assert client.post("/api/newsletter/subscribe", json={"email": "news@example.com"}).status_code == 409


def test_admin_access_messages_enrollment_cancel_and_headers(client: TestClient):
    assert client.get("/api/admin/stats").status_code == 401
    assert register(client).status_code == 201
    assert client.get("/api/admin/enrollments").status_code == 403
    assert client.post("/api/contact", json={"email": LEARNER_EMAIL, "message": "Please call me."}).status_code == 201
    admin_login(client)
    assert client.get("/api/admin/messages").json()[0]["is_read"] is False
    message = client.get("/api/admin/messages").json()[0]
    assert client.patch(f"/api/admin/messages/{message['id']}/read").json()["is_read"] is True
    assert client.get("/api/admin/stats").status_code == 200
    assert "invoice" in client.get("/api/admin/orders.csv").text
    assert client.get("/api/admin/users").json()["total"] >= 2
    users = client.get("/api/admin/users").json()["items"]
    learner = next(row for row in users if row["email"] == LEARNER_EMAIL)
    assert client.patch(f"/api/admin/users/{learner['id']}/active?enabled=false").status_code == 200
    client.post("/api/auth/logout")
    assert client.post("/api/auth/login", json={"email": LEARNER_EMAIL, "password": LEARNER_PASSWORD}).status_code == 403


def test_legacy_enrollment_endpoint_still_works_and_cancel_is_scoped(client: TestClient):
    assert client.post("/api/enrollments", json={
        "course_id": 1, "name": "Guest", "age": 20, "email": LEARNER_EMAIL,
        "phone": "2125550100", "payment_method": "credit",
    }).status_code == 401
    assert register(client).status_code == 201
    enrollment = client.post("/api/enrollments", json={
        "course_id": 1, "name": "Test Learner", "age": 20, "email": LEARNER_EMAIL,
        "phone": "2125550100", "payment_method": "credit",
    })
    assert enrollment.status_code == 201, enrollment.text
    assert client.post("/api/enrollments", json={
        "course_id": 1, "name": "Test Learner", "age": 20, "email": LEARNER_EMAIL,
        "phone": "2125550100", "payment_method": "credit",
    }).status_code == 409
    assert client.delete(f"/api/enrollments/{enrollment.json()['id']}").status_code == 200
    assert client.get("/api/enrollments/me").json()[0]["status"] == "canceled"


def test_login_attempt_rate_limit(client: TestClient):
    for _ in range(8):
        response = client.post(
            "/api/auth/login",
            json={"email": "rate-limit@example.com", "password": "wrong-password"},
        )
        assert response.status_code == 401
    limited = client.post(
        "/api/auth/login",
        json={"email": "rate-limit@example.com", "password": "wrong-password"},
    )
    assert limited.status_code == 429
