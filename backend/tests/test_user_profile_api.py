from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_profile_update_requires_authentication():
    response = client.put("/api/me/profile", json={
        "full_name": "New Name",
        "email": "new@example.com"
    })

    assert response.status_code == 401
