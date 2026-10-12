from fastapi import Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette import status

from app.dependencies import AuthDep, SessionDep
from app.repositories.listing import ListingRepository
from app.services.listing_service import LISTING_STATUSES, ROOM_TYPES, ListingService
from app.utilities.flash import flash
from . import router, templates


def _service(db: SessionDep) -> ListingService:
    return ListingService(ListingRepository(db))


def _require_role(user: AuthDep, expected: str) -> None:
    if user.role != expected:
        raise HTTPException(status_code=403, detail="You do not have access to this page.")


def _form_values(
    title: str,
    address: str,
    distance_to_campus: str,
    price: str,
    room_type: str,
    capacity: str,
    amenities: str,
    description: str,
) -> dict[str, str]:
    return {
        "title": title,
        "address": address,
        "distance_to_campus": distance_to_campus,
        "price": price,
        "room_type": room_type,
        "capacity": capacity,
        "amenities": amenities,
        "description": description,
    }


@router.get("/landlord/listings", response_class=HTMLResponse, name="landlord_listings_view")
def landlord_listings_view(
    request: Request,
    db: SessionDep,
    user: AuthDep,
):
    _require_role(user, "landlord")
    service = _service(db)
    listings = service.get_landlord_listings(user.id)
    active_status = request.query_params.get("status", "all")
    if active_status in LISTING_STATUSES:
        listings = [listing for listing in listings if listing.status == active_status]
    elif active_status != "all":
        active_status = "all"
    return templates.TemplateResponse(
        request=request,
        name="landlord-listings.html",
        context={
            "user": user,
            "listings": listings,
            "photos": service.get_listing_photos_for(listings),
            "statuses": LISTING_STATUSES,
            "active_status": active_status,
        },
    )


@router.get("/landlord/listings/new", response_class=HTMLResponse, name="listing_create_view")
def listing_create_view(request: Request, user: AuthDep):
    _require_role(user, "landlord")
    return templates.TemplateResponse(
        request=request,
        name="listing-form.html",
        context={
            "user": user,
            "listing": None,
            "photos": [],
            "page_title": "Create New Listing",
            "room_types": ROOM_TYPES,
        },
    )


@router.get(
    "/landlord/listings/{listing_id}/edit",
    response_class=HTMLResponse,
    name="listing_edit_view",
)
def listing_edit_view(
    listing_id: int,
    request: Request,
    db: SessionDep,
    user: AuthDep,
):
    _require_role(user, "landlord")
    service = _service(db)
    try:
        listing = service.get_editable_listing(listing_id, user.id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return templates.TemplateResponse(
        request=request,
        name="listing-form.html",
        context={
            "user": user,
            "listing": listing,
            "photos": service.get_listing_photos(listing_id),
            "page_title": "Edit Listing",
            "room_types": ROOM_TYPES,
        },
    )


@router.post("/landlord/listings", name="listing_create_action")
def listing_create_action(
    request: Request,
    db: SessionDep,
    user: AuthDep,
    title: str = Form(),
    address: str = Form(),
    distance_to_campus: str = Form(),
    price: str = Form(),
    room_type: str = Form(),
    capacity: str = Form(),
    amenities: str = Form(""),
    photos: str = Form(""),
    description: str = Form(),
    action: str = Form("draft"),
):
    _require_role(user, "landlord")
    service = _service(db)
    try:
        listing = service.create_listing(
            landlord_id=user.id,
            values=_form_values(
                title, address, distance_to_campus, price, room_type,
                capacity, amenities, description,
            ),
            photo_urls=photos,
            submit=action == "submit",
        )
    except ValueError as exc:
        flash(request, str(exc), "danger")
        return RedirectResponse(
            url=request.url_for("listing_create_view"),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    flash(request, "Listing submitted for verification." if action == "submit" else "Draft saved.")
    return RedirectResponse(
        url=request.url_for("landlord_listings_view"),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/landlord/listings/{listing_id}/edit",
    name="listing_update_action",
)
def listing_update_action(
    listing_id: int,
    request: Request,
    db: SessionDep,
    user: AuthDep,
    title: str = Form(),
    address: str = Form(),
    distance_to_campus: str = Form(),
    price: str = Form(),
    room_type: str = Form(),
    capacity: str = Form(),
    amenities: str = Form(""),
    photos: str = Form(""),
    description: str = Form(),
    action: str = Form("draft"),
):
    _require_role(user, "landlord")
    service = _service(db)
    try:
        service.update_listing(
            listing_id=listing_id,
            landlord_id=user.id,
            values=_form_values(
                title, address, distance_to_campus, price, room_type,
                capacity, amenities, description,
            ),
            photo_urls=photos,
            submit=action == "submit",
        )
    except ValueError as exc:
        flash(request, str(exc), "danger")
        return RedirectResponse(
            url=request.url_for("listing_edit_view", listing_id=listing_id),
            status_code=status.HTTP_303_SEE_OTHER,
        )
    flash(request, "Listing resubmitted for verification." if action == "submit" else "Draft saved.")
    return RedirectResponse(
        url=request.url_for("landlord_listings_view"),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.post(
    "/landlord/listings/{listing_id}/submit",
    name="listing_submit_action",
)
def listing_submit_action(
    listing_id: int,
    request: Request,
    db: SessionDep,
    user: AuthDep,
):
    _require_role(user, "landlord")
    try:
        _service(db).submit_listing(listing_id, user.id)
    except ValueError as exc:
        flash(request, str(exc), "danger")
    else:
        flash(request, "Listing submitted for verification.")
    return RedirectResponse(
        url=request.url_for("landlord_listings_view"),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get(
    "/admin/verification-queue",
    response_class=HTMLResponse,
    name="verification_queue_view",
)
def verification_queue_view(
    request: Request,
    db: SessionDep,
    user: AuthDep,
):
    _require_role(user, "admin")
    service = _service(db)
    listing_status = request.query_params.get("status", "pending")
    if listing_status not in {"pending", "verified", "rejected"}:
        listing_status = "pending"
    listings = service.get_admin_listings(listing_status)
    selected_id = request.query_params.get("listing_id")
    selected = next(
        (listing for listing in listings if str(listing.id) == selected_id),
        listings[0] if listings else None,
    )
    detail_photos = (
        service.get_listing_photos(selected.id)
        if selected is not None and selected.id is not None
        else []
    )
    return templates.TemplateResponse(
        request=request,
        name="verification-queue.html",
        context={
            "user": user,
            "listings": listings,
            "selected": selected,
            "detail_photos": detail_photos,
            "landlords": service.get_landlords_for(listings),
            "active_status": listing_status,
            "counts": {
                value: len(service.get_admin_listings(value))
                for value in ("pending", "verified", "rejected")
            },
        },
    )


@router.post(
    "/admin/listings/{listing_id}/moderate",
    name="listing_moderate_action",
)
def listing_moderate_action(
    listing_id: int,
    request: Request,
    db: SessionDep,
    user: AuthDep,
    decision: str = Form(),
    rejection_reason: str = Form(""),
):
    _require_role(user, "admin")
    if decision not in {"approve", "reject"}:
        raise HTTPException(status_code=400, detail="Unknown moderation action.")
    try:
        _service(db).moderate_listing(
            listing_id=listing_id,
            approved=decision == "approve",
            rejection_reason=rejection_reason,
        )
    except ValueError as exc:
        flash(request, str(exc), "danger")
    else:
        flash(
            request,
            "Listing verified." if decision == "approve" else "Listing rejected.",
            "success" if decision == "approve" else "danger",
        )
    return RedirectResponse(
        url=request.url_for(
            "verification_queue_view",
        ).include_query_params(status="pending"),
        status_code=status.HTTP_303_SEE_OTHER,
    )
