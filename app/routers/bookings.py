from datetime import date, datetime, timezone
from typing import Annotated

from fastapi import Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette import status

from app.dependencies import AuthDep, SessionDep
from app.repositories.booking import BookingRepository
from app.repositories.listing import ListingRepository
from app.repositories.review import ReviewRepository
from app.repositories.user import UserRepository
from app.services.booking_service import BookingService
from app.services.review_service import ReviewService
from app.utilities.flash import flash

from . import router, templates


def _service(db: SessionDep) -> BookingService:
    return BookingService(
        BookingRepository(db),
        ListingRepository(db),
        UserRepository(db),
    )


def _review_service(db: SessionDep) -> ReviewService:
    return ReviewService(
        ReviewRepository(db),
        BookingRepository(db),
        UserRepository(db),
    )


def _require_role(user: AuthDep, expected: str) -> None:
    if user.role != expected:
        raise HTTPException(status_code=403, detail="You do not have access to this page.")


@router.post(
    "/app/listings/{listing_id}/bookings",
    name="booking_create_action",
)
def booking_create_action(
    listing_id: int,
    request: Request,
    db: SessionDep,
    user: AuthDep,
    move_in_date: Annotated[date, Form()],
    move_out_date: Annotated[date, Form()],
    message: Annotated[str, Form()] = "",
    roommates: Annotated[str, Form()] = "",
):
    # student-build:snippet workflow=Student-booking-request layer=router
    # Bind the form values and call BookingService; keep persistence out of this handler.
    if user.role != "student":
        raise HTTPException(status_code=403, detail="Only students can request bookings.")

    service = _service(db)
    try:
        booking = service.create_request(
            listing_id=listing_id,
            booker=user,
            move_in_date=move_in_date,
            move_out_date=move_out_date,
            roommate_usernames=roommates.splitlines(),
            message=message,
        )
    except ValueError as exc:
        flash(request, str(exc), "danger")
        return RedirectResponse(
            url=request.url_for("listing_detail_view", listing_id=listing_id),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    if booking.status == "pending_roommates":
        flash(request, "Request sent. Waiting for your roommates to accept.")
    else:
        flash(request, "Request sent to the landlord.")
    return RedirectResponse(
        url=request.url_for("my_bookings_view"),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get(
    "/app/listings/{listing_id}",
    response_class=HTMLResponse,
    name="listing_detail_view",
)
def listing_detail_view(
    listing_id: int,
    request: Request,
    db: SessionDep,
    user: AuthDep,
):
    _require_role(user, "student")
    service = _service(db)
    try:
        listing, photos = service.get_verified_listing(listing_id, user)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Listing not found.") from exc
    return templates.TemplateResponse(
        request=request,
        name="listing-detail.html",
        context={
            "user": user,
            "listing": listing,
            "photos": photos,
            "review_data": _review_service(db).get_listing_data(listing_id),
        },
    )


@router.get(
    "/app/bookings",
    response_class=HTMLResponse,
    name="my_bookings_view",
)
def my_bookings_view(
    request: Request,
    db: SessionDep,
    user: AuthDep,
):
    _require_role(user, "student")
    service = _service(db)
    tab = request.query_params.get("tab", "active")
    if tab not in {"active", "confirmed", "closed", "invitations"}:
        tab = "active"
    bookings = service.get_student_bookings(user)
    invitations = service.get_pending_invitations(user)
    today = datetime.now(timezone.utc).date()
    counts = {
        "active": sum(
            item["booking"].status in {"pending_roommates", "pending_landlord"}
            for item in bookings
        ),
        "confirmed": sum(
            item["booking"].status == "confirmed"
            and item["booking"].moveOutDate >= today
            for item in bookings
        ),
        "closed": sum(
            item["booking"].status in {"declined", "cancelled"}
            or (
                item["booking"].status == "confirmed"
                and item["booking"].moveOutDate < today
            )
            for item in bookings
        ),
        "invitations": len(invitations),
    }
    try:
        reviewed_booking_ids = _review_service(db).get_reviewed_booking_ids(user)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return templates.TemplateResponse(
        request=request,
        name="my-bookings.html",
        context={
            "user": user,
            "tab": tab,
            "bookings": bookings,
            "invitations": invitations,
            "booking_tab_counts": counts,
            "reviewed_booking_ids": reviewed_booking_ids,
            "today": today,
        },
    )


@router.post(
    "/app/bookings/{booking_id}/cancel",
    name="booking_cancel_action",
)
def booking_cancel_action(
    booking_id: int,
    request: Request,
    db: SessionDep,
    user: AuthDep,
):
    _require_role(user, "student")
    try:
        _service(db).cancel_booking(booking_id, user)
    except ValueError as exc:
        flash(request, str(exc), "danger")
    else:
        flash(request, "Booking request cancelled.")
    return RedirectResponse(
        url=request.url_for("my_bookings_view").include_query_params(tab="active"),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/app/bookings/{booking_id}/invitation",
    name="booking_invitation_action",
)
def booking_invitation_action(
    booking_id: int,
    request: Request,
    db: SessionDep,
    user: AuthDep,
    decision: str = Form(),
):
    _require_role(user, "student")
    try:
        _service(db).respond_to_invitation(booking_id, user, decision)
    except ValueError as exc:
        flash(request, str(exc), "danger")
    else:
        flash(
            request,
            "Invitation accepted." if decision == "accept" else "Invitation declined.",
        )
    return RedirectResponse(
        url=request.url_for("my_bookings_view").include_query_params(tab="invitations"),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get(
    "/landlord/booking-requests",
    response_class=HTMLResponse,
    name="landlord_booking_requests_view",
)
def landlord_booking_requests_view(
    request: Request,
    db: SessionDep,
    user: AuthDep,
):
    _require_role(user, "landlord")
    service = _service(db)
    tab = request.query_params.get("tab", "pending")
    if tab not in {"pending", "confirmed", "declined"}:
        tab = "pending"
    return templates.TemplateResponse(
        request=request,
        name="landlord-booking-requests.html",
        context={
            "user": user,
            "tab": tab,
            "requests": service.get_landlord_bookings(user, tab),
        },
    )


@router.post(
    "/landlord/bookings/{booking_id}/decision",
    name="landlord_booking_decision_action",
)
def landlord_booking_decision_action(
    booking_id: int,
    request: Request,
    db: SessionDep,
    user: AuthDep,
    decision: str = Form(),
    decline_reason: str = Form(""),
):
    _require_role(user, "landlord")
    try:
        _service(db).decide_as_landlord(
            booking_id,
            user,
            decision,
            decline_reason,
        )
    except ValueError as exc:
        flash(request, str(exc), "danger")
    else:
        flash(
            request,
            "Booking confirmed." if decision == "accept" else "Booking declined.",
            "success" if decision == "accept" else "danger",
        )
    return RedirectResponse(
        url=request.url_for("landlord_booking_requests_view").include_query_params(
            tab="pending"
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )
