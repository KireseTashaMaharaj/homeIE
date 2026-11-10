from datetime import date, datetime, timezone

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from app.models.booking import Booking, BookingTenant
from app.models.listing import Listing
from app.models.review import Review
from app.models.user import User
from app.seed_data import _seed_past_confirmed_bookings


def test_past_booking_seeds_are_idempotent_and_leave_reviews_unchanged():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            users = {
                username: User(
                    username=username,
                    email=f"{username}@example.com",
                    passwordHash="not-used",
                    role="student" if username != "dev" else "landlord",
                )
                for username in ("bob", "sara", "dev")
            }
            session.add_all(users.values())
            session.commit()
            for user in users.values():
                session.refresh(user)

            verified_listings = {
                title: Listing(
                    landlordId=users["dev"].id,
                    title=title,
                    address=f"{index} Campus Road",
                    distanceToCampus=1.0,
                    price=2000,
                    roomType="Studio",
                    capacity=2,
                    amenities="WiFi",
                    description="Seed test listing.",
                    status="verified",
                )
                for index, title in enumerate(
                    (
                        "Room near campus",
                        "Shared flat, 3 bedroom",
                        "Courtyard student suite",
                    ),
                    start=1,
                )
            }
            session.add_all(verified_listings.values())
            session.commit()
            for listing in verified_listings.values():
                session.refresh(listing)

            existing_sara_booking = Booking(
                listingId=verified_listings["Shared flat, 3 bedroom"].id,
                bookerId=users["sara"].id,
                moveInDate=datetime(2024, 1, 1, tzinfo=timezone.utc).date(),
                moveOutDate=datetime(2024, 2, 1, tzinfo=timezone.utc).date(),
                status="confirmed",
            )
            session.add(existing_sara_booking)
            session.commit()
            session.refresh(existing_sara_booking)
            session.add(
                BookingTenant(
                    bookingId=existing_sara_booking.id,
                    userId=users["sara"].id,
                    tenantRole="booker",
                    response="accepted",
                )
            )
            original_review = Review(
                bookingId=existing_sara_booking.id,
                reviewerId=users["sara"].id,
                rating=5,
                comment="Existing Sara review stays unchanged.",
            )
            session.add(original_review)
            session.commit()
            session.refresh(original_review)
            original_review_id = original_review.id

            _seed_past_confirmed_bookings(session, users, verified_listings)
            bookings_after_first_run = list(session.exec(select(Booking)).all())
            users_after_first_run = list(session.exec(select(User)).all())
            listings_after_first_run = list(session.exec(select(Listing)).all())

            _seed_past_confirmed_bookings(session, users, verified_listings)
            all_bookings = list(session.exec(select(Booking)).all())
            all_reviews = list(session.exec(select(Review)).all())

            added = [
                booking
                for booking in all_bookings
                if booking.id != existing_sara_booking.id
            ]
            assert len(added) == 4
            assert len({booking.listingId for booking in added}) == 3
            listings_by_id = {
                listing.id: listing.title for listing in verified_listings.values()
            }
            booker_names = {
                user.id: username for username, user in users.items()
            }
            assert {
                (
                    listings_by_id[booking.listingId],
                    booker_names[booking.bookerId],
                    booking.moveInDate,
                    booking.moveOutDate,
                )
                for booking in added
            } == {
                ("Room near campus", "bob", date(2025, 1, 10), date(2025, 3, 10)),
                (
                    "Shared flat, 3 bedroom",
                    "bob",
                    date(2025, 4, 10),
                    date(2025, 6, 10),
                ),
                (
                    "Courtyard student suite",
                    "sara",
                    date(2025, 7, 10),
                    date(2025, 9, 10),
                ),
                ("Room near campus", "bob", date(2025, 10, 10), date(2025, 12, 10)),
            }
            assert len(all_bookings) == len(bookings_after_first_run)
            assert len(list(session.exec(select(User)).all())) == len(
                users_after_first_run
            )
            assert len(list(session.exec(select(Listing)).all())) == len(
                listings_after_first_run
            )
            assert len(all_reviews) == 1
            assert all_reviews[0].id == original_review_id
            assert all_reviews[0].comment == "Existing Sara review stays unchanged."
            assert all(
                booking.status == "confirmed"
                and booking.moveOutDate < datetime.now(timezone.utc).date()
                for booking in added
            )
            for booking in added:
                tenants = list(
                    session.exec(
                        select(BookingTenant).where(
                            BookingTenant.bookingId == booking.id
                        )
                    ).all()
                )
                assert len(tenants) == 1
                assert tenants[0].tenantRole == "booker"
                assert tenants[0].response == "accepted"
                assert not session.exec(
                    select(Review.id).where(Review.bookingId == booking.id)
                ).first()
    finally:
        engine.dispose()
