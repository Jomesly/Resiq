from sqlalchemy import select

from app.models import Workspace


def setup(client, auth):
    code = client.post("/api/workspace/recovery", headers=auth).json()["recovery_code"]
    assert (
        client.post(
            "/api/workspace/recovery/confirm", headers=auth, json={"recovery_code": code}
        ).status_code
        == 204
    )
    return code


def test_recovery_restores_receipts_and_revokes_old_access(client, auth, uploaded, runtime):
    code = setup(client, auth)
    with runtime.db.session() as session:
        row = session.scalar(select(Workspace))
        assert row.recovery_hash != code and row.pending_recovery_hash is None
    result = client.post("/api/workspaces/recover", json={"recovery_code": code})
    assert result.status_code == 200
    restored = {"Authorization": "Bearer " + result.json()["token"]}
    assert client.get("/api/receipts", headers=auth).status_code == 401
    assert client.get(f"/api/receipts/{uploaded}", headers=restored).status_code == 200
    # A lost recovery response can be retried using the saved code.
    assert client.post("/api/workspaces/recover", json={"recovery_code": code}).status_code == 200


def test_replacement_is_two_phase_and_old_code_is_revoked(client, auth):
    old = setup(client, auth)
    new = client.post("/api/workspace/recovery", headers=auth).json()["recovery_code"]
    assert client.post("/api/workspaces/recover", json={"recovery_code": new}).status_code == 401
    assert (
        client.post(
            "/api/workspace/recovery/confirm", headers=auth, json={"recovery_code": new}
        ).status_code
        == 204
    )
    assert (
        client.post(
            "/api/workspace/recovery/confirm", headers=auth, json={"recovery_code": new}
        ).status_code
        == 204
    )
    assert client.post("/api/workspaces/recover", json={"recovery_code": old}).status_code == 401
    assert client.post("/api/workspaces/recover", json={"recovery_code": new}).status_code == 200


def test_rotation_requires_recovery_and_preserves_it(client, auth):
    assert client.post("/api/workspace/rotate", headers=auth).status_code == 409
    code = setup(client, auth)
    result = client.post("/api/workspace/rotate", headers=auth)
    assert result.status_code == 200
    assert client.get("/api/workspace", headers=auth).status_code == 401
    assert client.post("/api/workspaces/recover", json={"recovery_code": code}).status_code == 200


def test_recovery_cannot_confirm_another_workspace_code(client, auth):
    other = {"Authorization": "Bearer " + client.post("/api/workspaces").json()["token"]}
    code = client.post("/api/workspace/recovery", headers=auth).json()["recovery_code"]
    assert (
        client.post(
            "/api/workspace/recovery/confirm", headers=other, json={"recovery_code": code}
        ).status_code
        == 400
    )
    assert client.post("/api/workspace/recovery").status_code == 401


def test_production_upload_requires_saved_recovery(client, auth, photo, runtime):
    runtime.settings.environment = "production"
    assert (
        client.post("/api/receipts", headers=auth, files={"file": ("photo.png", photo)}).status_code
        == 409
    )
    setup(client, auth)
    assert (
        client.post("/api/receipts", headers=auth, files={"file": ("photo.png", photo)}).status_code
        == 202
    )
