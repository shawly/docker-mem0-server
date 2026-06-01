# docker-mem0-server

Unofficial container images for the **[mem0](https://github.com/mem0ai/mem0)**
self-hosted server and dashboard.

[mem0](https://github.com/mem0ai/mem0) ships a `server/` directory with
Dockerfiles but does not publish prebuilt images. This repository is just a thin
build pipeline that mirrors those Dockerfiles into images on a schedule. It
contains **no upstream source code** — every build checks out mem0 at the
relevant commit/tag and builds it directly.

> [!WARNING]
> These images are **unofficial** and not affiliated with or endorsed by the
> mem0 project. They are provided **as-is, with no warranty and no support** —
> use them at your own risk. For the application itself, refer to the
> [upstream repository](https://github.com/mem0ai/mem0).

## Images

| Image | Source | Context |
| ----- | ------ | ------- |
| `ghcr.io/shawly/mem0-server` | [`server/Dockerfile`](https://github.com/mem0ai/mem0/blob/main/server/Dockerfile) | `server/` |
| `ghcr.io/shawly/mem0-dashboard` | [`server/dashboard/Dockerfile`](https://github.com/mem0ai/mem0/blob/main/server/dashboard/Dockerfile) | `server/dashboard/` |

Both are built for `linux/amd64` and `linux/arm64`.

### Tags

| Tag | Meaning |
| --- | ------- |
| `edge` | latest upstream default branch |
| `vX.Y.Z` | a specific upstream release that changed this component |
| `vX.Y`, `vX` | newest patch / minor of that line |
| `latest` | newest released version |
| `<sha>` | the exact upstream commit a build came from (short + full) |

```sh
docker pull ghcr.io/shawly/mem0-server:latest
docker pull ghcr.io/shawly/mem0-dashboard:edge
```

Every image carries OCI labels pointing back to its origin, including
`org.opencontainers.image.revision` (the upstream commit) and
`org.opencontainers.image.base.{name,digest}` (the base image it was built on).

## How it works

A daily [workflow](.github/workflows/mirror.yml) ([`discover.py`](.github/scripts/discover.py))
polls upstream and the registry, and builds an image only when:

1. **it doesn't exist yet** (a new release, or first run);
2. **the component source changed** — detected with `git diff` scoped to the
   component path, so a release that only touched docs never triggers a build;
3. **a base image drifted** — the digest stamped at build time no longer matches
   the current digest of the base tag. Base-drift rebuilds cover `edge` and the
   newest patch of every major/minor line, so security patches in
   `python`/`node` get picked up without source changes.

State is kept entirely in the registry (read back from image labels), so the
workflow is idempotent and safe to re-run or run manually
(**Actions → mirror → Run workflow**).

## License

[Apache-2.0](LICENSE), matching upstream mem0
(Copyright 2023 Taranjeet Singh). This repository adds only build tooling.
