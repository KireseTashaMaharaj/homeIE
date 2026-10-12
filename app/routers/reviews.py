from typing import Annotated

from fastapi import Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from starlette import status

from app.dependencies import AuthDep, SessionDep
from app.repositories.booking import BookingRepository
from app.repositories.review import ReviewRepository
from app.repositories.user import UserRepository
from app.services.review_service import ReviewService
from app.utilities.flash import flash

from . import router


@router.post(
    "/app/bookings/{booking_id}/reviews",
    name="review_create_action",
)
def review_create_action(
    booking_id: int,
    request: Request,
    db: SessionDep,
    user: AuthDep,
    rating: Annotated[int, Form()],
    comment: Annotated[str, Form()],
):
    # student-build:snippet workflow=Post-stay-review layer=router

    if user.role != "student":
        raise HTTPException(status_code=403, detail="Only students can leave reviews.")

    service = ReviewService(
        ReviewRepository(db),
        BookingRepository(db),
        UserRepository(db),
    )
    try:
        service.create_review(
            booking_id=booking_id,
            reviewer=user,
            rating=rating,
            comment=comment,
        )
    except ValueError as exc:
        flash(request, str(exc), "danger")
    else:
        flash(request, "Thanks! Your review has been posted.")

    return RedirectResponse(
        url=request.url_for("my_bookings_view").include_query_params(tab="closed"),
        status_code=status.HTTP_303_SEE_OTHER,
    )
