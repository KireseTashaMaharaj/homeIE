from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from app.models.booking import Booking, BookingTenant
from app.models.listing import Listing
from app.models.user import User
from app.repositories.booking import BookingRepository
from app.repositories.listing import ListingRepository
from app.repositories.review import ReviewRepository
from app.repositories.user import UserRepository
from app.services.booking_service import BookingService
from app.services.review_service import ReviewService


@pytest.fixture
def booking_context():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as db:
        landlord = User(
            username="landlord",
            email="landlord@example.com",
            passwordHash="not-used",
            role="landlord",
        )
        other_landlord = User(
            username="other",
            email="other@example.com",
            passwordHash="not-used",
            role="landlord",
        )
        student = User(
            username="student",
            email="student@example.com",
            passwordHash="not-used",
            role="student",
        )
        roommate = User(
            username="roommate",
            email="roommate@example.com",
            passwordHash="not-used",
            role="student",
        )
        second_roommate = User(
            username="second",
            email="second@example.com",
            passwordHash="not-used",
            role="student",
        )
        db.add_all([landlord, other_landlord, student, roommate, second_roommate])
        db.commit()
        for user in (landlord, other_landlord, student, roommate, second_roommate):
            db.refresh(user)

        listing = Listing(
            landlordId=landlord.id,
            title="Verified home",
            address="1 Campus Road",
            distanceToCampus=1.0,
            price=2500,
            roomType="Private room",
            capacity=3,
            amenities="WiFi",
            description="A sample listing.",
            status="verified",
        )
        db.add(listing)
        db.commit()
        db.refresh(listing)

        service = BookingService(
            BookingRepository(db),
            ListingRepository(db),
            UserRepository(db),
        )
        yield {
            "db": db,
            "service": service,
            "landlord": landlord,
            "other_landlord": other_landlord,
            "student": student,
            "roommate": roommate,
            "second_roommate": second_roommate,
            "listing": listing,
        }
    engine.dispose()


def request_booking(context, roommate_names: list[str] | None = None) -> Booking:
    return context["service"].create_request(
        listing_id=context["listing"].id,
        booker=context["student"],
        move_in_date=datetime.now(timezone.utc).date() + timedelta(days=30),
        move_out_date=datetime.now(timezone.utc).date() + timedelta(days=120),
        roommate_usernames=roommate_names or [],
        message="",
    )


def create_past_stay(context, roommate=None, move_out_date=None) -> Booking:
    db = context["db"]
    today = datetime.now(timezone.utc).date()
    booking = Booking(
        listingId=context["listing"].id,
        bookerId=context["student"].id,
        moveInDate=today - timedelta(days=90),
        moveOutDate=move_out_date or today - timedelta(days=10),
        status="confirmed",
    )
    db.add(booking)
    db.flush()
    db.add(
        BookingTenant(
            bookingId=booking.id,
            userId=context["student"].id,
            tenantRole="booker",
            response="accepted",
        )
    )
    if roommate is not None:
        db.add(
            BookingTenant(
                bookingId=booking.id,
                userId=roommate.id,
                tenantRole="roommate",
                response="accepted",
            )
        )
    db.commit()
    db.refresh(booking)
    return booking


def review_service(context) -> ReviewService:
    db = context["db"]
    return ReviewService(
        ReviewRepository(db),
        BookingRepository(db),
        UserRepository(db),
    )


def test_all_roommates_accept_before_landlord_review(booking_context):
    booking = request_booking(booking_context, ["roommate", "second"])

    assert booking.status == "pending_roommates"
    still_waiting = booking_context["service"].respond_to_invitation(
        booking.id,
        booking_context["roommate"],
        "accept",
    )
    assert still_waiting.status == "pending_roommates"
    updated = booking_context["service"].respond_to_invitation(
        booking.id,
        booking_context["second_roommate"],
        "accept",
    )

    assert updated.status == "pending_landlord"


def test_only_invited_student_can_respond_and_only_once(booking_context):
    booking = request_booking(booking_context, ["roommate"])
    service = booking_context["service"]
    with pytest.raises(ValueError, match="active invitation"):
        service.respond_to_invitation(
            booking.id,
            booking_context["second_roommate"],
            "accept",
        )

    service.respond_to_invitation(
        booking.id,
        booking_context["roommate"],
        "accept",
    )
    with pytest.raises(ValueError, match="no longer active"):
        service.respond_to_invitation(
            booking.id,
            booking_context["roommate"],
            "accept",
        )


def test_roommate_decline_cancels_and_is_visible_to_lead(booking_context):
    booking = request_booking(booking_context, ["roommate"])
    updated = booking_context["service"].respond_to_invitation(
        booking.id,
        booking_context["roommate"],
        "decline",
    )

    assert updated.status == "cancelled"
    student_rows = booking_context["service"].get_student_bookings(
        booking_context["student"]
    )
    declined_rows = [
        person
        for item in student_rows
        for person in item["tenants"]
        if person["tenant"].response == "declined"
    ]
    assert [person["user"].username for person in declined_rows] == ["roommate"]


def test_landlord_does_not_see_requests_waiting_on_roommates(booking_context):
    request_booking(booking_context, ["roommate"])

    assert booking_context["service"].get_landlord_bookings(
        booking_context["landlord"],
        "pending",
    ) == []


def test_landlord_ownership_and_decline_reason_are_enforced(booking_context):
    booking = request_booking(booking_context)
    service = booking_context["service"]
    with pytest.raises(ValueError, match="not found"):
        service.decide_as_landlord(
            booking.id,
            booking_context["other_landlord"],
            "accept",
        )
    with pytest.raises(ValueError, match="reason is required"):
        service.decide_as_landlord(
            booking.id,
            booking_context["landlord"],
            "decline",
        )

    declined = service.decide_as_landlord(
        booking.id,
        booking_context["landlord"],
        "decline",
        "Dates unavailable.",
    )
    assert declined.status == "declined"
    assert declined.declineReason == "Dates unavailable."


def test_only_booker_can_cancel_and_verified_listings_are_required(booking_context):
    booking = request_booking(booking_context)
    with pytest.raises(ValueError, match="not found"):
        booking_context["service"].cancel_booking(
            booking.id,
            booking_context["roommate"],
        )
    cancelled = booking_context["service"].cancel_booking(
        booking.id,
        booking_context["student"],
    )
    assert cancelled.status == "cancelled"

    booking_context["listing"].status = "pending"
    booking_context["db"].add(booking_context["listing"])
    booking_context["db"].commit()
    with pytest.raises(ValueError, match="not found"):
        booking_context["service"].get_verified_listing(
            booking_context["listing"].id,
            booking_context["student"],
        )


def test_only_a_tenant_on_a_past_confirmed_booking_can_review(booking_context):
    booking = create_past_stay(booking_context)
    service = review_service(booking_context)

    with pytest.raises(ValueError, match="Only tenants"):
        service.create_review(
            booking.id,
            booking_context["roommate"],
            5,
            "A lovely place and a very kind landlord.",
        )

    upcoming = create_past_stay(
        booking_context,
        move_out_date=datetime.now(timezone.utc).date() + timedelta(days=1),
    )
    with pytest.raises(ValueError, match="after your move-out"):
        service.create_review(
            upcoming.id,
            booking_context["student"],
            5,
            "A lovely place and a very kind landlord.",
        )

    landlord = booking_context["landlord"]
    with pytest.raises(ValueError, match="Only students"):
        service.create_review(
            booking.id,
            landlord,
            5,
            "A lovely place and a very kind landlord.",
        )


def test_accepted_roommate_can_review_and_only_once(booking_context):
    booking = create_past_stay(booking_context, booking_context["roommate"])
    service = review_service(booking_context)

    review = service.create_review(
        booking.id,
        booking_context["roommate"],
        4,
        "A comfortable room with a very helpful landlord.",
    )

    assert review.bookingId == booking.id
    assert review.reviewerId == booking_context["roommate"].id
    assert review.isRemoved is False
    with pytest.raises(ValueError, match="already reviewed"):
        service.create_review(
            booking.id,
            booking_context["roommate"],
            5,
            "Trying to add a second review for the same stay.",
        )


def test_review_rating_and_comment_limits_are_enforced(booking_context):
    booking = create_past_stay(booking_context)
    service = review_service(booking_context)

    with pytest.raises(ValueError, match="between 1 and 5"):
        service.create_review(
            booking.id,
            booking_context["student"],
            6,
            "A lovely place and a very kind landlord.",
        )
    with pytest.raises(ValueError, match="at least 20"):
        service.create_review(
            booking.id,
            booking_context["student"],
            5,
            "Too short",
        )
    with pytest.raises(ValueError, match="1000 characters or fewer"):
        service.create_review(
            booking.id,
            booking_context["student"],
            5,
            "x" * 1001,
        )
