from dataclasses import dataclass

import cv2
import numpy as np

from app.schemas import QualityReport


@dataclass
class PreparedImage:
    image: np.ndarray
    stages: dict[str, np.ndarray]
    quality: QualityReport


def preprocess(image: np.ndarray) -> PreparedImage:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness = float(gray.mean())
    quality = QualityReport(
        blur_score=round(blur, 2),
        is_blurry=blur < 70,
        brightness=round(brightness, 2),
        is_dark=brightness < 65,
    )
    if quality.is_blurry:
        quality.warnings.append("This photo may be blurry. Check the small print carefully.")
    if quality.is_dark:
        quality.warnings.append("This photo is dark. A brighter photo may read better.")
    edges = cv2.Canny(cv2.GaussianBlur(gray, (5, 5), 0), 40, 120)
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((5, 5), np.uint8))
    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    warped = image
    for contour in sorted(contours, key=cv2.contourArea, reverse=True)[:5]:
        area = cv2.contourArea(contour) / (image.shape[0] * image.shape[1])
        quad = cv2.approxPolyDP(contour, 0.02 * cv2.arcLength(contour, True), True)
        if 0.3 < area < 0.97 and len(quad) == 4 and cv2.isContourConvex(quad):
            pts = quad.reshape(4, 2).astype(np.float32)
            sums, diffs = pts.sum(axis=1), np.diff(pts, axis=1).ravel()
            ordered = np.array(
                [
                    pts[np.argmin(sums)],
                    pts[np.argmin(diffs)],
                    pts[np.argmax(sums)],
                    pts[np.argmax(diffs)],
                ]
            )
            if len(np.unique(ordered, axis=0)) != 4:
                continue
            tl, tr, br, bl = ordered
            width = int(max(np.linalg.norm(tr - tl), np.linalg.norm(br - bl)))
            height = int(max(np.linalg.norm(bl - tl), np.linalg.norm(br - tr)))
            if min(width, height) < 100:
                continue
            transform = cv2.getPerspectiveTransform(
                ordered,
                np.float32([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]]),
            )
            warped = cv2.warpPerspective(
                image, transform, (width, height), borderValue=(255, 255, 255)
            )
            quality.document_found = True
            break
    # Small deskew only; arbitrary page rotation is handled separately by the OCR adapter.
    gray = cv2.cvtColor(warped, cv2.COLOR_BGR2GRAY)
    lines = cv2.HoughLinesP(
        cv2.Canny(gray, 50, 150),
        1,
        np.pi / 180,
        80,
        minLineLength=max(80, gray.shape[1] // 4),
        maxLineGap=15,
    )
    if lines is not None:
        angles = [
            float(np.degrees(np.arctan2(y2 - y1, x2 - x1)))
            for [[x1, y1, x2, y2]] in lines
            if x2 != x1
        ]
        small = [a for a in angles if 0.3 < abs(a) < 10]
        if len(small) >= 3:
            angle = float(np.median(small))
            h, w = gray.shape
            matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1)
            warped = cv2.warpAffine(warped, matrix, (w, h), borderValue=(255, 255, 255))
            quality.skew_angle = round(angle, 2)
    lab = cv2.cvtColor(warped, cv2.COLOR_BGR2LAB)
    lab[:, :, 0] = cv2.createCLAHE(clipLimit=2, tileGridSize=(8, 8)).apply(lab[:, :, 0])
    enhanced = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
    return PreparedImage(enhanced, {"warped": warped, "enhanced": enhanced}, quality)
