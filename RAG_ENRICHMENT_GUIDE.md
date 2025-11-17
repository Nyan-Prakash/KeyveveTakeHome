# RAG Enrichment for Flights and Transit

This document describes the implementation of RAG (Retrieval Augmented Generation) enrichment for flights and transit data in the Keyveve travel planner.

## Overview

The RAG enrichment feature automatically enhances fixture flight and transit data with real-world information extracted from travel guide markdown chunks using LLM-based extraction. This follows the same pattern as the existing lodging and attractions enrichment.

## Implementation Details

### New LLM Extractors

#### `_extract_flight_info_from_rag(chunks: list[str])`

Extracts airline and flight information from RAG chunks:

**Extracted Fields:**
- `airline`: Airline name (e.g., "LATAM", "American Airlines", "TAP Air Portugal") 
- `route`: Flight route if specified (e.g., "JFK-GIG", "LAX-MAD")
- `origin_airport`: Origin airport code (e.g., "JFK", "LAX")
- `dest_airport`: Destination airport code (e.g., "GIG", "MAD")
- `price_usd`: Flight price in USD (converted to cents)
- `duration_hours`: Flight duration in hours

**Example Input:**
```markdown
# Airlines to Rio de Janeiro

## LATAM Airlines
- Direct flights from JFK to GIG
- Flight duration: 9.5 hours  
- Typical pricing: $650-800 for economy
- Good service and reliability

## American Airlines
- Connects through Miami (MIA)
- Total journey: 11-12 hours
- Pricing around $550-700
```

#### `_extract_transit_info_from_rag(chunks: list[str])`

Extracts public transportation information from RAG chunks:

**Extracted Fields:**
- `mode`: Transportation mode (metro, bus, taxi, walk, or train)
- `route_name`: Specific route name or line (e.g., "Line 1", "Metro Red Line", "Bus 150")
- `neighborhoods`: List of neighborhoods or areas served by this route
- `price_usd`: Transit cost in USD (converted to cents)
- `duration_minutes`: Typical journey time in minutes (converted to seconds)

**Example Input:**
```markdown
# Rio de Janeiro Transportation

## Metro System
- Line 1 (Orange): Ipanema to Centro
- Line 2 (Green): Copacabana to Botafogo  
- Single ride: R$4.30 (~$1.25)
- Journey time: 15-25 minutes typical

## Bus Network
- Bus 474: Copacabana to Centro
- Express routes available
- Fare: R$3.50 (~$1.00)
- Can take 30-45 minutes in traffic
```

### Enhanced tool_exec_node

The `tool_exec_node` function has been enhanced to enrich both flights and transit with RAG data:

#### Flight Enrichment

1. **Fixture Generation**: Standard flight fixtures are created using `get_flights()`
2. **RAG Extraction**: Flight information is extracted from RAG chunks using `_extract_flight_info_from_rag()`
3. **Matching Logic**: Flights are matched by airport codes (origin/destination pairs)
4. **Data Override**: Matching RAG data overrides fixture data for:
   - Airline name (updates `flight_id` to include airline)
   - Price (`price_usd_cents`)
   - Duration (`duration_seconds`)
   - Provenance (marked as "fixture+rag")

#### Transit Enrichment

1. **Choice Processing**: Transit choices from the plan are processed
2. **Fixture Generation**: Transit legs are created using `get_transit_leg()`  
3. **RAG Extraction**: Transit information is extracted from RAG chunks
4. **Matching Logic**: Transit is matched by mode (metro, bus, taxi, etc.)
5. **Data Override**: Matching RAG data overrides fixture data for:
   - Duration (`duration_seconds`)
   - Provenance (marked as "fixture+rag")

### Fallback Strategy

Both implementations include safe fallback mechanisms:
- If LLM extraction fails, a warning is logged and empty dictionaries are returned
- If matching fails, original fixture data is preserved unchanged
- If no RAG chunks are available, the system operates normally with fixture data only

## Usage Instructions

### Adding New Flight Knowledge

To add new airline/flight information that will be picked up by RAG enrichment:

1. **Create markdown content** with airline information:
   ```markdown
   # Airlines to [Destination]
   
   ## [Airline Name]
   - Route: [ORIGIN-DEST] (use IATA codes)
   - Duration: X hours
   - Typical pricing: $XXX for economy
   - Additional details...
   ```

2. **Upload to RAG system** following existing ingestion process
3. **Ensure airport codes match** the fixture flight origins/destinations
4. **Include pricing in USD** for cost override
5. **Specify flight duration** for timing accuracy

### Adding New Transit Knowledge  

To add new public transportation information:

1. **Create markdown content** with transit details:
   ```markdown
   # [City] Transportation
   
   ## [Mode] System (Metro/Bus/etc.)
   - [Line/Route Name]: [Area A] to [Area B]
   - Fare: $X.XX USD (or equivalent with conversion note)
   - Journey time: XX minutes typical
   - Coverage: [neighborhoods served]
   ```

2. **Upload to RAG system** following existing ingestion process  
3. **Use standard mode names**: metro, bus, taxi, walk, train
4. **Include USD pricing** (with conversion notes if needed)
5. **Specify journey times** for duration override

### Knowledge Format Best Practices

- **Use clear headings** with `##` for airline/transit system names
- **Include airport IATA codes** for reliable flight matching
- **Specify pricing in USD** with conversion context if needed
- **Provide duration estimates** in standard units (hours for flights, minutes for transit)
- **Use consistent mode terminology** (metro vs subway vs underground)
- **Include route/line identifiers** for specific transit matching

## Integration with Existing RAG

The new extractors reuse the existing RAG infrastructure:
- **RAG chunks** are provided in `state.rag_chunks` from the `rag_node`
- **Chunk format** remains the same (markdown text)
- **Ingestion process** is unchanged - no new data pipeline needed
- **LLM calls** use the same OpenAI configuration as lodging/attractions

## Testing

A comprehensive test suite has been created in `test_rag_enrichment.py`:

- **Unit tests** for LLM extraction functions
- **Integration tests** for tool_exec_node enrichment
- **Sample RAG chunks** demonstrating expected markdown format
- **Validation** of enriched data structure and provenance

## Monitoring and Debugging

RAG enrichment includes logging for operational visibility:

- **Extraction failures** are logged with warnings
- **Matching failures** are logged for debugging
- **Provenance tracking** distinguishes fixture vs enriched data
- **Fallback usage** is transparent to ensure system reliability

## Future Enhancements

Potential improvements for the RAG enrichment system:

- **Fuzzy matching** for airport codes and transit modes
- **Multi-language support** for international travel guides
- **Confidence scoring** for extracted information
- **Cache management** for LLM extraction results
- **A/B testing** framework for enrichment effectiveness
