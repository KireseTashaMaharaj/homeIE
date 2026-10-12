from datetime import date, datetime, timezone

from sqlmodel import Field, SQLModel


class Booking(SQLModel, table=True):
    # student-build:snippet workflow=Student-booking-request layer=model
    # Include the optional message agreed for Workflow 2.
    id: int | None = Field(default=None, primary_key=True)
    listingId: int = Field(foreign_key="listing.id", index=True)
    bookerId: int = Field(foreign_key="user.id", index=True)
    message: str | None = Field(default=None)
    moveInDate: date
    moveOutDate: date
    status: str = Field(default="pending_roommates")
    declineReason: str | None = Field(default=None)
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    


class BookingTenant(SQLModel, table=True):
    # Confirm the booker role default matches Booking.bookerId.
    id: int | None = Field(default=None, primary_key=True)
    bookingId: int = Field(foreign_key="booking.id", index=True)
    userId: int = Field(foreign_key="user.id", index=True)
    tenantRole: str = Field(default="booker")   
    response: str = Field(default="pending")      # "pending", "accepted", "declined"
    respondedAt: datetime | None = Field(default=None)
