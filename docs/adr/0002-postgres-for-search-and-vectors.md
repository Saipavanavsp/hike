# 0002. PostgreSQL full-text search and pgvector instead of Elasticsearch or a vector database

**Status:** Accepted

## Context
Search needs keyword matching with ranking, filters, typo tolerance and synonyms, and
matching needs 384-dimensional embeddings for jobs and resumes. There are tens to
thousands of jobs, not millions.

## Decision
Use PostgreSQL for everything:
- a weighted `tsvector` (title A, company and skills B, description C) maintained by a
  trigger, with a GIN index and `websearch_to_tsquery`/`phraseto_tsquery`;
- `pg_trgm` and `fuzzystrmatch` for typo correction against a vocabulary view;
- `pgvector` columns for job and resume embeddings, queried with cosine distance.

## Consequences
- One system to run, back up and restore; search results are always consistent with the
  data (no indexing lag, no sync job).
- Filters, joins and text search happen in one SQL statement.
- Relevance tuning is more manual than in Elasticsearch (no BM25 by default, no built-in
  synonym graphs); synonyms live in a JSON file and are expanded into the query.
- At large scale (millions of documents, heavy faceting) a dedicated search engine would
  be needed. The candidate set is capped at 1,000 and ranked in Python.

## Alternatives considered
- **Elasticsearch / OpenSearch**: better relevance tooling and scale; another cluster to
  run and keep in sync, and too heavy for a 512 MB free instance.
- **A vector database** (Pinecone, Qdrant): unnecessary at this size; pgvector keeps
  vectors next to the rows they describe.
