"""Session rotation happens in ONE place (app/api/route.py RotatingRoute), not in handlers.

A throwaway app with the real auth dependencies and the real route class, whose handlers contain NO rotation code:
a response under 400 rotates the caller's stored token exactly once and returns it in X-Refreshed-Token; an error
(raised, a 422, or a returned 4xx/5xx) never rotates; a route that opts out never rotates. Also checks that every
real /api/v1 route uses the rotating route class, so a new router cannot silently skip rotation."""

import importlib
import pkgutil
from datetime import timedelta

import pytest
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Response
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from pydantic import BaseModel

import app.api.routes as routes_pkg
from app.api.deps.auth import (
    Principal,
    require_institution_user_no_rotation,
    require_user_or_institution_user,
)
from app.api.route import RotatingRoute
from app.db.session import get_db
from app.main import app as real_app
from tests.conftest import bearer
from tests.test_connection_requests import _buyer

router = APIRouter(route_class=RotatingRoute)


class Body(BaseModel):
    n: int


@router.get("/ok")
def ok(principal: Principal = Depends(require_user_or_institution_user)):
    return {"ok": True}


@router.delete("/no-content", status_code=204)
def no_content(principal: Principal = Depends(require_user_or_institution_user)):
    return Response(status_code=204)  # its own Response: the old injected-header approach lost the header here


@router.get("/denied")
def denied(principal: Principal = Depends(require_user_or_institution_user)):
    raise HTTPException(status_code=404, detail="nope")


@router.post("/body")
def body(payload: Body, principal: Principal = Depends(require_user_or_institution_user)):
    return {"n": payload.n}


@router.get("/returned/{code}")
def returned(code: int, principal: Principal = Depends(require_user_or_institution_user)):
    return JSONResponse({"code": code}, status_code=code)


@router.get("/opt-out")
def opt_out(principal: Principal = Depends(require_institution_user_no_rotation)):
    return {"ok": True}


@pytest.fixture()
def tiny(session_factory, client):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_db] = real_app.dependency_overrides[get_db]
    return TestClient(app)


@pytest.fixture(params=["buyer", "officer"])
def token(request, client, officer):
    return officer["accessToken"] if request.param == "officer" else _buyer(client).token


def _tick(clock):
    clock["now"] += timedelta(seconds=5)


def _assert_rotated(tiny, clock, old, resp):
    new = resp.headers["X-Refreshed-Token"]
    assert new != old
    _tick(clock)
    assert tiny.get("/ok", headers=bearer(old)).status_code == 401  # superseded
    assert tiny.get("/ok", headers=bearer(new)).status_code == 200  # the new token is live (and rotates again)


def _assert_untouched(tiny, clock, old, resp):
    assert "X-Refreshed-Token" not in resp.headers
    _tick(clock)
    assert tiny.get("/ok", headers=bearer(old)).status_code == 200  # same token still works


def test_success_rotates_once(tiny, clock, token):
    _tick(clock)
    resp = tiny.get("/ok", headers=bearer(token))
    assert resp.status_code == 200
    _assert_rotated(tiny, clock, token, resp)


def test_204_with_own_response_rotates(tiny, clock, token):
    _tick(clock)
    resp = tiny.delete("/no-content", headers=bearer(token))
    assert resp.status_code == 204
    _assert_rotated(tiny, clock, token, resp)


@pytest.mark.parametrize(
    ("request_args", "code"),
    [
        (("GET", "/denied"), 404),
        (("POST", "/body", {"json": {"n": "not-a-number"}}), 422),
        (("GET", "/returned/400"), 400),
        (("GET", "/returned/500"), 500),
    ],
)
def test_errors_never_rotate(tiny, clock, token, request_args, code):
    method, path, *rest = request_args
    _tick(clock)
    resp = tiny.request(method, path, headers=bearer(token), **(rest[0] if rest else {}))
    assert resp.status_code == code
    _assert_untouched(tiny, clock, token, resp)


def test_opt_out_route_does_not_rotate(tiny, clock, officer):
    token = officer["accessToken"]
    _tick(clock)
    resp = tiny.get("/opt-out", headers=bearer(token))
    assert resp.status_code == 200
    _assert_untouched(tiny, clock, token, resp)


def test_every_routes_module_uses_the_rotating_route_class():
    modules = [m.name for m in pkgutil.iter_modules(routes_pkg.__path__) if m.name != "router"]
    assert modules
    for name in modules:
        module = importlib.import_module(f"app.api.routes.{name}")
        assert module.router.route_class is RotatingRoute, name
