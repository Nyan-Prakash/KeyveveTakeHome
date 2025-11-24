"""Backfill embeddings for existing knowledge items.

This script generates vector embeddings for any existing embedding records
that don't have vectors yet (vector field is NULL).

Run this after upgrading to the new embedding system to enable semantic search.
"""

import sys
from uuid import UUID

from sqlalchemy import select

from backend.app.db.models.embedding import Embedding
from backend.app.db.session import get_session_factory
from backend.app.graph.embedding_utils import batch_generate_embeddings


def backfill_embeddings(batch_size: int = 100, dry_run: bool = False):
    """Generate embeddings for records that don't have them yet.

    Args:
        batch_size: Number of embeddings to process in each batch
        dry_run: If True, only count records needing embeddings without generating
    """
    factory = get_session_factory()
    session = factory()

    try:
        # Find embeddings without vectors
        stmt = (
            select(Embedding)
            .where(Embedding.vector.is_(None))
            .where(Embedding.chunk_text.isnot(None))
        )

        embeddings_to_update = session.execute(stmt).scalars().all()
        total_count = len(embeddings_to_update)

        print(f"\n{'='*60}")
        print(f"EMBEDDING BACKFILL")
        print(f"{'='*60}")
        print(f"Found {total_count} embedding records without vectors")

        if dry_run:
            print("DRY RUN - no changes will be made")
            return

        if total_count == 0:
            print("✓ All embeddings already have vectors!")
            return

        # Process in batches
        successful = 0
        failed = 0

        for i in range(0, total_count, batch_size):
            batch = embeddings_to_update[i : i + batch_size]
            batch_texts = [emb.chunk_text for emb in batch]

            print(f"\nProcessing batch {i // batch_size + 1} ({len(batch)} items)...")

            # Generate embeddings
            vectors = batch_generate_embeddings(batch_texts)

            # Update records
            for embedding, vector in zip(batch, vectors):
                if vector:
                    embedding.vector = vector
                    successful += 1
                else:
                    failed += 1
                    print(f"  ⚠ Failed to generate embedding for {embedding.embedding_id}")

            # Commit batch
            session.commit()
            print(f"  ✓ Committed {len(batch)} records")

        print(f"\n{'='*60}")
        print(f"BACKFILL COMPLETE")
        print(f"{'='*60}")
        print(f"Successful: {successful}/{total_count}")
        print(f"Failed: {failed}/{total_count}")
        print(f"Success rate: {successful / total_count * 100:.1f}%")

    except Exception as e:
        print(f"\n❌ Error during backfill: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Backfill embeddings for existing knowledge items"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=100,
        help="Number of embeddings to process per batch (default: 100)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only count records needing embeddings without generating",
    )

    args = parser.parse_args()

    backfill_embeddings(batch_size=args.batch_size, dry_run=args.dry_run)
