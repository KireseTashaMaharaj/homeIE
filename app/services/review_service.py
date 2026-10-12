from datetime import datetime, timezone

from app.models.listing import Listing
from app.models.review import Review
from app.models.user import User
from app.repositories.booking import BookingRepository
from app.repositories.review import ReviewRepository
from app.repositories.user import UserRepository


class ReviewService:
    def __init__(
        self,
        reviews: ReviewRepository,
        bookings: BookingRepository,
        users: UserRepository,
    ):
        self.reviews = reviews
        self.bookings = bookings
        self.users = users

    def create_review(
        self,
        booking_id: int,
        reviewer: User,
        rating: int,
        comment: str,
    ) -> Review:
        # student-build:snippet workflow=Post-stay-review layer=service
        # Validate eligibility and review values, then use the repositories.
        if reviewer.role != "student":
            raise ValueError("Only students can leave reviews.")

        if reviewer.id is None:
            raise ValueError("The signed-in student account is invalid.")
        booking = self.bookings.get_by_id(booking_id)
        if booking is None:
            raise ValueError("Booking not found.")
        if booking.status != "confirmed":
            raise ValueError("Only confirmed stays can be reviewed.")

        tenant = self.bookings.get_tenant(booking_id, reviewer.id)
        if (
            tenant is None
            or tenant.tenantRole not in {"booker", "roommate"}
            or tenant.response != "accepted"
        ):
            raise ValueError("Only tenants on this stay can review it.")

        if booking.moveOutDate >= datetime.now(timezone.utc).date():
            raise ValueError("You can review this stay after your move-out date.")

        if self.reviews.get_for_booking_reviewer(booking_id, reviewer.id) is not None:
            raise ValueError("You have already reviewed this stay.")

        if rating < 1 or rating > 5:
            raise ValueError("Rating must be between 1 and 5 stars.")

        comment = (comment or "").strip()
        if len(comment) < 20:
            raise ValueError("Comment must be at least 20 characters.")
        if len(comment) > 1000:
            raise ValueError("Comment must be 1000 characters or fewer.")

        review = Review(
            bookingId=booking_id,
            reviewerId=reviewer.id,
            rating=rating,
            comment=comment,
        )
        return self.reviews.create(review)

    def get_listing_data(self, listing_id: int) -> dict[str, object]:
        listing_reviews = self.reviews.list_for_listing(listing_id)
        entries = []
        for review in listing_reviews:
            reviewer = self.users.get_by_id(review.reviewerId)
            if reviewer is None:
                raise RuntimeError(
                    f"Review {review.id} references a missing reviewer."
                )
            entries.append(
                {
                    "review": review,
                    "first_name": (reviewer.fullName or reviewer.username).split()[0],
                }
            )
        average = (
            sum(review.rating for review in listing_reviews) / len(listing_reviews)
            if listing_reviews
            else None
        )
        return {
            "reviews": entries,
            "average": average,
            "count": len(listing_reviews),
        }

    def get_listing_summaries(
        self,
        listings: list[Listing],
    ) -> dict[int, dict[str, object]]:
        summaries: dict[int, dict[str, object]] = {}
        for listing in listings:
            if listing.id is None:
                continue
            data = self.get_listing_data(listing.id)
            summaries[listing.id] = {
                "average": data["average"],
                "count": data["count"],
            }
        return summaries

    def get_reviewed_booking_ids(self, reviewer: User) -> set[int]:
        if reviewer.role != "student" or reviewer.id is None:
            raise ValueError("Only students can view their review status.")
        return {
            review.bookingId
            for review in self.reviews.list_for_reviewer(reviewer.id)
        }