# 🧠 BRAIN - PART 3: DATABASE SCHEMA

**Version:** 3.0 (Multi-Document Series)  
**Date:** November 15, 2025  
**Status:** Production Ready

---

## 📚 DOCUMENTATION SERIES

This is **Part 3 of 5** in the Brain documentation series:

| File | Content | Status |
|------|---------|--------|
| BRAIN_01_OVERVIEW.md | System architecture, intent detection, brain flow, streaming | ✅ Complete |
| BRAIN_02_COMPONENTS.md | Intent ledger, action registry, queue, schemas, workflows | ✅ Complete |
| **BRAIN_03_DATABASE.md** ← YOU ARE HERE | Complete database schema, tables, indexes, JSONB structures | ✅ Complete |
| BRAIN_04_INTEGRATION.md | API patterns, error handling, idempotency, configuration | ⏳ Next |
| BRAIN_05_ADVANCED_PATTERNS.md | Innovative patterns, reliability, telemetry, cold paths | ⏳ Next |

---

## 📑 TABLE OF CONTENTS (PART 3)

10. [Complete Database Schema](#10-complete-database-schema)
    - 10.1 [Intent Ledger Table](#101-intent-ledger-table)
    - 10.2 [Action Queue Table](#102-action-queue-table)
    - 10.3 [Dead Letter Queue Table](#103-dead-letter-queue-table)
    - 10.4 [User Schema State Table](#104-user-schema-state-table)
    - 10.5 [Brand Schemas Table](#105-brand-schemas-table)
    - 10.6 [Action Execution Log Table](#106-action-execution-log-table)
    - 10.7 [Workflow Instances Table](#107-workflow-instances-table)
    - 10.8 [Action Registry Table](#108-action-registry-table)
    - 10.9 [Existing Tables (Sessions, Messages, etc.)](#109-existing-tables)
    - 10.10 [Indexes Summary](#1010-indexes-summary)
    - 10.11 [JSONB Structures Reference](#1011-jsonb-structures-reference)

**➡️ Continue to BRAIN_04_INTEGRATION.md for API patterns & error handling**

---

# 10. COMPLETE DATABASE SCHEMA

## 10.1 Intent Ledger Table

**Purpose:** Tracks all detected intents across conversation turns for complete audit trail.

```sql
CREATE TABLE intent_ledger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    intent_id VARCHAR(100) UNIQUE NOT NULL,
    
    -- Context
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    brand_id VARCHAR(100) NOT NULL,
    instance_id UUID NOT NULL REFERENCES instances(id) ON DELETE CASCADE,
    
    -- Intent Details
    intent_type VARCHAR(50) NOT NULL,
    canonical_intent VARCHAR(255),
    match_type VARCHAR(50),  -- 'exact', 'fuzzy', 'synonym', 'not_found'
    confidence DECIMAL(3,2) NOT NULL,
    turn_number INT NOT NULL,
    sequence_order INT DEFAULT 1,
    reasoning TEXT,
    entities JSONB DEFAULT '{}',
    
    -- Status Tracking
    status VARCHAR(50) NOT NULL DEFAULT 'new',
    -- Status values: 'new', 'processing', 'queued', 'executing', 
    --                'completed', 'failed', 'blocked', 'action_not_found', 'cancelled'
    blocked_reason VARCHAR(255),
    
    -- Actions
    triggered_actions JSONB DEFAULT '[]',
    response_type VARCHAR(50),
    response_text TEXT,
    
    -- Resolution
    resolution TEXT,
    error TEXT,
    
    -- Timestamps
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    -- Indexes
    INDEX idx_intent_ledger_session_id (session_id),
    INDEX idx_intent_ledger_user_id (user_id),
    INDEX idx_intent_ledger_status (status),
    INDEX idx_intent_ledger_timestamp (timestamp),
    INDEX idx_intent_ledger_intent_type (intent_type),
    INDEX idx_intent_ledger_match_type (match_type)
);

-- Trigger for updated_at
CREATE TRIGGER update_intent_ledger_updated_at
    BEFORE UPDATE ON intent_ledger
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

**Key Points:**
- Immutable log of all intents
- Tracks status lifecycle from new → completed/failed/blocked
- Stores fuzzy search match_type ⭐ NEW
- Complete audit trail with timestamps

---

## 10.2 Action Queue Table

**Purpose:** Persistent, priority-based queue for action execution with retry management.

```sql
CREATE TABLE action_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    queue_id VARCHAR(100) UNIQUE NOT NULL,
    
    -- Action Details
    action_id VARCHAR(100) NOT NULL,
    action_name VARCHAR(255),
    
    -- Context
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    instance_id UUID NOT NULL REFERENCES instances(id) ON DELETE CASCADE,
    brand_id VARCHAR(100) NOT NULL,
    intent_id VARCHAR(100),
    workflow_instance_id UUID,
    
    -- Status
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    -- Status values: 'pending', 'ready', 'executing', 'completed', 
    --                'failed', 'retrying', 'blocked'
    priority INT DEFAULT 1,  -- 1=lowest, 10=highest
    
    -- Parameters
    params_collected JSONB DEFAULT '{}',
    params_missing JSONB DEFAULT '[]',
    params_validation_errors JSONB DEFAULT '{}',
    
    -- Retry Management
    retry_count INT DEFAULT 0,
    max_retries INT DEFAULT 3,
    last_retry_at TIMESTAMP,
    next_retry_at TIMESTAMP,
    retry_errors JSONB DEFAULT '[]',
    backoff_strategy VARCHAR(50) DEFAULT 'exponential',
    initial_delay_seconds INT DEFAULT 2,
    max_delay_seconds INT DEFAULT 60,
    
    -- Blocker
    blocker_reason VARCHAR(255),
    blocker_details JSONB,
    
    -- Idempotency
    idempotency_key VARCHAR(255) UNIQUE NOT NULL,
    execution_id UUID,
    
    -- Persistence
    persisted_to_db BOOLEAN DEFAULT TRUE,
    checkpoint_id VARCHAR(100),
    last_checkpoint_at TIMESTAMP,
    
    -- Timing
    added_at TIMESTAMP NOT NULL DEFAULT NOW(),
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    
    -- Metadata
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    -- Indexes
    INDEX idx_action_queue_session_id (session_id),
    INDEX idx_action_queue_user_id (user_id),
    INDEX idx_action_queue_status (status),
    INDEX idx_action_queue_priority (priority),
    INDEX idx_action_queue_next_retry_at (next_retry_at),
    INDEX idx_action_queue_idempotency_key (idempotency_key)
);

-- Trigger for updated_at
CREATE TRIGGER update_action_queue_updated_at
    BEFORE UPDATE ON action_queue
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

**Key Points:**
- Database-backed persistence (survives crashes)
- Priority-based execution
- Idempotency keys prevent duplicates
- Retry management with exponential backoff
- Checkpoint support for recovery

---

## 10.3 Dead Letter Queue Table

**Purpose:** Holds failed actions that exhausted retry attempts for manual intervention.

```sql
CREATE TABLE dead_letter_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dlq_id VARCHAR(100) UNIQUE NOT NULL,
    original_queue_id VARCHAR(100),
    
    -- Action Details
    action_id VARCHAR(100) NOT NULL,
    action_name VARCHAR(255),
    action_category VARCHAR(100),
    
    -- Context
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    instance_id UUID NOT NULL REFERENCES instances(id) ON DELETE CASCADE,
    brand_id VARCHAR(100) NOT NULL,
    intent_id VARCHAR(100),
    turn_number INT,
    
    -- Timing
    moved_to_dlq_at TIMESTAMP NOT NULL DEFAULT NOW(),
    original_added_at TIMESTAMP,
    time_in_queue_seconds INT,
    
    -- Failure Details
    original_status VARCHAR(50),
    retry_count INT,
    max_retries INT,
    final_error JSONB NOT NULL,
    retry_history JSONB DEFAULT '[]',
    
    -- Parameters
    params_collected JSONB DEFAULT '{}',
    
    -- Intervention
    requires_manual_intervention BOOLEAN DEFAULT FALSE,
    intervention_type VARCHAR(100),
    escalated_to_support BOOLEAN DEFAULT FALSE,
    escalation_ticket_id VARCHAR(100),
    escalated_at TIMESTAMP,
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMP,
    resolution_notes TEXT,
    
    -- User Communication
    user_notified BOOLEAN DEFAULT FALSE,
    user_notification_sent_at TIMESTAMP,
    user_notification_message TEXT,
    
    -- Idempotency
    idempotency_key VARCHAR(255),
    
    -- Metadata
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    -- Indexes
    INDEX idx_dlq_session_id (session_id),
    INDEX idx_dlq_user_id (user_id),
    INDEX idx_dlq_resolved (resolved),
    INDEX idx_dlq_escalated (escalated_to_support),
    INDEX idx_dlq_moved_to_dlq_at (moved_to_dlq_at)
);

-- Trigger for updated_at
CREATE TRIGGER update_dead_letter_queue_updated_at
    BEFORE UPDATE ON dead_letter_queue
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

**Key Points:**
- Tracks complete failure history
- Escalation to support ticketing system
- User notification tracking
- Manual resolution workflow

---

## 10.4 User Schema State Table

**Purpose:** Per-session cache of user data with computed key statuses.

```sql
CREATE TABLE user_schema_state (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Context
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    brand_id VARCHAR(100) NOT NULL,
    instance_id UUID NOT NULL REFERENCES instances(id) ON DELETE CASCADE,
    
    -- Schema Details
    schema_id VARCHAR(100) NOT NULL,
    schema_version VARCHAR(20),
    
    -- Fetch Metadata
    last_fetched_at TIMESTAMP,
    cache_expires_at TIMESTAMP,
    next_refresh_at TIMESTAMP,
    api_response_status VARCHAR(50),
    api_response_time_ms INT,
    api_error TEXT,
    
    -- Keys (all key statuses as JSONB)
    keys JSONB NOT NULL DEFAULT '{}',
    -- Structure: {"email": {"status": "complete", "value": "...", "last_updated": "..."}}
    
    -- Schema Status
    schema_status VARCHAR(50),
    -- Status values: 'none', 'incomplete', 'complete'
    schema_completion_percentage INT,
    required_keys_complete INT DEFAULT 0,
    required_keys_total INT DEFAULT 0,
    optional_keys_complete INT DEFAULT 0,
    optional_keys_total INT DEFAULT 0,
    
    -- Metadata
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    -- Constraints
    UNIQUE(session_id, schema_id),
    
    -- Indexes
    INDEX idx_user_schema_state_session_id (session_id),
    INDEX idx_user_schema_state_user_id (user_id),
    INDEX idx_user_schema_state_schema_id (schema_id),
    INDEX idx_user_schema_state_cache_expires_at (cache_expires_at)
);

-- Trigger for updated_at
CREATE TRIGGER update_user_schema_state_updated_at
    BEFORE UPDATE ON user_schema_state
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

**Key Points:**
- Per-session schema cache
- Tracks data freshness with TTL
- Computed completion percentages
- Fast eligibility lookups

---

## 10.5 Brand Schemas Table

**Purpose:** Defines schema structure and API configuration per brand.

```sql
CREATE TABLE brand_schemas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    schema_id VARCHAR(100) NOT NULL,
    brand_id VARCHAR(100) NOT NULL,
    
    -- Schema Details
    schema_name VARCHAR(200) NOT NULL,
    description TEXT,
    version VARCHAR(20) DEFAULT '1.0',
    category VARCHAR(100),
    
    -- API Configuration
    api_endpoint VARCHAR(500) NOT NULL,
    api_method VARCHAR(10) NOT NULL DEFAULT 'GET',
    api_auth JSONB NOT NULL,
    -- Structure: {"type": "bearer_token", "token_source": "...", "header_name": "..."}
    api_headers JSONB DEFAULT '{}',
    api_timeout_seconds INT DEFAULT 10,
    
    -- Caching
    refresh_strategy VARCHAR(50) DEFAULT 'on_demand',
    cache_ttl_seconds INT DEFAULT 300,
    cache_on_error BOOLEAN DEFAULT TRUE,
    stale_cache_threshold_seconds INT DEFAULT 600,
    
    -- Schema Keys (definitions)
    keys JSONB NOT NULL DEFAULT '[]',
    -- Structure: [{"key_name": "email", "data_type": "string", "required": true, ...}]
    
    -- Schema Completion Logic
    schema_completion_logic JSONB NOT NULL,
    -- Structure: {"type": "all_required_keys_complete", "compute_percentage": true}
    
    -- Error Handling
    api_error_handling JSONB DEFAULT '{}',
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Metadata
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    -- Constraints
    UNIQUE(brand_id, schema_id),
    
    -- Indexes
    INDEX idx_brand_schemas_brand_id (brand_id),
    INDEX idx_brand_schemas_schema_id (schema_id),
    INDEX idx_brand_schemas_is_active (is_active)
);

-- Trigger for updated_at
CREATE TRIGGER update_brand_schemas_updated_at
    BEFORE UPDATE ON brand_schemas
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

**Key Points:**
- Brand-specific schema definitions
- API endpoint + auth configuration
- Cache strategy configuration
- Key-level completion logic

---

## 10.6 Action Execution Log Table

**Purpose:** Immutable record of every action execution attempt.

```sql
CREATE TABLE action_execution_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id VARCHAR(100) UNIQUE NOT NULL,
    
    -- Action Details
    action_id VARCHAR(100) NOT NULL,
    action_name VARCHAR(255),
    
    -- Context
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    instance_id UUID NOT NULL REFERENCES instances(id) ON DELETE CASCADE,
    brand_id VARCHAR(100) NOT NULL,
    intent_id VARCHAR(100),
    queue_id VARCHAR(100),
    workflow_instance_id UUID,
    
    -- Timing
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    duration_ms INT,
    timeout_seconds INT,
    timed_out BOOLEAN DEFAULT FALSE,
    
    -- Status
    status VARCHAR(50) NOT NULL,
    -- Status values: 'executing', 'completed', 'failed', 'timeout'
    retry_attempt INT DEFAULT 0,
    final_retry BOOLEAN DEFAULT FALSE,
    
    -- Input
    params_used JSONB NOT NULL,
    params_validated BOOLEAN DEFAULT TRUE,
    validation_errors JSONB DEFAULT '[]',
    
    -- Output
    result JSONB,
    api_response_status INT,
    api_response_body JSONB,
    
    -- Error
    error TEXT,
    error_type VARCHAR(100),
    error_message TEXT,
    error_code VARCHAR(100),
    stack_trace TEXT,
    
    -- Rollback
    rollback_performed BOOLEAN DEFAULT FALSE,
    rollback_action_id VARCHAR(100),
    rollback_execution_id VARCHAR(100),
    
    -- Acknowledgement
    requires_acknowledgement BOOLEAN DEFAULT FALSE,
    acknowledged BOOLEAN DEFAULT FALSE,
    acknowledged_at TIMESTAMP,
    acknowledgement_timeout BOOLEAN DEFAULT FALSE,
    
    -- Idempotency
    idempotency_key VARCHAR(255) NOT NULL,
    duplicate_execution BOOLEAN DEFAULT FALSE,
    original_execution_id VARCHAR(100),
    
    -- Metadata
    trace_id VARCHAR(100),
    request_id VARCHAR(100),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    -- Indexes
    INDEX idx_execution_log_session_id (session_id),
    INDEX idx_execution_log_user_id (user_id),
    INDEX idx_execution_log_action_id (action_id),
    INDEX idx_execution_log_status (status),
    INDEX idx_execution_log_started_at (started_at),
    INDEX idx_execution_log_idempotency_key (idempotency_key),
    INDEX idx_execution_log_trace_id (trace_id)
);
```

**Key Points:**
- Complete audit trail
- Performance metrics (duration_ms)
- Idempotency tracking
- Error debugging support

---

## 10.7 Workflow Instances Table

**Purpose:** Tracks multi-step workflow execution progress.

```sql
CREATE TABLE workflow_instances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_instance_id VARCHAR(100) UNIQUE NOT NULL,
    
    -- Workflow Details
    workflow_id VARCHAR(100) NOT NULL,
    workflow_name VARCHAR(255),
    workflow_version VARCHAR(20),
    
    -- Context
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    instance_id UUID NOT NULL REFERENCES instances(id) ON DELETE CASCADE,
    
    -- Status
    status VARCHAR(50) NOT NULL DEFAULT 'in_progress',
    -- Status values: 'in_progress', 'completed', 'failed', 'cancelled'
    current_step INT,
    
    -- Progress
    progress_percentage INT DEFAULT 0,
    steps_completed INT DEFAULT 0,
    steps_total INT,
    steps_remaining INT,
    
    -- Steps Executed (history)
    steps_executed JSONB DEFAULT '[]',
    -- Structure: [{"sequence_id": 1, "action_id": "...", "status": "...", ...}]
    
    -- Timing
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP,
    timeout_at TIMESTAMP,
    timed_out BOOLEAN DEFAULT FALSE,
    estimated_completion_at TIMESTAMP,
    
    -- Rollback
    rollback_performed BOOLEAN DEFAULT FALSE,
    rollback_steps JSONB DEFAULT '[]',
    
    -- Metadata
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    -- Indexes
    INDEX idx_workflow_instances_session_id (session_id),
    INDEX idx_workflow_instances_workflow_id (workflow_id),
    INDEX idx_workflow_instances_status (status)
);

-- Trigger for updated_at
CREATE TRIGGER update_workflow_instances_updated_at
    BEFORE UPDATE ON workflow_instances
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

**Key Points:**
- Progress tracking
- Step execution history
- Rollback support
- Timeout management

---

## 10.8 Action Registry Table

**Purpose:** Centralized configuration for all available actions per instance.

```sql
CREATE TABLE action_registry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    action_id VARCHAR(100) NOT NULL,
    instance_id UUID NOT NULL REFERENCES instances(id) ON DELETE CASCADE,
    brand_id VARCHAR(100) NOT NULL,
    
    -- Action Details
    action_name VARCHAR(255) NOT NULL,
    display_name VARCHAR(255),
    description TEXT,
    category VARCHAR(100),
    synonyms JSONB DEFAULT '[]',  -- ⭐ NEW for fuzzy search
    
    -- Parameters
    params_required JSONB DEFAULT '[]',
    params_optional JSONB DEFAULT '[]',
    param_validation JSONB DEFAULT '{}',
    
    -- Eligibility
    eligibility_criteria JSONB NOT NULL,
    -- Structure: {"user_tier": [...], "schema_dependencies": {...}}
    blockers JSONB DEFAULT '[]',
    dependencies JSONB DEFAULT '[]',
    opposites JSONB DEFAULT '[]',
    
    -- Execution
    timeout_seconds INT DEFAULT 30,
    retry_policy JSONB NOT NULL,
    -- Structure: {"max_retries": 3, "backoff_strategy": "exponential", ...}
    rollback_possible BOOLEAN DEFAULT FALSE,
    rollback_action_id VARCHAR(100),
    requires_user_acknowledgement BOOLEAN DEFAULT FALSE,
    acknowledgement_timeout_seconds INT DEFAULT 300,
    estimated_duration_seconds INT,
    
    -- API Details
    execution_type VARCHAR(50),
    api_endpoint VARCHAR(500),
    api_method VARCHAR(10),
    api_auth_type VARCHAR(50),
    
    -- Workflow
    workflow_id VARCHAR(100),
    sequence_id INT,
    triggers_workflow BOOLEAN DEFAULT FALSE,
    
    -- Monitoring
    success_criteria JSONB,
    failure_criteria JSONB,
    
    -- Priority
    priority VARCHAR(20) DEFAULT 'normal',
    -- Priority values: 'low', 'normal', 'high', 'critical'
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Metadata
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    -- Constraints
    UNIQUE(instance_id, action_id),
    
    -- Indexes
    INDEX idx_action_registry_instance_id (instance_id),
    INDEX idx_action_registry_brand_id (brand_id),
    INDEX idx_action_registry_action_id (action_id),
    INDEX idx_action_registry_is_active (is_active),
    INDEX idx_action_registry_workflow_id (workflow_id)
);

-- Trigger for updated_at
CREATE TRIGGER update_action_registry_updated_at
    BEFORE UPDATE ON action_registry
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();
```

**Key Points:**
- Complete action configuration
- Synonyms for fuzzy search ⭐ NEW
- Comprehensive eligibility rules
- Workflow integration

---

## 10.9 Existing Tables

**These tables already exist in the system and are referenced by Brain tables:**

### Sessions Table (Enhanced)

```sql
-- EXISTING TABLE with NEW COLUMN
ALTER TABLE sessions ADD COLUMN IF NOT EXISTS state JSONB NOT NULL DEFAULT '{}';

-- The state JSONB stores Brain wires:
-- {
--   "expecting_response": bool,
--   "answer_sheet": {...},
--   "active_task": {...},
--   "previous_intents": [...],
--   "conversation_context": {...},
--   "available_signals": [...],
--   "intent_ledger": [...],
--   "action_queue": [...],
--   "schema_states": {...},
--   "streaming_updates": [...]
-- }
```

### Other Existing Tables

- **users** - User accounts
- **brands** - Brand/tenant definitions
- **instances** - Instance configurations
- **instance_configs** - Instance-specific config (stores popular_actions)
- **messages** - Conversation messages
- **templates** - LLM prompt templates
- **template_sets** - Template collections
- **llm_models** - LLM model definitions
- **user_identifiers** - Brand-scoped identity
- **idempotency_locks** - Request deduplication

---

## 10.10 Indexes Summary

**Critical Indexes for Performance:**

| Table | Index Name | Columns | Purpose |
|-------|------------|---------|---------|
| intent_ledger | idx_intent_ledger_session_id | session_id | Fast session lookups |
| intent_ledger | idx_intent_ledger_status | status | Filter by status |
| intent_ledger | idx_intent_ledger_match_type | match_type | Fuzzy search analytics |
| action_queue | idx_action_queue_priority | priority | Priority sorting |
| action_queue | idx_action_queue_status | status | Filter by status |
| action_queue | idx_action_queue_idempotency_key | idempotency_key | Duplicate detection |
| dead_letter_queue | idx_dlq_resolved | resolved | Find unresolved failures |
| dead_letter_queue | idx_dlq_escalated | escalated_to_support | Support queue |
| user_schema_state | idx_user_schema_state_cache_expires_at | cache_expires_at | Cache expiry checks |
| action_execution_log | idx_execution_log_trace_id | trace_id | Distributed tracing |
| workflow_instances | idx_workflow_instances_status | status | Active workflows |
| action_registry | idx_action_registry_is_active | is_active | Active actions only |

---

## 10.11 JSONB Structures Reference

**Complete reference for all JSONB columns:**

### sessions.state

```json
{
  "expecting_response": true,
  "answer_sheet": {
    "type": "confirmation",
    "options": {
      "yes": ["yes", "yeah", "sure"],
      "no": ["no", "nope", "cancel"]
    }
  },
  "active_task": {
    "task_id": "uuid",
    "canonical_action": "apply_job",
    "params_collected": {...},
    "params_missing": [...],
    "status": "collecting_params"
  },
  "previous_intents": [
    {"intent_type": "greeting", "confidence": 0.98, "turn": 1},
    {"intent_type": "action", "canonical_action": "search_jobs", "turn": 2}
  ],
  "conversation_context": {
    "domain": "job_search",
    "user_state": "browsing",
    "last_action": "searched_jobs"
  },
  "available_signals": ["yes", "no", "#1", "#2"],
  "intent_ledger": [...],
  "action_queue": [...],
  "schema_states": {
    "profile": {
      "schema_id": "profile",
      "keys": {
        "email": {"status": "complete", "value": "user@example.com"},
        "phone": {"status": "none", "value": null}
      },
      "schema_status": "incomplete",
      "cache_expires_at": "2025-11-15T10:35:00Z"
    }
  },
  "streaming_updates": [
    {"update_type": "action_lookup", "status": "found", "timestamp": "..."},
    {"update_type": "intent_logged", "intent_id": "...", "timestamp": "..."}
  ]
}
```

### intent_ledger.entities

```json
{
  "company": "Google",
  "job_id": "12345",
  "job_title": "Software Engineer",
  "location": "San Francisco"
}
```

### intent_ledger.triggered_actions

```json
[
  "action_001",
  "action_002"
]
```

### action_queue.params_collected

```json
{
  "amount": 100,
  "payment_method_id": "pm_abc123",
  "discount_code": "SAVE10"
}
```

### action_queue.retry_errors

```json
[
  {
    "attempt": 1,
    "error": "API timeout",
    "timestamp": "2025-11-15T10:30:00Z"
  },
  {
    "attempt": 2,
    "error": "Connection refused",
    "timestamp": "2025-11-15T10:30:02Z"
  }
]
```

### brand_schemas.keys

```json
[
  {
    "key_name": "email",
    "data_type": "string",
    "required_for_schema": true,
    "completion_logic": {
      "type": "non_empty",
      "validation": "email_format",
      "validation_regex": "^[\\w\\.-]+@[\\w\\.-]+\\.\\w+$"
    },
    "api_field_path": "data.contact.email"
  },
  {
    "key_name": "phone",
    "data_type": "string",
    "required_for_schema": true,
    "completion_logic": {
      "type": "non_empty",
      "validation": "phone_e164"
    },
    "api_field_path": "data.contact.phone"
  }
]
```

### action_registry.eligibility_criteria

```json
{
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
    }
  }
}
```

### action_registry.retry_policy

```json
{
  "max_retries": 3,
  "backoff_strategy": "exponential",
  "initial_delay_seconds": 2,
  "max_delay_seconds": 60,
  "retry_on_errors": ["timeout", "api_error", "network_error"]
}
```

### workflow_instances.steps_executed

```json
[
  {
    "sequence_id": 1,
    "action_id": "create_profile",
    "status": "completed",
    "execution_id": "exec_001",
    "started_at": "2025-11-15T10:00:00Z",
    "completed_at": "2025-11-15T10:00:05Z",
    "result": {"profile_id": "prof_123"}
  },
  {
    "sequence_id": 2,
    "action_id": "upload_resume",
    "status": "executing",
    "execution_id": "exec_002",
    "started_at": "2025-11-15T10:00:06Z"
  }
]
```

---

**END OF PART 3**

➡️ **Continue to BRAIN_04_INTEGRATION.md for API patterns, error handling, and configuration examples**