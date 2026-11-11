"""The one place a session token is rotated.

RotatingRoute wraps every handler of a router that uses it. The auth dependencies record the authenticated caller on
request.state (PENDING_ROTATION); after the response exists and only if its status is below 400, this wrapper rotates
that caller's stored token and returns the new one in X-Refreshed-Token on the response actually being sent. An
exception (HTTPException, 422) propagates through the wrapper untouched, so errors never rotate.

The rotation uses its own short Session from the app's get_db (honouring app.dependency_overrides, which is how the
tests swap in SQLite), not the request's: whether FastAPI has already closed the request's yield-dependency session
at this point depends on the FastAPI version, and rotation must not.
"""

from collections.abc import Callable, Coroutine
from contextlib import contextmanager
from typing import Any

from fastapi import Request, Response
from fastapi.concurrency import run_in_threadpool
from fastapi.routing import APIRoute

from app.api.deps.auth import PENDING_ROTATION, Principal
from app.db.session import get_db
from app.models import InstitutionUser, User
from app.services.auth import refresh_and_store_institution_token, refresh_and_store_user_token


def _rotate(request: Request, principal: Principal) -> str:
    get_session = contextmanager(request.app.dependency_overrides.get(get_db, get_db))
    with get_session() as db:
        if principal.user_type == "institution_user":
            officer = db.query(InstitutionUser).filter(InstitutionUser.id == principal.user_id).one()
            return refresh_and_store_institution_token(db, officer)
        user = db.query(User).filter(User.id == principal.user_id).one()
        return refresh_and_store_user_token(db, user)


class RotatingRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original = super().get_route_handler()

        async def handler(request: Request) -> Response:
            response = await original(request)
            principal = getattr(request.state, PENDING_ROTATION, None)
            if principal is not None and response.status_code < 400:
                response.headers["X-Refreshed-Token"] = await run_in_threadpool(_rotate, request, principal)
            return response

        return handler
