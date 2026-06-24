"""HTTP Range header parsing utilities."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ByteRange:
    start: int
    end: int  # inclusive

    @property
    def length(self) -> int:
        return self.end - self.start + 1


def parse_range(range_header: str | None, file_size: int) -> ByteRange:
    """Parse a single-range `Range: bytes=start-end` header.

    Falls back to the full file when the header is absent or malformed. Only the
    first range of a multi-range request is honored (sufficient for media
    players, which issue single ranges).
    """
    if file_size <= 0:
        return ByteRange(0, 0)

    last = file_size - 1
    if not range_header or not range_header.startswith("bytes="):
        return ByteRange(0, last)

    spec = range_header[len("bytes="):].split(",")[0].strip()
    start_s, _, end_s = spec.partition("-")

    try:
        if start_s == "":
            # Suffix range: bytes=-N  => last N bytes.
            n = int(end_s)
            if n <= 0:
                return ByteRange(0, last)
            start = max(0, file_size - n)
            return ByteRange(start, last)

        start = int(start_s)
        end = int(end_s) if end_s else last
    except ValueError:
        return ByteRange(0, last)

    start = max(0, start)
    end = min(end, last)
    if start > end:
        # Unsatisfiable; clamp to a valid full-file range.
        return ByteRange(0, last)
    return ByteRange(start, end)
