from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

import app.models
from app.database import get_session
from app.main import app
from app.models.listing import Listing
from app.models.user import User
from app.repositories.booking import BookingRepository
from app.repositories.listing import ListingRepository
from app.repositories.review import ReviewRepository
from app.repositories.user import UserRepository
from app.services.booking_service import BookingService
from app.services.listing_service import ListingService
from app.services.review_service import ReviewService
from app.utilities.security import encrypt_password


@pytest.fixture(scope="session")
def test_password_hash() -> str:
    return encrypt_password("testpass")


@pytest.fixture
def db_session() -> Iterator[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()


@pytest.fixture
def users(db_session: Session, test_password_hash: str) -> dict[str, User]:
    accounts = {
        "admin": User(
            username="admin",
            email="admin@example.com",
            passwordHash=test_password_hash,
            role="admin",
        ),
        "landlord": User(
            username="landlord",
            email="landlord@example.com",
            passwordHash=test_password_hash,
            role="landlord",
        ),
        "other_landlord": User(
            username="other-landlord",
            email="other-landlord@example.com",
            passwordHash=test_password_hash,
            role="landlord",
        ),
        "student": User(
            username="student",
            email="student@example.com",
            passwordHash=test_password_hash,
            role="student",
        ),
        "roommate": User(
            username="roommate",
            email="roommate@example.com",
            passwordHash=test_password_hash,
            role="student",
        ),
        "second_student": User(
            username="second-student",
            email="second-student@example.com",
            passwordHash=test_password_hash,
            role="student",
        ),
    }
    db_session.add_all(accounts.values())
    db_session.commit()
    for account in accounts.values():
        db_session.refresh(account)
    return accounts


@pytest.fixture
def verified_listing(db_session: Session, users: dict[str, User]) -> Listing:
    listing = Listing(
        landlordId=users["landlord"].id,
        title="Test verified home",
        address="1 Test Road",
        distanceToCampus=1.0,
        price=2500,
        roomType="Private room",
        capacity=2,
        amenities="WiFi",
        description="A verified test listing.",
        status="verified",
    )
    db_session.add(listing)
    db_session.commit()
    db_session.refresh(listing)
    return listing


@pytest.fixture
def listing_service(db_session: Session) -> ListingService:
    return ListingService(ListingRepository(db_session))


@pytest.fixture
def booking_service(db_session: Session) -> BookingService:
    return BookingService(
        BookingRepository(db_session),
        ListingRepository(db_session),
        UserRepository(db_session),
    )


@pytest.fixture
def review_service(db_session: Session) -> ReviewService:
    return ReviewService(
        ReviewRepository(db_session),
        BookingRepository(db_session),
        UserRepository(db_session),
    )


@pytest.fixture
def api_client(test_password_hash: str) -> Iterator[dict[str, object]]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    accounts = {
        "admin": User(
            username="admin",
            email="admin@example.com",
            passwordHash=test_password_hash,
            role="admin",
        ),
        "landlord": User(
            username="landlord",
            email="landlord@example.com",
            passwordHash=test_password_hash,
            role="landlord",
        ),
        "student": User(
            username="student",
            email="student@example.com",
            passwordHash=test_password_hash,
            role="student",
        ),
    }
    with Session(engine) as session:
        session.add_all(accounts.values())
        session.flush()
        session.add(
            Listing(
                landlordId=accounts["landlord"].id,
                title="Verified test home",
                address="2 Test Road",
                distanceToCampus=1.2,
                price=2200,
                roomType="Studio",
                capacity=2,
                amenities="WiFi",
                description="A verified listing for API tests.",
                status="verified",
            )
        )
        session.commit()
        for account in accounts.values():
            session.refresh(account)

    def get_test_session() -> Iterator[Session]:
        with Session(engine) as session:
            yield session

    previous_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_session] = get_test_session
    try:
        # Not using TestClient as a context manager avoids running the app lifespan,
        # which initializes the configured real database.
        yield {
            "client": TestClient(app),
            "engine": engine,
            "accounts": accounts,
        }
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous_overrides)
        engine.dispose()
