#!/usr/bin/env python3
"""Query and log all travel data from RAG database (embeddings/knowledge)."""

import sys
from uuid import UUID

from sqlalchemy import select

from backend.app.db.models.destination import Destination
from backend.app.db.models.embedding import Embedding
from backend.app.db.models.knowledge_item import KnowledgeItem
from backend.app.db.session import get_session_factory


def extract_travel_data_from_chunks(chunks: list[str]) -> dict:
    """Extract structured travel data from RAG chunks using LLM parsing."""
    from openai import OpenAI
    from backend.app.config import get_openai_api_key
    
    if not chunks:
        return {"flights": [], "lodging": [], "transit": [], "attractions": []}
    
    # Combine chunks
    combined_text = "\n\n".join(chunks[:50])  # Limit to 50 chunks
    
    prompt = f"""Extract ALL travel information from this text. For each item, extract the NAME and PRICE.

Extract:
1. **Flights/Airlines**: airline name and price in USD
2. **Hotels/Lodging**: hotel name and price per night in USD
3. **Transit**: transit option name (e.g., "Metro Line 1") and price in USD
4. **Attractions**: attraction name and entrance price in USD

Text:
{combined_text}

Return a JSON object with this EXACT structure:
{{
  "flights": [{{"name": "LATAM Airlines", "price": 610}}],
  "lodging": [{{"name": "Hotel Villa Magna", "price": 400}}],
  "transit": [{{"name": "Metro Line 1", "price": 1.25}}],
  "attractions": [{{"name": "Prado Museum", "price": 15}}]
}}

IMPORTANT: 
- Only include items with clear names and prices
- Prices should be numbers (not strings)
- Return null for price if not mentioned
- Use exact names from the text"""
    
    try:
        client = OpenAI(api_key=get_openai_api_key())
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a precise data extractor. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.0,
            max_tokens=3000
        )
        
        content = response.choices[0].message.content
        
        # Extract JSON from markdown if present
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        
        import json
        return json.loads(content.strip())
        
    except Exception as e:
        print(f"⚠ Error parsing travel data: {e}")
        return {"flights": [], "lodging": [], "transit": [], "attractions": []}


def log_rag_database_contents():
    """Query and log all travel data from RAG database."""
    print("\n" + "="*80)
    print("RAG DATABASE TRAVEL DATA INVENTORY")
    print("="*80)
    
    factory = get_session_factory()
    session = factory()
    
    try:
        # Get all destinations
        dest_stmt = select(Destination)
        destinations = session.execute(dest_stmt).scalars().all()
        
        if not destinations:
            print("\n⚠ No destinations found in database")
            return
        
        print(f"\nFound {len(destinations)} destination(s)")
        
        for dest in destinations:
            print(f"\n{'='*80}")
            print(f"📍 DESTINATION: {dest.city}, {dest.country}")
            print(f"   Dest ID: {dest.dest_id}")
            print(f"   Org ID: {dest.org_id}")
            print(f"{'='*80}")
            
            # Get all knowledge items for this destination
            item_stmt = (
                select(KnowledgeItem)
                .where(KnowledgeItem.dest_id == dest.dest_id)
            )
            knowledge_items = session.execute(item_stmt).scalars().all()
            
            print(f"\n📚 Knowledge Items: {len(knowledge_items)}")
            
            if not knowledge_items:
                print("   No knowledge items uploaded yet")
                continue
            
            # Get all embeddings/chunks for this destination
            chunk_stmt = (
                select(Embedding.chunk_text)
                .join(KnowledgeItem, Embedding.item_id == KnowledgeItem.item_id)
                .where(KnowledgeItem.dest_id == dest.dest_id)
                .where(Embedding.chunk_text.isnot(None))
            )
            
            chunks = session.execute(chunk_stmt).scalars().all()
            
            print(f"📄 Text Chunks: {len(chunks)}")
            
            if not chunks:
                print("   No chunks found")
                continue
            
            print("\n🔍 Extracting travel data from chunks...")
            travel_data = extract_travel_data_from_chunks(list(chunks))
            
            # Log Flights
            print(f"\n✈️  FLIGHTS/AIRLINES ({len(travel_data.get('flights', []))})")
            print("-" * 80)
            if travel_data.get('flights'):
                for idx, flight in enumerate(travel_data['flights'], 1):
                    name = flight.get('name', 'Unknown')
                    price = flight.get('price')
                    price_str = f"${price:,.2f}" if price else "Price not specified"
                    print(f"   {idx}. {name:<40} {price_str}")
            else:
                print("   No flights found in data")
            
            # Log Lodging
            print(f"\n🏨 HOTELS/LODGING ({len(travel_data.get('lodging', []))})")
            print("-" * 80)
            if travel_data.get('lodging'):
                for idx, hotel in enumerate(travel_data['lodging'], 1):
                    name = hotel.get('name', 'Unknown')
                    price = hotel.get('price')
                    price_str = f"${price:,.2f}/night" if price else "Price not specified"
                    print(f"   {idx}. {name:<40} {price_str}")
            else:
                print("   No lodging found in data")
            
            # Log Transit
            print(f"\n🚇 TRANSIT OPTIONS ({len(travel_data.get('transit', []))})")
            print("-" * 80)
            if travel_data.get('transit'):
                for idx, transit in enumerate(travel_data['transit'], 1):
                    name = transit.get('name', 'Unknown')
                    price = transit.get('price')
                    price_str = f"${price:.2f}" if price else "Price not specified"
                    print(f"   {idx}. {name:<40} {price_str}")
            else:
                print("   No transit options found in data")
            
            # Log Attractions
            print(f"\n🎭 ATTRACTIONS ({len(travel_data.get('attractions', []))})")
            print("-" * 80)
            if travel_data.get('attractions'):
                for idx, attraction in enumerate(travel_data['attractions'], 1):
                    name = attraction.get('name', 'Unknown')
                    price = attraction.get('price')
                    price_str = f"${price:.2f}" if price else "Free/Price not specified"
                    print(f"   {idx}. {name:<40} {price_str}")
            else:
                print("   No attractions found in data")
            
            # Summary
            total_items = (
                len(travel_data.get('flights', [])) +
                len(travel_data.get('lodging', [])) +
                len(travel_data.get('transit', [])) +
                len(travel_data.get('attractions', []))
            )
            
            print(f"\n{'='*80}")
            print(f"📊 SUMMARY FOR {dest.city}")
            print(f"   Total Travel Items Extracted: {total_items}")
            print(f"   ✈️  Flights: {len(travel_data.get('flights', []))}")
            print(f"   🏨 Lodging: {len(travel_data.get('lodging', []))}")
            print(f"   🚇 Transit: {len(travel_data.get('transit', []))}")
            print(f"   🎭 Attractions: {len(travel_data.get('attractions', []))}")
            print(f"{'='*80}")
        
        print("\n" + "="*80)
        print("✓ RAG DATABASE INVENTORY COMPLETE")
        print("="*80 + "\n")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        session.close()


if __name__ == "__main__":
    log_rag_database_contents()
