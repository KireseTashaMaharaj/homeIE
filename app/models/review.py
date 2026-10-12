from datetime import datetime, timezone

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


class Review(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("bookingId", "reviewerId", name="unique_booking_reviewer"),
    )

    id: int | None = Field(default=None, primary_key=True)
    bookingId: int = Field(foreign_key="booking.id", index=True)
    reviewerId: int = Field(foreign_key="user.id", index=True)
    isRemoved: bool = Field(default=False)
    rating: int
    comment: str
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    