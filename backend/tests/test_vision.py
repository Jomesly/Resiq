import cv2
import numpy as np
import pytest

from app.vision.io import UnsupportedImageError, load_image
from app.vision.preprocess import preprocess


def test_blank_image_fallback_and_dark_warning():
    image = np.full((600, 400, 3), 20, dtype=np.uint8)
    result = preprocess(image)
    assert result.image.shape == image.shape
    assert result.quality.is_dark and result.quality.is_blurry
    assert not result.quality.document_found


def test_document_detection_and_bounds():
    image = np.full((800, 600, 3), 30, dtype=np.uint8)
    cv2.fillConvexPoly(
        image, np.array([[100, 80], [520, 120], [480, 730], [60, 700]]), (245, 245, 245)
    )
    result = preprocess(image)
    assert result.quality.document_found
    assert result.image.shape[0] < 800
    assert result.image.shape[1] < 600


def test_bad_image_rejected():
    with pytest.raises(UnsupportedImageError):
        load_image(b"not an image", 2000, 30_000_000)
