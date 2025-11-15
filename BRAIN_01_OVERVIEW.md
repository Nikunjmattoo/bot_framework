# 🧠 BRAIN - PART 1: OVERVIEW & CORE FLOW

**Version:** 3.0 (Multi-Document Series)  
**Date:** November 15, 2025  
**Status:** Production Ready - Includes Fuzzy Search & Streaming Updates

---

## 📚 DOCUMENTATION SERIES

This is **Part 1 of 5** in the Brain documentation series:

| File | Content | Status |
|------|---------|--------|
| **BRAIN_01_OVERVIEW.md** ← YOU ARE HERE | System architecture, intent detection, brain flow, streaming | ✅ Complete |
| **BRAIN_02_COMPONENTS.md** | Intent ledger, action registry, queue, schemas, workflows | ⏳ Next |
| **BRAIN_03_DATABASE.md** | Complete database schema, tables, indexes, JSONB structures | ⏳ Next |
| **BRAIN_04_INTEGRATION.md** | API patterns, error handling, idempotency, configuration | ⏳ Next |
| **BRAIN_05_ADVANCED_PATTERNS.md** | Innovative patterns, reliability, telemetry, cold paths | ⏳ Next |

---

## 📚 ORIGINAL SOURCES

Content unified from:
- ✅ `architecture.md` - System overview, multi-tenancy, innovative patterns
- ✅ `brain.md` - Detailed brain components, database schema, implementation
- ✅ `intents.md` - Intent types, brain wires, multi-intent support

**Changes in v3.0:**
- ✅ Added fuzzy search with 3 canonical name candidates
- ✅ Added streaming updates at each processing step
- ✅ Reordered brain flow (action lookup BEFORE intent logging)
- ✅ Added exit points for action_not_found and blocked states
- ✅ Merged all duplicate content
- ✅ **ZERO information loss** from original files
- ✅ Split into 5 manageable documents

---

## 📑 TABLE OF CONTENTS (PART 1)

1. [Executive Overview](#1-executive-overview)
2. [System Architecture](#2-system-architecture)
3. [Multi-Tenant Scalability](#3-multi-tenant-scalability)
4. [Message Handler Workflow](#4-message-handler-workflow)
5. [Intent Detection](#5-intent-detection)
6. [Brain-Intent Wiring](#6-brain-intent-wiring)
7. [Brain Processing Flow](#7-brain-processing-flow) ⭐ **UPDATED**
8. [Streaming Updates](#8-streaming-updates) ⭐ **NEW**

**➡️ Continue to BRAIN_02_COMPONENTS.md for:**
- Core Components (Intent Ledger, Action Registry, Queue, Schemas, Workflows)

---

# 1. EXECUTIVE OVERVIEW

## 1.1 Purpose

The Brain is the central orchestration component of a production-grade, multi-tenant conversational AI framework. It receives intents detected by the Intent Detector and manages the complete lifecycle of actions, workflows, and state management required to fulfill user requests.

**Design Philosophy:** Data-driven orchestration with context-aware memory systems, combining enterprise-grade reliability with intelligent LLM-powered decision making.

## 1.2 Key Responsibilities

The Brain handles:

1. **Intent Management:** Tracks all detected intents across conversation turns with complete audit trail
2. **Action Orchestration:** Maps intents to actions with fuzzy search and manages execution
3. **State Management:** Maintains conversation state, task progress, and user data across turns
4. **Workflow Coordination:** Executes multi-step workflows with dependency management and branching
5. **Eligibility Validation:** Determines action eligibility based on real-time user data from brand APIs
6. **Queue Management:** Manages action execution queues with retry policies, persistence, and checkpointing
7. **Real-Time Data Integration:** Fetches and validates user data from brand APIs with caching
8. **Error Handling:** Manages failures, retries, dead letter queue, and escalations gracefully
9. **Streaming Updates:** Emits real-time progress updates for UI/voice/video interfaces
10. **Token Budget Control:** Dynamically adjusts context window based on task complexity

## 1.3 Design Philosophy

**Production-Grade Reliability:**
- Queue persistence survives server crashes
- Idempotency prevents duplicate executions
- Retry policies with exponential backoff (2s, 4s, 8s, 16s)
- Dead letter queue for permanent failures
- Comprehensive error tracking and escalation
- Distributed locks for concurrency control

**Real-Time Data Validation:**
- Fresh user data fetched from brand APIs on-demand
- Schema-based validation with computed key statuses (none/incomplete/complete)
- Action eligibility determined by actual data state (not just permissions)
- Cached data with configurable TTL (5 minutes default)
- Stale cache fallback for API failures

**Intelligent Orchestration:**
- Fuzzy search with 3 canonical name candidates from LLM
- Multi-intent detection with dependency resolution
- Dynamic token budget allocation based on task complexity
- Hierarchical multi-resolution RAG for temporal + semantic search
- Contextual reference resolution ("the second one", "that product")

**Flexible & Extensible:**
- Instance-specific action configurations
- Reusable workflows across multiple actions
- Plugin architecture for new action types
- Brand-specific schema definitions
- Interface-agnostic (text/voice/video)

---

# 2. SYSTEM ARCHITECTURE

## 2.1 High-Level Architecture Diagram

```
┌─────────────┐
│   Message   │
│   Handler   │  → Identity Resolution (brand-scoped)
└──────┬──────┘  → Session Management (timeout, resumption)
       │         → Context Preparation (history, user_context)
       │         → Adapter Building
       │
       ▼
┌─────────────┐
│ Orchestrator│  → Routes to Intent Detector
└──────┬──────┘  → Triggers Cold Paths (async)
       │         → Manages Response Flow
       │
       ├──────────────────┬────────────────┐
       │                  │                │
       ▼                  ▼                ▼
┌─────────────┐    ┌──────────┐    ┌──────────┐
│   Intent    │    │  Brain   │    │   Cold   │
│  Detector   │    │Processor │    │  Paths   │
│   (LLM)     │    │          │    │ (Async)  │
└──────┬──────┘    └────┬─────┘    └────┬─────┘
       │                │               │
       │                │               ├─→ Session Summary
       │                │               ├─→ Topic Extraction
       │                │               └─→ Timestamp Extraction
       │                │
       │                ├─→ Intent Ledger
       │                ├─→ Action Queue
       │                ├─→ Schema Validation
       │                ├─→ Workflow Engine
       │                ├─→ Streaming Updates
       │                └─→ Next Narrative
       │                
       └────────┬─────────┘
                │
                ▼
      ┌─────────────────┐
      │    Response     │
      │   Generator     │  → Uses next_narrative
      │     (LLM)       │  → Returns to user
      └─────────────────┘
```

## 2.2 Brain Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     INTENT DETECTOR                              │
│  (Detects user intents, extracts entities, determines           │
│   self-response vs brain-required)                              │
│  **NEW:** Returns 3 canonical name candidates for fuzzy search  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         │ Intents + Entities + Candidates
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                         BRAIN                                    │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  1. ACTION LOOKUP (FUZZY SEARCH) ⭐ NEW                  │  │
│  │     - Try 3 candidates from intent detector              │  │
│  │     - Exact match → fuzzy match → synonym match          │  │
│  │     - EXIT if not found (action_not_found)               │  │
│  │     - Emit streaming update                              │  │
│  └──────────────────────────────────────────────────────────┘  │
│                         │                                        │
│                         ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  2. INTENT LEDGER                                        │  │
│  │     - Logs intents with match_type ⭐ NEW                │  │
│  │     - Status: new/blocked/queued/completed               │  │
│  │     - Emit streaming update                              │  │
│  └──────────────────────────────────────────────────────────┘  │
│                         │                                        │
│                         ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  3. SCHEMA STATE MANAGER                                 │  │
│  │     - Fetches user data from brand APIs                  │  │
│  │     - Computes key statuses (none/incomplete/complete)   │  │
│  │     - Caches with TTL (5 min)                            │  │
│  │     - Emit streaming update                              │  │
│  └──────────────────────────────────────────────────────────┘  │
│                         │                                        │
│                         ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  4. ELIGIBILITY CHECKER                                  │  │
│  │     - User tier + schema dependencies + blockers         │  │
│  │     - Dependencies + opposites                           │  │
│  │     - EXIT if not eligible (blocked) ⭐ NEW              │  │
│  │     - Emit streaming update                              │  │
│  └──────────────────────────────────────────────────────────┘  │
│                         │                                        │
│                         ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  5. PARAMETER COLLECTOR                                  │  │
│  │     - Checks params complete                             │  │
│  │     - EXIT if missing (collecting_params) ⭐ NEW         │  │
│  │     - Creates answer_sheet                               │  │
│  │     - Emit streaming update                              │  │
│  └──────────────────────────────────────────────────────────┘  │
│                         │                                        │
│                         ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  6. ACTION QUEUE MANAGER                                 │  │
│  │     - Adds to queue with idempotency key                 │  │
│  │     - Priority + retry policy                            │  │
│  │     - Checkpoints to database                            │  │
│  │     - Emit streaming update                              │  │
│  └──────────────────────────────────────────────────────────┘  │
│                         │                                        │
│                         ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  7. ACTION EXECUTOR                                      │  │
│  │     - Calls brand APIs with timeout                      │  │
│  │     - Retry with exponential backoff                     │  │
│  │     - Moves to DLQ on failure                            │  │
│  │     - Emit progress updates ⭐ NEW                       │  │
│  └──────────────────────────────────────────────────────────┘  │
│                         │                                        │
│                         ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  8. WORKFLOW COORDINATOR                                 │  │
│  │     - Manages multi-step workflows                       │  │
│  │     - Tracks workflow progress                           │  │
│  │     - Handles workflow branching                         │  │
│  └──────────────────────────────────────────────────────────┘  │
│                         │                                        │
│                         ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  9. RESPONSE GENERATOR                                   │  │
│  │     - Updates active task                                │  │
│  │     - Generates next narrative (must + optional)         │  │
│  │     - Updates 8 wires for next turn                      │  │
│  │     - Creates response payload                           │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         │ Response + Next Narrative + Wires
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LLM RESPONDER                                 │
│  (Generates natural language response based on next narrative)  │
└─────────────────────────────────────────────────────────────────┘
```

## 2.3 Data Flow

**Turn N (User sends message):**

1. User message → Message Handler
2. Message Handler → Identity resolution (brand-scoped)
3. Message Handler → Session management
4. Message Handler → Build adapter payload
5. Adapter → Intent Detector (LLM)
6. Intent Detector → Brain (with detected intents + 3 candidates)
7. Brain → Fuzzy action lookup **⭐ NEW**
8. Brain → Logs intents to Intent Ledger
9. Brain → Fetches user schema state from APIs (if needed)
10. Brain → Computes action eligibility
11. Brain → Adds eligible actions to queue OR collects params
12. Brain → Processes queue (execute or retry)
13. Brain → Generates next narrative + updates wires
14. Brain → LLM Responder (with narrative)
15. LLM Responder → User (natural language response)

**Parallel (Async):**
- Streaming updates emitted at each step **⭐ NEW**
- Queue processor handles retries for failed actions
- Schema cache refreshes based on TTL
- Dead letter queue monitored for manual intervention
- Workflow coordinator tracks multi-step flows
- Cold path generates session summary

## 2.4 Component Interactions

```
Intent Ledger ←──────┐
                     │
Schema State ←───────┤
                     │
Action Registry ←────┼──── Brain Core Logic
                     │
Action Queue ←───────┤
                     │
Workflow Engine ←────┤
                     │
Streaming Updates ←──┘  ⭐ NEW

Action Queue ──→ Action Executor ──→ Brand APIs
                                  └──→ Action Execution Log
                                  └──→ Dead Letter Queue (on failure)

Schema State ──→ Brand APIs (GET user data)
              ↓
         Cache (5 min TTL)

Streaming Updates ──→ sessions.state["streaming_updates"]
                   └──→ Interface translation layer
```

---

# 3. MULTI-TENANT SCALABILITY

## 3.1 Architecture: Brand → Instance → Configuration

```
Brand (Tenant)
  ├─ Identity System (brand-scoped)
  ├─ Instances (Channels)
  │    ├─ WhatsApp Bot
  │    ├─ Web Chat
  │    └─ Mobile App
  └─ Data Isolation (complete)

Instance
  ├─ Active Configuration
  │    ├─ Template Set (intent → response mappings)
  │    ├─ LLM Models (per function)
  │    ├─ Token Budgets (per section)
  │    └─ Action Registry
  ├─ Sessions
  └─ Schemas
```

## 3.2 Design Principles

**Brand-Scoped Identity:**
- Same phone number = different users per brand
- Privacy-first multi-tenancy
- Complete data isolation
- No cross-brand data leakage

**Dynamic Configuration:**
- Switch LLM models without deployment
- Update templates in real-time
- Adjust token budgets per task
- Add/remove actions without code changes

**Cost Tracking:**
- Pricing snapshots at time of usage
- Per-session cost calculation
- Token usage tracking (planned vs actual)
- Historical billing accuracy

**Session State:**
- One active session per (user, instance)
- Timeout management (configurable)
- Session resumption
- State persistence

## 3.3 vs State-of-the-Art

| Feature | Our System | Intercom/Drift | Rasa | DialogFlow CX |
|---------|-----------|----------------|------|---------------|
| **Multi-tenancy** | True (brand-scoped) | Limited | Manual setup | N/A |
| **Data Isolation** | Complete | Partial | Manual | N/A |
| **Dynamic Config** | Yes | Limited | No | Limited |
| **Cost Control** | Per-session tracking | No | N/A | Expensive |
| **Schema Validation** | Real-time API | No | Slots only | Form-based |
| **Token Budget** | Dynamic | N/A | N/A | N/A |

**Our Advantage:** True multi-tenancy with complete data isolation, dynamic configuration, real-time schema validation, and granular cost control.

---

# 4. MESSAGE HANDLER WORKFLOW

## 4.1 Request Processing Flow

```
1. Message Arrives (WhatsApp/Web/API)
   ↓
2. Channel Detection
   ├─ WhatsApp: Extract E.164 phone, match recipient_number → instance
   ├─ Web/App: Extract auth_token/device_id, extract instance_id
   └─ Broadcast: Multiple recipients
   ↓
3. Identity Resolution (Brand-Scoped)
   ├─ Query: (identifier_value, identifier_type, channel, brand_id)
   ├─ If found: Load user
   └─ If not found:
      ├─ If accept_guest_users: Create anonymous user (tier=guest)
      └─ Else: Create verified user + identifier
   ↓
4. Session Management
   ├─ Query: (user_id, instance_id, active=true)
   ├─ Check: last_message_at within timeout window?
   ├─ If active & valid: Use existing session
   └─ If expired/none: End old, create new
   ↓
5. Idempotency Check
   ├─ Acquire lock on request_id
   ├─ If locked: Return cached response
   └─ If available: Proceed
   ↓
6. Context Preparation
   ├─ Load conversation history (last N messages)
   ├─ Build user_context (tier, identifiers, metadata)
   └─ Fetch token_plan from session
   ↓
7. Build Adapter Payload
   {
     "user_message": "...",
     "user_id": "...",
     "session_id": "...",
     "user_type": "verified",
     "template": {
       "json": {
         "intent": {"template": "intent_v1"},
         "response": {"template": "response_v1"}
       }
     },
     "token_plan": {
       "templates": {
         "intent_v1": {
           "provider": "openai",
           "api_model_name": "gpt-4o-mini",
           "temperature": 0.3,
           "max_tokens": 500
         }
       }
     }
   }
   ↓
8. Call Orchestrator (async)
   ↓
9. Store Response
   ├─ Save message to DB
   ├─ Record token usage (with pricing snapshot)
   └─ Update session timestamps
   ↓
10. Return to User
```

## 4.2 Key Features

- **Multi-channel support:** WhatsApp, Web, Mobile, Broadcast
- **Brand-scoped identity:** Same identifier = different users per brand
- **Session timeout:** Configurable (default 30 minutes)
- **Idempotency:** Distributed locks prevent duplicate processing
- **Token tracking:** Usage + cost per session
- **Monitoring:** Trace IDs, structured logs, Langfuse integration

## 4.3 Missing (By Design)

- Streaming (SSE) - not implemented yet
- Attachments - future feature
- PII protection - handled at application level
- Multi-language - handled by templates
- Live agent handoff - future feature

---

# 5. INTENT DETECTION

## 5.1 Intent Types (8 Types)

### 5.1.1 Self-Response Intents (Auto-Handled)

**Intent 1: greeting**
- **Examples:** "Hi", "Hello", "Hey there", "Good morning"
- **Response:** "Hello! How can I help you today?"
- **Brain Required:** NO
- **Auto-Response:** YES

**Intent 2: goodbye**
- **Examples:** "Bye", "See you", "Thanks, that's all", "Goodbye"
- **Response:** "Goodbye! Feel free to return anytime."
- **Brain Required:** NO
- **Auto-Response:** YES

**Intent 3: gratitude**
- **Examples:** "Thanks", "Thank you", "Appreciate it", "Cheers"
- **Response:** "You're welcome! Happy to help."
- **Brain Required:** NO
- **Auto-Response:** YES

**Intent 4: chitchat**
- **Examples:** "How are you?", "Tell me a joke", "What's your name?"
- **Response:** Casual, friendly response
- **Brain Required:** NO
- **Auto-Response:** YES

### 5.1.2 Brain-Required Intents

**Intent 5: action**
- **Examples:** "Apply to this job", "Book appointment", "Process payment"
- **Processing:** Brain maps to canonical_action, checks eligibility, executes
- **Brain Required:** YES
- **Auto-Response:** NO
- **NEW:** Returns 3 canonical name candidates for fuzzy search

**Output Format (Updated):**
```json
{
  "intent_type": "action",
  "canonical_intent_candidates": [
    "apply_job",           // Primary guess
    "submit_application",  // Alternative 1 (synonym)
    "create_application"   // Alternative 2 (broader)
  ],
  "confidence": 0.94,
  "entities": {
    "company": "Google",
    "job_id": "12345"
  }
}
```

**Intent 6: help**
- **Examples:** "What does job_title mean?", "How do I apply?", "What can you do?"
- **Processing:** Brain triggers RAG search, returns contextual help
- **Brain Required:** YES
- **Auto-Response:** NO

**Intent 7: response**
- **Examples:** "Yes", "No", "Option #2", "john@email.com"
- **Processing:** Brain matches against answer_sheet, continues active_task
- **Brain Required:** YES
- **Auto-Response:** NO

**Intent 8: unknown**
- **Examples:** "asdfkjh", "???", ambiguous without context
- **Processing:** Brain generates fallback, offers help
- **Brain Required:** YES
- **Auto-Response:** NO

## 5.2 Multi-Intent Detection

**The System Supports:**
- Multiple intents in single message
- Self-response + brain-required combinations
- Multiple actions in sequence with dependencies

**Example 1: Gratitude + Action**
```
User: "Thanks! Now apply me to the Google job"

Detected Intents:
[
  {
    "intent_type": "gratitude",
    "confidence": 0.96,
    "sequence": 1,
    "auto_response": true
  },
  {
    "intent_type": "action",
    "canonical_intent_candidates": [
      "apply_job",
      "submit_application",
      "create_job_application"
    ],
    "confidence": 0.94,
    "entities": {"company": "Google"},
    "sequence": 2,
    "auto_response": false
  }
]

Response Strategy:
1. Self-respond to gratitude: "You're welcome!"
2. Pass action to Brain
3. Combine: "You're welcome! I'll help you apply to Google..."
```

**Example 2: Multiple Actions with Dependencies**
```
User: "Create my profile and apply to the software engineer job"

Detected Intents:
[
  {
    "intent_type": "action",
    "canonical_intent_candidates": ["create_profile", "setup_profile", "register"],
    "confidence": 0.93,
    "sequence": 1,
    "priority": "high"
  },
  {
    "intent_type": "action",
    "canonical_intent_candidates": ["apply_job", "submit_application", "apply_for_job"],
    "confidence": 0.91,
    "entities": {"job_title": "software engineer"},
    "sequence": 2,
    "priority": "normal",
    "dependencies": ["create_profile"]
  }
]

Brain Resolution:
1. Check dependencies: apply_job depends on create_profile
2. Execute in sequence: create_profile → apply_job
3. If create_profile fails: Block apply_job
```

## 5.3 Multi-Action Resolution Logic

```
1. Extract all action intents
   ↓
2. For each action, check Action Registry:
   ├─ Dependencies (explicit from registry)
   ├─ Priority levels (high/normal/low)
   ├─ Opposites (conflicting actions)
   └─ Sequence (from intent detector)
   ↓
3. Build execution plan:
   ├─ Order by: dependencies → priority → sequence
   ├─ Check eligibility for each
   └─ Resolve conflicts (ask clarification if opposites)
   ↓
4. Execute in order:
   ├─ Action 1: Execute or queue
   ├─ If success: Proceed to Action 2
   ├─ If failure: Check if Action 2 can proceed independently
   └─ If blocked: Mark Action 2 as blocked with reason
   ↓
5. Generate unified next_narrative:
   "Profile created. Applying to software engineer role at Google..."
```

**Resolution Rules:**
- **Dependencies:** If A depends on B, B executes first (always)
- **Priority:** high > normal > low (breaks ties)
- **Sequence:** Lower sequence number first
- **Opposites:** If detected, ask user for clarification
- **Workflow:** If part of workflow, follow workflow definition

## 5.4 Intent Type Routing Table

| Intent Type | Auto-Response | Brain Required | Can Multi-Detect | Sequence Matters |
|-------------|---------------|----------------|------------------|------------------|
| greeting | ✅ | ❌ | ✅ | ❌ |
| goodbye | ✅ | ❌ | ✅ | ❌ |
| gratitude | ✅ | ❌ | ✅ | ❌ |
| chitchat | ✅ | ❌ | ✅ | ❌ |
| action | ❌ | ✅ | ✅ | ✅ (workflows) |
| help | ❌ | ✅ | ❌ | ❌ |
| response | ❌ | ✅ | ❌ | ❌ |
| unknown | ❌ | ✅ | ❌ | ❌ |

---

# 6. BRAIN-INTENT WIRING

## 6.1 Wire Overview

The Brain produces **7 wires** that feed into the Intent Detector for the next turn. The Cold Path produces **1 wire** asynchronously.

**Brain Produces (7 wires):**
1. `expecting_response` (boolean)
2. `answer_sheet` (object)
3. `active_task` (object)
4. `previous_intents` (array)
5. `available_signals` (array, derived)
6. `conversation_context` (object)
7. `popular_actions` (array)

**Cold Path Produces (1 wire):**
8. `session_summary` (string, async after turn)

## 6.2 Wire 1: expecting_response

**Type:** `boolean`  
**Source:** Brain sets when asking question  
**Purpose:** Tells Intent Detector user is responding vs initiating

**Values:**
```javascript
true  // Bot asked a question, waiting for answer
false // Normal state, no question pending
```

**Examples:**

**expecting_response: true**
```
Bot: "Which job do you want to apply to?"
Bot: "What's your email address?"
Bot: "Confirm apply to Google? Yes or No?"
Bot: "Do you have a resume ready?"
```

**expecting_response: false**
```
Normal conversation state
User initiating new requests
No active question
```

**Storage:** `sessions.state["expecting_response"]`

**Used By:** Intent Detector to prefer `response` intent when true

## 6.3 Wire 2: answer_sheet

**Type:** `object (JSONB)`  
**Source:** Brain creates when asking structured question  
**Purpose:** Maps expected answers to actions/signals

**Structure:**
```javascript
{
    "type": "confirmation" | "single_choice" | "multiple_choice" | "entity" | "text",
    "options": {...},
    "context": "string describing what question is about",
    "required": boolean
}
```

**Type 1: Confirmation**
```json
{
    "type": "confirmation",
    "options": {
        "yes": ["yes", "yeah", "sure", "ok", "yup", "confirm", "proceed"],
        "no": ["no", "nope", "cancel", "nah", "stop", "never mind"]
    },
    "context": "apply_to_job_confirmation",
    "required": true
}
```

**Type 2: Single Selection**
```json
{
    "type": "single_choice",
    "options": {
        "#1": ["1", "first", "google", "#1", "the first one"],
        "#2": ["2", "second", "meta", "#2", "the second one"],
        "#3": ["3", "third", "stripe", "#3", "the third one"]
    },
    "context": "job_selection",
    "required": true
}
```

**Type 3: Multiple Selection**
```json
{
    "type": "multiple_choice",
    "options": {
        "python": ["a", "python", "a)", "option a"],
        "react": ["b", "react", "b)", "option b"],
        "aws": ["c", "aws", "c)", "option c"]
    },
    "min_selections": 1,
    "max_selections": 3,
    "context": "skill_selection"
}
```

**Type 4: Entity Capture**
```json
{
    "type": "entity",
    "entity_type": "email",
    "validation": "^[\\w\\.-]+@[\\w\\.-]+\\.\\w+$",
    "context": "email_collection",
    "required": true
}
```

**Type 5: Open Text**
```json
{
    "type": "text",
    "entity_type": "experience_description",
    "min_length": 50,
    "max_length": 1000,
    "context": "experience_collection",
    "required": true
}
```

**Storage:** `sessions.state["answer_sheet"]`

**Used By:** Intent Detector to match user response against valid options

## 6.4 Wire 3: active_task

**Type:** `object (JSONB)`  
**Source:** Brain creates when user starts action  
**Purpose:** Track in-progress action, collected params

**Structure:**
```javascript
{
    "task_id": "uuid",
    "canonical_action": "string",
    "action_type": "BRAND_API" | "SYSTEM_API" | "FACTUAL_API",
    "params_required": ["array", "of", "params"],
    "params_collected": {...},
    "params_missing": ["array"],
    "status": "string",
    "created_at": "ISO datetime",
    "updated_at": "ISO datetime"
}
```

**Example: Job Application (In Progress)**
```json
{
    "task_id": "a1b2c3d4",
    "canonical_action": "apply_job",
    "action_type": "BRAND_API",
    "params_required": ["job_id", "resume_url"],
    "params_collected": {
        "job_id": "12345",
        "company": "Google",
        "job_title": "Software Engineer"
    },
    "params_missing": ["resume_url"],
    "status": "collecting_params",
    "created_at": "2025-11-15T10:00:00Z",
    "updated_at": "2025-11-15T10:02:00Z"
}
```

**Task Status Values:**
```
"initiated"          // Task just created
"collecting_params"  // Waiting for user to provide params
"ready_to_execute"   // All params collected
"executing"          // API call in progress
"completed"          // Task finished successfully
"failed"             // Task failed
"cancelled"          // User cancelled
```

**Storage:** `sessions.state["active_task"]`

**Used By:** Intent Detector for context about what user is doing

## 6.5 Wire 4: previous_intents

**Type:** `array`  
**Source:** Brain stores after each intent detection  
**Purpose:** Context for multi-turn conversations

**Structure:**
```javascript
[
    {
        "intent_type": "string",
        "canonical_action": "string (if action)",
        "matched_signal": "string (if response)",
        "confidence": 0.0-1.0,
        "timestamp": "ISO datetime",
        "turn": 1
    },
    ...
]
```

**Example:**
```json
[
    {
        "intent_type": "greeting",
        "confidence": 0.98,
        "timestamp": "2025-11-15T10:00:00Z",
        "turn": 1
    },
    {
        "intent_type": "action",
        "canonical_action": "search_jobs",
        "confidence": 0.95,
        "entities": {"role": "software engineer"},
        "timestamp": "2025-11-15T10:01:00Z",
        "turn": 2
    },
    {
        "intent_type": "response",
        "matched_signal": "#1",
        "confidence": 0.92,
        "timestamp": "2025-11-15T10:02:00Z",
        "turn": 3
    }
]
```

**Max Items:** Last 5 intents (rolling window)

**Storage:** `sessions.state["previous_intents"]`

**Used By:** Intent Detector to understand conversation flow and context

## 6.6 Wire 5: available_signals

**Type:** `array (derived from answer_sheet)`  
**Source:** Brain generates from answer_sheet  
**Purpose:** Quick list for Intent Detector matching

**Structure:**
```javascript
["signal1", "signal2", "signal3", ...]
```

**Example: From Confirmation**
```javascript
answer_sheet: {
    "type": "confirmation",
    "options": {
        "yes": ["yes", "yeah", "sure"],
        "no": ["no", "nope", "cancel"]
    }
}

available_signals: ["yes", "yeah", "sure", "no", "nope", "cancel"]
```

**Derivation Logic:**
```python
def extract_available_signals(answer_sheet):
    if not answer_sheet:
        return []
    
    signals = []
    options = answer_sheet.get("options", {})
    
    for key, variants in options.items():
        signals.append(key)  # Add the key itself
        signals.extend(variants)  # Add all variants
    
    return list(set(signals))  # Remove duplicates
```

**Storage:** Derived on-the-fly (not stored separately)

**Used By:** Intent Detector for quick signal matching

## 6.7 Wire 6: conversation_context

**Type:** `object`  
**Source:** Brain builds from session data  
**Purpose:** Additional context for intent detection

**Structure:**
```javascript
{
    "domain": "string",
    "user_state": "string",
    "last_action": "string",
    "pending_confirmation": boolean,
    "awaiting": "string (optional)"
}
```

**Example: Applying to Job**
```json
{
    "domain": "job_search",
    "user_state": "actively_applying",
    "last_action": "selected_job",
    "pending_confirmation": true,
    "awaiting": "resume_upload"
}
```

**User State Values:**
```
"new"                // First interaction
"browsing"           // Exploring options
"actively_applying"  // In process of action
"waiting"            // Waiting for response
"post_application"   // After completing action
"idle"               // No recent activity
```

**Storage:** `sessions.state["conversation_context"]`

**Used By:** Intent Detector for domain-specific understanding

## 6.8 Wire 7: popular_actions

**Type:** `array`  
**Source:** Brain/Config  
**Purpose:** Guide LLM to common actions for this instance

**Structure:**
```javascript
[
    {
        "canonical_action": "string",
        "display_name": "string",
        "description": "string",
        "category": "string"
    },
    ...
]
```

**Example:**
```json
[
    {
        "canonical_action": "search_jobs",
        "display_name": "Search Jobs",
        "description": "Find job openings matching your skills",
        "category": "job_search"
    },
    {
        "canonical_action": "apply_job",
        "display_name": "Apply to Job",
        "description": "Submit application for a specific job",
        "category": "job_search"
    },
    {
        "canonical_action": "view_profile",
        "display_name": "View Profile",
        "description": "See your current profile information",
        "category": "profile"
    }
]
```

**Max Items:** 3-7 actions (most common for this instance)

**Storage:** `instance_configs.config["popular_actions"]`

**Used By:** Intent Detector to bias toward common actions

## 6.9 Wire 8: session_summary

**Type:** `string`  
**Source:** Cold Path (async background process)  
**Purpose:** Compressed conversation history for context

**Structure:**
```
Free-form text (~150-500 tokens)
Summarizes key points from conversation
```

**Example:**
```
"User is searching for software engineering jobs. 
Interested in remote work at tech companies like Google or Meta. 
Has 5 years experience with Python and React. 
Applied to Google software engineer role (turn 5)."
```

**Generation Trigger:**
- After each turn (async, fire-and-forget)
- Compresses last 2000 tokens of conversation
- Saves to `sessions.session_summary`

**Key Points:**
- ✅ Generated ASYNC by Cold Path
- ✅ Triggered AFTER Intent Detection
- ✅ -1 turn delay is acceptable (historical context)
- ✅ Current state comes from `active_task` (always fresh)

**Storage:** `sessions.session_summary`

**Used By:** Intent Detector in turn N+1 for conversation context

## 6.10 Wire Summary Table

| Wire | Type | Source | Storage | Purpose |
|------|------|--------|---------|---------|
| **1. expecting_response** | boolean | Brain | sessions.state | Is bot waiting for answer? |
| **2. answer_sheet** | object | Brain | sessions.state | Valid answers map |
| **3. active_task** | object | Brain | sessions.state | In-progress action tracking |
| **4. previous_intents** | array | Brain | sessions.state | Recent intent history |
| **5. available_signals** | array | Brain (derived) | Computed | Quick signal list |
| **6. conversation_context** | object | Brain | sessions.state | User state & domain |
| **7. popular_actions** | array | Brain/Config | instance_configs.config | Common actions (3-7 items) |
| **8. session_summary** | string | **Cold Path** | sessions.session_summary | Compressed conversation (~500 tokens) |

---

# 7. BRAIN PROCESSING FLOW

## 7.1 Complete Turn Processing Flow

**⭐ UPDATED with fuzzy search, streaming updates, and exit points**

```
┌─────────────────────────────────────────────────────────────────┐
│ TURN N: User sends message                                      │
└─────────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 1. INTENT DETECTION                                             │
│    - Parse user message                                          │
│    - Detect intents with confidence                             │
│    - Extract entities                                            │
│    - Determine self_response vs brain_required                  │
│    - **NEW:** Return 3 canonical name candidates                │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. BRAIN RECEIVES INTENTS                                       │
│    Input: {                                                      │
│      "intent_type": "action",                                   │
│      "canonical_intent_candidates": [                           │
│        "apply_job",           # Primary guess                   │
│        "submit_application",  # Alternative 1                   │
│        "create_application"   # Alternative 2                   │
│      ],                                                          │
│      "confidence": 0.85,                                        │
│      "entities": {"job_id": "123"}                              │
│    }                                                             │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. MAP INTENT → ACTION (With Fuzzy Search & Exit Point) ⭐ NEW │
│                                                                  │
│    For each candidate in canonical_intent_candidates:           │
│      1. Try exact match on canonical_name                       │
│      2. If not found, try fuzzy match (Levenshtein, cutoff=0.8)│
│      3. If not found, try synonym lookup in action.config       │
│                                                                  │
│    Result:                                                       │
│      - action: ActionModel (if found)                           │
│      - match_type: "exact"|"fuzzy"|"synonym"|"not_found"       │
│                                                                  │
│    emit_streaming_update({                                      │
│      "update_type": "action_lookup",                            │
│      "status": "found" or "not_found",                          │
│      "match_type": match_type,                                  │
│      "timestamp": datetime.now()                                │
│    })                                                            │
│                                                                  │
│    ❌ EXIT POINT 1: If action NOT FOUND                         │
│       → Skip to Step 4 (still log intent with status)           │
│       → Log status="action_not_found"                           │
│       → Generate next_narrative: "I don't know how to do that"  │
│       → emit_streaming_update({                                 │
│           "update_type": "action_not_found",                    │
│           "canonical_intent_attempted": candidates              │
│         })                                                       │
│       → RETURN to orchestrator (exit brain flow)                │
└────────────────────────┬────────────────────────────────────────┘
                         │ ✅ ACTION FOUND
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. LOG TO INTENT LEDGER (Only if action found OR not_found)     │
│                                                                  │
│    Create entry:                                                 │
│      - intent_id (UUID)                                         │
│      - intent_type ("action")                                   │
│      - canonical_intent (matched action name OR first candidate)│
│      - match_type ("exact"|"fuzzy"|"synonym"|"not_found")      │
│      - confidence (0.85)                                        │
│      - turn_number (from session)                               │
│      - entities ({"job_id": "123"})                             │
│      - status ("new" if found, "action_not_found" if not)      │
│                                                                  │
│    Storage: sessions.state["intent_ledger"][]                   │
│                                                                  │
│    emit_streaming_update({                                      │
│      "update_type": "intent_logged",                            │
│      "intent_id": intent_id,                                    │
│      "status": status                                           │
│    })                                                            │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. FETCH SCHEMA STATE (Only if action found)                    │
│                                                                  │
│    emit_streaming_update({                                      │
│      "update_type": "fetching_schemas",                         │
│      "schemas": action.config["schema_dependencies"]            │
│    })                                                            │
│                                                                  │
│    For each required schema in action.config.schema_dependencies│
│      - Check cache validity (TTL)                               │
│      - If expired or force_refresh:                             │
│        a. Call brand API with auth                              │
│        b. Parse response using api_field_path                   │
│        c. Apply completion_logic to each key                    │
│        d. Compute key status (none/incomplete/complete)         │
│        e. Compute schema status                                 │
│        f. Update cache with new expiry                          │
│      - If cached and valid:                                     │
│        a. Return cached state                                   │
│                                                                  │
│    emit_streaming_update({                                      │
│      "update_type": "schemas_fetched",                          │
│      "cache_hit": True/False                                    │
│    })                                                            │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. CHECK ACTION ELIGIBILITY                                     │
│                                                                  │
│    emit_streaming_update({                                      │
│      "update_type": "checking_eligibility"                      │
│    })                                                            │
│                                                                  │
│    For each action:                                              │
│      a. User Tier Check                                         │
│         - Compare user_tier with eligibility.user_tier          │
│      b. Auth Check                                              │
│         - If requires_auth, verify user authenticated           │
│      c. Schema Dependency Check                                 │
│         - For each schema in schema_dependencies:               │
│           * For each required key:                              │
│             - Check if key status == "complete"                 │
│             - If not complete → NOT ELIGIBLE                    │
│      d. Blocker Check                                           │
│         - Check if any blockers are active                      │
│      e. Action Dependency Check                                 │
│         - For each dependency action:                           │
│           * Check if completed in execution log                 │
│           * If not completed → NOT ELIGIBLE                     │
│      f. Opposite Action Check                                   │
│         - Check if any opposite actions in queue/executing      │
│           * If yes → NOT ELIGIBLE                               │
│                                                                  │
│    Result: eligible (bool), reasons (list)                      │
│                                                                  │
│    emit_streaming_update({                                      │
│      "update_type": "eligibility_checked",                      │
│      "eligible": True/False,                                    │
│      "reasons": reasons                                         │
│    })                                                            │
│                                                                  │
│    ❌ EXIT POINT 2: If NOT ELIGIBLE                             │
│       → Update Intent Ledger: status="blocked"                  │
│       → Generate next_narrative with blocker explanation        │
│       → emit_streaming_update({                                 │
│           "update_type": "action_blocked",                      │
│           "reasons": reasons                                    │
│         })                                                       │
│       → RETURN to orchestrator (exit brain flow)                │
└────────────────────────┬────────────────────────────────────────┘
                         │ ✅ ELIGIBLE
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 7. CHECK PARAMS COMPLETENESS & ADD TO QUEUE                     │
│                                                                  │
│    Missing params = params_required - entities                  │
│                                                                  │
│    ❌ EXIT POINT 3: If MISSING PARAMS                           │
│       → Update active_task: params_missing=[...]                │
│       → Set expecting_response=True                             │
│       → Create answer_sheet                                     │
│       → Generate next_narrative: "Ask for missing params"       │
│       → emit_streaming_update({                                 │
│           "update_type": "collecting_params",                   │
│           "params_missing": [...]                               │
│         })                                                       │
│       → RETURN to orchestrator (exit brain flow)                │
│                                                                  │
│    ✅ ALL PARAMS PRESENT:                                       │
│       - Generate idempotency_key                                │
│       - Check if duplicate (same key in queue/log)              │
│       - If not duplicate:                                       │
│         a. Create queue entry                                   │
│         b. Set status (pending/ready)                           │
│         c. Set priority                                         │
│         d. Store params_collected, retry_policy                 │
│         e. Persist to database (checkpoint)                     │
│         f. Update intent status = "queued"                      │
│                                                                  │
│    emit_streaming_update({                                      │
│      "update_type": "action_queued",                            │
│      "queue_id": queue_id                                       │
│    })                                                            │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 8. CHECK IF WORKFLOW TRIGGERED                                  │
│    For each action:                                              │
│    - If triggers_workflow == true:                              │
│      a. Load workflow config                                    │
│      b. Create workflow_instance                                │
│      c. Add workflow steps to queue (respecting sequence)       │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 9. PROCESS ACTION QUEUE (With Streaming Progress) ⭐ NEW        │
│                                                                  │
│    emit_streaming_update({                                      │
│      "update_type": "action_executing",                         │
│      "progress": 0                                              │
│    })                                                            │
│                                                                  │
│    For each item in queue (ordered by priority):                │
│      1. Check status                                            │
│      2. If pending/ready:                                       │
│         - Check params complete                                 │
│         - Check idempotency                                     │
│         - Execute or collect params                             │
│      3. If retrying:                                            │
│         - Check if next_retry_at passed                         │
│         - Execute retry                                         │
│                                                                  │
│    During execution:                                             │
│      - Call brand API with timeout (30s)                        │
│      - Emit progress updates every 3 seconds:                   │
│        emit_streaming_update({                                  │
│          "update_type": "action_progress",                      │
│          "progress": 20, 40, 60, 80...                          │
│          "current_step": "Uploading resume"                     │
│        })                                                        │
│                                                                  │
│    On success:                                                   │
│      - Mark status = "completed"                                │
│      - Update Intent Ledger: status = "completed"               │
│      - emit_streaming_update({                                  │
│          "update_type": "action_completed",                     │
│          "result": result                                       │
│        })                                                        │
│                                                                  │
│    On failure:                                                   │
│      - Retry with exponential backoff (2s, 4s, 8s, 16s)        │
│      - If all retries fail:                                     │
│        → Move to Dead Letter Queue                              │
│        → Update Intent Ledger: status = "failed"                │
│        → emit_streaming_update({                                │
│            "update_type": "action_failed",                      │
│            "error": error                                       │
│          })                                                      │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 10. UPDATE ACTIVE TASK STATE                                    │
│                                                                  │
│    active_task: {                                                │
│      "status": "completed"|"failed"|"collecting_params",        │
│      "params_collected": {...},                                 │
│      "params_missing": []                                       │
│    }                                                             │
│                                                                  │
│    sessions.state["active_task"] = active_task                  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 11. GENERATE NEXT NARRATIVE                                     │
│                                                                  │
│    Based on current state:                                       │
│                                                                  │
│    IF collecting_params:                                        │
│      next_narrative = {                                         │
│        "generation_instruction": {                              │
│          "instruction_type": "ask_for_params",                  │
│          "primary_instruction": "Ask user for resume"           │
│        },                                                        │
│        "detection_context": {                                   │
│          "expecting_response": True,                            │
│          "answer_sheet": {"resume": {...}}                      │
│        }                                                         │
│      }                                                           │
│                                                                  │
│    IF executing:                                                │
│      next_narrative = {                                         │
│        "generation_instruction": {                              │
│          "instruction_type": "report_progress",                 │
│          "primary_instruction": "Tell user we're processing"    │
│        }                                                         │
│      }                                                           │
│                                                                  │
│    IF completed:                                                │
│      next_narrative = {                                         │
│        "generation_instruction": {                              │
│          "instruction_type": "report_completion",               │
│          "primary_instruction": "Confirm job application submitted"│
│        }                                                         │
│      }                                                           │
│                                                                  │
│    IF blocked:                                                  │
│      next_narrative = {                                         │
│        "generation_instruction": {                              │
│          "instruction_type": "handle_blocker",                  │
│          "primary_instruction": "Explain blocker: {reasons}"    │
│        }                                                         │
│      }                                                           │
│                                                                  │
│    IF action_not_found:                                         │
│      next_narrative = {                                         │
│        "generation_instruction": {                              │
│          "instruction_type": "report_error",                    │
│          "primary_instruction": "I don't know how to do that"   │
│        }                                                         │
│      }                                                           │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 12. UPDATE 8 WIRES FOR NEXT TURN                                │
│                                                                  │
│    sessions.state = {                                            │
│      "expecting_response": bool,                                │
│      "answer_sheet": {...} or null,                             │
│      "active_task": {...} or null,                              │
│      "previous_intents": [...],  // Last 5                      │
│      "conversation_context": {...},                             │
│      "available_signals": [...]  // Derived from answer_sheet   │
│    }                                                             │
│                                                                  │
│    sessions.session_summary = "..." // Updated by Cold Path     │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 13. CHECKPOINT QUEUE STATE TO DATABASE                          │
│     (Survives server crashes)                                    │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 14. UPDATE TOKEN PLAN (Dynamic budget allocation)               │
│     ├─ Simple task → reduce to 3K tokens                        │
│     ├─ Complex workflow → increase to 8K tokens                 │
│     └─ Add context sections based on task complexity            │
│     Stored in: sessions.token_plan                              │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 15. RETURN TO ORCHESTRATOR                                      │
│     {                                                            │
│       "next_narrative": {...},                                  │
│       "streaming_update": {...},                                │
│       "active_task": {...},                                     │
│       "expecting_response": bool,                               │
│       "answer_sheet": {...},                                    │
│       "intents": [...],                                         │
│       "self_response": False                                    │
│     }                                                            │
└─────────────────────────────────────────────────────────────────┘
```

## 7.2 Exit Points Summary

The brain flow has **3 exit points** where it can return early:

**EXIT POINT 1: Action Not Found (Step 3)**
- Trigger: No action matches any of the 3 canonical name candidates
- Status: `intent_ledger.status = "action_not_found"`
- Response: "I don't know how to do that"
- Streaming Update: `{"update_type": "action_not_found"}`

**EXIT POINT 2: Action Blocked (Step 6)**
- Trigger: Action eligibility check fails (schema incomplete, tier mismatch, etc.)
- Status: `intent_ledger.status = "blocked"`
- Response: Explain blocker with clear reason
- Streaming Update: `{"update_type": "action_blocked", "reasons": [...]}`

**EXIT POINT 3: Missing Params (Step 7)**
- Trigger: Required parameters not provided by user
- Status: `active_task.status = "collecting_params"`
- Response: Ask for missing params
- Streaming Update: `{"update_type": "collecting_params", "params_missing": [...]}`

---

# 8. STREAMING UPDATES

⭐ **NEW SECTION**

## 8.1 Purpose

Streaming updates provide real-time, machine-readable state information as the Brain processes intents. These updates enable:
- Progress tracking for long-running actions
- Real-time UI updates in text/voice/video interfaces
- Debugging and monitoring
- User experience improvements (showing what's happening)

## 8.2 Update Structure

```python
streaming_update = {
    "update_type": str,      # Type of update (see types below)
    "timestamp": datetime,   # When update occurred
    **context_fields         # Type-specific fields
}
```

## 8.3 Update Types

| Update Type | Emitted At | Context Fields |
|-------------|------------|----------------|
| `action_lookup` | Step 3 | `status`, `match_type` |
| `action_not_found` | Step 3 (exit) | `canonical_intent_attempted` |
| `intent_logged` | Step 4 | `intent_id`, `status` |
| `fetching_schemas` | Step 5 | `schemas` |
| `schemas_fetched` | Step 5 | `cache_hit` |
| `checking_eligibility` | Step 6 | - |
| `eligibility_checked` | Step 6 | `eligible`, `reasons` |
| `action_blocked` | Step 6 (exit) | `reasons` |
| `collecting_params` | Step 7 (exit) | `params_missing` |
| `action_queued` | Step 7 | `queue_id` |
| `action_executing` | Step 9 | `progress` (0-100) |
| `action_progress` | During Step 9 | `progress`, `current_step` |
| `action_completed` | Step 9 | `result` |
| `action_failed` | Step 9 | `error` |

## 8.4 Storage

```python
# Stored in session state
sessions.state["streaming_updates"] = [
    {
        "update_type": "action_lookup",
        "status": "found",
        "match_type": "fuzzy",
        "timestamp": "2025-11-15T10:30:45Z"
    },
    {
        "update_type": "intent_logged",
        "intent_id": "abc-123",
        "status": "new",
        "timestamp": "2025-11-15T10:30:46Z"
    },
    # ... up to last 20 updates (rolling window)
]
```

## 8.5 Usage by Interfaces

### Text Interface (WhatsApp)
Shows most updates as messages:
```
"⏳ Processing... 40%"
"✅ Done!"
```

### Voice Interface
Selective updates (only start/end/blockers):
```python
# Minimum 10s gap between announcements
if update_type in ["action_executing", "action_completed", "action_blocked"]:
    speak(translate(update))
```

### Video Interface
Real-time progress bars, live status updates:
```javascript
<ProgressBar value={update.progress} />
<StatusText>{update.current_step}</StatusText>
```

### API Polling
```http
GET /sessions/{id}/streaming-updates
```
Returns latest 20 updates.

## 8.6 Implementation

```python
def emit_streaming_update(session_id: str, update: dict):
    """
    Emit a streaming update.
    
    Stores in session state for retrieval.
    """
    db = next(get_db())
    session = db.query(SessionModel).filter_by(id=session_id).first()
    
    if not session:
        return
    
    # Initialize if needed
    if "streaming_updates" not in session.state:
        session.state["streaming_updates"] = []
    
    # Add timestamp
    update["timestamp"] = datetime.utcnow().isoformat()
    
    # Append update
    session.state["streaming_updates"].append(update)
    
    # Keep only last 20 (rolling window)
    session.state["streaming_updates"] = session.state["streaming_updates"][-20:]
    
    # Mark modified for JSONB update
    flag_modified(session, "state")
    db.commit()
```

## 8.7 Translation to Human Language

**Machine State → Human Language Examples:**

**Action Lookup:**
```python
# Machine
{"update_type": "action_lookup", "status": "found", "match_type": "fuzzy"}

# Text
"Got it! Found similar action."

# Voice
[Silent - no announcement needed]
```

**Action Executing:**
```python
# Machine
{"update_type": "action_executing", "progress": 40, "current_step": "Uploading resume"}

# Text
"⏳ Uploading resume... 40%"

# Voice (only at milestones)
if progress == 0:
    "I'm working on that"
elif progress == 100:
    "Done!"
# Skip 10%, 20%, 30%... announcements
```

**Action Blocked:**
```python
# Machine
{"update_type": "action_blocked", "reasons": ["schema_dependency_failed:profile.phone"]}

# Text
"I need your phone number to proceed"

# Voice
"Before I can do that, I'll need your phone number"
```

---

**(Continued in next message due to length...)**