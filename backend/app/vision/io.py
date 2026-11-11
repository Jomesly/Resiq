import io
import warnings

import cv2
import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
from pillow_heif import register_heif_opener

register_heif_opener()
ALLOWED_FORMATS = {
    "JPEG": ("image/jpeg", "jpg"),
    "PNG": ("image/png", "png"),
    "WEBP": ("image/webp", "webp"),
    "HEIF": ("image/heic", "heic"),
}


class UnsupportedImageError(ValueError):
    pass


def load_image(
    data: bytes, max_side: int = 2000, max_pixels: int = 30_000_000
) -> tuple[np.ndarray, str, str]:
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as source:
                if (
                    source.format not in ALLOWED_FORMATS
                    or source.width * source.height > max_pixels
                ):
                    raise UnsupportedImageError(
                        "Use a JPG, PNG, WebP or HEIC photo under the pixel limit."
                    )
                content_type, extension = ALLOWED_FORMATS[source.format]
                source.seek(0)
                upright = ImageOps.exif_transpose(source)
                upright.thumbnail((max_side, max_side))
                if "A" in upright.getbands() or upright.mode == "P":
                    rgba = upright.convert("RGBA")
                    background = Image.new("RGBA", rgba.size, "white")
                    upright = Image.alpha_composite(background, rgba)
                rgb = np.array(upright.convert("RGB"))
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), content_type, extension
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ) as exc:
        raise UnsupportedImageError("This file could not be decoded as a receipt photo.") from exc


def jpeg(image: np.ndarray) -> bytes:
    okay, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 94])
    if not okay:
        raise ValueError("Could not encode the processed photo.")
    return encoded.tobytes()
