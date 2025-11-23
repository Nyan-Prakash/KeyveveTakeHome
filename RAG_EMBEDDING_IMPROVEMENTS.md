# RAG Embedding Enhancement Guide

This document explains the improvements made to the RAG (Retrieval-Augmented Generation) system and how to use them effectively.

## What Changed

### Before (Problems)
1. **No real embeddings**: Vector field was always NULL - embeddings weren't actually generated
2. **No semantic search**: Retrieval was based on recency (`ORDER BY created_at`), not relevance
3. **Inefficient**: LLM parsing of markdown chunks to extract venue info was slow and unreliable
4. **No diversity**: Retrieved chunks could be highly redundant

### After (Solutions)
1. **Real vector embeddings**: Using OpenAI's `text-embedding-3-small` (1536 dimensions)
2. **Semantic search**: Cosine similarity matching via pgvector (`<=>` operator)
3. **Batch processing**: Efficient batch embedding generation
4. **MMR diversity**: Maximal Marginal Relevance to reduce redundancy in results

## Architecture

```
Document Upload → Chunking → PII Stripping → Batch Embedding → pgvector Storage
                                                                        ↓
Query → Query Embedding → Cosine Similarity Search → MMR Filtering → Results
```

### Key Components

1. **`backend/app/graph/embedding_utils.py`**
   - `generate_embedding()`: Single text embedding
   - `batch_generate_embeddings()`: Efficient batch processing

2. **`backend/app/graph/rag.py`**
   - `retrieve_knowledge_for_destination()`: Main retrieval function
   - `_apply_mmr()`: Maximal Marginal Relevance for diversity
   - `_cosine_similarity()`: Similarity calculation

3. **`backend/app/api/knowledge.py`**
   - Document upload endpoint with real embedding generation
   - PII stripping before embedding
   - Batch processing for efficiency

4. **`scripts/backfill_embeddings.py`**
   - Migration tool for existing records
   - Batch processing with progress tracking

## Database Requirements

### PostgreSQL + pgvector (Required for Semantic Search)

**⚠️ IMPORTANT**: Semantic search with vector embeddings **requires PostgreSQL with pgvector extension**. 

The system will automatically fall back to recency-based retrieval if using SQLite.

To enable semantic search:

1. **Switch to PostgreSQL**:
   ```bash
   # Update .env
   POSTGRES_URL=postgresql://user:password@localhost:5432/keyveve
   ```

2. **Install pgvector extension**:
   ```sql
   CREATE EXTENSION vector;
   ```

3. **Run migrations** (schema already supports pgvector):
   ```bash
   alembic upgrade head
   ```

### Schema (Already Exists)

```sql
-- Embedding table (already exists)
CREATE TABLE embedding (
    embedding_id UUID PRIMARY KEY,
    item_id UUID REFERENCES knowledge_item(item_id),
    vector VECTOR(1536),  -- Supports embeddings with PostgreSQL + pgvector
    chunk_text TEXT,
    chunk_metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE
);

-- Index for fast cosine similarity search (already exists)
CREATE INDEX idx_embedding_vector 
ON embedding USING ivfflat (vector vector_cosine_ops) 
WITH (lists = 100);
```

### SQLite Mode (Development Fallback)

When using SQLite (default for development):
- ✅ Document upload and chunking works
- ✅ Recency-based retrieval works
- ❌ Vector embeddings are **not generated** (no OpenAI API calls)
- ❌ Semantic search is **disabled** (falls back to recency)

## Usage

### 1. Backfill Existing Data

Generate embeddings for existing knowledge items:

```bash
# Dry run to see how many records need embeddings
python scripts/backfill_embeddings.py --dry-run

# Actually generate embeddings (batch size 100)
python scripts/backfill_embeddings.py --batch-size 100
```

### 2. Upload New Documents

New documents will automatically get embeddings:

```bash
curl -X POST "http://localhost:8000/destinations/{dest_id}/knowledge/upload" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@guide.md"
```

### 3. Query with Semantic Search

The retrieval now automatically uses semantic search:

```python
from backend.app.graph.rag import retrieve_knowledge_for_destination
from uuid import UUID

# Retrieve relevant chunks for Madrid
chunks = retrieve_knowledge_for_destination(
    org_id=UUID("your-org-id"),
    city="Madrid",
    limit=20,
    use_mmr=True  # Enable diversity filtering
)
```

## Configuration

### Embedding Model

Currently using `text-embedding-3-small` (1536 dimensions):
- **Pros**: Fast, cost-effective, good quality
- **Cons**: Slightly lower quality than larger models

To upgrade to `text-embedding-3-large` (3072 dimensions):

1. Update `embedding_utils.py`:
   ```python
   dimensions = 3072  # Instead of 1536
   ```

2. Update database schema:
   ```sql
   ALTER TABLE embedding 
   ALTER COLUMN vector TYPE vector(3072);
   ```

3. Run backfill to regenerate all embeddings

### MMR Parameters

In `rag.py`, adjust the MMR balance:

```python
mmr_results = _apply_mmr(
    results, 
    query_vector, 
    lambda_param=0.5,  # 0.0 = max diversity, 1.0 = max relevance
    k=limit
)
```

- **λ = 0.5**: Balanced (default)
- **λ = 0.7**: More relevance, less diversity
- **λ = 0.3**: More diversity, less relevance

### Retrieval Strategy

```python
# Standard semantic search (fastest)
chunks = retrieve_knowledge_for_destination(
    org_id=org_id,
    city=city,
    limit=20,
    use_mmr=False
)

# With MMR diversity (better quality, slightly slower)
chunks = retrieve_knowledge_for_destination(
    org_id=org_id,
    city=city,
    limit=20,
    use_mmr=True
)
```

## Performance Considerations

### Costs

**OpenAI Embedding API Pricing** (as of 2025):
- `text-embedding-3-small`: $0.02 per 1M tokens
- For a 10-page travel guide (~5000 words):
  - Chunked into ~10 chunks
  - Cost: ~$0.0001 (negligible)

**Batch Processing Benefits**:
- Single API call for multiple texts (up to 2048)
- Reduces latency and API overhead
- More cost-effective than individual calls

### Query Performance

With pgvector IVFFlat index:
- **< 10ms** for similarity search on 10K embeddings
- **< 50ms** for 100K embeddings
- MMR adds ~5-10ms overhead

### Storage

- Each embedding: 1536 floats × 4 bytes = 6KB
- 1000 chunks = ~6MB storage
- Negligible for most use cases

## Monitoring

### Check Embedding Coverage

```sql
-- Count embeddings without vectors
SELECT COUNT(*) 
FROM embedding 
WHERE vector IS NULL;

-- Coverage percentage
SELECT 
    COUNT(CASE WHEN vector IS NOT NULL THEN 1 END) * 100.0 / COUNT(*) as coverage_pct
FROM embedding;
```

### Test Semantic Search

```python
from backend.app.graph.rag import retrieve_knowledge_for_destination

# Should return relevant chunks about museums
chunks = retrieve_knowledge_for_destination(
    org_id=your_org_id,
    city="Madrid",
    limit=5,
)

# Print top results
for i, chunk in enumerate(chunks, 1):
    print(f"{i}. {chunk[:200]}...")
```

## Troubleshooting

### Problem: "Falling back to recency-based retrieval"

**Cause**: No embeddings with vectors in database

**Solution**:
```bash
python scripts/backfill_embeddings.py
```

### Problem: Poor retrieval quality

**Solutions**:
1. Enable MMR: `use_mmr=True`
2. Increase limit: `limit=40` (then apply MMR to get top 20)
3. Improve chunking in `knowledge.py` (better sentence boundaries)
4. Check embedding coverage (run backfill)

### Problem: Slow retrieval

**Solutions**:
1. Disable MMR if not needed: `use_mmr=False`
2. Check pgvector index exists:
   ```sql
   SELECT indexname FROM pg_indexes 
   WHERE tablename = 'embedding';
   ```
3. Reduce fetch limit for MMR candidates

### Problem: OpenAI API errors

**Cause**: Rate limits or API key issues

**Solution**:
- Check API key: `echo $OPENAI_API_KEY`
- Reduce batch size: `--batch-size 50`
- Add retry logic (already implemented in `embedding_utils.py`)

## Best Practices

1. **Always use semantic search**: It's dramatically better than recency-based
2. **Enable MMR for user-facing results**: Reduces redundancy
3. **Batch uploads**: Process multiple documents together for efficiency
4. **Monitor coverage**: Run backfill after bulk imports
5. **Chunk size matters**: 1000 chars (~250 tokens) works well for travel content
6. **PII stripping**: Already implemented - don't disable it

## Future Enhancements

Potential improvements:
1. **Hybrid search**: Combine semantic + keyword (BM25) search
2. **Reranking**: Use cross-encoder model for better ranking
3. **Query expansion**: Generate multiple query variations
4. **Caching**: Cache query embeddings for repeated searches
5. **Metadata filtering**: Filter by document type, date, etc. before similarity search

## Summary

The improved RAG system now provides:
- ✅ **Real semantic search** with vector embeddings
- ✅ **Diverse results** via MMR
- ✅ **Efficient batch processing**
- ✅ **No database changes required**
- ✅ **Backward compatible** (fallback to recency if no embeddings)

Simply run the backfill script to enable semantic search on existing data!
