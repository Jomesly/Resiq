from dataclasses import dataclass

from app.config import Settings
from app.extraction import extract
from app.schemas import Extraction, OcrLine, QualityReport
from app.vision.io import jpeg, load_image
from app.vision.preprocess import preprocess


@dataclass
class ProcessingResult:
    images: dict[str, bytes]
    width: int
    height: int
    quality: QualityReport
    lines: list[OcrLine]
    extraction: Extraction


def process(data: bytes, settings: Settings, engine) -> ProcessingResult:
    image, _, _ = load_image(data, settings.max_image_side, settings.max_image_pixels)
    prepared = preprocess(image)
    ocr = engine.read(prepared.image)
    extraction = extract(ocr.lines, ocr.engine)
    return ProcessingResult(
        images={
            **{key: jpeg(value) for key, value in prepared.stages.items()},
            "processed": jpeg(ocr.image),
        },
        width=ocr.image.shape[1],
        height=ocr.image.shape[0],
        quality=prepared.quality,
        lines=ocr.lines,
        extraction=extraction,
    )
