# Example: mem0 + dashboard with Milvus

A ready-to-run [`docker-compose.yml`](docker-compose.yml) for the self-hosted
mem0 server and dashboard, using an **external Milvus** as the vector store and
a small Postgres for the application database.

## What runs where

| Data | Store |
| ---- | ----- |
| Memory vectors | **your external Milvus** (`MILVUS_*`) |
| App data (users, API keys, request logs, settings) | Postgres (`postgres` service) |
| Memory change history | SQLite on the `mem0_history` volume |

Postgres is **not** the vector store here — it only holds the app's own tables.

## Usage

```sh
cp .env.example .env
# edit .env: OPENAI_API_KEY, JWT_SECRET, POSTGRES_PASSWORD, MILVUS_URL, ...
docker compose up -d
```

- Dashboard: <http://localhost:3000>  (first visit → `/setup` to create an admin)
- API + docs: <http://localhost:8000/docs>

Pin an image tag (e.g. `ghcr.io/shawly/mem0-server:v2.0.3`) instead of `:latest`
for reproducible deploys.

## Why these images differ from upstream

mem0's upstream image hardcodes **pgvector** and doesn't ship `pymilvus`, and its
runtime `/configure` can't switch stores (it merges your override onto the
pgvector defaults, so Milvus rejects the leftover keys). These images add
`pymilvus` and a small, env-gated patch so the store is chosen declaratively:

- `MEM0_VECTOR_STORE=milvus` → vectors go to `MILVUS_URL`
- unset / `pgvector` → identical to upstream

## Sharing one Milvus with other tools

A single Milvus instance hosts many collections (and databases), so mem0 can
share it with e.g. `claude-context` — they just use different collections.
For tidy isolation give mem0 its own database via `MILVUS_DB_NAME`, but **create
it first** (mem0 auto-creates collections, not databases):

```python
from pymilvus import MilvusClient
MilvusClient(uri="http://your-milvus-host:19530", token="").create_database("mem0")
```

Leave `MILVUS_DB_NAME` empty to use Milvus's `default` database.

## Don't have a Milvus yet?

Add a minimal standalone Milvus to the compose file and point
`MILVUS_URL=http://milvus:19530` at it:

```yaml
  milvus:
    image: milvusdb/milvus:v2.5.4
    command: ["milvus", "run", "standalone"]
    environment:
      ETCD_USE_EMBED: "true"
      ETCD_DATA_DIR: /var/lib/milvus/etcd
      COMMON_STORAGETYPE: local
    volumes:
      - milvus_data:/var/lib/milvus
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:9091/healthz"]
      interval: 30s
      start_period: 90s
      timeout: 20s
      retries: 5
    security_opt:
      - seccomp:unconfined
# and add `milvus_data:` under top-level volumes, plus a depends_on under mem0.
```

For anything beyond a quick trial, run Milvus from its
[official compose](https://milvus.io/docs/install_standalone-docker-compose.md).
