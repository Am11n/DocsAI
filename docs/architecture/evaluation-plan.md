# Evaluation plan (phase 5.5)

## Dataset

- 20-50 representative PDFs (contracts, invoices, letters).
- Ground truth metadata for each document:
  - `dato`, `parter`, `belop`, `valuta`, `nokkelvilkar`.
- 10-20 fixed semantic queries with expected relevant chunks.

## Metrics

- Metadata accuracy: exact/partial match per field.
- Retrieval relevance: top-k hit rate against expected chunk references.
- Grounding quality: answer claims supported by returned sources.
- Processing reliability: success rate and failures by phase.

## Procedure

1. Upload full evaluation set.
2. Export metadata/search/chat outputs.
3. Score against expected outcomes.
4. Tune prompt/chunking/top-k and rerun.
