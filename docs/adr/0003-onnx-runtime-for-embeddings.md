# 0003. MiniLM through ONNX Runtime in production, sentence-transformers as the reference

**Status:** Accepted

## Context
Matching uses `all-MiniLM-L6-v2` embeddings. `sentence-transformers` needs PyTorch (about
500 MB of RAM and a large image), which does not fit a 512 MB instance.

## Decision
Production runs the model's official ONNX export with `onnxruntime` and `tokenizers`,
with the same mean pooling and normalisation. `sentence-transformers` stays as a dev
dependency and the reference implementation. The model is downloaded at image build
time, not at start-up.

## Consequences
- Small image and memory footprint; no network access needed at start-up.
- Two implementations must agree: `tests/test_embeddings.py` checks the ONNX vectors
  against the reference (measured maximum difference 1.1e-7).
- Model upgrades need a new export and a rerun of that test and both evaluations.

## Alternatives considered
- **sentence-transformers everywhere**: simplest code, too heavy for the target host.
- **A hosted embedding API**: no model in the image, but per-request cost, latency, a
  vendor dependency, and resume text leaving the system.
