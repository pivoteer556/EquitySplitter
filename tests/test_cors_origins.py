from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app.main import cors_origins

LOCAL = ["http://localhost:4200", "http://127.0.0.1:4200"]


def test_empty_setting_keeps_only_localhost():
    assert cors_origins("") == LOCAL


def test_extra_origins_are_split_stripped_and_cleaned():
    raw = " https://site.example.net , ,https://other.example/, "
    assert cors_origins(raw) == [*LOCAL, "https://site.example.net", "https://other.example"]


def test_duplicates_and_wildcard_are_dropped():
    assert cors_origins("http://localhost:4200,*,https://a.example,https://a.example") == [*LOCAL, "https://a.example"]


def _preflight(origin: str):
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins("https://site.example.net,https://other.example"),
        allow_methods=["*"],
        allow_headers=["*"],
    )
    headers = {"Origin": origin, "Access-Control-Request-Method": "POST"}
    return TestClient(app).options("/anything", headers=headers)


def test_preflight_allows_configured_and_localhost_origins_only():
    assert _preflight("https://site.example.net").headers["access-control-allow-origin"] == "https://site.example.net"
    assert _preflight("http://localhost:4200").headers["access-control-allow-origin"] == "http://localhost:4200"
    assert "access-control-allow-origin" not in _preflight("https://evil.example").headers
