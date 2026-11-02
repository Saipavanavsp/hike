"""Peak memory of embedding the 50 seed jobs (used to size small instances).

python scripts/mem_probe.py [batch] [arena 0|1]
"""

import json
import resource
import sys

import onnxruntime as ort

from app.ml import embeddings
from app.services.matching import job_text


def rss_mb() -> int:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss // 1024


batch = int(sys.argv[1]) if len(sys.argv) > 1 else embeddings.ONNX_BATCH
arena = sys.argv[2] == "1" if len(sys.argv) > 2 else True
embeddings.ONNX_BATCH = batch
real_opts = ort.SessionOptions


def opts():
    o = real_opts()
    o.enable_cpu_mem_arena = arena
    return o


ort.SessionOptions = opts
with open("seed/data/jobs.json", encoding="utf-8") as f:
    jobs = json.load(f)
before = rss_mb()
emb = embeddings.get_embedder()
loaded = rss_mb()
embeddings.embed_documents([job_text(j["title"], j["skills"], j["description_md"]) for j in jobs])
print(
    f"batch={batch} arena={arena}: start {before} MB, model loaded {loaded} MB, peak {rss_mb()} MB"
)
