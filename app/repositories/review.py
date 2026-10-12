from sqlmodel import Session, select

from app.models.booking import Booking
from app.models.review import Review


class ReviewRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_for_booking_reviewer(
        self,
        booking_id: int,
        reviewer_id: int,
    ) -> Review | None:
        # student-build:snippet workflow=Post-stay-review layer=repository
        # Return the Review for this booking and reviewer, if one exists.
        statement = select(Review).where(
            Review.bookingId == booking_id,
            Review.reviewerId == reviewer_id,
        )
        return self.db.exec(statement).first()

    
    def create(self, review: Review) -> Review:
        self.db.add(review)
        self.db.commit()
        self.db.refresh(review)
        return review

    def list_for_listing(self, listing_id: int) -> list[Review]:
        statement = (
            select(Review)
            .join(Booking, Booking.id == Review.bookingId)
            .where(
                Booking.listingId == listing_id,
                Review.isRemoved.is_(False),
            )
            .order_by(Review.createdAt.desc(), Review.id.desc())
        )
        return list(self.db.exec(statement).all())

    def list_for_reviewer(self, reviewer_id: int) -> list[Review]:
        statement = select(Review).where(Review.reviewerId == reviewer_id)
        return list(self.db.exec(statement).all())
