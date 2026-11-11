"""OCR adapters return both text and the image whose coordinates their boxes use."""

from dataclasses import dataclass
from importlib.metadata import version

import cv2
import numpy as np

from app.config import Settings
from app.schemas import OcrLine


@dataclass
class OcrResult:
    image: np.ndarray
    lines: list[OcrLine]
    engine: str


class PaddleEngine:
    def __init__(self, settings: Settings):
        from paddleocr import PaddleOCR

        options = {}
        if settings.paddle_model_root:
            options["text_detection_model_dir"] = str(
                settings.paddle_model_root / settings.paddle_det_model
            )
            options["text_recognition_model_dir"] = str(
                settings.paddle_model_root / settings.paddle_rec_model
            )
        self.model = PaddleOCR(
            text_detection_model_name=settings.paddle_det_model,
            text_recognition_model_name=settings.paddle_rec_model,
            use_doc_orientation_classify=True,
            use_doc_unwarping=False,
            use_textline_orientation=False,
            device="cpu",
            cpu_threads=settings.cpu_threads,
            enable_mkldnn=False,
            **options,
        )
        self.version = "paddleocr-" + version("paddleocr")

    def read(self, image: np.ndarray) -> OcrResult:
        result = next(iter(self.model.predict(image)))
        processed = result.get("doc_preprocessor_res", {}).get("output_img", image)
        height, width = processed.shape[:2]
        lines = []
        for text, score, box in zip(
            result["rec_texts"], result["rec_scores"], result["rec_boxes"], strict=True
        ):
            x0, y0, x1, y1 = map(int, box)
            if text.strip():
                lines.append(
                    OcrLine(
                        text=text,
                        confidence=float(np.clip(score, 0, 1)),
                        box=(max(0, x0), max(0, y0), min(width, x1), min(height, y1)),
                    )
                )
        return OcrResult(processed, lines, self.version)


class TesseractEngine:
    def __init__(self, settings: Settings):
        import pytesseract

        self.version = "tesseract-" + str(pytesseract.get_tesseract_version())
        self.timeout = settings.ocr_timeout_s - 2

    def read(self, image: np.ndarray) -> OcrResult:
        import pytesseract
        from pytesseract import Output

        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        try:
            osd = pytesseract.image_to_osd(
                rgb, output_type=Output.DICT, timeout=min(10, self.timeout)
            )
            if osd.get("orientation_conf", 0) >= 5 and osd.get("rotate") in (90, 180, 270):
                image = np.ascontiguousarray(np.rot90(image, -int(osd["rotate"]) // 90))
                rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        except pytesseract.TesseractError:
            pass  # Too few characters for orientation is expected on short receipts.
        data = pytesseract.image_to_data(
            rgb, config="--psm 6", output_type=Output.DICT, timeout=self.timeout
        )
        rows: dict[tuple, list] = {}
        for i, text in enumerate(data["text"]):
            score = float(data["conf"][i])
            if text.strip() and score >= 0:
                key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
                x, y, w, h = (data[k][i] for k in ("left", "top", "width", "height"))
                rows.setdefault(key, []).append((text, score / 100, (x, y, x + w, y + h)))
        lines = [
            OcrLine(
                text=" ".join(v[0] for v in row),
                confidence=sum(v[1] for v in row) / len(row),
                box=(
                    min(v[2][0] for v in row),
                    min(v[2][1] for v in row),
                    max(v[2][2] for v in row),
                    max(v[2][3] for v in row),
                ),
            )
            for row in rows.values()
        ]
        return OcrResult(image, lines, self.version)


class FakeEngine:
    def read(self, image: np.ndarray) -> OcrResult:
        return OcrResult(image, [], "test-empty")


def create_engine(settings: Settings):
    cv2.setNumThreads(settings.cpu_threads)
    if settings.ocr_engine == "paddle":
        return PaddleEngine(settings)
    if settings.ocr_engine == "tesseract":
        return TesseractEngine(settings)
    if settings.environment != "test":
        raise ValueError("Fake OCR is restricted to tests.")
    return FakeEngine()
