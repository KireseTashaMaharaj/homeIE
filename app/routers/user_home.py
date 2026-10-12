from fastapi import HTTPException, Request
from fastapi.responses import HTMLResponse
from app.dependencies.session import SessionDep
from app.dependencies.auth import AuthDep
from app.repositories.listing import ListingRepository
from app.services.listing_service import ListingService
from . import router, templates


@router.get("/app", response_class=HTMLResponse)
def user_home_view(
    request: Request,
    user: AuthDep,
    db: SessionDep,
):
    if user.role != "student":
        raise HTTPException(status_code=403, detail="This page is for students.")
    service = ListingService(ListingRepository(db))
    listings = service.get_verified_listings()
    return templates.TemplateResponse(
        request=request,
        name="app.html",
        context={
            "user": user,
            "listings": listings,
            "photos": service.get_listing_photos_for(listings),
        },
    )