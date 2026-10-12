from datetime import date, datetime, timedelta, timezone

from sqlmodel import select

from app.database import ensure_db_and_tables, get_cli_session
from app.models.booking import Booking, BookingTenant
from app.models.listing import Listing
from app.models.review import Review
from app.models.user import UserBase
from app.repositories.booking import BookingRepository
from app.repositories.listing import ListingRepository
from app.repositories.user import UserRepository
from app.services.listing_service import ListingService
from app.utilities.security import encrypt_password

DEMO_USERS = (
    ("admin", "admin@homeie.com", "adminpass", "homeIE Admin", "admin"),
    ("maria", "maria@homeie.com", "mariapass", "Maria Lopez", "landlord"),
    ("dev", "dev@homeie.com", "devpass", "Dev Ramkissoon", "landlord"),
    ("bob", "bob@homeie.com", "bobpass", "Bob Student", "student"),
    ("sara", "sara@homeie.com", "sarapass", "Sara Student", "student"),
)

DEMO_LISTINGS = (
    {
        "owner": "maria",
        "title": "Room near campus",
        "address": "12 Example Street, Tunapuna",
        "distance": "1.2",
        "price": "1800",
        "room_type": "Private room",
        "capacity": "3",
        "amenities": "WiFi, air conditioning, laundry",
        "description": "A bright, furnished room in a friendly shared home, a short ride from campus.",
        "photos": "/static/img/listings/student-studio.svg\n/static/img/listings/courtyard-room.svg",
        "state": "verified",
    },
    {
        "owner": "maria",
        "title": "Double occupancy near campus",
        "address": "8 Palm Avenue, St. Augustine",
        "distance": "0.9",
        "price": "2500",
        "room_type": "Shared room",
        "capacity": "2",
        "amenities": "WiFi, kitchen access",
        "description": "Comfortable shared room close to UWI with space for two students.",
        "photos": "/static/img/listings/shared-flat.svg",
        "state": "rejected",
        "reason": "Please add clear photos of the bathroom.",
    },
    {
        "owner": "maria",
        "title": "Garden-side studio",
        "address": "4 College Road, St. Augustine",
        "distance": "1.5",
        "price": "3200",
        "room_type": "Studio",
        "capacity": "1",
        "amenities": "WiFi, kitchenette, private bath",
        "description": "A quiet self-contained studio with a sunny courtyard view.",
        "photos": "/static/img/listings/courtyard-room.svg",
        "state": "pending",
    },
    {
        "owner": "dev",
        "title": "Shared flat, 3 bedroom",
        "address": "19 Campus Crescent, Tunapuna",
        "distance": "0.5",
        "price": "5500",
        "room_type": "Shared flat",
        "capacity": "3",
        "amenities": "WiFi, air conditioning, laundry, parking",
        "description": "A spacious shared flat with a welcoming common area and campus nearby.",
        "photos": "/static/img/listings/shared-flat.svg\n/static/img/listings/student-studio.svg",
        "state": "verified",
    },
    {
        "owner": "dev",
        "title": "Sunny single room",
        "address": "25 Student Lane, Tunapuna",
        "distance": "0.7",
        "price": "2100",
        "room_type": "Private room",
        "capacity": "1",
        "amenities": "WiFi, desk, shared kitchen",
        "description": "A simple, bright room with a desk and shared kitchen access.",
        "photos": "/static/img/listings/student-studio.svg",
        "state": "draft",
    },
)

PAST_BOOKING_FIXTURES = (
    {
        "listing": "Room near campus",
        "booker": "bob",
        "move_in": date(2025, 1, 10),
        "move_out": date(2025, 3, 10),
    },
    {
        "listing": "Shared flat, 3 bedroom",
        "booker": "bob",
        "move_in": date(2025, 4, 10),
        "move_out": date(2025, 6, 10),
    },
    {
        "listing": "Courtyard student suite",
        "booker": "sara",
        "move_in": date(2025, 7, 10),
        "move_out": date(2025, 9, 10),
    },
)


def _seed_past_confirmed_bookings(session, users, verified_listings) -> None:
    booking_repo = BookingRepository(session)
    for fixture in PAST_BOOKING_FIXTURES:
        listing = verified_listings.get(fixture["listing"])
        booker = users[fixture["booker"]]
        if (
            listing is None
            or listing.id is None
            or listing.status != "verified"
            or booker.id is None
        ):
            raise RuntimeError("Past booking seed data requires verified listings and users.")

        existing_id = session.exec(
            select(Booking.id).where(
                Booking.listingId == listing.id,
                Booking.bookerId == booker.id,
                Booking.moveInDate == fixture["move_in"],
                Booking.moveOutDate == fixture["move_out"],
                Booking.status == "confirmed",
            )
        ).first()
        if existing_id is not None:
            continue

        booking = Booking(
            listingId=listing.id,
            bookerId=booker.id,
            moveInDate=fixture["move_in"],
            moveOutDate=fixture["move_out"],
            status="confirmed",
        )
        booking_repo.create(
            booking,
            [
                BookingTenant(
                    userId=booker.id,
                    tenantRole="booker",
                    response="accepted",
                )
            ],
        )


def seed_homeie() -> None:
    """Create the homeIE marker accounts and a small, repeatable listing set."""
    ensure_db_and_tables()
    with get_cli_session() as session:
        user_repo = UserRepository(session)
        users = {}
        created = 0
        updated = 0
        for username, email, password, full_name, role in DEMO_USERS:
            user = user_repo.get_by_username(username)
            if user is None:
                user = user_repo.create(
                    UserBase(
                        username=username,
                        email=email,
                        passwordHash=encrypt_password(password),
                        fullName=full_name,
                        role=role,
                    )
                )
                created += 1
            else:
                user.role = role
                user.fullName = full_name
                session.add(user)
                session.commit()
                updated += 1
            if user is None:
                raise RuntimeError(f"Could not create demo account {username}.")
            users[username] = user

        listing_repo = ListingRepository(session)
        listing_service = ListingService(listing_repo)
        seeded_landlords = {
            landlord_id
            for landlord_id in (
                users["maria"].id,
                users["dev"].id,
            )
            if landlord_id is not None
            and listing_repo.list_for_landlord(landlord_id)
        }
        listings_created = 0
        for data in DEMO_LISTINGS:
            landlord = users[data["owner"]]
            if landlord.id is None or landlord.id in seeded_landlords:
                continue
            listing = listing_service.create_listing(
                landlord_id=landlord.id,
                values={
                    "title": data["title"],
                    "address": data["address"],
                    "distance_to_campus": data["distance"],
                    "price": data["price"],
                    "room_type": data["room_type"],
                    "capacity": data["capacity"],
                    "amenities": data["amenities"],
                    "description": data["description"],
                },
                photo_urls=data["photos"],
                submit=data["state"] != "draft",
            )
            if data["state"] == "verified":
                listing_service.moderate_listing(listing.id, approved=True)
            elif data["state"] == "rejected":
                listing_service.moderate_listing(
                    listing.id,
                    approved=False,
                    rejection_reason=data["reason"],
                )
            listings_created += 1
            if data["owner"] == "dev" and data["state"] == "draft":
                seeded_landlords.add(landlord.id)

        dev = users["dev"]
        if dev.id is None:
            raise RuntimeError("The Dev account has no ID for listing seed data.")
        extra_listing = session.exec(
            select(Listing).where(
                Listing.landlordId == dev.id,
                Listing.title == "Courtyard student suite",
            )
        ).first()
        if extra_listing is None:
            extra_listing = listing_service.create_listing(
                landlord_id=dev.id,
                values={
                    "title": "Courtyard student suite",
                    "address": "31 Orchid Way, Tunapuna",
                    "distance_to_campus": "1.0",
                    "price": "2900",
                    "room_type": "Studio",
                    "capacity": "1",
                    "amenities": "WiFi, kitchenette, private bath",
                    "description": "A quiet studio with a private bath and courtyard access.",
                },
                photo_urls="/static/img/listings/courtyard-room.svg",
                submit=True,
            )
            extra_listing = listing_service.moderate_listing(
                extra_listing.id,
                approved=True,
            )
        elif extra_listing.status != "verified":
            raise RuntimeError(
                "The seeded Courtyard student suite exists but is not verified."
            )

        booking_exists = session.exec(select(Booking.id).limit(1)).first()
        if not booking_exists:
            seeded_listings = {
                listing.title: listing
                for listing in session.exec(
                    select(Listing).where(Listing.status == "verified")
                ).all()
            }
            booking_repo = BookingRepository(session)
            today = datetime.now(timezone.utc).date()
            fixtures = (
                {
                    "listing": "Room near campus",
                    "booker": "bob",
                    "roommates": [("sara", "pending")],
                    "status": "pending_roommates",
                    "move_in": today + timedelta(days=30),
                    "move_out": today + timedelta(days=150),
                },
                {
                    "listing": "Shared flat, 3 bedroom",
                    "booker": "bob",
                    "roommates": [],
                    "status": "pending_landlord",
                    "move_in": today + timedelta(days=45),
                    "move_out": today + timedelta(days=180),
                },
                {
                    "listing": "Room near campus",
                    "booker": "sara",
                    "roommates": [],
                    "status": "confirmed",
                    "move_in": today + timedelta(days=60),
                    "move_out": today + timedelta(days=240),
                },
                {
                    "listing": "Shared flat, 3 bedroom",
                    "booker": "sara",
                    "roommates": [],
                    "status": "declined",
                    "decline_reason": "The requested dates are no longer available.",
                    "move_in": today + timedelta(days=20),
                    "move_out": today + timedelta(days=120),
                },
                {
                    "listing": "Room near campus",
                    "booker": "bob",
                    "roommates": [("sara", "declined")],
                    "status": "cancelled",
                    "move_in": today + timedelta(days=90),
                    "move_out": today + timedelta(days=210),
                },
                {
                    "listing": "Shared flat, 3 bedroom",
                    "booker": "sara",
                    "roommates": [],
                    "status": "confirmed",
                    "move_in": today - timedelta(days=120),
                    "move_out": today - timedelta(days=30),
                },
                {
                    "listing": "Room near campus",
                    "booker": "bob",
                    "roommates": [],
                    "status": "confirmed",
                    "move_in": today - timedelta(days=100),
                    "move_out": today - timedelta(days=20),
                },
            )
            for fixture in fixtures:
                listing = seeded_listings.get(fixture["listing"])
                booker = users[fixture["booker"]]
                if listing is None or listing.id is None or booker.id is None:
                    raise RuntimeError("Booking seed data requires verified listings and users.")
                booking = Booking(
                    listingId=listing.id,
                    bookerId=booker.id,
                    moveInDate=fixture["move_in"],
                    moveOutDate=fixture["move_out"],
                    status=fixture["status"],
                    declineReason=fixture.get("decline_reason"),
                )
                tenants = [
                    BookingTenant(
                        userId=booker.id,
                        tenantRole="booker",
                        response="accepted",
                    )
                ]
                for username, response in fixture["roommates"]:
                    roommate = users[username]
                    if roommate.id is None:
                        raise RuntimeError(f"Booking seed account {username} has no ID.")
                    tenants.append(
                        BookingTenant(
                            userId=roommate.id,
                            tenantRole="roommate",
                            response=response,
                        )
                    )
                booking_repo.create(booking, tenants)

            sara = users["sara"]
            if sara.id is None:
                raise RuntimeError("Review seed data requires the Sara account.")
            past_sara_booking = session.exec(
                select(Booking)
                .where(
                    Booking.bookerId == sara.id,
                    Booking.status == "confirmed",
                    Booking.moveOutDate < today,
                )
                .order_by(Booking.moveOutDate.desc())
            ).first()
            if past_sara_booking is not None and past_sara_booking.id is not None:
                session.add(
                    Review(
                        bookingId=past_sara_booking.id,
                        reviewerId=sara.id,
                        rating=5,
                        comment="Bright room, kind landlord, and an easy trip to campus.",
                    )
                )
                session.commit()

        verified_listings = {
            listing.title: listing
            for listing in session.exec(
                select(Listing).where(Listing.status == "verified")
            ).all()
        }
        _seed_past_confirmed_bookings(session, users, verified_listings)

    print(
        f"Seed done — created {created} accounts, updated {updated}, "
        f"created {listings_created} listings."
    )
    print(
        "Demo accounts: admin/adminpass, maria/mariapass, dev/devpass, "
        "bob/bobpass, sara/sarapass"
    )
