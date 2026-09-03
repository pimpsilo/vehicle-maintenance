import base64
import pytest
from fastapi.testclient import TestClient
from app.config import settings
from app.main import app
from app.services.qr_service import QRService

from app.models.vehicle import Vehicle

def test_healthz_endpoint(client: TestClient):
    """Verifies that /healthz returns 200 and version information."""
    response = client.get("/healthz")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data

def test_dynamic_base_public_url_in_qr_service():
    """Verifies that QRService uses settings.base_public_url dynamically."""
    original_url = settings.base_public_url
    try:
        settings.base_public_url = "http://100.85.12.34:8000"
        url = QRService.get_vehicle_portal_url(vehicle_id=1)
        assert url == "http://100.85.12.34:8000/v/1"

        # Explicit base_url override should take precedence
        magic_url = QRService.get_vehicle_portal_url(vehicle_id=1, base_url="http://nas6e810d.tail8ba0ff.ts.net:8000")
        assert magic_url == "http://nas6e810d.tail8ba0ff.ts.net:8000/v/1"

        lan_url = QRService.get_vehicle_portal_url(vehicle_id=1, base_url="http://192.168.1.198:8000/")
        assert lan_url == "http://192.168.1.198:8000/v/1"

        svg_content = QRService.generate_qr_svg(vehicle_id=1, base_url="http://100.91.20.86:8000")
        assert "<svg" in svg_content

        png_bytes = QRService.generate_qr_png_bytes(vehicle_id=1, base_url="http://nas6e810d.tail8ba0ff.ts.net:8000")
        assert len(png_bytes) > 0
        assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"
    finally:
        settings.base_public_url = original_url

def test_qr_endpoint_with_custom_base_url_param(client: TestClient, sample_vehicle: Vehicle):
    """Verifies /api/v1/vehicles/{id}/qr respects the ?base_url= parameter."""
    # Test PNG format
    res_png = client.get(f"/api/v1/vehicles/{sample_vehicle.id}/qr?format=png&base_url=http://nas6e810d.tail8ba0ff.ts.net:8000")
    assert res_png.status_code == 200
    assert res_png.headers["content-type"] == "image/png"
    assert res_png.content[:8] == b"\x89PNG\r\n\x1a\n"

    # Test SVG format
    res_svg = client.get(f"/api/v1/vehicles/{sample_vehicle.id}/qr?format=svg&base_url=http://192.168.1.198:8000")
    assert res_svg.status_code == 200
    assert "image/svg+xml" in res_svg.headers["content-type"]
    assert "<svg" in res_svg.text



def test_auth_disabled_by_default(client):
    """When enable_auth is False, endpoints should be accessible without credentials."""
    original_state = settings.enable_auth
    try:
        settings.enable_auth = False
        response = client.get("/healthz")
        assert response.status_code == 200
        # Check an API endpoint
        response = client.get("/api/v1/vehicles/")
        assert response.status_code == 200
    finally:
        settings.enable_auth = original_state

def test_auth_enabled_enforcement(client):
    """When enable_auth is True, requests without or with wrong credentials should get 401."""
    original_state = settings.enable_auth
    original_user = settings.auth_username
    original_pass = settings.auth_password
    try:
        settings.enable_auth = True
        settings.auth_username = "testadmin"
        settings.auth_password = "secretpassword123"

        # /healthz should still be accessible (health check probe exemption)
        health_resp = client.get("/healthz")
        assert health_resp.status_code == 200

        # Unauthenticated request to /api/v1/vehicles/ should be rejected with 401
        unauth_resp = client.get("/api/v1/vehicles/")
        assert unauth_resp.status_code == 401
        assert "WWW-Authenticate" in unauth_resp.headers

        # Invalid credentials should be rejected with 401
        bad_auth = base64.b64encode(b"wronguser:wrongpass").decode("utf-8")
        bad_resp = client.get("/api/v1/vehicles/", headers={"Authorization": f"Basic {bad_auth}"})
        assert bad_resp.status_code == 401

        # Valid credentials should be accepted
        good_auth = base64.b64encode(b"testadmin:secretpassword123").decode("utf-8")
        good_resp = client.get("/api/v1/vehicles/", headers={"Authorization": f"Basic {good_auth}"})
        assert good_resp.status_code == 200
    finally:
        settings.enable_auth = original_state
        settings.auth_username = original_user
        settings.auth_password = original_pass
