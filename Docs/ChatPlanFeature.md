# Chat Plan Feature Documentation

## Overview

The **Chat Plan** feature transforms the itinerary creation experience from a form-based interface to a natural, conversational chat interface. Users can describe their travel plans in natural language, and the system intelligently extracts their intent, applies all constraints, and generates a personalized itinerary.

## Key Features

### 1. Conversational Intent Extraction
- Users describe their trip naturally: "I want to visit Madrid for 5 days in March with a $3000 budget"
- System extracts structured intent (destination, dates, budget, preferences) using OpenAI
- Multi-turn conversation support for missing information
- Intelligent date and budget parsing (handles formats like "next March", "$3k", etc.)
- Automatic timezone inference based on destination

### 2. Smart Constraint Application
- All existing constraint verification and repair logic is reused
- Budget verification (10% slippage)
- Feasibility checks (timing, venue hours, DST, last train)
- Weather-based activity recommendations
- Preference matching (kid-friendly, themes, avoid overnight flights)

### 3. Conversational Edits
After an itinerary is generated, users can request changes naturally:
- "Make it $300 cheaper" → Reduces budget by $300
- "Shift dates forward 2 days" → Moves all dates
- "Make it more kid-friendly" → Updates preferences
- "Add more museums" → Adds cultural themes

### 4. Real-time Progress
- Shows generation progress with polling
- Displays itinerary when ready
- Formatted cost breakdown and daily activities

## Architecture

### Backend Components

#### 1. Intent Extractor (`backend/app/chat/intent_extractor.py`)
- Uses OpenAI function calling to extract `IntentV1` from conversation
- Handles partial extraction (asks follow-up questions)
- Maps natural language to structured data:
  ```python
  {
    "city": "Madrid",
    "date_window": {"start": "2024-03-15", "end": "2024-03-20", "tz": "Europe/Madrid"},
    "budget_usd_cents": 300000,
    "airports": ["JFK", "EWR"],
    "prefs": {"kid_friendly": false, "themes": ["art", "food"], "avoid_overnight": false}
  }
  ```

#### 2. Edit Parser (`backend/app/chat/edit_parser.py`)
- Parses natural language edit requests
- Uses OpenAI function calling to extract edit operations
- Maps to structured `EditPlanRequest`:
  - `delta_budget_usd_cents`: Budget change in cents
  - `shift_dates_days`: Days to shift (positive = later, negative = earlier)
  - `new_prefs`: Updated preferences

#### 3. Chat API Endpoint (`backend/app/api/chat.py`)
- `POST /chat`: Main conversation endpoint
- Supports two modes:
  1. **Initial planning**: Extract intent → start run when complete
  2. **Edit mode**: Parse edit → apply to existing itinerary
- Stateless (no persistence) - frontend manages conversation

### Frontend Component

#### Chat Plan Page (`frontend/pages/04_Chat_Plan.py`)
- Streamlit chat interface (`st.chat_message`, `st.chat_input`)
- Session state management for conversation history
- Polling for itinerary completion
- Formatted itinerary display
- Conversational edit support

## Usage

### Initial Planning Flow

1. User opens Chat Plan page
2. User types: "I want to visit Denver for a week in July with a $4000 budget"
3. System extracts: city, dates, budget
4. System asks: "Which airport would you like to depart from?"
5. User responds: "DIA"
6. System confirms details and starts generation
7. Itinerary is generated using existing graph pipeline
8. System displays formatted itinerary in chat

### Edit Flow

1. User views generated itinerary
2. User types: "Make it $500 cheaper and more kid-friendly"
3. System parses: `delta_budget_usd_cents: -50000`, `new_prefs: {kid_friendly: true}`
4. System applies edits and starts new run
5. Updated itinerary is displayed

## Configuration

### Environment Variables

Add to `.env`:
```bash
# OpenAI Configuration (required for Chat Plan feature)
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4-turbo-preview
```

### Dependencies

Added to `pyproject.toml`:
```toml
"openai>=1.0.0"
```

## Integration with Existing System

### Reused Components
- **Entire graph pipeline**: Intent → Planner → Selector → RAG → ToolExec → Resolve → Verifier → Repair → Synth → Responder
- **Constraint verification**: Budget, feasibility, weather, preferences
- **Repair logic**: Bounded repair with move limits
- **RAG enrichment**: Knowledge base integration
- **Database**: Same `agent_run` and `itinerary` tables
- **Streaming**: SSE endpoints for progress updates

### New Components
- Chat interface layer (frontend + backend endpoints)
- OpenAI integration for NLP
- Intent extraction and edit parsing modules

## Example Conversations

### Example 1: Complete Intent in One Message
```
User: I want to visit Madrid for 5 days in March with a $3000 budget, departing from JFK