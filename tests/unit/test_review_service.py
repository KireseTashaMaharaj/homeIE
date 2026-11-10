from datetime import datetime, timedelta, timezone

import pytest

from app.models.booking import Booking, BookingTenant


def add_stay(
    db_session,
    listing,
    booker,
    *,
    status="confirmed",
    move_out=None,
):
    today = datetime.now(timezone.utc).date()
    booking = Booking(
        listingId=listing.id,
        bookerId=booker.id,
        moveInDate=today - timedelta(days=60),
        moveOutDate=move_out or today - timedelta(days=1),
        status=status,
    )
    db_session.add(booking)
    db_session.flush()
    db_session.add(
        BookingTenant(
            bookingId=booking.id,
            userId=booker.id,
            tenantRole="booker",
            response="accepted",
        )
    )
    db_session.commit()
    db_session.refresh(booking)
    return booking


def submit_review(service, booking, reviewer, rating=5, comment=None):
    return service.create_review(
        booking.id,
        reviewer,
        rating,
        comment or "A comfortable stay near campus.",
    )


def test_only_confirmed_stays_can_be_reviewed(
    db_session, review_service, verified_listing, users
):
    booking = add_stay(
        db_session,
        verified_listing,
        users["student"],
        status="pending_landlord",
    )

    with pytest.raises(ValueError, match="Only confirmed stays"):
        submit_review(review_service, booking, users["student"])


def test_only_a_tenant_can_review(
    db_session, review_service, verified_listing, users
):
    booking = add_stay(db_session, verified_listing, users["student"])

    with pytest.raises(ValueError, match="Only tenants"):
        submit_review(review_service, booking, users["roommate"])


def test_review_is_not_allowed_before_move_out(
    db_session, review_service, verified_listing, users
):
    booking = add_stay(
        db_session,
        verified_listing,
        users["student"],
        move_out=datetime.now(timezone.utc).date() + timedelta(days=1),
    )

    with pytest.raises(ValueError, match="after your move-out"):
        submit_review(review_service, booking, users["student"])


def test_booking_can_only_be_reviewed_once(
    db_session, review_service, verified_listing, users
):
    booking = add_stay(db_session, verified_listing, users["student"])
    submit_review(review_service, booking, users["student"])

    with pytest.raises(ValueError, match="already reviewed"):
        submit_review(review_service, booking, users["student"])


def test_rating_must_be_from_one_to_five(
    db_session, review_service, verified_listing, users
):
    booking = add_stay(db_session, verified_listing, users["student"])

    for rating in (0, 6):
        with pytest.raises(ValueError, match="between 1 and 5"):
            submit_review(review_service, booking, users["student"], rating=rating)


def test_comment_must_be_at_least_twenty_characters(
    db_session, review_service, verified_listing, users
):
    booking = add_stay(db_session, verified_listing, users["student"])

    with pytest.raises(ValueError, match="at least 20"):
        submit_review(
            review_service,
            booking,
            users["student"],
            comment="Too short",
        )
