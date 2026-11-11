"""Shared embedding dimension used by the ORM, migration, and embedders."""

# Must match the `chunks.embedding` vector column (Alembic 0003).
EMBEDDING_DIMENSIONS = 1536
