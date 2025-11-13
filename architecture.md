# AI Conversational Framework - Architecture & Design

**Design Philosophy:** Production-grade, multi-tenant conversational AI framework with data-driven orchestration and context-aware memory systems.

---

## 1. SYSTEM ARCHITECTURE OVERVIEW

### **Core Flow**

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

---

## 2. MULTI-TENANT SCALABILITY

### **Architecture: Brand → Instance → Configuration**

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
  │    └─ Token Budgets (per section)
  ├─ Sessions
  └─ Action Registry
```

**Design Principles:**
- **Brand-Scoped Identity:** Same phone = different users per brand (privacy-first multi-tenancy)
- **Dynamic Configuration:** Switch LLM models, templates, budgets without deployment
- **Cost Tracking:** Pricing snapshots at time of usage (accurate historical billing)
- **Session State:** One active session per (user, instance) with timeout management

**vs State-of-the-Art:**
- **Intercom/Drift:** Single-tenant or limited multi-tenancy, no brand-scoped identity
- **Rasa:** Self-hosted only, manual multi-tenancy setup
- **DialogFlow CX:** Google Cloud lock-in, expensive at scale

**Our Advantage:** True multi-tenancy with complete data isolation, dynamic config, and cost control.

---

## 3. MESSAGE HANDLER WORKFLOW

### **Request Processing Flow**

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

**Key Features:**
- Multi-channel support (WhatsApp, Web, Mobile, Broadcast)
- Brand-scoped identity resolution
- Session timeout and resumption
- Idempotency with distributed locks
- Token usage tracking with cost calculation
- Monitoring (trace IDs, structured logs, Langfuse)

**Missing (By Design):** Streaming (SSE), attachments, PII protection, multi-language, live agent handoff

---

## 4. INTENT DETECTION WORKFLOW

### **How Intent Detection Works**

```
1. Receive adapter_payload from Message Handler
   ↓
2. Extract LLM Config from token_plan
   ├─ provider: "openai"
   ├─ api_model_name: "gpt-4o-mini"
   ├─ temperature: 0.3
   └─ max_tokens: 500
   ↓
3. Fetch Template from DB (by template_key)
   ↓
4. Fetch Enrichment Data:
   ├─ session_summary (from Cold Path)
   │  "User wants to apply to Google. Provided name, email."
   ├─ previous_messages (last 4 messages = 2 turns)
   │  [{"role": "user", "content": "..."}, ...]
   ├─ active_task (current task from Brain)
   │  {"task_id": "...", "canonical_action": "apply_job", 
   │   "params_collected": {"job_id": "123"}, 
   │   "params_missing": ["resume_url"]}
   └─ next_narrative (guidance from previous turn)
      "User wants to apply. Need resume. Ask for resume upload."
   ↓
5. Build Template Variables
   {
     "user_message": "I want to upload my resume",
     "user_type": "verified",
     "session_summary": "User wants to apply...",
     "previous_messages": "User: I want to apply...\nBot: ...",
     "active_task": "Task: apply_job, Missing: resume_url",
     "next_narrative": "User wants to apply..."
   }
   ↓
6. Fill Template with Variables
   (Jinja2-style: {{user_message}} → actual message)
   ↓
7. Call LLM (async)
   ├─ Provider from token_plan
   ├─ Model from token_plan
   └─ Temperature from token_plan
   ↓
8. Parse LLM Response
   {
     "intents": [
       {
         "intent_type": "action",
         "canonical_action": "upload_resume",
         "confidence": 0.94,
         "entities": {"file_type": "resume"}
       }
     ],
     "self_response": false,
     "response_text": null,
     "reasoning": "User wants to upload resume for job application"
   }
   ↓
9. Trigger Cold Paths (async, fire-and-forget)
   ├─ Session Summary Generator
   ├─ Topic/Timestamp Extractor
   └─ (Future: Tone, State of Mind, Entity Filter)
   ↓
10. Return to Orchestrator
    {
      "intents": [...],
      "self_response": false,
      "reasoning": "...",
      "token_usage": {"prompt_tokens": 847, "completion_tokens": 52}
    }
```

**Sample Request:**
```json
{
  "user_message": "I want to apply to Google",
  "user_id": "user-123",
  "session_id": "session-abc",
  "user_type": "verified",
  "template": {"json": {"intent": {"template": "intent_v1"}}},
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
```

**Sample Response:**
```json
{
  "intents": [
    {
      "intent_type": "action",
      "canonical_action": "apply_job",
      "confidence": 0.94,
      "entities": {"company": "Google"}
    }
  ],
  "self_response": false,
  "reasoning": "User explicitly wants to apply to Google",
  "token_usage": {"prompt_tokens": 847, "completion_tokens": 52, "total_tokens": 899}
}
```

---

## 5. BRAIN ARCHITECTURE (Orchestrator Core)

### **Design Philosophy**

The Brain is the central orchestration component that manages action lifecycle, validates user data state, and coordinates multi-step workflows with production-grade reliability.

### **How Brain Processor Works**

```
1. Receive intent from Intent Detector
   {"intent_type": "action", "canonical_action": "process_payment"}
   ↓
2. Log to Intent Ledger (audit trail)
   ├─ intent_id, intent_type, confidence, turn_number
   ├─ entities, reasoning
   └─ status: "new"
   ↓
3. Map intent → action from Action Registry
   ├─ Lookup: canonical_action="process_payment"
   └─ Load: params_required, eligibility_criteria, retry_policy
   ↓
4. Fetch User Data Schemas (with 5-min cache)
   ├─ Required schemas: ["profile", "payment_methods"]
   ├─ For each schema:
   │  ├─ Check cache validity (TTL)
   │  ├─ If expired: Call brand API
   │  │  GET api.brand.com/users/{user_id}/profile
   │  │  Response: {"email": "user@email.com", "phone": "+1234567890"}
   │  └─ Compute key status:
   │     ├─ email: "complete" (has value, valid format)
   │     ├─ phone: "complete" (has value, E.164 format)
   │     └─ address: "none" (missing)
   └─ Update cache with new expiry
   ↓
5. Check Action Eligibility
   ├─ User Tier Check
   │  ├─ Required: ["verified", "premium"]
   │  └─ User's tier: "verified" ✅
   ├─ Schema Dependencies
   │  ├─ Required: profile.email=complete AND profile.phone=complete
   │  └─ User's profile: email=complete ✅, phone=complete ✅
   ├─ Blockers
   │  └─ Check: insufficient_balance, payment_method_expired
   ├─ Dependencies
   │  └─ Check: prerequisite actions completed?
   └─ Opposites
      └─ Check: conflicting actions in queue?
   ↓
6. If Eligible:
   ├─ Check params complete
   ├─ If yes: Add to Action Queue
   │  ├─ queue_id, action_id, status="pending"
   │  ├─ params_collected, params_missing
   │  ├─ idempotency_key, priority
   │  └─ retry_policy (max_retries, backoff_strategy)
   └─ If no: Collect missing params
      ├─ Update active_task: params_missing=["amount"]
      └─ Set expecting_response=true, create answer_sheet
   ↓
   If Not Eligible:
   ├─ Log block reason: "profile.phone incomplete"
   ├─ Update Intent Ledger: status="blocked"
   └─ Generate next_narrative: "Please provide phone number"
   ↓
7. Process Action Queue
   ├─ Fetch pending actions (sorted by priority)
   ├─ For each action:
   │  ├─ Check idempotency (already executed?)
   │  ├─ Execute with timeout
   │  ├─ On success: Mark completed
   │  └─ On failure: Retry with exponential backoff (2s, 4s, 8s, 16s)
   └─ After max retries: Move to Dead Letter Queue
   ↓
8. Update Active Task State
   {
     "task_id": "abc-123",
     "canonical_action": "process_payment",
     "status": "executing",
     "params_collected": {"amount": 100, "method": "card"},
     "params_missing": []
   }
   Stored in: sessions.state["active_task"]
   ↓
9. Generate Next Narrative (for Response Generator)
   Examples:
   - "Payment processed successfully. Amount: $100."
   - "Phone number missing. Ask for phone in friendly way."
   - "User wants to pay but insufficient balance. Offer top-up."
   ↓
10. Checkpoint Queue State to Database
    (Survives server crashes)
    ↓
11. Update Token Plan (dynamic budget allocation)
    ├─ Simple task → reduce to 3K tokens
    ├─ Complex workflow → increase to 8K tokens
    └─ Add context sections based on task complexity
    Stored in: sessions.token_plan
    ↓
12. Return to Orchestrator
    {
      "next_narrative": "...",
      "active_task": {...},
      "expecting_response": true/false,
      "answer_sheet": {...}
    }
```

### **Brain Components**

**1. Intent Ledger**
- Complete audit trail of ALL intents across conversation
- Tracks status: new → processing → executing → completed/failed/blocked
- Enables pattern analysis and debugging

**2. Action Registry (per instance)**
- Defines all available actions
- Configuration: params, eligibility, retry policy, timeout, blockers, dependencies, opposites
- Example: process_payment requires profile.email + profile.phone complete

**3. User Data Schemas**
- Dynamic validation against real-time brand API data
- Each schema: keys with completion logic (none/incomplete/complete)
- Cached with 5-min TTL, force refresh on critical actions
- Example schemas: profile, cart, loyalty, payment_methods, order_history

**4. Action Queue**
- Persistent (database-backed, survives crashes)
- Priority-based execution
- Retry with exponential backoff
- Idempotency keys prevent duplicates
- Checkpointed for recovery

**5. Dead Letter Queue**
- Failed actions after max retries
- Tracks retry history, final error
- Manual intervention by support
- Escalation to ticketing system

**6. Schema State Tracker**
- Per-session cache of user data
- Tracks: last_fetched, cache_expiry, API response status
- Key statuses per schema field
- Stale data fallback (if API fails)

**7. Workflow Engine**
- Multi-step action orchestration
- Sequential execution with dependencies
- Branching (optional steps)
- Rollback on failure
- Resume from checkpoint

**8. Active Task Tracker**
- Current task state (mutable, updated every turn)
- Stored in sessions.state["active_task"]
- Separate from Intent Ledger (immutable log)

**9. Next Narrative Generator**
- Constructs instructions for Response Generator LLM
- Includes: what happened, what's needed, user message tone

---

## 6. COLD PATH ARCHITECTURE (Async Background Processing)

### **How Cold Paths Work**

```
Turn N: User sends message
↓
Intent Detection completes (synchronous)
↓
Response sent to user
↓
Cold Path Trigger Manager fires (async, fire-and-forget):

┌─────────────────────────────────────┐
│   Session Summary Generator         │
│                                     │
│   Input: conversation_history       │
│   Goal: Compress to 150 tokens     │
│   Process:                          │
│   1. Fetch last 2000 tokens         │
│   2. Call GROQ (fast LLM)           │
│   3. Generate summary               │
│   4. Save to sessions.session_summary│
│                                     │
│   Output: "User wants to apply to  │
│   Google. Provided name, email."    │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│   Topic & Timestamp Extractor       │
│                                     │
│   Input: user_message               │
│   Process:                          │
│   1. Extract timestamps             │
│      "last month" → "-30 days"      │
│      "5 years ago" → "2020"         │
│   2. Extract hierarchical topics    │
│      ["shopping", "shoes",          │
│       "red_shoes", "purchase_2020"] │
│   3. Save to messages.topic_paths   │
│                                     │
│   Enables: Multi-resolution RAG     │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│   Future Cold Paths                 │
│   - Tone Detector                   │
│   - State of Mind Analyzer          │
│   - Entity Filter (for handoffs)    │
└─────────────────────────────────────┘

Next Turn N+1:
Intent Detector reads:
- session_summary (from Turn N)
- topic_paths (from Turn N)
- active_task (fresh from Turn N+1)
```

**Why Async (Fire-and-Forget)?**
- Don't block user response
- Background enrichment for next turn
- Summary has -1 turn delay (acceptable)
- Topic tagging enables future RAG queries

**vs State-of-the-Art:**
- **OpenAI Assistants:** No automatic summarization, manual memory management
- **LangChain:** Requires manual summary chains, not automatic
- **AutoGen:** Agent-based, no built-in conversation compression

**Our Advantage:** Automatic, asynchronous enrichment with zero latency impact.

---

## 7. INNOVATIVE DESIGN PATTERNS

### **Pattern 1: Dynamic Token Budget Allocation**

**Problem:** Traditional systems use fixed conversation windows (4K, 8K tokens) that either waste tokens or miss context.

**Our Approach:** Brain dynamically adjusts token budget based on task complexity.

```
Message Handler creates initial token_plan:
{
  "response_v1": {
    "max_tokens": 1000,
    "budget": 5000,
    "sections": {
      "system": 500,
      "history": 3000,
      "user_message": 500,
      "context": 1000
    }
  }
}
Stored in: sessions.token_plan

Brain receives intent, assesses complexity:
- Simple greeting → reduce budget to 2000 tokens
- Complex multi-action workflow → increase to 8000 tokens
- Add/remove sections based on need

Brain updates token_plan:
{
  "response_v1": {
    "max_tokens": 1500,
    "budget": 8000,  ← Brain changed this
    "sections": {
      "system": 500,
      "history": 5000,  ← More history for complex task
      "user_message": 500,
      "context": 2000  ← Added context section
    }
  }
}
Stored back in: sessions.token_plan

Message Handler uses updated plan:
- Knows how much history to include
- No arbitrary truncation
- Context-aware token allocation
```

**Why This Matters:**
- Efficient token usage (simple tasks use fewer tokens)
- Comprehensive context for complex tasks
- No mid-sentence truncation
- Brain controls what's relevant

**State-of-the-Art Comparison:**
- **ChatGPT:** Fixed 128K window, no dynamic allocation
- **Claude:** Fixed 200K window, manual context management
- **Anthropic Prompt Caching:** Static caching, not dynamic budget

**Unexplored Territory:** Dynamic token budget allocation based on real-time task complexity assessment by orchestrator.

---

### **Pattern 2: Hierarchical Multi-Resolution RAG**

**Problem:** Traditional RAG searches by semantic similarity only. Fails on temporal + topical queries like "What did I discuss about red shoes last month?"

**Our Approach:** Autonomous topic tagging with timestamp extraction enables multi-resolution search.

```
Cold Path (async):
User: "Remember the red shoes I bought 5 years ago?"
↓
Timestamp Extractor LLM:
- Timestamps: ["5 years ago"] → converts to "2020"
- Topics: hierarchical extraction
↓
Store in messages.topic_paths:
[
  "shopping",           // Level 1 (broad)
  "shoes",             // Level 2 (category)
  "red_shoes",         // Level 3 (specific)
  "purchase_2020"      // Level 4 (temporal anchor)
]

RAG Search (next turn):
User: "Tell me about those red shoes"
↓
Multi-resolution strategy:
1. Try Level 4 (most specific):
   WHERE topic_paths @> '["shopping", "shoes", "red_shoes", "purchase_2020"]'
   AND created_at BETWEEN '2020-01-01' AND '2020-12-31'

2. If no results, Level 3 (broader):
   WHERE topic_paths @> '["shopping", "shoes", "red_shoes"]'
   AND created_at BETWEEN '2019-01-01' AND '2021-12-31'

3. If no results, Level 2 (broadest):
   WHERE topic_paths @> '["shopping", "shoes"]'
   AND created_at >= '2019-01-01'

4. Return best match with confidence score
```

**Why This Matters:**
- Temporal + semantic search combined
- Works for "recent", "last month", "2020", "5 years ago"
- Automatic (no manual tagging)
- Progressive fallback (specific → broad)

**State-of-the-Art Comparison:**
- **Pinecone/Weaviate:** Semantic only, no temporal anchors
- **LangChain Memory:** Manual timestamp parsing, no hierarchy
- **OpenAI RAG:** Semantic search only, no multi-resolution

**Unexplored Territory:** Autonomous hierarchical topic extraction with temporal anchors for multi-resolution conversational memory.

---

### **Pattern 3: Contextual Reference Resolution ("Torch in the Night")**

**Problem:** Traditional RAG returns top-K globally. User says "the second one" or "that product" → fails to resolve reference.

**Our Approach:** Conversation-scoped RAG with active entity tracking and reference resolution.

**The Torch Metaphor:**
Traditional RAG = flashlight scanning entire field (global search)
Our RAG = torch following conversation trail (contextual search)

```
Turn 1: User: "Show me red shoes"
↓
Brain returns 5 products: [101, 102, 103, 104, 105]
↓
Store in sessions.state["active_entities"]:
{
  "products": [101, 102, 103, 104, 105],
  "last_mentioned": [101, 102, 103, 104, 105],
  "conversation_scope": "product_search"
}
↓
Turn 2: User: "Tell me more about the second one"
↓
Reference Resolution:
- "the second one" → product_id 102 (from active_entities[1])
↓
Scoped Search:
WHERE topic_paths @> '["product_102"]'
  AND session_id = current_session
  AND created_at > Turn1_timestamp
↓
Returns: Details about product 102
↓
Turn 3: User: "Compare it with the last one"
↓
Reference Resolution:
- "it" → product_id 102 (last_mentioned)
- "the last one" → product_id 105 (active_entities[-1])
↓
Scoped Search:
WHERE product_id IN (102, 105)
  AND session_id = current_session
↓
Returns: Comparison of 102 vs 105
```

**Multi-Resolution Reference Types:**
- High Resolution: "the second one" → exact position
- Medium Resolution: "those shoes" → all shoes in context
- Low Resolution: "what we discussed earlier" → temporal filter

**Why This Matters:**
- Resolves pronouns ("that", "it", "those")
- Conversation-scoped (not global)
- Natural follow-ups without repeating context
- Maintains active entity context per session

**State-of-the-Art Comparison:**
- **Claude Projects:** Global knowledge base, no reference resolution
- **ChatGPT Memory:** Stores facts, doesn't resolve "that one"
- **Semantic Kernel:** No built-in reference resolution

**Unexplored Territory:** Conversational reference resolution with multi-resolution entity tracking and scoped search.

---

## 8. DATA-DRIVEN ACTION ELIGIBILITY (Schema Validation)

**Problem:** Traditional bots check user_tier or permissions only. Real-world actions require actual user data state (profile complete? payment method added?).

**Our Approach:** Dynamic schema validation against real-time brand APIs.

```
Action Registry defines eligibility:
{
  "action_id": "process_payment",
  "eligibility_criteria": {
    "user_tier": ["verified", "premium"],
    "schema_dependencies": {
      "profile": {
        "required_keys": ["email", "phone"],
        "all_must_be": "complete"
      },
      "payment_methods": {
        "required_keys": ["default_method"],
        "all_must_be": "complete"
      }
    }
  }
}

Brain fetches real data:
GET api.brand.com/users/{user_id}/profile
Response: {"email": "user@email.com", "phone": null}

Compute key status:
- email: "complete" (has value, valid format)
- phone: "none" (missing)

Check eligibility:
- User tier: verified ✅
- profile.email: complete ✅
- profile.phone: none ❌

Result: Action BLOCKED
Reason: "profile.phone incomplete"

Brain generates next_narrative:
"User wants to pay but phone number is missing. 
Ask for phone in friendly way. Explain it's for order confirmation."

Response Generator creates:
"To process your payment, I'll need your phone number for order updates. 
What's your phone number?"
```

**Schema Definition Example:**
```json
{
  "schema_id": "profile",
  "api_endpoint": "https://api.brand.com/users/{user_id}/profile",
  "cache_ttl_seconds": 300,
  "keys": [
    {
      "key_name": "email",
      "required_for_schema": true,
      "completion_logic": {
        "type": "non_empty",
        "validation": "email_format"
      },
      "api_field_path": "data.contact.email"
    },
    {
      "key_name": "phone",
      "required_for_schema": true,
      "completion_logic": {
        "type": "non_empty",
        "validation": "phone_e164"
      }
    }
  ]
}
```

**Why This Matters:**
- Eligibility based on actual data state (not just permissions)
- Dynamic API calls to brand systems (fresh data)
- Multi-schema dependencies (profile + payment + cart)
- Clear block reasons ("profile.phone incomplete")
- Cache with TTL (minimize API load)

**State-of-the-Art Comparison:**
- **Rasa:** Slot filling only, no schema validation
- **DialogFlow CX:** Form-based, no real-time API validation
- **Microsoft Bot Framework:** Manual validation, no schema engine

**Unexplored Territory:** Real-time user data schema validation with cached API calls and completion logic for action eligibility.

---

## 9. PRODUCTION-GRADE RELIABILITY

**Queue Persistence:**
- Database-backed action queue
- Survives server crashes
- Checkpointed for recovery

**Idempotency:**
- Unique keys prevent duplicate execution
- Distributed locks (database-based)
- Cached responses for collisions

**Retry Policies:**
- Exponential backoff (2s, 4s, 8s, 16s)
- Per-action retry configuration
- Dead Letter Queue for permanent failures

**Error Handling:**
- Comprehensive error tracking
- Retry history logged
- Escalation to support (manual intervention)

**Observability:**
- Intent Ledger (complete audit trail)
- Execution logs (every action tracked)
- Schema state tracking (data freshness visibility)
- Trace IDs (distributed debugging)
- Structured logging
- Langfuse integration (LLM observability)

**Scalability:**
- Stateless message processing
- Horizontal scaling support
- Database-backed state
- Schema caching (minimize API calls)

---

## 10. TELEMETRY & OBSERVABILITY (Three Pillars)

### **Pillar 1: User Journey Tracking**

**What We Track:**
- Session lifecycle (start, timeout, end)
- Intent types per turn
- Action execution success/failure
- User drop-off points
- Conversation completion rate

**Example Events:**
```
user_journey:session_started
user_journey:intent_detected → intent_type=action, canonical_action=apply_job
user_journey:action_executed → action_id=apply_job, status=completed, duration_ms=1247
user_journey:user_dropped_off → last_intent=action, last_action=collect_resume
user_journey:session_completed → total_turns=12, actions_completed=3
```

**Why This Matters:**
- Identify friction points (where users drop off)
- Optimize conversation flows
- Measure task completion rates
- A/B test different flows

---

### **Pillar 2: Resource & Performance Tracking**

**What We Track:**
- Per-component latency (Message Handler, Intent Detection, Brain, Response Gen)
- LLM call duration (provider, model, tokens)
- Database query time
- API call latency (brand APIs)
- Token usage (planned vs actual)
- Cost per session

**Example Metrics:**
```
performance:message_handler_latency_ms → 47ms
performance:intent_detection_latency_ms → 892ms
  ├─ llm_call_latency_ms → 734ms
  ├─ db_fetch_latency_ms → 89ms
  └─ template_fill_latency_ms → 12ms
performance:brain_processing_latency_ms → 234ms
  ├─ schema_fetch_latency_ms → 156ms (with cache)
  ├─ eligibility_check_latency_ms → 34ms
  └─ queue_processing_latency_ms → 44ms
performance:total_request_latency_ms → 1543ms

cost:token_usage_planned → 3000
cost:token_usage_actual → 2847 (sent) + 412 (received) = 3259
cost:session_cost_usd → $0.0423
```

**Why This Matters:**
- Identify bottlenecks (which component is slow?)
- Optimize expensive operations
- Track token budget accuracy
- Monitor cost per conversation

---

### **Pillar 3: Error Tracking & Debugging**

**What We Track:**
- Error type and frequency
- Error location (component, function)
- Retry attempts and outcomes
- Dead Letter Queue entries
- Schema API failures
- LLM call failures

**Example Error Events:**
```
error:intent_detection_failed
  ├─ error_code: LLM_TIMEOUT
  ├─ error_message: "LLM call timed out after 15s"
  ├─ trace_id: abc-123
  ├─ provider: openai
  └─ model: gpt-4o-mini

error:schema_api_failed
  ├─ error_code: API_UNREACHABLE
  ├─ schema_id: profile
  ├─ api_endpoint: https://api.brand.com/users/123/profile
  ├─ retry_count: 3
  └─ action: Using stale cache

error:action_moved_to_dlq
  ├─ action_id: process_payment
  ├─ queue_id: queue-456
  ├─ retry_history: [timeout, api_error, timeout]
  ├─ final_error: "Payment gateway unreachable"
  └─ escalation_required: true
```

**Why This Matters:**
- Rapid debugging with trace IDs
- Identify recurring failures
- Monitor third-party API health
- Escalate critical failures

**Integration:**
- Langfuse (LLM observability)
- Structured logging (JSON)
- Performance timers (per-component)
- Distributed tracing (trace_id propagation)

---

## 11. INTENT DETECTION: TYPES & MULTI-INTENT SUPPORT

**vs Open-Source Frameworks:**
- **Rasa:** No multi-tenancy, manual action orchestration, limited scalability
- **Botpress:** Node.js only, no Python ecosystem, limited LLM integration
- **LangChain:** Library not framework, manual state management

**vs Commercial Platforms:**
- **Intercom/Drift:** Limited customization, expensive, no brand-scoped identity
- **DialogFlow CX:** Google lock-in, expensive, no dynamic token budgets
- **Microsoft Bot Framework:** Complex setup, no schema validation engine

**Our Strengths:**
1. True multi-tenancy with complete data isolation
2. Dynamic token budget allocation (context-aware)
3. Hierarchical multi-resolution RAG (temporal + semantic)
4. Contextual reference resolution (conversation-scoped)
5. Data-driven action eligibility (schema validation)
6. Production-grade reliability (queue persistence, retry, DLQ)
7. Autonomous enrichment (cold paths for summarization + tagging)
8. Cost control (pricing snapshots, per-session tracking)
9. Multi-intent detection with dependency resolution
10. Three-pillar telemetry (user journey, performance, errors)

---

## 11. INTENT DETECTION: TYPES & MULTI-INTENT SUPPORT

### **Intent Types (8 Types)**

**Self-Response Intents (Auto-Handled):**
```
1. greeting
   Examples: "Hi", "Hello", "Hey there"
   Response: "Hello! How can I help you today?"
   Brain Required: NO

2. goodbye
   Examples: "Bye", "See you", "Thanks, that's all"
   Response: "Goodbye! Feel free to return anytime."
   Brain Required: NO

3. gratitude
   Examples: "Thanks", "Thank you", "Appreciate it"
   Response: "You're welcome! Happy to help."
   Brain Required: NO

4. chitchat
   Examples: "How are you?", "Tell me a joke", "What's your name?"
   Response: Casual, friendly response
   Brain Required: NO
```

**Brain-Required Intents:**
```
5. action
   Examples: "Apply to this job", "Book appointment", "Process payment"
   Processing: Brain maps to canonical_action, checks eligibility, executes
   Brain Required: YES

6. help
   Examples: "What does job_title mean?", "How do I apply?", "What can you do?"
   Processing: Brain triggers RAG search, returns contextual help
   Brain Required: YES

7. response
   Examples: "Yes", "No", "Option #2", "john@email.com"
   Processing: Brain matches against answer_sheet, continues active_task
   Brain Required: YES

8. unknown
   Examples: "asdfkjh", "???", ambiguous without context
   Processing: Brain generates fallback, offers help
   Brain Required: YES
```

### **Multi-Intent Detection**

**The System Supports:**
- Multiple intents in single message
- Self-response + brain-required combinations
- Multiple actions in sequence

**Example 1: Gratitude + Action**
```
User: "Thanks! Now apply me to the Google job"

Detected Intents:
[
  {
    "intent_type": "gratitude",
    "confidence": 0.96,
    "sequence": 1
  },
  {
    "intent_type": "action",
    "canonical_action": "apply_job",
    "confidence": 0.94,
    "entities": {"company": "Google"},
    "sequence": 2
  }
]

Response Strategy:
1. Self-respond to gratitude: "You're welcome!"
2. Pass action to Brain
3. Combine: "You're welcome! I'll help you apply to Google..."
```

**Example 2: Multiple Actions**
```
User: "Create my profile and apply to the software engineer job"

Detected Intents:
[
  {
    "intent_type": "action",
    "canonical_action": "create_profile",
    "confidence": 0.93,
    "sequence": 1,
    "priority": "high"
  },
  {
    "intent_type": "action",
    "canonical_action": "apply_job",
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

### **Multi-Action Resolution Logic**

**When Multiple Actions Detected:**

```
1. Extract all action intents
   ↓
2. For each action, check Action Registry:
   ├─ Dependencies (explicit from registry)
   │  Example: apply_job requires create_profile completed
   ├─ Priority levels (high/normal/low)
   │  Example: high priority actions first
   ├─ Opposites (conflicting actions)
   │  Example: cancel_order + confirm_order = conflict
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
- **Sequence:** Lower sequence number first (from intent detector)
- **Opposites:** If detected, ask user for clarification
- **Workflow:** If part of workflow, follow workflow definition

---

## 12. ACTION REGISTRY: ATTRIBUTES & DEPTH

**Why Action Attributes Matter:** The Brain's accuracy depends on comprehensive action configuration. Each action in the registry defines behavior, constraints, and execution policies.

### **Action Attributes (Complete Specification)**

```json
{
  "action_id": "process_payment",
  "action_name": "Process Payment",
  "description": "Processes payment for order using user's selected payment method",
  "category": "BRAND_API",
  
  "params_required": ["amount", "payment_method_id"],
  "params_optional": ["discount_code", "tip_amount"],
  "param_validation": {
    "amount": {
      "type": "number",
      "min": 1,
      "max": 100000,
      "validation": "positive_number"
    },
    "payment_method_id": {
      "type": "string",
      "format": "uuid",
      "validation": "uuid_format"
    },
    "discount_code": {
      "type": "string",
      "pattern": "^[A-Z0-9]{6,10}$"
    }
  },
  
  "eligibility_criteria": {
    "user_tier": ["verified", "premium"],
    "requires_auth": true,
    "schema_dependencies": {
      "profile": {
        "required_keys": ["email", "phone"],
        "all_must_be": "complete"
      },
      "payment_methods": {
        "required_keys": ["default_method"],
        "all_must_be": "complete"
      },
      "cart": {
        "required_keys": ["items", "total"],
        "all_must_be": "complete"
      }
    }
  },
  
  "blockers": [
    "insufficient_balance",
    "payment_method_expired",
    "fraud_detection_triggered",
    "cart_empty"
  ],
  
  "dependencies": ["verify_cart", "validate_address"],
  "opposites": ["cancel_payment", "refund_payment"],
  
  "timeout_seconds": 30,
  "estimated_duration_seconds": 5,
  
  "retry_policy": {
    "max_retries": 3,
    "backoff_strategy": "exponential",
    "initial_delay_seconds": 2,
    "max_delay_seconds": 60,
    "retry_on_errors": ["timeout", "api_error", "network_error"]
  },
  
  "rollback_possible": true,
  "rollback_action_id": "refund_payment",
  
  "requires_user_acknowledgement": true,
  "acknowledgement_timeout_seconds": 300,
  
  "execution_type": "api_call",
  "api_endpoint": "https://api.brand.com/payments/process",
  "api_method": "POST",
  "api_auth_type": "bearer_token",
  
  "workflow_id": "checkout_flow",
  "sequence_id": 3,
  "triggers_workflow": false,
  
  "success_criteria": {
    "status_code": 200,
    "response_contains": "payment_id"
  },
  "failure_criteria": {
    "status_code": [400, 402, 403, 500],
    "response_contains": ["error", "failed"]
  },
  
  "priority": "high",
  "is_active": true
}
```

### **Attribute Categories**

**1. Identification & Metadata**
- `action_id`, `action_name`, `description`, `category`
- Purpose: Unique identification and classification

**2. Parameters**
- `params_required`, `params_optional`, `param_validation`
- Purpose: Define what data is needed and validation rules
- Impact: Brain knows what to collect from user

**3. Eligibility Criteria**
- `user_tier`, `requires_auth`, `schema_dependencies`
- Purpose: Determine if user can execute this action
- Impact: Brain blocks ineligible actions with clear reasons

**4. Constraints**
- `blockers`, `dependencies`, `opposites`
- Purpose: Business rules and execution constraints
- Impact: Brain prevents invalid action sequences

**5. Execution Configuration**
- `timeout_seconds`, `retry_policy`, `api_endpoint`
- Purpose: How to execute and handle failures
- Impact: Brain manages retries and timeouts automatically

**6. Rollback & Recovery**
- `rollback_possible`, `rollback_action_id`
- Purpose: Undo actions on failure
- Impact: Brain can automatically rollback failed payments

**7. Workflow Integration**
- `workflow_id`, `sequence_id`, `triggers_workflow`
- Purpose: Multi-step flow coordination
- Impact: Brain orchestrates complex workflows

**8. Success/Failure Detection**
- `success_criteria`, `failure_criteria`
- Purpose: Determine execution outcome
- Impact: Brain knows when to retry vs fail permanently

### **Why This Depth Matters**

**Accuracy Impact:**
```
Without detailed action attributes:
- Brain doesn't know what params to collect
- Brain can't determine eligibility
- Brain can't handle failures gracefully
- Brain can't orchestrate workflows

With detailed action attributes:
- Brain collects exactly what's needed
- Brain blocks ineligible actions with reasons
- Brain retries with exponential backoff
- Brain orchestrates multi-step flows
- Brain rolls back on failures
```

**Example: Payment Processing**
```
User: "I want to pay"

Brain checks process_payment action:
1. Eligibility:
   - user_tier: verified ✅
   - profile.email: complete ✅
   - profile.phone: complete ✅
   - payment_methods.default_method: complete ✅
   - cart.items: complete ✅
   
2. Blockers:
   - insufficient_balance: false ✅
   - payment_method_expired: false ✅
   - fraud_detection_triggered: false ✅
   - cart_empty: false ✅
   
3. Dependencies:
   - verify_cart: completed ✅
   - validate_address: completed ✅
   
4. Opposites in queue:
   - cancel_payment: false ✅
   - refund_payment: false ✅
   
Result: ELIGIBLE → Add to queue
Execute with:
- timeout: 30s
- retry: up to 3 times with exponential backoff
- rollback: refund_payment if fails
```

**State-of-the-Art Comparison:**
- **Rasa:** Basic slots, no schema dependencies
- **DialogFlow:** Form-based, limited eligibility logic
- **LangChain:** Manual action management
- **AutoGen:** Agent-based, no centralized registry

**Our Advantage:** Comprehensive action attributes enable intelligent orchestration, automatic eligibility checking, and production-grade reliability.