from __future__ import annotations

import hashlib
from pathlib import Path


HASH_BLOCK_SIZE_BYTES = 4 * 1024


class Sha256FileHasher:
    def __init__(
        self,
        chunk_size: int = HASH_BLOCK_SIZE_BYTES,
        partial_bytes: int = 64 * 1024,
    ) -> None:
        self._chunk_size = HASH_BLOCK_SIZE_BYTES
        self._partial_bytes = partial_bytes

    def partial_hash(self, path: Path) -> str:
        digest = hashlib.sha256()
        remaining = self._partial_bytes
        with path.open("rb") as handle:
            while remaining > 0:
                block = handle.read(min(self._chunk_size, remaining))
                if not block:
                    break
                digest.update(block)
                remaining -= len(block)
        return digest.hexdigest()

    def full_hash(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while True:
                block = handle.read(self._chunk_size)
                if not block:
                    break
                digest.update(block)
        return digest.hexdigest()
