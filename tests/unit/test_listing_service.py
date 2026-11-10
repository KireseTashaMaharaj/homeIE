import pytest


def listing_values(**overrides: str) -> dict[str, str]:
    values = {
        "title": "Sunny student room",
        "address": "10 Campus Road",
        "distance_to_campus": "1.0",
        "price": "2500",
        "room_type": "Private room",
        "capacity": "2",
        "amenities": "WiFi",
        "description": "A bright room close to campus.",
    }
    values.update(overrides)
    return values


def create_pending_listing(service, landlord_id: int):
    return service.create_listing(
        landlord_id=landlord_id,
        values=listing_values(),
        photo_urls="",
        submit=True,
    )


def test_create_listing_starts_as_draft(listing_service, users):
    listing = listing_service.create_listing(
        landlord_id=users["landlord"].id,
        values=listing_values(),
        photo_urls="",
        submit=False,
    )

    assert listing.status == "draft"


def test_bad_price_is_refused(listing_service, users):
    with pytest.raises(ValueError, match="positive"):
        listing_service.create_listing(
            users["landlord"].id,
            listing_values(price="0"),
            "",
            False,
        )


def test_bad_room_type_is_refused(listing_service, users):
    with pytest.raises(ValueError, match="room types"):
        listing_service.create_listing(
            users["landlord"].id,
            listing_values(room_type="Tent"),
            "",
            False,
        )


def test_submit_moves_listing_to_pending(listing_service, users):
    listing = listing_service.create_listing(
        users["landlord"].id,
        listing_values(),
        "",
        False,
    )

    submitted = listing_service.submit_listing(listing.id, users["landlord"].id)

    assert submitted.status == "pending"


def test_admin_approval_makes_listing_verified(listing_service, users):
    listing = create_pending_listing(listing_service, users["landlord"].id)

    approved = listing_service.moderate_listing(listing.id, approved=True)

    assert approved.status == "verified"


def test_admin_rejection_needs_a_reason(listing_service, users):
    listing = create_pending_listing(listing_service, users["landlord"].id)

    with pytest.raises(ValueError, match="rejection reason is required"):
        listing_service.moderate_listing(
            listing.id,
            approved=False,
            rejection_reason=" ",
        )

    rejected = listing_service.moderate_listing(
        listing.id,
        approved=False,
        rejection_reason="Add a clear photo.",
    )
    assert rejected.status == "rejected"
