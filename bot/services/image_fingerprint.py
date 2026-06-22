from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

HASH_HEX_LENGTH = 16


class ImageFingerprintError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ImageFingerprint:
    ahash: str
    dhash: str


def image_fingerprint(image_bytes: bytes) -> ImageFingerprint:
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError as error:
        raise ImageFingerprintError("Pillow is required for image fingerprinting") from error

    try:
        with Image.open(BytesIO(image_bytes)) as image:
            grayscale = image.convert("L")
            return ImageFingerprint(
                ahash=_average_hash(grayscale),
                dhash=_difference_hash(grayscale),
            )
    except (OSError, UnidentifiedImageError) as error:
        raise ImageFingerprintError("Cannot decode image") from error


def _average_hash(image) -> str:
    resized = image.resize((8, 8))
    pixels = list(resized.getdata())
    average = sum(pixels) / len(pixels)
    value = 0
    for pixel in pixels:
        value = (value << 1) | int(pixel >= average)
    return f"{value:016x}"


def _difference_hash(image) -> str:
    resized = image.resize((9, 8))
    pixels = list(resized.getdata())
    value = 0
    for row in range(8):
        row_offset = row * 9
        for column in range(8):
            left = pixels[row_offset + column]
            right = pixels[row_offset + column + 1]
            value = (value << 1) | int(left > right)
    return f"{value:016x}"
