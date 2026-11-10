from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.models.booking import Booking, BookingTenant
from app.models.listing import Listing
from app.models.user import User


def token_for(client, username: str) -> str:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": "testpass"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_login_returns_bearer_token(api_client):
    response = api_client["client"].post(
        "/api/auth/login",
        json={"username": "student", "password": "testpass"},
    )

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]


def test_wrong_password_returns_401(api_client):
    response = api_client["client"].post(
        "/api/auth/login",
        json={"username": "student", "password": "wrong"},
    )

    assert response.status_code == 401


def test_student_cannot_create_listing_and_missing_token_is_401(api_client):
    client = api_client["client"]
    body = {
        "title": "Test room",
        "address": "20 Campus Road",
        "distance_to_campus": 1.0,
        "price": 2000,
        "room_type": "Studio",
        "capacity": 1,
        "amenities": "WiFi",
        "description": "A room for API testing.",
        "photos": [],
    }
    student_token = token_for(client, "student")

    forbidden = client.post(
        "/api/listings",
        json=body,
        headers=headers(student_token),
    )
    unauthenticated = client.post("/api/listings", json=body)

    assert forbidden.status_code == 403
    assert unauthenticated.status_code == 401


def test_landlord_submits_admin_approves_and_student_browses(api_client):
    client = api_client["client"]
    landlord_token = token_for(client, "landlord")
    admin_token = token_for(client, "admin")
    student_token = token_for(client, "student")
    body = {
        "title": "New API listing",
        "address": "30 Campus Road",
        "distance_to_campus": 0.8,
        "price": 2400,
        "room_type": "Private room",
        "capacity": 2,
        "amenities": "WiFi",
        "description": "A new listing created in the integration test.",
        "photos": [],
    }

    created = client.post(
        "/api/listings",
        json=body,
        headers=headers(landlord_token),
    )
    assert created.status_code == 201
    listing_id = created.json()["id"]

    submitted = client.post(
        f"/api/listings/{listing_id}/submit",
        headers=headers(landlord_token),
    )
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "pending"

    approved = client.post(
        f"/api/admin/listings/{listing_id}/approve",
        headers=headers(admin_token),
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "verified"

    listings = client.get("/api/listings", headers=headers(student_token))
    assert listings.status_code == 200
    assert listing_id in {item["id"] for item in listings.json()}


def test_student_books_and_landlord_confirms(api_client):
    client = api_client["client"]
    student_token = token_for(client, "student")
    landlord_token = token_for(client, "landlord")
    with Session(api_client["engine"]) as session:
        listing = session.exec(
            select(Listing).where(Listing.title == "Verified test home")
        ).first()
        assert listing is not None
        listing_id = listing.id

    today = datetime.now(timezone.utc).date()
    booking = client.post(
        "/api/bookings",
        json={
            "listing_id": listing_id,
            "move_in_date": (today + timedelta(days=30)).isoformat(),
            "move_out_date": (today + timedelta(days=90)).isoformat(),
            "roommate_usernames": [],
            "message": "Integration booking request.",
        },
        headers=headers(student_token),
    )
    assert booking.status_code == 201
    booking_id = booking.json()["id"]

    decision = client.post(
        f"/api/bookings/{booking_id}/decision",
        json={"decision": "accept", "decline_reason": ""},
        headers=headers(landlord_token),
    )
    assert decision.status_code == 200
    assert decision.json()["status"] == "confirmed"


def test_student_posts_review_and_reads_listing_reviews(api_client):
    client = api_client["client"]
    student_token = token_for(client, "student")
    with Session(api_client["engine"]) as session:
        listing = session.exec(
            select(Listing).where(Listing.status == "verified")
        ).first()
        assert listing is not None
        reviewer = session.exec(
            select(User).where(User.username == "student")
        ).first()
        assert reviewer is not None
        today = datetime.now(timezone.utc).date()
        booking = Booking(
            listingId=listing.id,
            bookerId=reviewer.id,
            moveInDate=today - timedelta(days=60),
            moveOutDate=today - timedelta(days=1),
            status="confirmed",
        )
        session.add(booking)
        session.flush()
        session.add(
            BookingTenant(
                bookingId=booking.id,
                userId=reviewer.id,
                tenantRole="booker",
                response="accepted",
            )
        )
        session.commit()
        booking_id = booking.id
        listing_id = listing.id

    created = client.post(
        f"/api/bookings/{booking_id}/reviews",
        json={
            "rating": 5,
            "comment": "A wonderful stay close to campus.",
        },
        headers=headers(student_token),
    )
    assert created.status_code == 201
    assert created.json()["booking_id"] == booking_id
    assert "passwordHash" not in created.json()

    listing_reviews = client.get(
        f"/api/listings/{listing_id}/reviews",
        headers=headers(student_token),
    )
    assert listing_reviews.status_code == 200
    assert listing_reviews.json()["count"] == 1
    assert listing_reviews.json()["average"] == 5
    assert listing_reviews.json()["reviews"][0]["reviewer_first_name"] == "student"
