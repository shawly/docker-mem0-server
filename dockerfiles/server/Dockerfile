# syntax=docker/dockerfile:1
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# docker-mem0-server: bundle the Milvus client, which upstream omits (mem0's
# milvus store raises ImportError without it). >=2.5 for Function/FunctionType.
RUN pip install --no-cache-dir "pymilvus>=2.5,<3"

COPY . .

# docker-mem0-server: let MEM0_VECTOR_STORE select the vector store at runtime.
# Upstream hardcodes pgvector in DEFAULT_CONFIG, and server_state's config merge
# can't switch stores cleanly (it leaks pgvector keys into MilvusDBConfig, which
# rejects extras). This swaps the vector_store block wholesale when
# MEM0_VECTOR_STORE=milvus; unset/"pgvector" keeps upstream behavior unchanged.
# The build fails loudly if the upstream anchor moves, so drift can't pass silently.
RUN python3 <<'PY'
import pathlib, sys

main = pathlib.Path("main.py")
src = main.read_text()
anchor = "initialize_state(DEFAULT_CONFIG)"

if anchor not in src:
    sys.exit(f"PATCH FAILED: {anchor!r} not found in main.py; upstream layout changed")

if "MEM0_VECTOR_STORE" not in src:
    block = (
        "import os as _vs_os\n"
        "_vs = _vs_os.environ.get('MEM0_VECTOR_STORE', '').strip().lower()\n"
        "if _vs == 'milvus':\n"
        "    _vs_cfg = {\n"
        "        'url': _vs_os.environ.get('MILVUS_URL', 'http://localhost:19530'),\n"
        "        'collection_name': _vs_os.environ.get('MILVUS_COLLECTION_NAME', 'mem0'),\n"
        "        'embedding_model_dims': int(_vs_os.environ.get('MILVUS_EMBEDDING_DIMS', '1536')),\n"
        "        'metric_type': _vs_os.environ.get('MILVUS_METRIC_TYPE', 'L2'),\n"
        "        'db_name': _vs_os.environ.get('MILVUS_DB_NAME', ''),\n"
        "    }\n"
        "    _vs_token = _vs_os.environ.get('MILVUS_TOKEN', '')\n"
        "    if _vs_token:\n"  # omit when empty so MilvusDBConfig's default applies (no auth)
        "        _vs_cfg['token'] = _vs_token\n"
        "    DEFAULT_CONFIG['vector_store'] = {'provider': 'milvus', 'config': _vs_cfg}\n"
        "elif _vs and _vs != 'pgvector':\n"
        "    raise SystemExit(f\"Unsupported MEM0_VECTOR_STORE={_vs!r}; use 'pgvector' or 'milvus'\")\n"
    )
    src = src.replace(anchor, block + anchor, 1)
    main.write_text(src)
    print("patched main.py: MEM0_VECTOR_STORE support added")
else:
    print("main.py already supports MEM0_VECTOR_STORE")
PY

EXPOSE 8000

ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
