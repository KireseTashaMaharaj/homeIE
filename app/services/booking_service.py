from datetime import date, datetime, timezone

from app.models.booking import Booking, BookingTenant
from app.models.user import User
from app.repositories.booking import BookingRepository
from app.repositories.listing import ListingRepository
from app.repositories.user import UserRepository


class BookingService:
    def __init__(
        self,
        booking_repo: BookingRepository,
        listing_repo: ListingRepository,
        user_repo: UserRepository,
    ):
        self.booking_repo = booking_repo
        self.listing_repo = listing_repo
        self.user_repo = user_repo

    def create_request(
        self,
        listing_id: int,
        booker: User,
        move_in_date: date,
        move_out_date: date,
        roommate_usernames: list[str],
        message: str,
    ) -> Booking:
        # student-build:snippet workflow=Student-booking-request layer=service
        # Validate the request, resolve invited students, then save Booking + BookingTenant rows.
        if booker.role != "student" or booker.id is None:
            raise ValueError("Only students can request a booking.")

        listing = self.listing_repo.get_by_id(listing_id)
        if listing is None or listing.id is None or listing.status != "verified":
            raise ValueError("This listing is not available.")

        if move_in_date <= datetime.now(timezone.utc).date():
            raise ValueError("Move-in date must be in the future.")
        if move_out_date <= move_in_date:
            raise ValueError("Move-out date must be after move-in date.")

        cleaned: list[str] = []
        seen_usernames: set[str] = set()
        for name in roommate_usernames:
            name = name.strip()
            if not name:
                continue
            username_key = name.casefold()
            if username_key in seen_usernames:
                raise ValueError(f"'{name}' was invited more than once.")
            seen_usernames.add(username_key)
            cleaned.append(name)

        roommates: list[User] = []
        for username in cleaned:
            if username.casefold() == booker.username.casefold():
                raise ValueError("You can't invite yourself.")
            user = self.user_repo.get_by_username(username)
            if user is None or user.id is None or user.role != "student":
                raise ValueError(f"'{username}' is not a student account.")
            roommates.append(user)

        if self.booking_repo.has_active_request(listing_id, booker.id):
            raise ValueError("You already have an active request for this listing.")
        if 1 + len(roommates) > listing.capacity:
            raise ValueError(f"This listing sleeps {listing.capacity}.")

        status = "pending_roommates" if roommates else "pending_landlord"
        booking = Booking(
            listingId=listing.id,
            bookerId=booker.id,
            moveInDate=move_in_date,
            moveOutDate=move_out_date,
            status=status,
            message=(message or "").strip() or None,
        )

        tenants = [
            BookingTenant(userId=booker.id, tenantRole="booker", response="accepted")
        ]
        for user in roommates:
            tenants.append(BookingTenant(userId=user.id, tenantRole="roommate", response="pending"))

        return self.booking_repo.create(booking, tenants)

    def get_verified_listing(self, listing_id: int, user: User):
        if user.role != "student":
            raise ValueError("Only students can view listing details.")
        listing = self.listing_repo.get_by_id(listing_id)
        if listing is None or listing.status != "verified":
            raise ValueError("Listing not found.")
        return listing, self.listing_repo.get_photos(listing_id)

    def get_student_bookings(self, user: User) -> list[dict[str, object]]:
        if user.role != "student" or user.id is None:
            raise ValueError("Only students can view bookings.")
        result: list[dict[str, object]] = []
        for booking in self.booking_repo.list_for_student(user.id):
            if booking.id is None:
                continue
            listing = self.listing_repo.get_by_id(booking.listingId)
            if listing is None:
                continue
            tenants = []
            for tenant in self.booking_repo.list_tenants(booking.id):
                tenant_user = self.user_repo.get_by_id(tenant.userId)
                if tenant_user is not None:
                    tenants.append({"tenant": tenant, "user": tenant_user})
            result.append(
                {
                    "booking": booking,
                    "listing": listing,
                    "tenants": tenants,
                    "photos": self.listing_repo.get_photos(listing.id),
                }
            )
        return result

    def get_pending_invitations(self, user: User) -> list[dict[str, object]]:
        if user.role != "student" or user.id is None:
            raise ValueError("Only students can view invitations.")
        result: list[dict[str, object]] = []
        for tenant in self.booking_repo.list_pending_invitations(user.id):
            booking = self.booking_repo.get_by_id(tenant.bookingId)
            if booking is None or booking.id is None:
                continue
            listing = self.listing_repo.get_by_id(booking.listingId)
            inviter = self.user_repo.get_by_id(booking.bookerId)
            if listing is not None and inviter is not None:
                result.append(
                    {
                        "booking": booking,
                        "listing": listing,
                        "inviter": inviter,
                        "tenant": tenant,
                    }
                )
        return result

    def respond_to_invitation(
        self,
        booking_id: int,
        user: User,
        decision: str,
    ) -> Booking:
        if user.role != "student" or user.id is None:
            raise ValueError("Only students can respond to invitations.")
        if decision not in {"accept", "decline"}:
            raise ValueError("Unknown invitation response.")
        booking = self.booking_repo.get_by_id(booking_id)
        if booking is None or booking.status != "pending_roommates":
            raise ValueError("This invitation is no longer active.")
        tenant = self.booking_repo.get_tenant(booking_id, user.id)
        if (
            tenant is None
            or tenant.tenantRole != "roommate"
            or tenant.response != "pending"
        ):
            raise ValueError("You do not have an active invitation for this booking.")

        tenant.response = "accepted" if decision == "accept" else "declined"
        tenant.respondedAt = datetime.now(timezone.utc)
        if decision == "decline":
            booking.status = "cancelled"
        elif all(
            item.response == "accepted"
            for item in self.booking_repo.list_tenants(booking_id)
            if item.tenantRole == "roommate"
        ):
            booking.status = "pending_landlord"
        return self.booking_repo.save(booking, tenant)

    def cancel_booking(self, booking_id: int, user: User) -> Booking:
        if user.role != "student" or user.id is None:
            raise ValueError("Only students can cancel bookings.")
        booking = self.booking_repo.get_by_id(booking_id)
        if booking is None or booking.bookerId != user.id:
            raise ValueError("Booking not found.")
        if booking.status not in {"pending_roommates", "pending_landlord"}:
            raise ValueError("Only pending bookings can be cancelled.")
        booking.status = "cancelled"
        return self.booking_repo.save(booking)

    def get_landlord_bookings(
        self,
        user: User,
        tab: str,
    ) -> list[dict[str, object]]:
        if user.role != "landlord" or user.id is None:
            raise ValueError("Only landlords can view booking requests.")
        tab_statuses = {
            "pending": "pending_landlord",
            "confirmed": "confirmed",
            "declined": "declined",
        }
        if tab not in tab_statuses:
            raise ValueError("Unknown booking request tab.")
        result: list[dict[str, object]] = []
        for booking in self.booking_repo.list_for_landlord(
            user.id,
            tab_statuses[tab],
        ):
            if booking.id is None:
                continue
            listing = self.listing_repo.get_by_id(booking.listingId)
            if listing is None:
                continue
            tenants = []
            for tenant in self.booking_repo.list_tenants(booking.id):
                tenant_user = self.user_repo.get_by_id(tenant.userId)
                if tenant_user is not None:
                    tenants.append({"tenant": tenant, "user": tenant_user})
            result.append(
                {
                    "booking": booking,
                    "listing": listing,
                    "tenants": tenants,
                }
            )
        return result

    def decide_as_landlord(
        self,
        booking_id: int,
        user: User,
        decision: str,
        decline_reason: str = "",
    ) -> Booking:
        if user.role != "landlord" or user.id is None:
            raise ValueError("Only landlords can review booking requests.")
        if decision not in {"accept", "decline"}:
            raise ValueError("Unknown booking decision.")
        booking = self.booking_repo.get_by_id(booking_id)
        listing = (
            self.listing_repo.get_by_id(booking.listingId)
            if booking is not None
            else None
        )
        if booking is None or listing is None or listing.landlordId != user.id:
            raise ValueError("Booking request not found.")
        if booking.status != "pending_landlord":
            raise ValueError("Only requests sent to the landlord can be reviewed.")
        if decision == "decline":
            reason = decline_reason.strip()
            if not reason:
                raise ValueError("A decline reason is required.")
            booking.status = "declined"
            booking.declineReason = reason
        else:
            booking.status = "confirmed"
            booking.declineReason = None
        return self.booking_repo.save(booking)