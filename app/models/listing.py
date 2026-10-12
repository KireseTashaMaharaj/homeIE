from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


class Listing(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    landlordId: int = Field(foreign_key="user.id", index=True)
    title: str = Field(max_length=160)
    description: str
    amenities: str
    address: str = Field(max_length=240)
    distanceToCampus: float
    price: float
    roomType: str = Field(max_length=80)
    capacity: int
    status: str = Field(default="draft", index=True)
    rejectionReason: str | None = None
    createdAt: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ListingPhoto(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    listingId: int = Field(foreign_key="listing.id", index=True)
    image: str
