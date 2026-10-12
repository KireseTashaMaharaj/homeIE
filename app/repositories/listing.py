import logging

from sqlmodel import Session, col, select

from app.models.booking import Booking
from app.models.listing import Listing, ListingPhoto
from app.models.user import User

logger = logging.getLogger(__name__)


class ListingRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, listing: Listing, photo_urls: list[str]) -> Listing:
        try:
            self.db.add(listing)
            self.db.flush()
            if listing.id is None:
                raise RuntimeError("The database did not assign a listing ID.")
            self.db.add_all(
                ListingPhoto(listingId=listing.id, image=image)
                for image in photo_urls
            )
            self.db.commit()
            self.db.refresh(listing)
            return listing
        except Exception:
            logger.exception("Could not create listing")
            self.db.rollback()
            raise

    def get_by_id(self, listing_id: int) -> Listing | None:
        return self.db.get(Listing, listing_id)

    def has_active_request(self, listing_id: int, booker_id: int) -> bool:
        statement = select(Booking).where(
            Booking.listingId == listing_id,
            Booking.bookerId == booker_id,
             col(Booking.status).in_(["pending_roommates", "pending_landlord"]),
        )
        return self.db.exec(statement).first() is not None

    def get_photos(self, listing_id: int) -> list[ListingPhoto]:
        statement = select(ListingPhoto).where(ListingPhoto.listingId == listing_id)
        return list(self.db.exec(statement).all())

    def update_with_photos(
        self,
        listing: Listing,
        photo_urls: list[str],
    ) -> Listing:
        if listing.id is None:
            raise ValueError("Cannot update an unsaved listing.")
        try:
            photos = self.get_photos(listing.id)
            for photo in photos:
                self.db.delete(photo)
            self.db.add_all(
                ListingPhoto(listingId=listing.id, image=image)
                for image in photo_urls
            )
            self.db.add(listing)
            self.db.commit()
            self.db.refresh(listing)
            return listing
        except Exception:
            logger.exception("Could not update listing photos")
            self.db.rollback()
            raise

    def save(self, listing: Listing) -> Listing:
        try:
            self.db.add(listing)
            self.db.commit()
            self.db.refresh(listing)
            return listing
        except Exception:
            logger.exception("Could not save listing")
            self.db.rollback()
            raise

    def list_for_landlord(self, landlord_id: int) -> list[Listing]:
        statement = (
            select(Listing)
            .where(Listing.landlordId == landlord_id)
            .order_by(Listing.createdAt.desc(), Listing.id.desc())
        )
        return list(self.db.exec(statement).all())

    def list_by_status(self, listing_status: str) -> list[Listing]:
        statement = (
            select(Listing)
            .where(Listing.status == listing_status)
            .order_by(Listing.createdAt.desc(), Listing.id.desc())
        )
        return list(self.db.exec(statement).all())

    def list_verified(self) -> list[Listing]:
        return self.list_by_status("verified")

    def get_landlord(self, landlord_id: int) -> User | None:
        return self.db.get(User, landlord_id)
