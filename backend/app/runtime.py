from dataclasses import dataclass

from app.config import Settings
from app.db import Database
from app.storage import BlobStore, ImageSigner


@dataclass(frozen=True)
class Runtime:
    settings: Settings
    db: Database
    store: BlobStore
    signer: ImageSigner
