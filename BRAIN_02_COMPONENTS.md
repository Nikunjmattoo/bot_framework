# 🧠 BRAIN - PART 2: CORE COMPONENTS

**Version:** 3.0 (Multi-Document Series)  
**Date:** November 15, 2025  
**Status:** Production Ready

---

## 📚 DOCUMENTATION SERIES

This is **Part 2 of 5** in the Brain documentation series:

| File | Content | Status |
|------|---------|--------|
| BRAIN_01_OVERVIEW.md | System architecture, intent detection, brain flow, streaming | ✅ Complete |
| **BRAIN_02_COMPONENTS.md** ← YOU ARE HERE | Intent ledger, action registry, queue, schemas, workflows | ✅ Complete |
| BRAIN_03_DATABASE.md | Complete database schema, tables, indexes, JSONB structures | ⏳ Next |
| BRAIN_04_INTEGRATION.md | API patterns, error handling, idempotency, configuration | ⏳ Next |
| BRAIN_05_ADVANCED_PATTERNS.md | Innovative patterns, reliability, telemetry, cold paths | ⏳ Next |

---

## 📑 TABLE OF CONTENTS (PART 2)

9. [Core Components](#9-core-components)
   - 9.1 [Intent Ledger](#91-intent-ledger)
   - 9.2 [Action Registry](#92-action-registry)
   - 9.3 [Action Execution Queue](#93-action-execution-queue)
   - 9.4 [User Data Schemas](#94-user-data-schemas)
   - 9.5 [Schema State Tracker](#95-schema-state-tracker)
   - 9.6 [Active Task Tracker](#96-active-task-tracker)
   - 9.7 [Next Narrative Generator](#97-next-narrative-generator)
   - 9.8 [Workflow Engine](#98-workflow-engine)
   - 9.9 [Action Execution Log](#99-action-execution-log)
   - 9.10 [Dead Letter Queue](#910-dead-letter-queue)

**➡️ Continue to BRAIN_03_DATABASE.md for database schema**

---

# 9. CORE COMPONENTS

## 9.1 Intent Ledger

**Purpose:** State manager that tracks ALL intents detected across all conversation turns for a session.

**Why it exists:** Provides complete audit trail of user intentions, enables pattern analysis, supports context retention across multiple turns.

### 9.1.1 Data Structure

```python
intent_ledger_entry = {
    "intent_id": "uuid",
    "session_id": "uuid",
    "user_id": "uuid",
    "turn_number": int,
    "intent_type": "action" | "help" | "response" | "unknown" | "greeting" | "goodbye" | "gratitude" | "chitchat",
    "canonical_intent": "string",  # Matched action name
    "match_type": "exact" | "fuzzy" | "synonym" | "not_found",  # ⭐ NEW (from fuzzy search)
    "confidence": 0.0-1.0,
    "entities": {...},
    "reasoning": "string",
    "status": "new" | "processing" | "queued" | "executing" | "completed" | "failed" | "blocked" | "action_not_found",
    "sequence_order": int,
    "triggered_actions": [...],
    "response_type": "self_response" | "brain_required",
    "response_text": "string (optional)",
    "blocked_reason": "string (optional)",
    "created_at": "ISO datetime",
    "updated_at": "ISO datetime",
    "resolution": "string (optional)",
    "error": "string (optional)"
}
```

### 9.1.2 Example Intent Ledger

```json
{
    "session_id": "abc-123",
    "user_id": "user_12345",
    "intents": [
        {
            "id": "intent_001",
            "intent_type": "greeting",
            "confidence": 0.95,
            "turn_number": 1,
            "timestamp": "2025-11-15T10:00:00Z",
            "status": "completed",
            "reasoning": "User said 'Hi there' which is a clear greeting",
            "entities": {},
            "triggered_actions": [],
            "response_type": "self_response",
            "response_text": "Hello! How can I help you today?"
        },
        {
            "id": "intent_002",
            "intent_type": "action",
            "canonical_intent": "create_profile",
            "match_type": "exact",
            "confidence": 0.90,
            "turn_number": 2,
            "timestamp": "2025-11-15T10:01:00Z",
            "status": "processing",
            "reasoning": "User wants to create a profile based on 'I want to sign up'",
            "entities": {
                "action_name": "create_profile"
            },
            "triggered_actions": ["action_001"],
            "response_type": "brain_required",
            "response_text": null
        },
        {
            "id": "intent_003",
            "intent_type": "action",
            "canonical_intent": "process_payment",
            "match_type": "fuzzy",
            "confidence": 0.85,
            "turn_number": 5,
            "timestamp": "2025-11-15T10:05:00Z",
            "status": "blocked",
            "reasoning": "User wants to process payment",
            "entities": {
                "action_name": "process_payment",
                "amount": 5000
            },
            "triggered_actions": ["action_002"],
            "blocked_reason": "insufficient_schema_data: profile.payment_method incomplete",
            "response_type": "brain_required",
            "response_text": null
        }
    ]
}
```

### 9.1.3 Intent Status Lifecycle

```
new → processing → queued → executing → completed
                       ↓
                   blocked (exit: eligibility failed)
                       ↓
                   action_not_found (exit: no matching action)
                       ↓
                   failed (after max retries)
```

| Status | Description | When Applied |
|--------|-------------|--------------|
| `new` | Intent just detected | Immediately after intent detection |
| `processing` | Action(s) triggered and queued | After adding to action queue |
| `collecting_params` | Waiting for user to provide required params | When params missing for action |
| `queued` | Action added to execution queue | After eligibility check passes |
| `executing` | Action currently executing | During action execution |
| `completed` | Action successfully completed | After successful execution |
| `failed` | Action failed (exhausted retries) | After all retries failed |
| `blocked` | Cannot proceed due to blocker | When eligibility check fails |
| `action_not_found` | No matching action found | When fuzzy search fails |
| `cancelled` | User cancelled the intent | User says "cancel" or "stop" |

### 9.1.4 Operations

**Log Intent:**
```python
def log_intent(
    session_id: str,
    intent_type: str,
    canonical_intent: str,
    match_type: str,  # ⭐ NEW
    confidence: float,
    turn_number: int,
    reasoning: str,
    entities: dict,
    triggered_actions: list
) -> str:
    """
    Logs a new intent to the ledger.
    Returns intent_id for reference.
    """
    intent_id = str(uuid.uuid4())
    
    intent_entry = {
        "intent_id": intent_id,
        "session_id": session_id,
        "intent_type": intent_type,
        "canonical_intent": canonical_intent,
        "match_type": match_type,
        "confidence": confidence,
        "turn_number": turn_number,
        "reasoning": reasoning,
        "entities": entities,
        "triggered_actions": triggered_actions,
        "status": "new",
        "created_at": datetime.utcnow().isoformat()
    }
    
    # Store in sessions.state["intent_ledger"]
    state = get_session_state(db, session_id)
    if "intent_ledger" not in state:
        state["intent_ledger"] = []
    state["intent_ledger"].append(intent_entry)
    update_session_state(db, session_id, state)
    
    return intent_id
```

**Update Intent Status:**
```python
def update_intent_status(
    session_id: str,
    intent_id: str,
    new_status: str,
    additional_info: dict = None
) -> bool:
    """
    Updates the status of an existing intent.
    Optionally adds metadata like blocked_reason, error, resolution.
    """
    state = get_session_state(db, session_id)
    intent_ledger = state.get("intent_ledger", [])
    
    for intent in intent_ledger:
        if intent["intent_id"] == intent_id:
            intent["status"] = new_status
            intent["updated_at"] = datetime.utcnow().isoformat()
            
            if additional_info:
                intent.update(additional_info)
            
            update_session_state(db, session_id, state)
            return True
    
    return False
```

**Query Intents:**
```python
def get_intent_history(
    session_id: str,
    filters: dict = None,
    limit: int = 10
) -> list:
    """
    Retrieves intents for a session.
    Filters can include: status, intent_type, turn_range
    """
    state = get_session_state(db, session_id)
    intents = state.get("intent_ledger", [])
    
    if filters:
        if "status" in filters:
            intents = [i for i in intents if i["status"] == filters["status"]]
        if "intent_type" in filters:
            intents = [i for i in intents if i["intent_type"] == filters["intent_type"]]
    
    return intents[-limit:]
```

### 9.1.5 Storage Location

**Current Implementation:** `sessions.state["intent_ledger"]` (JSONB array)

**Alternative:** Dedicated `intent_ledger` table (see BRAIN_03_DATABASE.md)

---

## 9.2 Action Registry

**Purpose:** Centralized configuration store for all available actions per instance. Defines action metadata, eligibility rules, execution policies, and workflow associations.

**Why it exists:** Separates action logic from code, enables dynamic action addition without deployment, provides comprehensive metadata for intelligent orchestration.

### 9.2.1 Complete Action Configuration

```json
{
  "action_id": "process_payment",
  "action_name": "Process Payment",
  "description": "Processes payment for order using user's selected payment method",
  "category": "BRAND_API",
  "display_name": "Make Payment",
  "synonyms": ["pay", "make_payment", "submit_payment", "checkout"],  # ⭐ For fuzzy search
  
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

### 9.2.2 Action Attribute Categories

**1. Identification & Metadata**
- `action_id`, `action_name`, `description`, `category`, `display_name`
- `synonyms` ⭐ NEW - Used for fuzzy search matching
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
- `timeout_seconds`, `retry_policy`, `api_endpoint`, `api_method`
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

### 9.2.3 Why Action Attributes Matter

**Without detailed action attributes:**
- Brain doesn't know what params to collect
- Brain can't determine eligibility
- Brain can't handle failures gracefully
- Brain can't orchestrate workflows

**With detailed action attributes:**
- Brain collects exactly what's needed
- Brain blocks ineligible actions with reasons
- Brain retries with exponential backoff
- Brain orchestrates multi-step flows
- Brain rolls back on failures

### 9.2.4 Action Lookup (Fuzzy Search)

⭐ **NEW in v3.0**

The Brain performs fuzzy search using 3 canonical name candidates from the Intent Detector:

```python
def lookup_action_fuzzy(
    instance_id: str,
    candidates: list[str]  # 3 candidates from intent detector
) -> tuple[ActionModel, str]:
    """
    Fuzzy action lookup with 3 candidates.
    
    Returns: (action, match_type)
    match_type: "exact" | "fuzzy" | "synonym" | "not_found"
    """
    # Load all actions for instance
    actions = get_actions_by_instance(instance_id)
    
    for candidate in candidates:
        # 1. Try exact match on canonical_name
        for action in actions:
            if action.canonical_name.lower() == candidate.lower():
                return (action, "exact")
        
        # 2. Try fuzzy match (Levenshtein distance)
        from fuzzywuzzy import fuzz
        for action in actions:
            similarity = fuzz.ratio(candidate.lower(), action.canonical_name.lower())
            if similarity >= 80:  # 80% cutoff
                return (action, "fuzzy")
        
        # 3. Try synonym match
        for action in actions:
            synonyms = action.config.get("synonyms", [])
            if candidate.lower() in [s.lower() for s in synonyms]:
                return (action, "synonym")
    
    # Not found
    return (None, "not_found")
```

---

## 9.3 Action Execution Queue

**Purpose:** Persistent, priority-based queue that manages action execution with retry policies, idempotency, and crash recovery.

**Why it exists:** Ensures actions execute reliably, survive server crashes, prevent duplicates, and handle failures gracefully.

### 9.3.1 Queue Entry Structure

```python
queue_entry = {
    "queue_id": "uuid",
    "action_id": "string",
    "action_name": "string",
    
    # Context
    "session_id": "uuid",
    "user_id": "uuid",
    "instance_id": "uuid",
    "brand_id": "string",
    "intent_id": "string",
    "workflow_instance_id": "uuid (optional)",
    
    # Status
    "status": "pending" | "ready" | "executing" | "completed" | "failed" | "retrying" | "blocked",
    "priority": 1-10,  # 1=lowest, 10=highest
    
    # Parameters
    "params_collected": {...},
    "params_missing": [...],
    "params_validation_errors": {...},
    
    # Retry Management
    "retry_count": 0,
    "max_retries": 3,
    "last_retry_at": "ISO datetime",
    "next_retry_at": "ISO datetime",
    "retry_errors": [...],
    "backoff_strategy": "exponential",
    "initial_delay_seconds": 2,
    "max_delay_seconds": 60,
    
    # Blocker
    "blocker_reason": "string",
    "blocker_details": {...},
    
    # Idempotency
    "idempotency_key": "string",
    "execution_id": "uuid (optional)",
    
    # Persistence
    "persisted_to_db": true,
    "checkpoint_id": "string",
    "last_checkpoint_at": "ISO datetime",
    
    # Timing
    "added_at": "ISO datetime",
    "started_at": "ISO datetime",
    "completed_at": "ISO datetime",
    
    # Metadata
    "created_at": "ISO datetime",
    "updated_at": "ISO datetime"
}
```

### 9.3.2 Queue Operations

**Add to Queue:**
```python
def add_to_queue(
    session_id: str,
    action_id: str,
    params_collected: dict,
    params_missing: list,
    priority: int = 1,
    idempotency_key: str = None
) -> str:
    """
    Adds action to execution queue.
    Returns queue_id.
    """
    queue_id = str(uuid.uuid4())
    
    # Generate idempotency key if not provided
    if not idempotency_key:
        idempotency_key = f"{session_id}:{action_id}:{hash(json.dumps(params_collected, sort_keys=True))}"
    
    # Check if duplicate
    if is_duplicate(idempotency_key):
        logger.info(f"Duplicate action detected: {idempotency_key}")
        return None
    
    queue_entry = {
        "queue_id": queue_id,
        "action_id": action_id,
        "session_id": session_id,
        "params_collected": params_collected,
        "params_missing": params_missing,
        "priority": priority,
        "idempotency_key": idempotency_key,
        "status": "pending" if params_missing else "ready",
        "retry_count": 0,
        "added_at": datetime.utcnow().isoformat()
    }
    
    # Persist to database
    save_to_action_queue_table(queue_entry)
    
    # Also store in session state
    state = get_session_state(db, session_id)
    if "action_queue" not in state:
        state["action_queue"] = []
    state["action_queue"].append(queue_entry)
    update_session_state(db, session_id, state)
    
    return queue_id
```

**Process Queue:**
```python
def process_action_queue(session_id: str) -> dict:
    """
    Processes all ready items in the queue.
    
    For each item (ordered by priority):
    1. Check status
    2. If pending/ready:
       - Check params complete
       - Check idempotency
       - Execute or collect params
    3. If retrying:
       - Check if next_retry_at passed
       - Execute retry
    4. If blocked:
       - Check if blocker resolved
       - Move to pending or keep blocked
    5. Update checkpoint
    
    Returns summary of actions taken
    """
    state = get_session_state(db, session_id)
    queue = state.get("action_queue", [])
    
    # Sort by priority (high to low)
    queue = sorted(queue, key=lambda x: x.get("priority", 1), reverse=True)
    
    results = {
        "executed": [],
        "failed": [],
        "params_collected": [],
        "still_blocked": []
    }
    
    for item in queue:
        if item["status"] == "ready":
            # Execute action
            result = execute_action(item)
            if result["success"]:
                item["status"] = "completed"
                results["executed"].append(item["queue_id"])
            else:
                # Handle retry
                item["retry_count"] += 1
                if item["retry_count"] < item["max_retries"]:
                    item["status"] = "retrying"
                    item["next_retry_at"] = calculate_next_retry(item)
                else:
                    # Move to dead letter queue
                    move_to_dlq(item, result["error"])
                    item["status"] = "failed"
                    results["failed"].append(item["queue_id"])
        
        elif item["status"] == "retrying":
            # Check if retry time reached
            if datetime.utcnow() >= datetime.fromisoformat(item["next_retry_at"]):
                result = execute_action(item)
                # ... same retry logic
    
    # Update queue in session
    update_session_state(db, session_id, {"action_queue": queue})
    
    return results
```

**Checkpoint Queue:**
```python
def checkpoint_queue(session_id: str) -> bool:
    """
    Persists current queue state to database.
    
    Critical for:
    - Server crash recovery
    - Load balancing across instances
    - Audit trail
    """
    state = get_session_state(db, session_id)
    queue = state.get("action_queue", [])
    
    checkpoint_id = str(uuid.uuid4())
    
    for item in queue:
        item["checkpoint_id"] = checkpoint_id
        item["last_checkpoint_at"] = datetime.utcnow().isoformat()
        update_action_queue_table(item)
    
    logger.info(f"Checkpointed queue for session {session_id}: {len(queue)} items")
    return True
```

**Restore Queue:**
```python
def restore_queue(session_id: str) -> dict:
    """
    Restores queue from last checkpoint.
    
    Called on:
    - Server restart
    - Session recovery
    - Queue corruption
    """
    # Load from database
    queue_items = load_from_action_queue_table(session_id)
    
    state = get_session_state(db, session_id)
    state["action_queue"] = queue_items
    update_session_state(db, session_id, state)
    
    logger.info(f"Restored queue for session {session_id}: {len(queue_items)} items")
    return {"restored": len(queue_items)}
```

---

## 9.4 User Data Schemas

**Purpose:** Defines the structure and validation rules for real-time user data fetched from brand APIs. Each schema represents a data domain (profile, cart, loyalty, etc.) with keys that have completion logic.

**Why it exists:** Enables dynamic eligibility checking based on actual user data state, separates data structure from code, allows per-brand customization.

### 9.4.1 Schema Configuration Structure

```json
{
    "schema_id": "profile",
    "schema_name": "User Profile",
    "description": "User profile information from brand's CRM",
    "version": "1.0",
    
    "api_endpoint": "https://api.brand-xyz.com/v1/users/{user_id}/profile",
    "api_method": "GET",
    "api_auth": {
        "type": "bearer_token",
        "token_source": "instance_config",
        "header_name": "Authorization",
        "token_prefix": "Bearer"
    },
    "api_headers": {
        "Content-Type": "application/json",
        "X-Brand-ID": "{brand_id}"
    },
    "api_timeout_seconds": 10,
    
    "refresh_strategy": "on_demand",
    "cache_ttl_seconds": 300,
    "cache_on_error": true,
    "stale_cache_threshold_seconds": 600,
    
    "keys": [
        {
            "key_name": "email",
            "display_name": "Email Address",
            "description": "User's primary email address",
            "data_type": "string",
            "required_for_schema": true,
            
            "completion_logic": {
                "type": "non_empty",
                "validation": "email_format",
                "validation_regex": "^[\\w\\.-]+@[\\w\\.-]+\\.\\w+$"
            },
            
            "default_status": "none",
            "api_field_path": "data.contact.email",
            "fallback_value": null,
            
            "collection_prompt": "What's your email address?",
            "validation_error_message": "Please provide a valid email address"
        },
        {
            "key_name": "phone",
            "display_name": "Phone Number",
            "description": "User's primary phone number",
            "data_type": "string",
            "required_for_schema": true,
            
            "completion_logic": {
                "type": "non_empty",
                "validation": "phone_e164",
                "validation_regex": "^\\+[1-9]\\d{1,14}$"
            },
            
            "default_status": "none",
            "api_field_path": "data.contact.phone",
            "fallback_value": null,
            
            "collection_prompt": "What's your phone number?",
            "validation_error_message": "Please provide a valid phone number (e.g., +1234567890)"
        },
        {
            "key_name": "address",
            "display_name": "Address",
            "description": "User's shipping address",
            "data_type": "object",
            "required_for_schema": false,
            
            "completion_logic": {
                "type": "nested_object",
                "required_subkeys": ["street", "city", "zip"],
                "validation": "address_format"
            },
            
            "default_status": "none",
            "api_field_path": "data.address",
            "fallback_value": null
        }
    ],
    
    "schema_completion_logic": {
        "type": "all_required_keys_complete",
        "compute_percentage": true
    }
}
```

### 9.4.2 Key Completion Logic Types

**Type 1: non_empty**
```python
# Key is complete if:
# - Value exists
# - Value is not null
# - Value is not empty string
# - Passes validation (if specified)

def compute_non_empty(value, validation):
    if value is None or value == "":
        return "none"
    if validation:
        if not passes_validation(value, validation):
            return "incomplete"
    return "complete"
```

**Type 2: nested_object**
```python
# Key is complete if:
# - Object exists
# - All required_subkeys are present
# - All subkeys pass validation

def compute_nested_object(value, required_subkeys):
    if value is None:
        return "none"
    for subkey in required_subkeys:
        if subkey not in value or value[subkey] is None:
            return "incomplete"
    return "complete"
```

**Type 3: array_non_empty**
```python
# Key is complete if:
# - Array exists
# - Array has at least one item

def compute_array_non_empty(value):
    if value is None:
        return "none"
    if isinstance(value, list) and len(value) > 0:
        return "complete"
    return "incomplete"
```

**Type 4: enum_value**
```python
# Key is complete if:
# - Value is one of allowed values

def compute_enum_value(value, allowed_values):
    if value is None:
        return "none"
    if value in allowed_values:
        return "complete"
    return "incomplete"
```

### 9.4.3 Schema Operations

**Fetch Schema Data:**
```python
def fetch_schema_data(
    user_id: str,
    schema_id: str,
    force_refresh: bool = False
) -> dict:
    """
    Fetches user data for schema from brand API.
    Uses cache if valid, otherwise calls API.
    """
    # Check cache
    cache_key = f"{user_id}:{schema_id}"
    cached = get_from_cache(cache_key)
    
    if cached and not force_refresh:
        if datetime.utcnow() < cached["expires_at"]:
            return cached["data"]
    
    # Fetch from API
    schema_config = get_schema_config(schema_id)
    
    url = schema_config["api_endpoint"].replace("{user_id}", user_id)
    headers = build_auth_headers(schema_config["api_auth"])
    
    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=schema_config["api_timeout_seconds"]
        )
        
        if response.status_code == 200:
            data = response.json()
            
            # Cache it
            save_to_cache(cache_key, {
                "data": data,
                "expires_at": datetime.utcnow() + timedelta(seconds=schema_config["cache_ttl_seconds"])
            })
            
            return data
        else:
            # Use stale cache if available
            if cached and schema_config["cache_on_error"]:
                return cached["data"]
            
            raise Exception(f"API error: {response.status_code}")
    
    except Exception as e:
        # Use stale cache if available
        if cached and schema_config["cache_on_error"]:
            return cached["data"]
        raise e
```

**Compute Key Statuses:**
```python
def compute_key_statuses(
    schema_id: str,
    api_data: dict
) -> dict:
    """
    Computes completion status for each key.
    Returns: {key_name: status, ...}
    status: "none" | "incomplete" | "complete"
    """
    schema_config = get_schema_config(schema_id)
    statuses = {}
    
    for key_config in schema_config["keys"]:
        key_name = key_config["key_name"]
        api_field_path = key_config["api_field_path"]
        completion_logic = key_config["completion_logic"]
        
        # Extract value from API data using path
        value = extract_value(api_data, api_field_path)
        
        # Compute status based on completion_logic type
        logic_type = completion_logic["type"]
        
        if logic_type == "non_empty":
            statuses[key_name] = compute_non_empty(
                value,
                completion_logic.get("validation")
            )
        elif logic_type == "nested_object":
            statuses[key_name] = compute_nested_object(
                value,
                completion_logic["required_subkeys"]
            )
        elif logic_type == "array_non_empty":
            statuses[key_name] = compute_array_non_empty(value)
        elif logic_type == "enum_value":
            statuses[key_name] = compute_enum_value(
                value,
                completion_logic["allowed_values"]
            )
        else:
            statuses[key_name] = "none"
    
    return statuses
```

---

## 9.5 Schema State Tracker

**Purpose:** Per-session cache of user data with computed key statuses. Tracks data freshness, API health, and provides stale data fallback.

**Why it exists:** Minimizes API calls, provides visibility into data state, enables fast eligibility checks.

### 9.5.1 Schema State Structure

```python
schema_state = {
    "session_id": "uuid",
    "user_id": "uuid",
    "schema_id": "string",
    "schema_version": "string",
    
    # Fetch Metadata
    "last_fetched_at": "ISO datetime",
    "cache_expires_at": "ISO datetime",
    "next_refresh_at": "ISO datetime",
    "api_response_status": "success" | "error" | "timeout",
    "api_response_time_ms": int,
    "api_error": "string (optional)",
    
    # Keys (all key statuses)
    "keys": {
        "email": {
            "status": "complete",
            "value": "user@example.com",
            "last_updated": "ISO datetime"
        },
        "phone": {
            "status": "none",
            "value": null,
            "last_updated": "ISO datetime"
        },
        "address": {
            "status": "incomplete",
            "value": {"street": "123 Main", "city": null, "zip": null},
            "last_updated": "ISO datetime"
        }
    },
    
    # Schema Status
    "schema_status": "incomplete",
    "schema_completion_percentage": 66,
    "required_keys_complete": 1,
    "required_keys_total": 2,
    "optional_keys_complete": 0,
    "optional_keys_total": 1,
    
    # Metadata
    "created_at": "ISO datetime",
    "updated_at": "ISO datetime"
}
```

### 9.5.2 Schema State Operations

**Get Schema State:**
```python
def get_schema_state(
    session_id: str,
    schema_id: str,
    force_refresh: bool = False
) -> dict:
    """
    Gets schema state for session.
    Refreshes if cache expired or force_refresh=True.
    """
    # Load from session state
    state = get_session_state(db, session_id)
    schema_states = state.get("schema_states", {})
    
    if schema_id in schema_states and not force_refresh:
        schema_state = schema_states[schema_id]
        
        # Check if cache valid
        if datetime.utcnow() < datetime.fromisoformat(schema_state["cache_expires_at"]):
            return schema_state
    
    # Fetch fresh data
    user_id = get_user_id_from_session(session_id)
    api_data = fetch_schema_data(user_id, schema_id, force_refresh)
    
    # Compute key statuses
    key_statuses = compute_key_statuses(schema_id, api_data)
    
    # Build schema state
    schema_state = {
        "session_id": session_id,
        "user_id": user_id,
        "schema_id": schema_id,
        "last_fetched_at": datetime.utcnow().isoformat(),
        "cache_expires_at": (datetime.utcnow() + timedelta(seconds=300)).isoformat(),
        "keys": key_statuses,
        "schema_status": compute_schema_status(key_statuses),
        "updated_at": datetime.utcnow().isoformat()
    }
    
    # Save to session state
    schema_states[schema_id] = schema_state
    update_session_state(db, session_id, {"schema_states": schema_states})
    
    return schema_state
```

**Check Schema Dependency:**
```python
def check_schema_dependency(
    session_id: str,
    schema_id: str,
    required_keys: list[str],
    all_must_be: str = "complete"
) -> tuple[bool, list[str]]:
    """
    Checks if schema dependency is satisfied.
    
    Returns: (satisfied, missing_keys)
    """
    schema_state = get_schema_state(session_id, schema_id)
    
    missing_keys = []
    
    for key_name in required_keys:
        key_status = schema_state["keys"].get(key_name, {}).get("status", "none")
        
        if all_must_be == "complete":
            if key_status != "complete":
                missing_keys.append(f"{schema_id}.{key_name}")
        elif all_must_be == "non_empty":
            if key_status == "none":
                missing_keys.append(f"{schema_id}.{key_name}")
    
    return (len(missing_keys) == 0, missing_keys)
```

---

## 9.6 Active Task Tracker

**Purpose:** Tracks the current in-progress action/task for a session. Mutable state updated every turn.

**Why it exists:** Separate from Intent Ledger (immutable log), provides current task context for param collection and continuity.

### 9.6.1 Active Task Structure

```python
active_task = {
    "task_id": "uuid",
    "canonical_action": "string",
    "action_type": "BRAND_API" | "SYSTEM_API" | "FACTUAL_API",
    "params_required": [...],
    "params_collected": {...},
    "params_missing": [...],
    "status": "initiated" | "collecting_params" | "ready_to_execute" | "executing" | "completed" | "failed" | "cancelled",
    "created_at": "ISO datetime",
    "updated_at": "ISO datetime"
}
```

### 9.6.2 Example Active Task

**Job Application (Collecting Params):**
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

**Profile View (Ready):**
```json
{
    "task_id": "e5f6g7h8",
    "canonical_action": "view_profile",
    "action_type": "SYSTEM_API",
    "params_required": [],
    "params_collected": {},
    "params_missing": [],
    "status": "ready_to_execute",
    "created_at": "2025-11-15T10:05:00Z",
    "updated_at": "2025-11-15T10:05:00Z"
}
```

### 9.6.3 Active Task Operations

**Create Active Task:**
```python
def create_active_task(
    session_id: str,
    canonical_action: str,
    params_required: list[str],
    params_collected: dict
) -> str:
    """
    Creates a new active task.
    Returns task_id.
    """
    task_id = str(uuid.uuid4())
    
    params_missing = [p for p in params_required if p not in params_collected]
    
    active_task = {
        "task_id": task_id,
        "canonical_action": canonical_action,
        "params_required": params_required,
        "params_collected": params_collected,
        "params_missing": params_missing,
        "status": "collecting_params" if params_missing else "ready_to_execute",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat()
    }
    
    # Store in session state
    update_session_state(db, session_id, {"active_task": active_task})
    
    return task_id
```

**Update Active Task:**
```python
def update_active_task(
    session_id: str,
    updates: dict
) -> bool:
    """
    Updates active task with new data.
    Recalculates params_missing.
    """
    state = get_session_state(db, session_id)
    active_task = state.get("active_task")
    
    if not active_task:
        return False
    
    # Apply updates
    for key, value in updates.items():
        active_task[key] = value
    
    # Recalculate params_missing
    params_missing = [
        p for p in active_task["params_required"]
        if p not in active_task["params_collected"]
    ]
    active_task["params_missing"] = params_missing
    
    # Update status
    if not params_missing and active_task["status"] == "collecting_params":
        active_task["status"] = "ready_to_execute"
    
    active_task["updated_at"] = datetime.utcnow().isoformat()
    
    # Save
    update_session_state(db, session_id, {"active_task": active_task})
    
    return True
```

**Clear Active Task:**
```python
def clear_active_task(session_id: str) -> bool:
    """
    Clears active task (on completion or cancellation).
    """
    update_session_state(db, session_id, {"active_task": None})
    return True
```

---

## 9.7 Next Narrative Generator

**Purpose:** Constructs structured instructions for the Response Generator LLM based on current brain state. Separates "what to say" (must) from "how to say it" (optional).

**Why it exists:** Provides clear, consistent interface between Brain logic and LLM response generation. Enables deterministic response patterns while preserving natural language flexibility.

### 9.7.1 Next Narrative Structure

```python
next_narrative = {
    "generation_instruction": {
        "instruction_type": "ask_for_params" | "report_progress" | "report_completion" | "handle_blocker" | "report_error",
        "primary_instruction": "string",  # MUST include
        "optional_context": "string",     # CAN include
        "tone": "friendly" | "formal" | "urgent" | "celebratory"
    },
    "detection_context": {
        "expecting_response": bool,
        "answer_sheet": {...} or null,
        "active_task": {...} or null
    }
}
```

### 9.7.2 Instruction Types

**Type 1: ask_for_params**
```python
{
    "generation_instruction": {
        "instruction_type": "ask_for_params",
        "primary_instruction": "Ask user for resume URL. Explain it's needed to complete job application.",
        "optional_context": "User is applying to Google for Software Engineer role.",
        "tone": "friendly"
    },
    "detection_context": {
        "expecting_response": true,
        "answer_sheet": {
            "type": "entity",
            "entity_type": "resume_url",
            "validation": "url_format"
        }
    }
}
```

**Generated Response:** 
> "To complete your application to Google for the Software Engineer role, I'll need your resume. Could you provide the URL to your resume?"

---

**Type 2: report_progress**
```python
{
    "generation_instruction": {
        "instruction_type": "report_progress",
        "primary_instruction": "Tell user we're processing their payment.",
        "optional_context": "Amount: $100. Payment method: Visa ending in 1234.",
        "tone": "reassuring"
    },
    "detection_context": {
        "expecting_response": false,
        "answer_sheet": null
    }
}
```

**Generated Response:**
> "Processing your payment of $100 using your Visa ending in 1234. This should only take a moment..."

---

**Type 3: report_completion**
```python
{
    "generation_instruction": {
        "instruction_type": "report_completion",
        "primary_instruction": "Confirm job application submitted successfully.",
        "optional_context": "Application ID: APP-12345. Recruiter will contact within 3 business days.",
        "tone": "celebratory"
    },
    "detection_context": {
        "expecting_response": false,
        "answer_sheet": null
    }
}
```

**Generated Response:**
> "Great news! Your application has been submitted successfully (Application ID: APP-12345). A recruiter will reach out within 3 business days."

---

**Type 4: handle_blocker**
```python
{
    "generation_instruction": {
        "instruction_type": "handle_blocker",
        "primary_instruction": "Explain that phone number is required to proceed with payment.",
        "optional_context": "Phone needed for order confirmation SMS.",
        "tone": "friendly"
    },
    "detection_context": {
        "expecting_response": true,
        "answer_sheet": {
            "type": "entity",
            "entity_type": "phone",
            "validation": "phone_e164"
        }
    }
}
```

**Generated Response:**
> "To proceed with your payment, I'll need your phone number for order confirmation. What's your phone number?"

---

**Type 5: report_error**
```python
{
    "generation_instruction": {
        "instruction_type": "report_error",
        "primary_instruction": "Apologize that action is not available.",
        "optional_context": "Action attempted: 'schedule_interview'. Not found in registry.",
        "tone": "apologetic"
    },
    "detection_context": {
        "expecting_response": false,
        "answer_sheet": null
    }
}
```

**Generated Response:**
> "I apologize, but I'm not able to schedule interviews at this time. Is there something else I can help you with?"

---

### 9.7.3 Next Narrative Generation Logic

```python
def generate_next_narrative(
    intent_type: str,
    status: str,
    active_task: dict,
    blocker_reason: str = None,
    completion_result: dict = None
) -> dict:
    """
    Generates next_narrative based on brain state.
    """
    
    if status == "collecting_params":
        return {
            "generation_instruction": {
                "instruction_type": "ask_for_params",
                "primary_instruction": f"Ask user for {', '.join(active_task['params_missing'])}.",
                "optional_context": f"Needed to complete {active_task['canonical_action']}.",
                "tone": "friendly"
            },
            "detection_context": {
                "expecting_response": True,
                "answer_sheet": create_answer_sheet(active_task["params_missing"][0])
            }
        }
    
    elif status == "blocked":
        return {
            "generation_instruction": {
                "instruction_type": "handle_blocker",
                "primary_instruction": f"Explain blocker: {blocker_reason}",
                "tone": "friendly"
            },
            "detection_context": {
                "expecting_response": False
            }
        }
    
    elif status == "executing":
        return {
            "generation_instruction": {
                "instruction_type": "report_progress",
                "primary_instruction": f"Tell user we're processing {active_task['canonical_action']}.",
                "tone": "reassuring"
            },
            "detection_context": {
                "expecting_response": False
            }
        }
    
    elif status == "completed":
        return {
            "generation_instruction": {
                "instruction_type": "report_completion",
                "primary_instruction": f"Confirm {active_task['canonical_action']} completed successfully.",
                "optional_context": str(completion_result),
                "tone": "celebratory"
            },
            "detection_context": {
                "expecting_response": False
            }
        }
    
    elif status == "action_not_found":
        return {
            "generation_instruction": {
                "instruction_type": "report_error",
                "primary_instruction": "Apologize that action is not available.",
                "tone": "apologetic"
            },
            "detection_context": {
                "expecting_response": False
            }
        }
```

---

## 9.8 Workflow Engine

**Purpose:** Manages multi-step action sequences with dependencies, branching, and rollback capabilities.

**Why it exists:** Enables complex business processes (onboarding, checkout, application flows) with coordinated multi-action execution.

### 9.8.1 Workflow Configuration

```json
{
    "workflow_id": "job_application_flow",
    "workflow_name": "Complete Job Application",
    "description": "Multi-step workflow for applying to a job",
    "version": "1.0",
    
    "steps": [
        {
            "sequence_id": 1,
            "step_name": "create_or_load_profile",
            "action_id": "create_profile",
            "required": true,
            "on_failure": "abort",
            "rollback_on_workflow_failure": false
        },
        {
            "sequence_id": 2,
            "step_name": "upload_resume",
            "action_id": "upload_resume",
            "required": true,
            "on_failure": "abort",
            "rollback_on_workflow_failure": true,
            "depends_on": [1]
        },
        {
            "sequence_id": 3,
            "step_name": "submit_application",
            "action_id": "apply_job",
            "required": true,
            "on_failure": "abort",
            "rollback_on_workflow_failure": true,
            "depends_on": [1, 2]
        },
        {
            "sequence_id": 4,
            "step_name": "schedule_interview",
            "action_id": "schedule_interview",
            "required": false,
            "on_failure": "continue",
            "depends_on": [3]
        }
    ],
    
    "rollback_strategy": "reverse_order",
    "timeout_seconds": 300,
    "is_active": true
}
```

### 9.8.2 Workflow Instance State

```python
workflow_instance = {
    "workflow_instance_id": "uuid",
    "workflow_id": "string",
    "workflow_name": "string",
    
    "session_id": "uuid",
    "user_id": "uuid",
    "instance_id": "uuid",
    
    "status": "in_progress" | "completed" | "failed" | "cancelled",
    "current_step": int,
    
    "progress_percentage": int,
    "steps_completed": int,
    "steps_total": int,
    "steps_remaining": int,
    
    "steps_executed": [
        {
            "sequence_id": 1,
            "action_id": "create_profile",
            "status": "completed",
            "execution_id": "uuid",
            "started_at": "ISO datetime",
            "completed_at": "ISO datetime",
            "result": {...}
        },
        {
            "sequence_id": 2,
            "action_id": "upload_resume",
            "status": "executing",
            "execution_id": "uuid",
            "started_at": "ISO datetime"
        }
    ],
    
    "started_at": "ISO datetime",
    "completed_at": "ISO datetime",
    "timeout_at": "ISO datetime",
    "timed_out": false,
    
    "rollback_performed": false,
    "rollback_steps": [...],
    
    "created_at": "ISO datetime",
    "updated_at": "ISO datetime"
}
```

### 9.8.3 Workflow Operations

**Start Workflow:**
```python
def start_workflow(
    session_id: str,
    workflow_id: str,
    params: dict
) -> str:
    """
    Initiates workflow instance.
    Returns workflow_instance_id.
    """
    workflow_config = get_workflow_config(workflow_id)
    workflow_instance_id = str(uuid.uuid4())
    
    workflow_instance = {
        "workflow_instance_id": workflow_instance_id,
        "workflow_id": workflow_id,
        "session_id": session_id,
        "status": "in_progress",
        "current_step": 0,
        "steps_total": len(workflow_config["steps"]),
        "steps_executed": [],
        "started_at": datetime.utcnow().isoformat(),
        "timeout_at": (datetime.utcnow() + timedelta(seconds=workflow_config["timeout_seconds"])).isoformat()
    }
    
    # Execute first step
    execute_workflow_step(workflow_instance_id, 1)
    
    return workflow_instance_id
```

**Execute Workflow Step:**
```python
def execute_workflow_step(
    workflow_instance_id: str,
    sequence_id: int
) -> dict:
    """
    Executes a single workflow step.
    """
    workflow_instance = get_workflow_instance(workflow_instance_id)
    workflow_config = get_workflow_config(workflow_instance["workflow_id"])
    
    step_config = next(s for s in workflow_config["steps"] if s["sequence_id"] == sequence_id)
    
    # Check dependencies
    for dep_id in step_config.get("depends_on", []):
        dep_step = next(s for s in workflow_instance["steps_executed"] if s["sequence_id"] == dep_id)
        if dep_step["status"] != "completed":
            raise Exception(f"Step {sequence_id} depends on {dep_id} which is not completed")
    
    # Execute action
    result = execute_action(step_config["action_id"], workflow_instance["session_id"])
    
    # Record execution
    step_execution = {
        "sequence_id": sequence_id,
        "action_id": step_config["action_id"],
        "status": "completed" if result["success"] else "failed",
        "execution_id": result["execution_id"],
        "started_at": datetime.utcnow().isoformat(),
        "completed_at": datetime.utcnow().isoformat(),
        "result": result
    }
    
    workflow_instance["steps_executed"].append(step_execution)
    workflow_instance["current_step"] = sequence_id
    workflow_instance["steps_completed"] = len([s for s in workflow_instance["steps_executed"] if s["status"] == "completed"])
    workflow_instance["progress_percentage"] = int((workflow_instance["steps_completed"] / workflow_instance["steps_total"]) * 100)
    
    # Check if workflow complete
    if workflow_instance["steps_completed"] == workflow_instance["steps_total"]:
        workflow_instance["status"] = "completed"
        workflow_instance["completed_at"] = datetime.utcnow().isoformat()
    
    # Save
    save_workflow_instance(workflow_instance)
    
    return result
```

**Check Workflow Progress:**
```python
def check_workflow_progress(workflow_instance_id: str) -> dict:
    """
    Checks workflow status and progress.
    """
    workflow_instance = get_workflow_instance(workflow_instance_id)
    
    # Check timeout
    if datetime.utcnow() > datetime.fromisoformat(workflow_instance["timeout_at"]):
        if workflow_instance["status"] == "in_progress":
            workflow_instance["status"] = "failed"
            workflow_instance["timed_out"] = True
            save_workflow_instance(workflow_instance)
    
    return {
        "workflow_instance_id": workflow_instance_id,
        "status": workflow_instance["status"],
        "progress_percentage": workflow_instance["progress_percentage"],
        "current_step": workflow_instance["current_step"],
        "steps_completed": workflow_instance["steps_completed"],
        "steps_total": workflow_instance["steps_total"]
    }
```

---

## 9.9 Action Execution Log

**Purpose:** Immutable record of every action execution attempt, including inputs, outputs, timing, and errors.

**Why it exists:** Provides complete audit trail, enables debugging, supports idempotency checks, tracks performance metrics.

### 9.9.1 Execution Log Entry

```python
execution_log_entry = {
    "execution_id": "uuid",
    "action_id": "string",
    "action_name": "string",
    
    "session_id": "uuid",
    "user_id": "uuid",
    "instance_id": "uuid",
    "brand_id": "string",
    "intent_id": "string",
    "queue_id": "string",
    "workflow_instance_id": "uuid (optional)",
    
    "started_at": "ISO datetime",
    "completed_at": "ISO datetime",
    "duration_ms": int,
    "timeout_seconds": int,
    "timed_out": false,
    
    "status": "completed" | "failed" | "timeout",
    "retry_attempt": int,
    "final_retry": false,
    
    "params_used": {...},
    "params_validated": true,
    "validation_errors": [...],
    
    "result": {...},
    "api_response_status": int,
    "api_response_body": {...},
    
    "error": "string (optional)",
    "error_type": "string",
    "error_message": "string",
    "error_code": "string",
    "stack_trace": "string",
    
    "rollback_performed": false,
    "rollback_action_id": "string",
    "rollback_execution_id": "string",
    
    "requires_acknowledgement": false,
    "acknowledged": false,
    "acknowledged_at": "ISO datetime",
    
    "idempotency_key": "string",
    "duplicate_execution": false,
    "original_execution_id": "string",
    
    "trace_id": "string",
    "request_id": "string",
    "created_at": "ISO datetime"
}
```

### 9.9.2 Logging Operations

**Log Execution Start:**
```python
def log_execution_start(
    action_id: str,
    session_id: str,
    params: dict,
    idempotency_key: str
) -> str:
    """
    Logs start of action execution.
    Returns execution_id.
    """
    execution_id = str(uuid.uuid4())
    
    log_entry = {
        "execution_id": execution_id,
        "action_id": action_id,
        "session_id": session_id,
        "params_used": params,
        "idempotency_key": idempotency_key,
        "status": "executing",
        "started_at": datetime.utcnow().isoformat()
    }
    
    save_to_execution_log(log_entry)
    
    return execution_id
```

**Log Execution Complete:**
```python
def log_execution_complete(
    execution_id: str,
    result: dict,
    duration_ms: int
) -> bool:
    """
    Logs successful execution completion.
    """
    update_execution_log(execution_id, {
        "status": "completed",
        "result": result,
        "duration_ms": duration_ms,
        "completed_at": datetime.utcnow().isoformat()
    })
    
    return True
```

**Log Execution Failed:**
```python
def log_execution_failed(
    execution_id: str,
    error: str,
    error_type: str,
    duration_ms: int
) -> bool:
    """
    Logs failed execution.
    """
    update_execution_log(execution_id, {
        "status": "failed",
        "error": error,
        "error_type": error_type,
        "duration_ms": duration_ms,
        "completed_at": datetime.utcnow().isoformat()
    })
    
    return True
```

---

## 9.10 Dead Letter Queue

**Purpose:** Holds failed actions that have exhausted retry attempts. Requires manual intervention or escalation.

**Why it exists:** Prevents silent failures, enables support team intervention, tracks unrecoverable errors, provides escalation path.

### 9.10.1 DLQ Entry Structure

```python
dlq_entry = {
    "dlq_id": "uuid",
    "original_queue_id": "string",
    
    "action_id": "string",
    "action_name": "string",
    "action_category": "string",
    
    "session_id": "uuid",
    "user_id": "uuid",
    "instance_id": "uuid",
    "brand_id": "string",
    "intent_id": "string",
    "turn_number": int,
    
    "moved_to_dlq_at": "ISO datetime",
    "original_added_at": "ISO datetime",
    "time_in_queue_seconds": int,
    
    "original_status": "string",
    "retry_count": int,
    "max_retries": int,
    "final_error": {...},
    "retry_history": [...],
    
    "params_collected": {...},
    
    "requires_manual_intervention": true,
    "intervention_type": "support" | "engineering" | "business",
    "escalated_to_support": false,
    "escalation_ticket_id": "string",
    "escalated_at": "ISO datetime",
    
    "resolved": false,
    "resolved_at": "ISO datetime",
    "resolution_notes": "string",
    
    "user_notified": false,
    "user_notification_sent_at": "ISO datetime",
    "user_notification_message": "string",
    
    "idempotency_key": "string",
    
    "created_at": "ISO datetime",
    "updated_at": "ISO datetime"
}
```

### 9.10.2 DLQ Operations

**Move to DLQ:**
```python
def move_to_dlq(
    queue_entry: dict,
    final_error: dict
) -> str:
    """
    Moves failed action to dead letter queue.
    Returns dlq_id.
    """
    dlq_id = str(uuid.uuid4())
    
    dlq_entry = {
        "dlq_id": dlq_id,
        "original_queue_id": queue_entry["queue_id"],
        "action_id": queue_entry["action_id"],
        "session_id": queue_entry["session_id"],
        "user_id": queue_entry["user_id"],
        "retry_count": queue_entry["retry_count"],
        "max_retries": queue_entry["max_retries"],
        "final_error": final_error,
        "retry_history": queue_entry.get("retry_errors", []),
        "params_collected": queue_entry["params_collected"],
        "moved_to_dlq_at": datetime.utcnow().isoformat(),
        "requires_manual_intervention": True,
        "resolved": False
    }
    
    save_to_dlq(dlq_entry)
    
    # Notify user
    notify_user_of_failure(queue_entry["session_id"], queue_entry["action_id"])
    
    # Escalate if critical
    if is_critical_action(queue_entry["action_id"]):
        escalate_to_support(dlq_id)
    
    return dlq_id
```

**Escalate to Support:**
```python
def escalate_to_support(dlq_id: str) -> str:
    """
    Escalates DLQ entry to support ticketing system.
    Returns ticket_id.
    """
    dlq_entry = get_dlq_entry(dlq_id)
    
    # Create support ticket
    ticket = create_support_ticket({
        "title": f"Failed Action: {dlq_entry['action_name']}",
        "description": f"Action {dlq_entry['action_id']} failed after {dlq_entry['retry_count']} retries.",
        "priority": determine_priority(dlq_entry),
        "assigned_to": "support_team",
        "metadata": {
            "dlq_id": dlq_id,
            "user_id": dlq_entry["user_id"],
            "session_id": dlq_entry["session_id"],
            "final_error": dlq_entry["final_error"]
        }
    })
    
    # Update DLQ entry
    update_dlq_entry(dlq_id, {
        "escalated_to_support": True,
        "escalation_ticket_id": ticket["ticket_id"],
        "escalated_at": datetime.utcnow().isoformat()
    })
    
    return ticket["ticket_id"]
```

**Resolve DLQ Entry:**
```python
def resolve_dlq_entry(
    dlq_id: str,
    resolution_notes: str,
    retry_action: bool = False
) -> bool:
    """
    Marks DLQ entry as resolved.
    Optionally retries action.
    """
    update_dlq_entry(dlq_id, {
        "resolved": True,
        "resolved_at": datetime.utcnow().isoformat(),
        "resolution_notes": resolution_notes
    })
    
    if retry_action:
        dlq_entry = get_dlq_entry(dlq_id)
        # Re-add to action queue with fresh retry count
        add_to_queue(
            session_id=dlq_entry["session_id"],
            action_id=dlq_entry["action_id"],
            params_collected=dlq_entry["params_collected"],
            params_missing=[]
        )
    
    return True
```

---

**END OF PART 2**

➡️ **Continue to BRAIN_03_DATABASE.md for complete database schema**