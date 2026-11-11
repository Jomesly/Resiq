import io
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi import HTTPException
from PIL import Image

from app.services.access import check_rate
from app.services.journal import safe_cell
from app.storage import LocalBlobStore
from app.vision.io import UnsupportedImageError, load_image


def test_rate_bucket_is_atomic(runtime):
    runtime.settings.rate_limit_enabled = True

    def attempt(_):
        try:
            check_rate(runtime, "test", "same-identity", 3)
            return True
        except HTTPException as exc:
            assert exc.status_code == 429
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(attempt, range(12))) == 3


def test_quota_rejection_does_not_leave_files(client, auth, uploaded, photo, runtime):
    runtime.settings.max_receipts_per_workspace = 1
    assert (
        client.post(
            "/api/receipts", headers=auth, files={"file": ("another.png", photo)}
        ).status_code
        == 429
    )
    assert len(list(runtime.settings.storage_root.glob("*/*"))) == 1


@pytest.mark.parametrize("key", ["../outside", "/absolute", "C:/data", "a/../b", "a\\b", "."])
def test_storage_paths_stay_inside_root(tmp_path, key):
    with pytest.raises(ValueError):
        LocalBlobStore(tmp_path).put(key, b"test")


@pytest.mark.parametrize(
    "value", ['=HYPERLINK("example")', " +123", "@SUM(1)", "\tformula", "-1+2"]
)
def test_csv_text_is_neutralized(value):
    assert safe_cell(value).startswith("'")


def test_exif_rotation_transparency_and_pixel_limit():
    image = Image.new("RGB", (100, 200), "white")
    exif = Image.Exif()
    exif[274] = 6
    data = io.BytesIO()
    image.save(data, format="JPEG", exif=exif)
    upright, _, _ = load_image(data.getvalue(), 2000, 30000)
    assert upright.shape[:2] == (100, 200)
    with pytest.raises(UnsupportedImageError):
        load_image(data.getvalue(), 2000, 100)
    data = io.BytesIO()
    Image.new("RGBA", (100, 100), (0, 0, 0, 0)).save(data, format="PNG")
    opaque, _, _ = load_image(data.getvalue(), 2000, 30000)
    assert opaque.min() == 255


def test_heic_decode():
    import pillow_heif

    data = io.BytesIO()
    pillow_heif.from_pillow(Image.new("RGB", (200, 300), "white")).save(data)
    image, content_type, extension = load_image(data.getvalue(), 2000, 100000)
    assert image.shape[:2] == (300, 200)
    assert content_type == "image/heic" and extension == "heic"
