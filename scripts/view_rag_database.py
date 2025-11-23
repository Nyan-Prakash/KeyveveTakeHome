#!/usr/bin/env python3
"""View all RAG knowledge in the database - flights, lodging, transit, attractions."""

import sys
from uuid import UUID

from sqlalchemy import select

from backend.app.db.models.destination import Destination
from backend.app.db.models.embedding import Embedding
from backend.app.db.models.knowledge_item import KnowledgeItem
from backend.app.db.models.org import Org
from backend.app.db.session import get_session_factory


def log_rag_database():
    """Log all knowledge items, chunks, and extracted information."""
    print("\n" + "="*80)
    print("RAG DATABASE CONTENTS")
    print("="*80)
    
    factory = get_session_factory()
    session = factory()
    
    try:
        # Get all organizations
        orgs = session.query(Org).all()
        print(f"\n📊 Found {len(orgs)} organization(s)")
        
        for org in orgs:
            print(f"\n{'='*80}")
            print(f"ORGANIZATION: {org.name} (ID: {org.org_id})")
            print(f"{'='*80}")
            
            # Get destinations for this org
            destinations = session.query(Destination).filter_by(org_id=org.org_id).all()
            print(f"\n  📍 Destinations: {len(destinations)}")
            
            for dest in destinations:
                print(f"\n  {'─'*76}")
                print(f"  🌆 {dest.city}, {dest.country}")
                print(f"     Destination ID: {dest.dest_id}")
                if dest.geo:
                    if isinstance(dest.geo, dict):
                        print(f"     Coordinates: {dest.geo.get('lat')}, {dest.geo.get('lon')}")
                    else:
                        print(f"     Coordinates: {dest.geo}")
                print(f"  {'─'*76}")
                
                # Get knowledge items for this destination
                knowledge_items = session.query(KnowledgeItem).filter_by(
                    org_id=org.org_id,
                    dest_id=dest.dest_id
                ).all()
                
                print(f"\n  📚 Knowledge Items: {len(knowledge_items)}")
                
                for item in knowledge_items:
                    filename = item.item_metadata.get('filename', 'Unknown') if item.item_metadata else 'Unknown'
                    print(f"\n    📄 Document: {filename}")
                    print(f"       Item ID: {item.item_id}")
                    print(f"       Created: {item.created_at}")
                    print(f"       Content Length: {len(item.content)} characters")
                    
                    # Get embeddings/chunks for this item
                    embeddings = session.query(Embedding).filter_by(item_id=item.item_id).all()
                    print(f"       Chunks: {len(embeddings)}")
                    
                    # Count chunks with vectors
                    chunks_with_vectors = sum(1 for e in embeddings if e.vector is not None)
                    print(f"       Chunks with vectors: {chunks_with_vectors}/{len(embeddings)}")
                    
                    # Show sample chunks
                    if embeddings:
                        print(f"\n    📝 Sample Chunks:")
                        for idx, emb in enumerate(embeddings[:3], 1):
                            snippet = emb.chunk_text[:100] if emb.chunk_text else "No text"
                            has_vector = "✓" if emb.vector else "✗"
                            vector_dim = len(emb.vector) if emb.vector else 0
                            print(f"\n       [{idx}] {has_vector} Vector ({vector_dim} dims)")
                            print(f"           {snippet}...")
                            if emb.chunk_metadata:
                                print(f"           Metadata: {emb.chunk_metadata}")
                        
                        if len(embeddings) > 3:
                            print(f"\n       ... and {len(embeddings) - 3} more chunks")
                
                # Analyze content for entity types
                print(f"\n  🔍 Analyzing Content for Entities...")
                all_chunks = []
                for item in knowledge_items:
                    embeddings = session.query(Embedding).filter_by(item_id=item.item_id).all()
                    all_chunks.extend([e.chunk_text for e in embeddings if e.chunk_text])
                
                combined_text = " ".join(all_chunks).lower()
                
                # Count mentions of different entity types
                flight_keywords = ['flight', 'airline', 'airport', 'fly', 'latam', 'american airlines', 'united']
                lodging_keywords = ['hotel', 'hostel', 'accommodation', 'stay', 'resort', 'inn', 'airbnb']
                transit_keywords = ['metro', 'bus', 'subway', 'train', 'taxi', 'uber', 'transport']
                attraction_keywords = ['museum', 'park', 'palace', 'cathedral', 'beach', 'mountain', 'attraction', 'monument']
                
                flight_mentions = sum(combined_text.count(kw) for kw in flight_keywords)
                lodging_mentions = sum(combined_text.count(kw) for kw in lodging_keywords)
                transit_mentions = sum(combined_text.count(kw) for kw in transit_keywords)
                attraction_mentions = sum(combined_text.count(kw) for kw in attraction_keywords)
                
                print(f"\n  📊 Entity Mentions in Text:")
                print(f"     ✈️  Flights/Airlines: {flight_mentions} mentions")
                print(f"     🏨 Lodging: {lodging_mentions} mentions")
                print(f"     🚇 Transit: {transit_mentions} mentions")
                print(f"     🎭 Attractions: {attraction_mentions} mentions")
                
                # Extract sample entities
                if flight_mentions > 0:
                    print(f"\n  ✈️  Flight/Airline Samples:")
                    for chunk in all_chunks[:10]:
                        for keyword in flight_keywords:
                            if keyword in chunk.lower():
                                # Find sentence containing keyword
                                sentences = chunk.split('.')
                                for sent in sentences:
                                    if keyword in sent.lower():
                                        print(f"     • {sent.strip()[:120]}...")
                                        break
                                break
                
                if lodging_mentions > 0:
                    print(f"\n  🏨 Lodging Samples:")
                    for chunk in all_chunks[:10]:
                        for keyword in lodging_keywords:
                            if keyword in chunk.lower():
                                sentences = chunk.split('.')
                                for sent in sentences:
                                    if keyword in sent.lower():
                                        print(f"     • {sent.strip()[:120]}...")
                                        break
                                break
                
                if transit_mentions > 0:
                    print(f"\n  🚇 Transit Samples:")
                    for chunk in all_chunks[:10]:
                        for keyword in transit_keywords:
                            if keyword in chunk.lower():
                                sentences = chunk.split('.')
                                for sent in sentences:
                                    if keyword in sent.lower():
                                        print(f"     • {sent.strip()[:120]}...")
                                        break
                                break
                
                if attraction_mentions > 0:
                    print(f"\n  🎭 Attraction Samples:")
                    for chunk in all_chunks[:10]:
                        for keyword in attraction_keywords:
                            if keyword in chunk.lower():
                                sentences = chunk.split('.')
                                for sent in sentences:
                                    if keyword in sent.lower():
                                        print(f"     • {sent.strip()[:120]}...")
                                        break
                                break
        
        # Summary statistics
        print(f"\n{'='*80}")
        print("SUMMARY STATISTICS")
        print(f"{'='*80}")
        
        total_orgs = len(orgs)
        total_dests = session.query(Destination).count()
        total_items = session.query(KnowledgeItem).count()
        total_chunks = session.query(Embedding).count()
        total_vectors = session.query(Embedding).filter(Embedding.vector.isnot(None)).count()
        
        print(f"\n  Organizations: {total_orgs}")
        print(f"  Destinations: {total_dests}")
        print(f"  Knowledge Items: {total_items}")
        print(f"  Total Chunks: {total_chunks}")
        print(f"  Chunks with Vectors: {total_vectors} ({total_vectors/max(total_chunks,1)*100:.1f}%)")
        
        print(f"\n{'='*80}")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        session.close()


if __name__ == "__main__":
    log_rag_database()
