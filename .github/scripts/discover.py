#!/usr/bin/env python3
"""Decide which mem0 images need (re)building and emit a GitHub Actions matrix.

An image gets built when any of these is true:

1. it does not exist in the registry yet (bootstrap / new release);
2. the upstream component changed -- detected with ``git diff`` scoped to the
   component path, so a release that only touched docs never triggers a build;
3. its base image drifted to a new digest (only for the freshness set: ``edge``
   and the newest patch of every major/minor line).

State lives entirely in the registry: we read back the OCI labels stamped at
build time (revision, base digests) rather than keeping local bookkeeping, which
makes this idempotent and safe to re-run. Run from inside a full checkout of the
upstream repo (all tags + history). Writes ``matrix`` and ``has_builds`` to
``$GITHUB_OUTPUT``.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

REGISTRY = os.environ.get("REGISTRY", "ghcr.io")
OWNER = os.environ["OWNER"]
SEMVER = re.compile(r"^v\d+\.\d+\.\d+$")

# We build with our own vendored Dockerfiles (this repo) against the upstream
# source as build context. discover.py runs inside the upstream checkout, so our
# Dockerfiles live under $GITHUB_WORKSPACE.
WORKSPACE = Path(os.environ.get("GITHUB_WORKSPACE") or Path.cwd().parent)


@dataclass(frozen=True)
class Component:
    name: str
    image: str
    context: str      # build context, relative to the upstream checkout
    dockerfile: str   # our Dockerfile, relative to this repo (WORKSPACE)
    pathspec: tuple[str, ...]  # git pathspec scoping "did this component change?"


COMPONENTS = [
    Component(
        "server",
        f"{REGISTRY}/{OWNER}/mem0-server",
        "server",
        "dockerfiles/server/Dockerfile",
        ("server", ":(exclude)server/dashboard"),
    ),
    Component(
        "dashboard",
        f"{REGISTRY}/{OWNER}/mem0-dashboard",
        "server/dashboard",
        "dockerfiles/dashboard/Dockerfile",
        ("server/dashboard",),
    ),
]


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=check, text=True, capture_output=True)


def git(*args: str) -> str:
    return run("git", *args).stdout.strip()


def git_ok(*args: str) -> bool:
    return run("git", *args, check=False).returncode == 0


# --- registry: the source of truth for "what is already built" --------------

def image_exists(ref: str) -> bool:
    return run("crane", "digest", ref, check=False).returncode == 0


def label_value(ref: str, label: str) -> str:
    res = run("crane", "config", "--platform", "linux/amd64", ref, check=False)
    if res.returncode != 0:
        return ""
    labels = (json.loads(res.stdout or "{}").get("config") or {}).get("Labels") or {}
    return labels.get(label, "")


def base_drifted(ref: str) -> bool:
    """True if any base image stamped on ``ref`` now resolves to a new digest."""
    stored = label_value(ref, "mirror.base.digests")
    if not stored:
        return False
    for entry in stored.split(","):
        name, _, old = entry.partition("@")
        current = run("crane", "digest", name, check=False).stdout.strip()
        if current and current != old:
            return True
    return False


def dockerfile_digest(comp: Component) -> str:
    return "sha256:" + hashlib.sha256((WORKSPACE / comp.dockerfile).read_bytes()).hexdigest()


def dockerfile_changed(ref: str, comp: Component) -> bool:
    """True if our Dockerfile differs from the one ``ref`` was built with.

    Covers Dockerfiles we maintain ourselves (e.g. a Dependabot base-image bump):
    a published image carries the digest of the Dockerfile it was built from, so
    a mismatch — including images built before this label existed — forces a
    rebuild.
    """
    return label_value(ref, "mirror.dockerfile.digest") != dockerfile_digest(comp)


def needs_refresh(ref: str, comp: Component) -> bool:
    """An already-published image is stale if its base or Dockerfile changed."""
    return base_drifted(ref) or dockerfile_changed(ref, comp)


# --- git: the source of truth for "what changed" ----------------------------

def component_changed(comp: Component, frm: str, to: str) -> bool:
    return not git_ok("diff", "--quiet", frm, to, "--", *comp.pathspec)


# --- planning ---------------------------------------------------------------

def sha_tags(image: str, commit: str) -> list[str]:
    short = git("rev-parse", "--short=12", commit)
    return [f"{image}:{short}", f"{image}:{commit}"]


def plan_edge(comp: Component, head: str) -> dict | None:
    """Plan the edge build for one component, or None if nothing to do."""
    edge = f"{comp.image}:edge"
    if not image_exists(edge):
        build = True
    else:
        last = label_value(edge, "org.opencontainers.image.revision")
        if last == head:
            build = needs_refresh(edge, comp)  # source identical; base/Dockerfile?
        elif last and git_ok("cat-file", "-e", f"{last}^{{commit}}"):
            build = component_changed(comp, last, head) or needs_refresh(edge, comp)
        else:
            build = True  # unknown / unreachable previous build
    if not build:
        return None
    return entry(comp, ref=head, revision=head, version="edge",
                 tags=[edge, *sha_tags(comp.image, head)])


def plan_versions(comp: Component, tags: list[str]) -> list[dict]:
    # We keep only one released image per component: the newest release that
    # actually changed it. Older versions are never (re)built, so there is no
    # backfill — `latest`, `vX`, `vX.Y` all point at this single build.
    target: str | None = None
    prev: str | None = None
    for v in tags:
        if prev is None or component_changed(comp, prev, v):
            target = v
        prev = v
    if target is None:
        return []

    # Rebuild only if missing, or its base image / Dockerfile changed.
    if image_exists(f"{comp.image}:{target}") and not needs_refresh(f"{comp.image}:{target}", comp):
        return []

    major, minor, _ = target[1:].split(".")
    revision = git("rev-parse", f"{target}^{{commit}}")
    tags_out = [
        f"{comp.image}:{target}",
        *sha_tags(comp.image, revision),
        f"{comp.image}:v{major}.{minor}",
        f"{comp.image}:v{major}",
        f"{comp.image}:latest",
    ]
    return [entry(comp, ref=target, revision=revision, version=target, tags=tags_out)]


def entry(comp: Component, *, ref: str, revision: str, version: str,
          tags: list[str]) -> dict:
    return {
        "component": comp.name,
        "image": comp.image,
        "context": comp.context,
        "dockerfile": comp.dockerfile,
        "ref": ref,
        "revision": revision,
        "version": version,
        "tags": ",".join(tags),
        "title": comp.image.rsplit("/", 1)[-1],
    }


def main() -> None:
    head = git("rev-parse", "HEAD")
    versions = sorted(
        (t for t in git("tag", "-l", "v*").splitlines() if SEMVER.match(t)),
        key=lambda v: tuple(int(p) for p in v[1:].split(".")),
    )

    entries: list[dict] = []
    for comp in COMPONENTS:
        edge = plan_edge(comp, head)
        if edge:
            entries.append(edge)
        entries.extend(plan_versions(comp, versions))

    output = "\n".join(
        [f"matrix={json.dumps(entries)}",
         f"has_builds={'true' if entries else 'false'}"]
    )
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as fh:
        fh.write(output + "\n")

    print(f"Planned {len(entries)} build(s):", file=sys.stderr)
    for e in entries:
        print(f"  - {e['title']}:{e['version']}  [{e['tags']}]", file=sys.stderr)


if __name__ == "__main__":
    main()
