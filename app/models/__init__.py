"""Database table models.

Import every table model here so ``SQLModel.metadata.create_all`` sees them.
"""

from app.models.user import User
from app.models.listing import Listing, ListingPhoto
from app.models.booking import Booking, BookingTenant
from app.models.review import Review

__all__ = ["User", "Listing", "ListingPhoto", "Booking", "BookingTenant", "Review"]
