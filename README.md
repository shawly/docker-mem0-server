# docker-mem0-server

Unofficial container images for the **[mem0](https://github.com/mem0ai/mem0)**
self-hosted server and dashboard.

mem0 ships a `server/` directory with Dockerfiles but publishes no prebuilt
images. This repo is a thin pipeline that builds and publishes them on a
schedule. It contains **no upstream source code** — every build checks out mem0
at the relevant commit/tag and uses it as the build context.

It does, however, keep its **own copies of the Dockerfiles** under
[`dockerfiles/`](dockerfiles), because upstream isn't maintaining theirs (e.g.
the dashboard was pinned to an EOL Node that no longer builds). These are minimal
edits over upstream's Dockerfiles and are kept current via Dependabot; the
application code itself always comes from upstream unchanged.

## Images

| Image | Source | Context |
| ----- | ------ | ------- |
| `ghcr.io/shawly/mem0-server` | [`server/Dockerfile`](https://github.com/mem0ai/mem0/blob/main/server/Dockerfile) | `server/` |
| `ghcr.io/shawly/mem0-dashboard` | [`server/dashboard/Dockerfile`](https://github.com/mem0ai/mem0/blob/main/server/dashboard/Dockerfile) | `server/dashboard/` |

Both are built for `linux/amd64` and `linux/arm64`.

```sh
docker pull ghcr.io/shawly/mem0-server:latest
docker pull ghcr.io/shawly/mem0-dashboard:edge
```

Every image carries OCI labels pointing back to its origin — including
`org.opencontainers.image.revision` (the upstream commit) and
`org.opencontainers.image.base.{name,digest}` (the base image it was built on).

## Usage

See [`examples/`](examples) for a complete `docker-compose.yml` (server +
dashboard + Postgres) wired to an external **Milvus** vector store, plus an
exhaustive [`.env.example`](examples/.env.example).

The server image adds a couple of things upstream lacks: it bundles `pymilvus`
and lets you pick the vector store with `MEM0_VECTOR_STORE` (`pgvector` —
upstream default — or `milvus`). With `MEM0_VECTOR_STORE=milvus`, memory vectors
go to your Milvus while Postgres holds only the app database. See the
[example README](examples/README.md) for details.

## Tags

Tracking the upstream default branch:

- **`edge`** — the latest default-branch build
- **`<sha>`** — the exact upstream commit it was built from (both short and full)

Tracking upstream releases (`vX.Y.Z` tags that changed the component):

- **`vX.Y.Z`** — that exact release
- **`vX.Y`** / **`vX`** — the newest patch / minor in that line
- **`latest`** — the newest release overall
- **`<sha>`** — the upstream commit the release points at (short and full)

## Disclaimer

This is a personal, best-effort mirror, largely AI-assisted — treat it as
**slop until proven otherwise**. It is **unofficial**, not affiliated with or
endorsed by the mem0 project, and comes with **no warranty, no guarantees, and
no support**. Read the workflow before trusting it and use it entirely at your
own discretion and risk. For the application itself, see the
[upstream repository](https://github.com/mem0ai/mem0).

## License

[Apache-2.0](LICENSE), matching upstream mem0 (Copyright 2023 Taranjeet Singh).
This repository adds only build tooling.
