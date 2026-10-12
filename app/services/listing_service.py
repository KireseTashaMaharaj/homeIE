import math

from app.models.listing import Listing
from app.repositories.listing import ListingRepository

LISTING_STATUSES = ("draft", "pending", "verified", "rejected")
ROOM_TYPES = ("Private room", "Shared room", "Studio", "Shared flat")


class ListingService:
    def __init__(self, listing_repo: ListingRepository):
        self.listing_repo = listing_repo

    @staticmethod
    def parse_photo_urls(value: str) -> list[str]:
        urls = [item.strip() for item in value.replace(",", "\n").splitlines()]
        urls = [item for item in urls if item]
        for image in urls:
            if not image.startswith("/static/") and not image.startswith(
                ("https://", "http://")
            ):
                raise ValueError("Use a /static/ image path or an http(s) image URL.")
        return urls

    @staticmethod
    def _validate_listing(values: dict[str, str]) -> dict[str, object]:
        title = values["title"].strip()
        address = values["address"].strip()
        room_type = values["room_type"].strip()
        description = values["description"].strip()
        amenities = values["amenities"].strip()
        if not title or not address or not room_type or not description:
            raise ValueError("Title, address, room type, and description are required.")
        if room_type not in ROOM_TYPES:
            raise ValueError("Choose one of the available room types.")
        try:
            price = float(values["price"])
            distance = float(values["distance_to_campus"])
            capacity = int(values["capacity"])
        except ValueError as exc:
            raise ValueError("Price, distance, and capacity must be valid numbers.") from exc
        if (
            not math.isfinite(price)
            or not math.isfinite(distance)
            or price <= 0
            or distance < 0
            or capacity < 1
        ):
            raise ValueError("Price and capacity must be positive; distance cannot be negative.")
        return {
            "title": title,
            "address": address,
            "roomType": room_type,
            "description": description,
            "amenities": amenities,
            "price": price,
            "distanceToCampus": distance,
            "capacity": capacity,
        }

    def create_listing(
        self,
        landlord_id: int,
        values: dict[str, str],
        photo_urls: str,
        submit: bool,
    ) -> Listing:
        fields = self._validate_listing(values)
        listing = Listing(
            landlordId=landlord_id,
            status="pending" if submit else "draft",
            rejectionReason=None,
            **fields,
        )
        return self.listing_repo.create(
            listing,
            self.parse_photo_urls(photo_urls),
        )

    def update_listing(
        self,
        listing_id: int,
        landlord_id: int,
        values: dict[str, str],
        photo_urls: str,
        submit: bool,
    ) -> Listing:
        listing = self._owned_listing(listing_id, landlord_id)
        if listing.status not in {"draft", "rejected"}:
            raise ValueError("Only draft or rejected listings can be edited.")
        fields = self._validate_listing(values)
        for field, value in fields.items():
            setattr(listing, field, value)
        listing.rejectionReason = None
        listing.status = "pending" if submit else "draft"
        return self.listing_repo.update_with_photos(
            listing,
            self.parse_photo_urls(photo_urls),
        )

    def _owned_listing(self, listing_id: int, landlord_id: int) -> Listing:
        listing = self.listing_repo.get_by_id(listing_id)
        if listing is None or listing.landlordId != landlord_id:
            raise ValueError("Listing not found.")
        return listing

    def get_landlord_listings(self, landlord_id: int) -> list[Listing]:
        return self.listing_repo.list_for_landlord(landlord_id)

    def get_editable_listing(self, listing_id: int, landlord_id: int) -> Listing:
        listing = self._owned_listing(listing_id, landlord_id)
        if listing.status not in {"draft", "rejected"}:
            raise ValueError("Only draft or rejected listings can be edited.")
        return listing

    def get_listing_photos(self, listing_id: int):
        return self.listing_repo.get_photos(listing_id)

    def submit_listing(self, listing_id: int, landlord_id: int) -> Listing:
        listing = self.get_editable_listing(listing_id, landlord_id)
        listing.status = "pending"
        listing.rejectionReason = None
        return self.listing_repo.save(listing)

    def get_admin_listings(self, status: str) -> list[Listing]:
        if status not in LISTING_STATUSES:
            raise ValueError("Unknown listing status.")
        return self.listing_repo.list_by_status(status)

    def moderate_listing(
        self,
        listing_id: int,
        approved: bool,
        rejection_reason: str = "",
    ) -> Listing:
        listing = self.listing_repo.get_by_id(listing_id)
        if listing is None:
            raise ValueError("Listing not found.")
        if listing.status != "pending":
            raise ValueError("Only pending listings can be reviewed.")
        if approved:
            listing.status = "verified"
            listing.rejectionReason = None
        else:
            reason = rejection_reason.strip()
            if not reason:
                raise ValueError("A rejection reason is required.")
            listing.status = "rejected"
            listing.rejectionReason = reason
        return self.listing_repo.save(listing)

    def get_verified_listings(self) -> list[Listing]:
        return self.listing_repo.list_verified()

    def get_listing_photos_for(self, listings: list[Listing]):
        return {
            listing.id: self.get_listing_photos(listing.id)
            for listing in listings
            if listing.id is not None
        }

    def get_landlords_for(self, listings: list[Listing]):
        return {
            listing.landlordId: landlord
            for listing in listings
            if (landlord := self.listing_repo.get_landlord(listing.landlordId))
            is not None
        }
