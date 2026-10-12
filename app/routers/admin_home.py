from fastapi import Request
from fastapi.responses import RedirectResponse
from starlette import status
from app.dependencies.auth import AdminDep
from . import router


@router.get("/admin")
async def admin_home_view(
    request: Request,
    user: AdminDep,
):
    return RedirectResponse(
        url=request.url_for("verification_queue_view"),
        status_code=status.HTTP_303_SEE_OTHER,
    )
