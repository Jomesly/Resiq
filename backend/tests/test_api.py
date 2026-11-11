from urllib.parse import parse_qs, urlencode, urlsplit
from uuid import UUID

from sqlalchemy import select

from app.models import Receipt, Workspace
from app.schemas import Extraction

ENTRY = {
    "merchant": "Kapihan sa Kanto",
    "merchant_tin": "000-482-117-000",
    "receipt_number": "0004417",
    "receipt_date": "2026-11-09",
    "category": "Food & Drinks",
    "subtotal": None,
    "vatable_sales": "120.54",
    "vat_amount": "14.46",
    "vat_exempt": None,
    "total": "135.00",
    "line_items": [
        {
            "position": 0,
            "description": "Coffee",
            "quantity": "3",
            "unit_price": "45.00",
            "amount": "135.00",
        }
    ],
}


def make_ready(runtime, receipt_id):
    with runtime.db.session() as session:
        receipt = session.get(Receipt, UUID(receipt_id))
        receipt.status = "needs_review"
        receipt.extraction = Extraction(engine_version="test").model_dump(mode="json")
        session.commit()


def test_workspace_token_is_hashed_and_unknown_tokens_fail(client, auth, runtime):
    with runtime.db.session() as session:
        stored = session.scalar(select(Workspace.token_hash))
    assert stored != auth["Authorization"].removeprefix("Bearer ")
    assert client.get("/api/receipts").status_code == 401
    assert (
        client.get("/api/receipts", headers={"Authorization": "Bearer unknown"}).status_code == 401
    )


def test_workspace_cannot_access_other_receipts(client, auth, uploaded):
    other = {"Authorization": "Bearer " + client.post("/api/workspaces").json()["token"]}
    assert client.get("/api/receipts", headers=other).json()["items"] == []
    for method in ["get", "delete"]:
        assert (
            getattr(client, method)(f"/api/receipts/{uploaded}", headers=other).status_code == 404
        )
    assert client.put(f"/api/receipts/{uploaded}", headers=other, json=ENTRY).status_code == 404
    assert client.post(f"/api/receipts/{uploaded}/reprocess", headers=other).status_code == 404


def test_upload_validates_content_and_limits(client, auth, runtime):
    assert (
        client.post(
            "/api/receipts",
            headers=auth,
            files={"file": ("fake.jpg", b"not an image", "image/jpeg")},
        ).status_code
        == 415
    )
    runtime.settings.max_upload_bytes = 10
    assert (
        client.post(
            "/api/receipts", headers=auth, files={"file": ("large.png", b"x" * 11, "image/png")}
        ).status_code
        == 413
    )


def test_signed_images_expire_and_cannot_be_tampered(client, auth, uploaded):
    detail = client.get(f"/api/receipts/{uploaded}", headers=auth).json()
    image_url = detail["image"]["original_url"]
    assert client.get(image_url).status_code == 200
    parts = urlsplit(image_url)
    params = parse_qs(parts.query)
    params["exp"] = ["1"]
    tampered = parts.path + "?" + urlencode({key: value[0] for key, value in params.items()})
    assert client.get(tampered).status_code == 403
    assert client.get(image_url.replace("/original?", "/processed?")).status_code == 403


def test_save_preserves_extraction_and_verified_only_journal(client, auth, uploaded, runtime):
    assert client.put(f"/api/receipts/{uploaded}", headers=auth, json=ENTRY).status_code == 409
    make_ready(runtime, uploaded)
    before = client.get(f"/api/receipts/{uploaded}", headers=auth).json()["extraction"]
    assert client.get("/api/journal?month=2026-11", headers=auth).json()["items"] == []
    result = client.put(f"/api/receipts/{uploaded}", headers=auth, json=ENTRY)
    assert result.status_code == 200, result.text
    assert result.json()["total"] == "135.00"
    assert result.json()["status"] == "verified"
    assert result.json()["extraction"] == before
    summary = client.get("/api/stats/summary?month=2026-11", headers=auth).json()
    assert summary["total"] == "135.00" and summary["count"] == 1
    assert summary["by_category"] == [{"category": "Food & Drinks", "total": "135.00", "count": 1}]
    assert client.get("/api/journal/months", headers=auth).json() == ["2026-11"]
    exported = client.get("/api/receipts/export.csv?month=2026-11", headers=auth)
    assert (
        exported.text.splitlines()[0]
        == "date,merchant,tin,receipt_number,category,vatable_sales,vat_amount,vat_exempt,total,status"
    )
    assert ",135.00,verified" in exported.text
    assert client.post(f"/api/receipts/{uploaded}/reprocess", headers=auth).status_code == 409
    assert (
        client.post(f"/api/receipts/{uploaded}/reprocess?force=true", headers=auth).status_code
        == 202
    )


def test_invalid_money_and_missing_required_fields_rejected(client, auth, uploaded, runtime):
    make_ready(runtime, uploaded)
    for changes in [
        {"total": "NaN"},
        {"total": 135.00},
        {"total": "0.001"},
        {"total": "10000000000.00"},
        {"merchant": ""},
        {"receipt_date": "2026-02-30"},
    ]:
        assert (
            client.put(
                f"/api/receipts/{uploaded}", headers=auth, json={**ENTRY, **changes}
            ).status_code
            == 422
        )


def test_keyset_pagination_filters_and_delete(client, auth, photo, uploaded, runtime):
    second = client.post(
        "/api/receipts", headers=auth, files={"file": ("receipt.png", photo)}
    ).json()["id"]
    for receipt_id in [uploaded, second]:
        make_ready(runtime, receipt_id)
        assert (
            client.put(f"/api/receipts/{receipt_id}", headers=auth, json=ENTRY).status_code == 200
        )
    first = client.get(
        "/api/receipts?limit=1&status=verified&month=2026-11&q=Kapihan", headers=auth
    ).json()
    assert len(first["items"]) == 1 and first["next_cursor"]
    page2 = client.get(
        "/api/receipts", params={"limit": 1, "cursor": first["next_cursor"]}, headers=auth
    ).json()
    assert page2["items"][0]["id"] != first["items"][0]["id"]
    assert page2["next_cursor"] is None
    assert client.get("/api/receipts?cursor=garbage", headers=auth).status_code == 400
    image = client.get(f"/api/receipts/{uploaded}", headers=auth).json()["thumbnail_url"]
    assert client.delete(f"/api/receipts/{uploaded}", headers=auth).status_code == 204
    assert client.get(f"/api/receipts/{uploaded}", headers=auth).status_code == 404
    assert client.get(image).status_code == 404
