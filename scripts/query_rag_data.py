#!/usr/bin/env python3
"""Query and log all travel data from RAG database."""

import sys
from collections import defaultdict
from uuid import UUID

from sqlalchemy import select

from backend.app.db.models.destination import Destination
from backend.app.db.models.embedding import Embedding
from backend.app.db.models.knowledge_item import KnowledgeItem
from backend.app.db.session import get_session_factory


def extract_attractions_from_text(text: str) -> list[dict]:
    """Extract attraction names and prices from chunk text."""
    attractions = []
    lines = text.split('\n')
    
    for line in lines:
        # Look for patterns like "Museum Name: 150" or "**Museum Name**: 150"
        if ':' in line and any(word in line.lower() for word in ['museum', 'palace', 'park', 'temple', 'garden', 'beach', 'market']):
            parts = line.split(':')
            if len(parts) >= 2:
                name = parts[0].strip().replace('**', '').replace('*', '').replace('-', '').strip()
                price_part = parts[1].strip()
                
                # Try to extract price
                price = None
                for word in price_part.split():
                    try:
                        price = float(word.replace(',', '').replace('$', '').replace('€', ''))
                        break
                    except ValueError:
                        continue
                
                if name and len(name) > 3:
                    attractions.append({
                        'name': name,
                        'price_usd': price,
                        'line': line.strip()
                    })
    
    return attractions


def extract_flights_from_text(text: str) -> list[dict]:
    """Extract flight info from chunk text."""
    flights = []
    lines = text.split('\n')
    
    for line in lines:
        # Look for airline mentions and prices
        if any(airline in line for airline in ['LATAM', 'American', 'United', 'Delta', 'TAP', 'Iberia', 'Airlines']):
            price = None
            for word in line.split():
                cleaned = word.replace('$', '').replace(',', '').replace('€', '')
                try:
                    if cleaned.isdigit() or '.' in cleaned:
                        price = float(cleaned)
                        if 100 < price < 5000:  # Reasonable flight price range
                            break
                except ValueError:
                    continue
            
            flights.append({
                'name': line.strip()[:100],
                'price_usd': price,
                'line': line.strip()
            })
    
    return flights


def extract_lodging_from_text(text: str) -> list[dict]:
    """Extract lodging info from chunk text."""
    lodging = []
    lines = text.split('\n')
    
    for line in lines:
        # Look for hotel/lodging patterns
        if any(word in line.lower() for word in ['hotel', 'hostel', 'villa', 'resort', 'inn', 'lodge']):
            if ':' in line:
                parts = line.split(':')
                name = parts[0].strip().replace('**', '').replace('*', '').replace('-', '').strip()
                price_part = parts[1].strip() if len(parts) > 1 else ''
                
                price = None
                for word in price_part.split():
                    try:
                        price = float(word.replace(',', '').replace('$', '').replace('€', ''))
                        if 20 < price < 2000:  # Reasonable nightly rate
                            break
                    except ValueError:
                        continue
                
                if name and len(name) > 5:
                    lodging.append({
                        'name': name,
                        'price_usd': price,
                        'line': line.strip()
                    })
    
    return lodging


def extract_transit_from_text(text: str) -> list[dict]:
    """Extract transit info from chunk text."""
    transit = []
    lines = text.split('\n')
    
    for line in lines:
        # Look for transit patterns
        if any(word in line.lower() for word in ['metro', 'bus', 'train', 'taxi', 'line', 'transport']):
            price = None
            for word in line.split():
                cleaned = word.replace('$', '').replace(',', '').replace('€', '')
                try:
                    price = float(cleaned)
                    if 0.5 < price < 100:  # Reasonable transit price
                        break
                except ValueError:
                    continue
            
            transit.append({
                'name': line.strip()[:100],
                'price_usd': price,
                'line': line.strip()
            })
    
    return transit


def query_rag_database(dest_id: UUID | None = None):
    """Query and log all travel data from RAG database."""
    print("\n" + "="*80)
    print("RAG DATABASE TRAVEL DATA REPORT")
    print("="*80)
    
    factory = get_session_factory()
    session = factory()
    
    try:
        # Get all destinations or filter by dest_id
        if dest_id:
            dest_stmt = select(Destination).where(Destination.dest_id == dest_id)
        else:
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
            print(f"{'='*80}")
            
            # Get all embeddings for this destination
            stmt = (
                select(Embedding, KnowledgeItem)
                .join(KnowledgeItem, Embedding.item_id == KnowledgeItem.item_id)
                .where(KnowledgeItem.dest_id == dest.dest_id)
                .where(Embedding.chunk_text.isnot(None))
            )
            
            results = session.execute(stmt).all()
            
            if not results:
                print("\n   ⚠ No knowledge chunks found")
                continue
            
            print(f"\n   Analyzing {len(results)} knowledge chunks...")
            
            # Aggregate data
            all_attractions = []
            all_flights = []
            all_lodging = []
            all_transit = []
            
            for embedding, knowledge_item in results:
                text = embedding.chunk_text
                if not text:
                    continue
                
                all_attractions.extend(extract_attractions_from_text(text))
                all_flights.extend(extract_flights_from_text(text))
                all_lodging.extend(extract_lodging_from_text(text))
                all_transit.extend(extract_transit_from_text(text))
            
            # Deduplicate by name
            unique_attractions = {a['name']: a for a in all_attractions}.values()
            unique_flights = {f['name']: f for f in all_flights}.values()
            unique_lodging = {l['name']: l for l in all_lodging}.values()
            unique_transit = {t['name']: t for t in all_transit}.values()
            
            # Print Attractions
            print(f"\n   🎭 ATTRACTIONS ({len(unique_attractions)} found)")
            print("   " + "-"*76)
            for attr in sorted(unique_attractions, key=lambda x: x['name']):
                price_str = f"${attr['price_usd']:.2f}" if attr['price_usd'] else "Price not listed"
                print(f"   • {attr['name']:<50} {price_str:>20}")
            
            # Print Flights
            print(f"\n   ✈️  FLIGHTS ({len(unique_flights)} found)")
            print("   " + "-"*76)
            for flight in list(unique_flights)[:10]:  # Limit to 10
                price_str = f"${flight['price_usd']:.2f}" if flight['price_usd'] else "Price not listed"
                print(f"   • {flight['name']:<50} {price_str:>20}")
            
            # Print Lodging
            print(f"\n   🏨 LODGING ({len(unique_lodging)} found)")
            print("   " + "-"*76)
            for hotel in sorted(unique_lodging, key=lambda x: x['name']):
                price_str = f"${hotel['price_usd']:.2f}/night" if hotel['price_usd'] else "Price not listed"
                print(f"   • {hotel['name']:<50} {price_str:>20}")
            
            # Print Transit
            print(f"\n   🚇 TRANSIT ({len(unique_transit)} found)")
            print("   " + "-"*76)
            for trans in list(unique_transit)[:15]:  # Limit to 15
                price_str = f"${trans['price_usd']:.2f}" if trans['price_usd'] else "Price not listed"
                print(f"   • {trans['name']:<50} {price_str:>20}")
            
            # Summary stats
            print(f"\n   📊 SUMMARY")
            print("   " + "-"*76)
            print(f"   Total unique attractions: {len(unique_attractions)}")
            print(f"   Total unique flights:     {len(unique_flights)}")
            print(f"   Total unique lodging:     {len(unique_lodging)}")
            print(f"   Total unique transit:     {len(unique_transit)}")
            
            # Price statistics
            attr_with_price = [a for a in unique_attractions if a['price_usd']]
            if attr_with_price:
                avg_price = sum(a['price_usd'] for a in attr_with_price) / len(attr_with_price)
                print(f"   Avg attraction price:     ${avg_price:.2f}")
            
            hotel_with_price = [h for h in unique_lodging if h['price_usd']]
            if hotel_with_price:
                avg_hotel = sum(h['price_usd'] for h in hotel_with_price) / len(hotel_with_price)
                print(f"   Avg lodging price:        ${avg_hotel:.2f}/night")
        
        print(f"\n{'='*80}")
        print("END OF REPORT")
        print("="*80 + "\n")
        
    finally:
        session.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Query RAG database for travel data")
    parser.add_argument("--dest-id", type=str, help="Filter by destination ID (UUID)")
    
    args = parser.parse_args()
    
    dest_id = UUID(args.dest_id) if args.dest_id else None
    query_rag_database(dest_id)
