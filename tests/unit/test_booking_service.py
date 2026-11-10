from datetime import datetime, timedelta, timezone

import pytest


def future_dates():
    today = datetime.now(timezone.utc).date()
    return today + timedelta(days=30), today + timedelta(days=90)


def request_booking(service, listing, student, roommates=None, move_in=None, move_out=None):
    default_in, default_out = future_dates()
    return service.create_request(
        listing_id=listing.id,
        booker=student,
        move_in_date=move_in or default_in,
        move_out_date=move_out or default_out,
        roommate_usernames=roommates or [],
        message="",
    )


def test_move_in_must_be_in_the_future(
    booking_service, verified_listing, users
):
    today = datetime.now(timezone.utc).date()

    with pytest.raises(ValueError, match="future"):
        request_booking(
            booking_service,
            verified_listing,
            users["student"],
            move_in=today,
            move_out=today + timedelta(days=30),
        )


def test_move_out_must_be_after_move_in(booking_service, verified_listing, users):
    move_in, _ = future_dates()

    with pytest.raises(ValueError, match="after move-in"):
        request_booking(
            booking_service,
            verified_listing,
            users["student"],
            move_in=move_in,
            move_out=move_in,
        )


def test_duplicate_active_request_is_refused(
    booking_service, verified_listing, users
):
    request_booking(booking_service, verified_listing, users["student"])

    with pytest.raises(ValueError, match="active request"):
        request_booking(booking_service, verified_listing, users["student"])


def test_student_cannot_invite_themself(booking_service, verified_listing, users):
    with pytest.raises(ValueError, match="invite yourself"):
        request_booking(
            booking_service,
            verified_listing,
            users["student"],
            roommates=["student"],
        )


def test_roommates_cannot_exceed_listing_capacity(
    booking_service, verified_listing, users
):
    with pytest.raises(ValueError, match="sleeps 2"):
        request_booking(
            booking_service,
            verified_listing,
            users["student"],
            roommates=["roommate", "second-student"],
        )


def test_only_pending_bookings_can_be_cancelled(
    booking_service, verified_listing, users
):
    booking = request_booking(booking_service, verified_listing, users["student"])
    booking_service.decide_as_landlord(
        booking.id,
        users["landlord"],
        "accept",
    )

    with pytest.raises(ValueError, match="Only pending bookings"):
        booking_service.cancel_booking(booking.id, users["student"])


def test_landlord_decline_requires_a_reason(
    booking_service, verified_listing, users
):
    booking = request_booking(booking_service, verified_listing, users["student"])

    with pytest.raises(ValueError, match="reason is required"):
        booking_service.decide_as_landlord(
            booking.id,
            users["landlord"],
            "decline",
        )

    declined = booking_service.decide_as_landlord(
        booking.id,
        users["landlord"],
        "decline",
        "The dates are unavailable.",
    )
    assert declined.status == "declined"
