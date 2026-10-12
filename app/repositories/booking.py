from sqlalchemy import or_
from sqlmodel import Session, select

from app.models.booking import Booking, BookingTenant
from app.models.listing import Listing


class BookingRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, booking: Booking, tenants: list[BookingTenant]) -> Booking:
        # student-build:snippet workflow=Student-booking-request layer=repository
        self.db.add(booking)
        self.db.flush()

        if booking.id is None:
            self.db.rollback()
            raise RuntimeError("The database did not assign a booking ID.")

        for tenant in tenants:
            tenant.bookingId = booking.id
        self.db.add_all(tenants)

        self.db.commit()
        self.db.refresh(booking)
        return booking

    def has_active_request(self, listing_id: int, booker_id: int) -> bool:
        statement = select(Booking.id).where(
            Booking.listingId == listing_id,
            Booking.bookerId == booker_id,
            Booking.status.in_(
                ("pending_roommates", "pending_landlord", "confirmed")
            ),
        )
        return self.db.exec(statement).first() is not None

    def get_by_id(self, booking_id: int) -> Booking | None:
        return self.db.get(Booking, booking_id)

    def list_for_student(self, user_id: int) -> list[Booking]:
        statement = (
            select(Booking)
            .outerjoin(BookingTenant, BookingTenant.bookingId == Booking.id)
            .where(
                or_(
                    Booking.bookerId == user_id,
                    BookingTenant.userId == user_id,
                )
            )
            .distinct()
            .order_by(Booking.createdAt.desc(), Booking.id.desc())
        )
        return list(self.db.exec(statement).all())

    def list_tenants(self, booking_id: int) -> list[BookingTenant]:
        statement = (
            select(BookingTenant)
            .where(BookingTenant.bookingId == booking_id)
            .order_by(BookingTenant.id)
        )
        return list(self.db.exec(statement).all())

    def get_tenant(
        self,
        booking_id: int,
        user_id: int,
    ) -> BookingTenant | None:
        statement = select(BookingTenant).where(
            BookingTenant.bookingId == booking_id,
            BookingTenant.userId == user_id,
        )
        return self.db.exec(statement).first()

    def list_pending_invitations(self, user_id: int) -> list[BookingTenant]:
        statement = (
            select(BookingTenant)
            .join(Booking, Booking.id == BookingTenant.bookingId)
            .where(
                BookingTenant.userId == user_id,
                BookingTenant.tenantRole == "roommate",
                BookingTenant.response == "pending",
                Booking.status == "pending_roommates",
            )
            .order_by(Booking.createdAt.desc())
        )
        return list(self.db.exec(statement).all())

    def list_for_landlord(
        self,
        landlord_id: int,
        booking_status: str,
    ) -> list[Booking]:
        statement = (
            select(Booking)
            .join(Listing, Listing.id == Booking.listingId)
            .where(
                Listing.landlordId == landlord_id,
                Booking.status == booking_status,
            )
            .order_by(Booking.createdAt.desc(), Booking.id.desc())
        )
        return list(self.db.exec(statement).all())

    def save(self, booking: Booking, tenant: BookingTenant | None = None) -> Booking:
        self.db.add(booking)
        if tenant is not None:
            self.db.add(tenant)
        self.db.commit()
        self.db.refresh(booking)
        if tenant is not None:
            self.db.refresh(tenant)
        return booking
