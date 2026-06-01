#!/usr/bin/env python3
"""Resolve a Dockerfile's concrete base images to pinned digests.

Parses every ``FROM`` instruction, skips references to earlier build stages
(e.g. ``FROM builder AS runner``) and unresolvable ``FROM ${ARG}`` bases, then
resolves each remaining image tag to its current registry digest via crane.

Prints ``name@sha256:...`` entries, comma-separated, on one line. The last entry
is the final stage's base (the runtime base).

Usage: bases.py path/to/Dockerfile
"""
from __future__ import annotations

import re
import subprocess
import sys

FROM_RE = re.compile(r"^\s*FROM\s+(?:--platform=\S+\s+)?(\S+)(?:\s+AS\s+(\S+))?", re.IGNORECASE)


def concrete_bases(dockerfile: str) -> list[str]:
    """Return concrete base images in order, deduplicated, skipping stages."""
    stages: set[str] = set()
    seen: set[str] = set()
    images: list[str] = []
    with open(dockerfile, encoding="utf-8") as fh:
        for line in fh:
            match = FROM_RE.match(line)
            if not match:
                continue
            image, alias = match.group(1), match.group(2)
            is_stage_ref = image in stages
            is_arg = image.startswith("$") or "${" in image
            if not (is_stage_ref or is_arg or image in seen):
                seen.add(image)
                images.append(image)
            if alias:
                stages.add(alias)
    return images


def digest(image: str) -> str:
    return subprocess.run(
        ["crane", "digest", image], check=True, text=True, capture_output=True
    ).stdout.strip()


def main(dockerfile: str) -> None:
    resolved = [f"{image}@{digest(image)}" for image in concrete_bases(dockerfile)]
    print(",".join(resolved))


if __name__ == "__main__":
    main(sys.argv[1])
