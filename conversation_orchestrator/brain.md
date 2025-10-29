# 🧠 BRAIN ARCHITECTURE - COMPLETE DESIGN SPECIFICATION

**Version:** 2.0  
**Date:** October 28, 2025  
**Status:** Design Complete - Ready for Implementation

---

## 📑 TABLE OF CONTENTS

1. [Executive Overview](#executive-overview)
2. [System Architecture](#system-architecture)
3. [Core Components](#core-components)
   - 3.1 [Intent Ledger](#31-intent-ledger)
   - 3.2 [Action Registry](#32-action-registry)
   - 3.3 [Action Execution Queue](#33-action-execution-queue)
   - 3.4 [User Data Schemas](#34-user-data-schemas)
   - 3.5 [Schema State Tracker](#35-schema-state-tracker)
   - 3.6 [Active Task Tracker](#36-active-task-tracker)
   - 3.7 [Next Narrative Generator](#37-next-narrative-generator)
   - 3.8 [Workflow Engine](#38-workflow-engine)
   - 3.9 [Action Execution Log](#39-action-execution-log)
   - 3.10 [Dead Letter Queue](#310-dead-letter-queue)
4. [Processing Flow](#processing-flow)
5. [Database Schema](#database-schema)
6. [API Integration Patterns](#api-integration-patterns)
7. [Error Handling & Retry Strategies](#error-handling--retry-strategies)
8. [Idempotency & Concurrency Control](#idempotency--concurrency-control)
9. [Configuration Examples](#configuration-examples)
10. [Implementation Guidelines](#implementation-guidelines)

---

## 1. EXECUTIVE OVERVIEW

### 1.1 Purpose

The Brain is the central orchestration component of the conversational AI system. It receives intents detected by the Intent Detector and manages the complete lifecycle of actions, workflows, and state management required to fulfill user requests.

### 1.2 Key Responsibilities

The Brain handles:

1. **Intent Management:** Tracks all detected intents across conversation turns
2. **Action Orchestration:** Maps intents to actions and manages execution
3. **State Management:** Maintains conversation state, task progress, and user data
4. **Workflow Coordination:** Executes multi-step workflows with dependency management
5. **Eligibility Validation:** Determines action eligibility based on user data, permissions, and business rules
6. **Queue Management:** Manages action execution queues with retry policies and persistence
7. **Real-Time Data Integration:** Fetches and validates user data from brand APIs
8. **Error Handling:** Manages failures, retries, and escalations gracefully

### 1.3 Design Philosophy

**Production-Grade Reliability:**
- Queue persistence survives server crashes
- Idempotency prevents duplicate executions
- Retry policies with exponential backoff
- Dead letter queue for permanent failures
- Comprehensive error tracking and escalation

**Real-Time Data Validation:**
- Fresh user data fetched from brand APIs on-demand
- Schema-based validation with computed key statuses
- Action eligibility determined by data completeness
- Cached data with configurable TTL

**Flexible & Extensible:**
- Instance-specific action configurations
- Reusable workflows across multiple actions
- Plugin architecture for new action types
- Brand-specific schema definitions

---

## 2. SYSTEM ARCHITECTURE

### 2.1 High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     INTENT DETECTOR                              │
│  (Detects user intents, extracts entities, determines           │
│   self-response vs brain-required)                              │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         │ Intents + Entities
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                         BRAIN                                    │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  1. INTENT LEDGER                                        │  │
│  │     - Logs all intents with confidence, turn, status     │  │
│  └──────────────────────────────────────────────────────────┘  │
│                         │                                        │
│                         ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  2. SCHEMA STATE TRACKER                                 │  │
│  │     - Fetches user data from brand APIs                  │  │
│  │     - Computes key statuses (none/incomplete/complete)   │  │
│  │     - Caches with TTL                                    │  │
│  └──────────────────────────────────────────────────────────┘  │
│                         │                                        │
│                         ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  3. ACTION ELIGIBILITY CHECKER                           │  │
│  │     - Schema dependency validation                       │  │
│  │     - User tier & auth checks                            │  │
│  │     - Blocker detection                                  │  │
│  │     - Action dependency validation                       │  │
│  └──────────────────────────────────────────────────────────┘  │
│                         │                                        │
│                         ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  4. ACTION EXECUTION QUEUE                               │  │
│  │     - Priority-based queue                               │  │
│  │     - Idempotency tracking                               │  │
│  │     - Retry policy enforcement                           │  │
│  │     - Queue persistence to database                      │  │
│  └──────────────────────────────────────────────────────────┘  │
│                         │                                        │
│                         ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  5. ACTION EXECUTOR                                      │  │
│  │     - Executes actions with timeout                      │  │
│  │     - Handles retries with backoff                       │  │
│  │     - Moves failures to dead letter queue                │  │
│  │     - Logs execution results                             │  │
│  └──────────────────────────────────────────────────────────┘  │
│                         │                                        │
│                         ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  6. WORKFLOW COORDINATOR                                 │  │
│  │     - Manages multi-step workflows                       │  │
│  │     - Tracks workflow progress                           │  │
│  │     - Handles workflow branching                         │  │
│  └──────────────────────────────────────────────────────────┘  │
│                         │                                        │
│                         ▼                                        │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  7. RESPONSE GENERATOR                                   │  │
│  │     - Updates active task                                │  │
│  │     - Generates next narrative (must + optional)         │  │
│  │     - Creates response payload                           │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         │ Response + Next Narrative
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LLM RESPONDER                                 │
│  (Generates natural language response based on next narrative)  │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 Data Flow

**Turn N (User sends message):**

1. User message → Intent Detector
2. Intent Detector → Brain (with detected intents)
3. Brain logs intents to Intent Ledger
4. Brain fetches user schema state from APIs (if needed)
5. Brain computes action eligibility
6. Brain adds eligible actions to queue
7. Brain processes queue:
   - Collects missing params OR
   - Executes action if params complete
8. Brain generates next narrative
9. Brain → LLM Responder (with narrative)
10. LLM Responder → User (natural language response)

**Background (Async):**

- Queue processor handles retries for failed actions
- Schema cache refreshes based on TTL
- Dead letter queue monitored for manual intervention
- Workflow coordinator tracks multi-step flows

### 2.3 Component Interactions

```
Intent Ledger ←──────┐
                     │
Schema State ←───────┤
                     │
Action Registry ←────┼──── Brain Core Logic
                     │
Action Queue ←───────┤
                     │
Workflow Engine ←────┘

Action Queue ──→ Action Executor ──→ Brand APIs
                                  └──→ Action Execution Log
                                  └──→ Dead Letter Queue (on failure)

Schema State ──→ Brand APIs (GET user data)
```

---

## 3. CORE COMPONENTS

### 3.1 INTENT LEDGER

**Purpose:** State manager that tracks ALL intents detected across all conversation turns for a session.

**Why it exists:** Provides complete audit trail of user intentions, enables pattern analysis, supports context retention across multiple turns.

#### 3.1.1 Data Structure

```python
intent_ledger = {
    "session_id": "abc-123",
    "user_id": "user_12345",
    "intents": [
        {
            "id": "intent_001",
            "intent_type": "greeting",
            "confidence": 0.95,
            "turn_number": 1,
            "timestamp": "2025-10-28T10:00:00Z",
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
            "confidence": 0.90,
            "turn_number": 2,
            "timestamp": "2025-10-28T10:01:00Z",
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
            "confidence": 0.85,
            "turn_number": 5,
            "timestamp": "2025-10-28T10:05:00Z",
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

#### 3.1.2 Intent Status Values

| Status | Description | When Applied |
|--------|-------------|--------------|
| `new` | Intent just detected | Immediately after intent detection |
| `processing` | Action(s) triggered and queued | After adding to action queue |
| `collecting_params` | Waiting for user to provide required params | When params missing for action |
| `executing` | Action currently executing | During action execution |
| `completed` | Action successfully completed | After successful execution |
| `failed` | Action failed (exhausted retries) | After all retries failed |
| `blocked` | Cannot proceed due to blocker | When eligibility check fails |
| `cancelled` | User cancelled the intent | User says "cancel" or "stop" |

#### 3.1.3 Operations

**Log Intent:**
```python
def log_intent(
    session_id: str,
    intent_type: str,
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
```

**Update Intent Status:**
```python
def update_intent_status(
    intent_id: str,
    new_status: str,
    additional_info: dict = None
) -> bool:
    """
    Updates the status of an existing intent.
    Optionally adds metadata like blocked_reason.
    """
```

**Query Intents:**
```python
def get_intents_by_session(
    session_id: str,
    filters: dict = None
) -> list:
    """
    Retrieves all intents for a session.
    Filters can include: status, intent_type, turn_range
    """
```

---

### 3.2 ACTION REGISTRY

**Purpose:** Global configuration of all available actions per instance. Defines action metadata, eligibility rules, execution policies, and workflow associations.

**Why it exists:** Separates action configuration from code, enables per-instance customization, provides single source of truth for action capabilities.

#### 3.2.1 Action Configuration Structure

Each action has the following configuration:

```python
{
    "action_id": "create_profile",
    "action_name": "Create User Profile",
    "description": "Creates a new user profile in the brand's CRM system",
    "category": "onboarding",
    
    # Parameters
    "params_required": ["name", "email", "phone"],
    "params_optional": ["address", "date_of_birth", "preferences"],
    
    # Parameter Validation Rules
    "param_validation": {
        "name": {
            "type": "string",
            "min_length": 2,
            "max_length": 100,
            "regex": "^[a-zA-Z\\s]+$",
            "error_message": "Name must contain only letters and spaces"
        },
        "email": {
            "type": "string",
            "regex": "^[\\w\\.-]+@[\\w\\.-]+\\.\\w+$",
            "error_message": "Please provide a valid email address"
        },
        "phone": {
            "type": "string",
            "regex": "^\\+?[1-9]\\d{1,14}$",
            "error_message": "Please provide a valid phone number"
        }
    },
    
    # Eligibility Criteria
    "eligibility_criteria": {
        "user_tier": ["verified", "guest"],
        "min_age": 18,
        "requires_auth": False,
        "max_concurrent_executions": 1,
        
        # Schema Dependencies (NEW)
        "schema_dependencies": {
            "profile": {
                "keys_required": ["email"],
                "keys_optional": ["phone"]
            }
        }
    },
    
    # Blockers
    "blockers": [
        "profile_already_exists",
        "email_in_use",
        "phone_in_use"
    ],
    
    # Dependencies (other actions that must complete first)
    "dependencies": [],
    
    # Opposites (actions that conflict with this one)
    "opposites": ["delete_profile"],
    
    # Execution Configuration
    "timeout_seconds": 30,
    "retry_policy": {
        "max_retries": 3,
        "backoff_strategy": "exponential",
        "initial_delay_seconds": 2,
        "max_delay_seconds": 60,
        "retry_on_errors": ["timeout", "api_error", "network_error", "rate_limit"],
        "no_retry_on_errors": ["validation_error", "auth_error", "conflict_error"]
    },
    
    # Rollback & Acknowledgement
    "rollback_possible": True,
    "rollback_action_id": "delete_profile",
    "requires_user_acknowledgement": True,
    "acknowledgement_timeout_seconds": 300,
    
    # Execution Details
    "estimated_duration_seconds": 5,
    "execution_type": "api_call",
    "api_endpoint": "https://api.brand-xyz.com/v1/users",
    "api_method": "POST",
    "api_auth_type": "bearer_token",
    
    # Workflow Integration
    "workflow_id": "onboarding_flow",
    "sequence_id": 1,
    "triggers_workflow": False,
    
    # Monitoring
    "success_criteria": {
        "response_status": [200, 201],
        "required_response_fields": ["user_id"]
    },
    "failure_criteria": {
        "response_status": [400, 401, 403, 404, 409, 500, 503]
    }
}
```

#### 3.2.2 Complete Action Registry Example

```python
instance_actions = {
    "instance_id": "retail-store-001",
    "brand_id": "brand-xyz",
    "brand_name": "XYZ Retail",
    "available_actions": [
        {
            # ACTION 1: Create Profile
            "action_id": "create_profile",
            "action_name": "Create User Profile",
            "description": "Creates a new user profile in the brand's CRM system",
            "category": "onboarding",
            "params_required": ["name", "email", "phone"],
            "params_optional": ["address", "preferences"],
            "param_validation": {
                "name": {
                    "type": "string",
                    "min_length": 2,
                    "max_length": 100,
                    "error_message": "Name must be 2-100 characters"
                },
                "email": {
                    "type": "string",
                    "regex": "^[\\w\\.-]+@[\\w\\.-]+\\.\\w+$",
                    "error_message": "Please provide a valid email"
                },
                "phone": {
                    "type": "string",
                    "regex": "^\\+?[1-9]\\d{9,14}$",
                    "error_message": "Please provide a valid phone number"
                }
            },
            "eligibility_criteria": {
                "user_tier": ["verified", "guest"],
                "min_age": 18,
                "requires_auth": False,
                "schema_dependencies": {}
            },
            "blockers": ["profile_already_exists", "email_in_use"],
            "dependencies": [],
            "opposites": ["delete_profile"],
            "timeout_seconds": 30,
            "retry_policy": {
                "max_retries": 3,
                "backoff_strategy": "exponential",
                "initial_delay_seconds": 2,
                "max_delay_seconds": 60,
                "retry_on_errors": ["timeout", "api_error"],
                "no_retry_on_errors": ["validation_error", "conflict_error"]
            },
            "rollback_possible": True,
            "rollback_action_id": "delete_profile",
            "requires_user_acknowledgement": True,
            "acknowledgement_timeout_seconds": 300,
            "estimated_duration_seconds": 5,
            "workflow_id": "onboarding_flow",
            "sequence_id": 1,
            "triggers_workflow": False
        },
        {
            # ACTION 2: Process Payment
            "action_id": "process_payment",
            "action_name": "Process Payment",
            "description": "Processes payment for an order",
            "category": "financial",
            "params_required": ["amount", "payment_method", "order_id"],
            "params_optional": ["discount_code", "installment_plan"],
            "param_validation": {
                "amount": {
                    "type": "number",
                    "min": 1,
                    "max": 1000000,
                    "error_message": "Amount must be between 1 and 1,000,000"
                },
                "payment_method": {
                    "type": "enum",
                    "allowed_values": ["credit_card", "debit_card", "upi", "wallet", "net_banking"],
                    "error_message": "Invalid payment method"
                },
                "order_id": {
                    "type": "string",
                    "regex": "^ORD-[0-9]{8}$",
                    "error_message": "Invalid order ID format"
                }
            },
            "eligibility_criteria": {
                "user_tier": ["verified"],
                "requires_auth": True,
                "min_age": 18,
                "schema_dependencies": {
                    "profile": {
                        "keys_required": ["email", "phone", "payment_method"],
                        "keys_optional": []
                    },
                    "cart": {
                        "keys_required": ["items", "total_amount"],
                        "keys_optional": ["discount_code"]
                    }
                }
            },
            "blockers": [
                "insufficient_balance",
                "payment_method_invalid",
                "order_not_found",
                "payment_already_processed"
            ],
            "dependencies": ["create_profile", "add_to_cart"],
            "opposites": ["cancel_order", "refund_payment"],
            "timeout_seconds": 60,
            "retry_policy": {
                "max_retries": 0,
                "backoff_strategy": "none",
                "retry_on_errors": [],
                "no_retry_on_errors": ["*"]
            },
            "rollback_possible": True,
            "rollback_action_id": "refund_payment",
            "requires_user_acknowledgement": True,
            "acknowledgement_timeout_seconds": 180,
            "estimated_duration_seconds": 10,
            "workflow_id": "checkout_flow",
            "sequence_id": 3,
            "triggers_workflow": False
        },
        {
            # ACTION 3: Start Onboarding Workflow
            "action_id": "start_onboarding",
            "action_name": "Start Onboarding Workflow",
            "description": "Initiates the complete user onboarding workflow",
            "category": "workflow_trigger",
            "params_required": [],
            "params_optional": ["referral_code"],
            "param_validation": {},
            "eligibility_criteria": {
                "user_tier": ["guest"],
                "requires_auth": False,
                "schema_dependencies": {}
            },
            "blockers": ["already_onboarded", "onboarding_in_progress"],
            "dependencies": [],
            "opposites": [],
            "timeout_seconds": 300,
            "retry_policy": {
                "max_retries": 0,
                "backoff_strategy": "none",
                "retry_on_errors": [],
                "no_retry_on_errors": ["*"]
            },
            "rollback_possible": False,
            "requires_user_acknowledgement": False,
            "estimated_duration_seconds": 120,
            "workflow_id": "onboarding_flow",
            "sequence_id": 0,
            "triggers_workflow": True
        },
        {
            # ACTION 4: Send Email Notification
            "action_id": "send_email",
            "action_name": "Send Email Notification",
            "description": "Sends an email notification to the user",
            "category": "communication",
            "params_required": ["email", "template_id"],
            "params_optional": ["variables"],
            "param_validation": {
                "email": {
                    "type": "string",
                    "regex": "^[\\w\\.-]+@[\\w\\.-]+\\.\\w+$",
                    "error_message": "Invalid email address"
                },
                "template_id": {
                    "type": "string",
                    "error_message": "Template ID is required"
                }
            },
            "eligibility_criteria": {
                "user_tier": ["verified", "guest"],
                "requires_auth": False,
                "schema_dependencies": {
                    "profile": {
                        "keys_required": ["email"],
                        "keys_optional": []
                    }
                }
            },
            "blockers": ["email_service_unavailable", "invalid_email"],
            "dependencies": [],
            "opposites": [],
            "timeout_seconds": 30,
            "retry_policy": {
                "max_retries": 5,
                "backoff_strategy": "exponential",
                "initial_delay_seconds": 5,
                "max_delay_seconds": 300,
                "retry_on_errors": ["timeout", "smtp_error", "rate_limit"],
                "no_retry_on_errors": ["invalid_email", "template_not_found"]
            },
            "rollback_possible": False,
            "requires_user_acknowledgement": False,
            "estimated_duration_seconds": 3,
            "workflow_id": null,
            "sequence_id": null,
            "triggers_workflow": False
        },
        {
            # ACTION 5: Update KYC Status
            "action_id": "update_kyc",
            "action_name": "Update KYC Verification Status",
            "description": "Updates user's KYC verification status",
            "category": "compliance",
            "params_required": ["kyc_status", "verification_id"],
            "params_optional": ["documents"],
            "param_validation": {
                "kyc_status": {
                    "type": "enum",
                    "allowed_values": ["pending", "verified", "rejected"],
                    "error_message": "Invalid KYC status"
                },
                "verification_id": {
                    "type": "string",
                    "min_length": 10,
                    "error_message": "Invalid verification ID"
                }
            },
            "eligibility_criteria": {
                "user_tier": ["verified", "guest"],
                "requires_auth": True,
                "schema_dependencies": {
                    "profile": {
                        "keys_required": ["email", "phone", "kyc_verified"],
                        "keys_optional": []
                    }
                }
            },
            "blockers": ["kyc_already_verified", "invalid_documents"],
            "dependencies": ["create_profile"],
            "opposites": [],
            "timeout_seconds": 45,
            "retry_policy": {
                "max_retries": 2,
                "backoff_strategy": "linear",
                "initial_delay_seconds": 10,
                "max_delay_seconds": 30,
                "retry_on_errors": ["timeout", "api_error"],
                "no_retry_on_errors": ["validation_error", "already_verified"]
            },
            "rollback_possible": False,
            "requires_user_acknowledgement": True,
            "acknowledgement_timeout_seconds": 600,
            "estimated_duration_seconds": 15,
            "workflow_id": "kyc_flow",
            "sequence_id": 2,
            "triggers_workflow": False
        }
    ]
}
```

#### 3.2.3 Retry Policy Strategies

**Exponential Backoff:**
```
Retry 1: Wait initial_delay_seconds (e.g., 2s)
Retry 2: Wait 2 × initial_delay_seconds (e.g., 4s)
Retry 3: Wait 4 × initial_delay_seconds (e.g., 8s)
Retry 4: Wait 8 × initial_delay_seconds (e.g., 16s)
...capped at max_delay_seconds
```

**Linear Backoff:**
```
Retry 1: Wait initial_delay_seconds (e.g., 10s)
Retry 2: Wait initial_delay_seconds + 10s (e.g., 20s)
Retry 3: Wait initial_delay_seconds + 20s (e.g., 30s)
...capped at max_delay_seconds
```

**Fixed Delay:**
```
All retries: Wait initial_delay_seconds
```

**No Retry:**
```
max_retries = 0
Used for payment actions where duplicate execution is dangerous
```

---

### 3.3 ACTION EXECUTION QUEUE

**Purpose:** Manages the ordered execution of actions with status tracking, retry policies, and persistence.

**Why it exists:** Ensures actions execute in correct order, handles failures gracefully, survives server crashes through persistence.

#### 3.3.1 Queue Item Structure

```python
{
    "queue_id": "q_001",
    "action_id": "create_profile",
    "action_name": "Create User Profile",
    
    # Status Tracking
    "status": "pending",
    "added_at": "2025-10-28T10:01:00Z",
    "started_at": null,
    "completed_at": null,
    
    # Priority (higher = more urgent)
    "priority": 1,
    
    # Parameters
    "params_collected": {
        "name": "Nikunj",
        "email": "nikunj@example.com",
        "phone": null
    },
    "params_missing": ["phone"],
    "params_validation_errors": {},
    
    # Retry Management
    "retry_count": 0,
    "max_retries": 3,
    "last_retry_at": null,
    "next_retry_at": null,
    "retry_errors": [],
    "backoff_strategy": "exponential",
    "initial_delay_seconds": 2,
    "max_delay_seconds": 60,
    
    # Blocker Information
    "blocker_reason": null,
    "blocker_details": null,
    
    # Idempotency
    "idempotency_key": "session_abc-123_action_create_profile_20251028100100",
    "execution_id": null,
    
    # Persistence
    "persisted_to_db": true,
    "checkpoint_id": "chk_001",
    "last_checkpoint_at": "2025-10-28T10:01:00Z",
    
    # Context
    "session_id": "abc-123",
    "user_id": "user_12345",
    "intent_id": "intent_002",
    "workflow_id": null,
    "workflow_step": null
}
```

#### 3.3.2 Queue Status Values

| Status | Description | Next Steps |
|--------|-------------|------------|
| `pending` | Waiting to execute | Check params → Execute or collect params |
| `collecting_params` | Waiting for user input | Ask user for missing params |
| `ready` | All params collected, ready to execute | Execute immediately |
| `executing` | Currently executing | Wait for completion or timeout |
| `retrying` | In retry backoff period | Wait until next_retry_at, then execute |
| `completed` | Successfully executed | Remove from queue, log to execution log |
| `failed` | Execution failed (non-retriable error) | Move to dead letter queue |
| `blocked` | Cannot execute due to blocker | Resolve blocker or escalate |
| `cancelled` | User cancelled | Remove from queue |
| `dead_letter` | Moved to dead letter queue | Manual intervention required |

#### 3.3.3 Complete Queue Structure

```python
action_queue = {
    "session_id": "abc-123",
    "user_id": "user_12345",
    "brand_id": "brand-xyz",
    
    # Main Queue
    "queue": [
        {
            "queue_id": "q_001",
            "action_id": "create_profile",
            "status": "pending",
            "added_at": "2025-10-28T10:01:00Z",
            "priority": 1,
            "params_collected": {
                "name": "Nikunj",
                "email": "nikunj@example.com",
                "phone": null
            },
            "params_missing": ["phone"],
            "retry_count": 0,
            "max_retries": 3,
            "idempotency_key": "session_abc-123_action_create_profile_001",
            "persisted_to_db": true,
            "checkpoint_id": "chk_001"
        },
        {
            "queue_id": "q_002",
            "action_id": "send_email",
            "status": "retrying",
            "added_at": "2025-10-28T10:02:00Z",
            "started_at": "2025-10-28T10:02:05Z",
            "priority": 2,
            "params_collected": {
                "email": "nikunj@example.com",
                "template_id": "welcome"
            },
            "params_missing": [],
            "retry_count": 2,
            "max_retries": 5,
            "last_retry_at": "2025-10-28T10:02:35Z",
            "next_retry_at": "2025-10-28T10:03:05Z",
            "retry_errors": [
                {
                    "attempt": 1,
                    "error_type": "timeout",
                    "error_message": "SMTP server timeout after 30s",
                    "timestamp": "2025-10-28T10:02:10Z",
                    "stack_trace": "..."
                },
                {
                    "attempt": 2,
                    "error_type": "smtp_error",
                    "error_message": "Connection refused - port 587",
                    "timestamp": "2025-10-28T10:02:35Z",
                    "stack_trace": "..."
                }
            ],
            "backoff_strategy": "exponential",
            "initial_delay_seconds": 5,
            "idempotency_key": "session_abc-123_action_send_email_002",
            "execution_id": "exec_002",
            "persisted_to_db": true,
            "checkpoint_id": "chk_002"
        },
        {
            "queue_id": "q_003",
            "action_id": "process_payment",
            "status": "blocked",
            "added_at": "2025-10-28T10:05:00Z",
            "priority": 3,
            "params_collected": {
                "amount": 5000,
                "payment_method": null,
                "order_id": "ORD-20251028"
            },
            "params_missing": ["payment_method"],
            "blocker_reason": "schema_dependency_not_met",
            "blocker_details": {
                "schema": "profile",
                "key": "payment_method",
                "current_status": "incomplete",
                "required_status": "complete"
            },
            "retry_count": 0,
            "max_retries": 0,
            "idempotency_key": "session_abc-123_action_process_payment_003",
            "persisted_to_db": true,
            "checkpoint_id": "chk_003"
        }
    ],
    
    # Dead Letter Queue
    "dead_letter_queue": [
        {
            "dlq_id": "dlq_001",
            "original_queue_id": "q_999",
            "action_id": "charge_credit_card",
            "action_name": "Charge Credit Card",
            "moved_to_dlq_at": "2025-10-28T09:50:00Z",
            "original_status": "failed",
            "retry_count": 3,
            "final_error": {
                "error_type": "payment_declined",
                "error_code": "insufficient_funds",
                "error_message": "Card declined - insufficient funds",
                "timestamp": "2025-10-28T09:49:55Z",
                "api_response": {
                    "status": 402,
                    "body": {
                        "error": "Card declined",
                        "code": "insufficient_funds",
                        "decline_code": "insufficient_funds"
                    }
                }
            },
            "params_collected": {
                "card_token": "tok_xxxxxxxxxx",
                "amount": 5000,
                "order_id": "ORD-20251028"
            },
            "requires_manual_intervention": true,
            "escalated_to_support": false,
            "escalation_ticket_id": null,
            "idempotency_key": "session_abc-123_action_charge_credit_card_999",
            "context": {
                "session_id": "abc-123",
                "user_id": "user_12345",
                "intent_id": "intent_010",
                "turn_number": 8
            }
        }
    ],
    
    # Queue Metadata
    "queue_metadata": {
        "total_pending": 1,
        "total_collecting_params": 0,
        "total_ready": 0,
        "total_executing": 0,
        "total_retrying": 1,
        "total_blocked": 1,
        "total_completed_today": 15,
        "total_failed_today": 0,
        "total_dead_letter": 1,
        "last_checkpoint_at": "2025-10-28T10:05:30Z",
        "queue_depth": 3,
        "queue_depth_warning_threshold": 10,
        "oldest_pending_item": {
            "queue_id": "q_001",
            "age_seconds": 270,
            "age_warning_threshold_seconds": 300
        },
        "retry_budget_remaining": 8,
        "retry_budget_total": 20
    }
}
```

#### 3.3.4 Queue Operations

**Add to Queue:**
```python
def enqueue_action(
    session_id: str,
    action_id: str,
    params_collected: dict,
    priority: int = 1
) -> str:
    """
    Adds an action to the execution queue.
    
    Steps:
    1. Generate idempotency_key
    2. Check if already in queue (deduplicate)
    3. Validate params
    4. Determine status (pending/collecting_params/blocked)
    5. Persist to database
    6. Return queue_id
    """
```

**Process Queue:**
```python
def process_queue(session_id: str) -> dict:
    """
    Processes all items in the queue.
    
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
```

---

### 3.4 USER DATA SCHEMAS

**Purpose:** Defines the structure and validation rules for real-time user data fetched from brand APIs. Each schema represents a data domain (profile, cart, loyalty, etc.) with keys that have completion logic.

**Why it exists:** Enables dynamic eligibility checking based on actual user data state, separates data structure from code, allows per-brand customization.

#### 3.4.1 Schema Configuration Structure

```python
{
    "schema_id": "profile",
    "schema_name": "User Profile",
    "description": "User profile information from brand's CRM",
    "version": "1.0",
    
    # API Configuration
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
    
    # Caching Strategy
    "refresh_strategy": "on_demand",
    "cache_ttl_seconds": 300,
    "cache_on_error": true,
    "stale_cache_threshold_seconds": 600,
    
    # Schema Keys
    "keys": [
        {
            "key_name": "email",
            "display_name": "Email Address",
            "description": "User's primary email address",
            "data_type": "string",
            "required_for_schema": true,
            
            # Completion Logic
            "completion_logic": {
                "type": "non_empty",
                "validation": "email_format",
                "validation_regex": "^[\\w\\.-]+@[\\w\\.-]+\\.\\w+$"
            },
            
            "default_status": "none",
            "api_field_path": "data.contact.email",
            "fallback_value": null,
            
            # User-facing messages
            "collection_prompt": "What's your email address?",
            "validation_error_message": "Please provide a valid email address",
            "missing_message": "We need your email to proceed"
        },
        {
            "key_name": "phone",
            "display_name": "Phone Number",
            "description": "User's mobile phone number",
            "data_type": "string",
            "required_for_schema": true,
            
            "completion_logic": {
                "type": "non_empty",
                "validation": "e164_phone_format",
                "validation_regex": "^\\+?[1-9]\\d{9,14}$"
            },
            
            "default_status": "none",
            "api_field_path": "data.contact.phone",
            "fallback_value": null,
            
            "collection_prompt": "What's your phone number?",
            "validation_error_message": "Please provide a valid phone number with country code",
            "missing_message": "We need your phone number to continue"
        },
        {
            "key_name": "address",
            "display_name": "Address",
            "description": "User's primary address",
            "data_type": "object",
            "required_for_schema": false,
            
            "completion_logic": {
                "type": "nested_keys_complete",
                "required_nested_keys": ["street", "city", "postal_code", "country"],
                "validation": "address_format"
            },
            
            "default_status": "none",
            "api_field_path": "data.address",
            "fallback_value": null,
            
            "collection_prompt": "What's your address?",
            "validation_error_message": "Please provide a complete address",
            "missing_message": "We need your address for delivery"
        },
        {
            "key_name": "payment_method",
            "display_name": "Payment Method",
            "description": "User's default payment method",
            "data_type": "string",
            "required_for_schema": false,
            
            "completion_logic": {
                "type": "enum",
                "allowed_values": ["credit_card", "debit_card", "upi", "wallet", "net_banking"],
                "validation": "enum_match"
            },
            
            "default_status": "none",
            "api_field_path": "data.payment.default_method",
            "fallback_value": null,
            
            "collection_prompt": "What's your preferred payment method?",
            "validation_error_message": "Please choose a valid payment method",
            "missing_message": "We need to know your payment method"
        },
        {
            "key_name": "kyc_verified",
            "display_name": "KYC Verification",
            "description": "Whether user has completed KYC verification",
            "data_type": "boolean",
            "required_for_schema": false,
            
            "completion_logic": {
                "type": "boolean_true",
                "validation": "boolean"
            },
            
            "default_status": "none",
            "api_field_path": "data.verification.kyc_status",
            "fallback_value": false,
            
            "collection_prompt": "Would you like to complete KYC verification?",
            "validation_error_message": "KYC verification is required",
            "missing_message": "KYC verification is pending"
        },
        {
            "key_name": "age",
            "display_name": "Age",
            "description": "User's age in years",
            "data_type": "number",
            "required_for_schema": false,
            
            "completion_logic": {
                "type": "number_in_range",
                "min": 18,
                "max": 120,
                "validation": "positive_integer"
            },
            
            "default_status": "none",
            "api_field_path": "data.personal.age",
            "fallback_value": null,
            
            "collection_prompt": "What's your age?",
            "validation_error_message": "You must be at least 18 years old",
            "missing_message": "We need to verify your age"
        }
    ],
    
    # Schema-Level Completion
    "schema_completion_logic": {
        "type": "all_required_keys_complete",
        "min_required_keys": 2,
        "completion_percentage_threshold": 80
    },
    
    # Error Handling
    "api_error_handling": {
        "on_timeout": "use_cache",
        "on_404": "treat_as_empty",
        "on_401": "escalate_auth_error",
        "on_500": "retry_with_backoff"
    }
}
```

#### 3.4.2 Complete Brand Schemas Example

```python
brand_schemas = {
    "brand_id": "brand-xyz",
    "brand_name": "XYZ Retail",
    "schemas": [
        {
            # SCHEMA 1: User Profile
            "schema_id": "profile",
            "schema_name": "User Profile",
            "description": "User profile information from brand's CRM",
            "version": "1.0",
            "api_endpoint": "https://api.brand-xyz.com/v1/users/{user_id}/profile",
            "api_method": "GET",
            "api_auth": {
                "type": "bearer_token",
                "token_source": "instance_config"
            },
            "api_timeout_seconds": 10,
            "refresh_strategy": "on_demand",
            "cache_ttl_seconds": 300,
            "keys": [
                {
                    "key_name": "email",
                    "data_type": "string",
                    "required_for_schema": true,
                    "completion_logic": {
                        "type": "non_empty",
                        "validation": "email_format"
                    },
                    "api_field_path": "data.contact.email",
                    "collection_prompt": "What's your email?"
                },
                {
                    "key_name": "phone",
                    "data_type": "string",
                    "required_for_schema": true,
                    "completion_logic": {
                        "type": "non_empty",
                        "validation": "e164_phone_format"
                    },
                    "api_field_path": "data.contact.phone",
                    "collection_prompt": "What's your phone number?"
                },
                {
                    "key_name": "payment_method",
                    "data_type": "string",
                    "required_for_schema": false,
                    "completion_logic": {
                        "type": "enum",
                        "allowed_values": ["credit_card", "debit_card", "upi", "wallet"]
                    },
                    "api_field_path": "data.payment.default_method"
                }
            ],
            "schema_completion_logic": {
                "type": "all_required_keys_complete"
            }
        },
        {
            # SCHEMA 2: Shopping Cart
            "schema_id": "cart",
            "schema_name": "Shopping Cart",
            "description": "User's shopping cart from e-commerce platform",
            "version": "1.0",
            "api_endpoint": "https://api.brand-xyz.com/v1/users/{user_id}/cart",
            "api_method": "GET",
            "api_auth": {
                "type": "api_key",
                "header_name": "X-API-Key",
                "token_source": "instance_config"
            },
            "api_timeout_seconds": 5,
            "refresh_strategy": "on_demand",
            "cache_ttl_seconds": 60,
            "keys": [
                {
                    "key_name": "items",
                    "data_type": "array",
                    "required_for_schema": true,
                    "completion_logic": {
                        "type": "array_not_empty",
                        "min_length": 1
                    },
                    "api_field_path": "data.cart.items"
                },
                {
                    "key_name": "total_amount",
                    "data_type": "number",
                    "required_for_schema": true,
                    "completion_logic": {
                        "type": "number_greater_than",
                        "threshold": 0
                    },
                    "api_field_path": "data.cart.total"
                },
                {
                    "key_name": "discount_code",
                    "data_type": "string",
                    "required_for_schema": false,
                    "completion_logic": {
                        "type": "non_empty"
                    },
                    "api_field_path": "data.cart.discount_code"
                }
            ],
            "schema_completion_logic": {
                "type": "all_required_keys_complete"
            }
        },
        {
            # SCHEMA 3: Loyalty Program
            "schema_id": "loyalty",
            "schema_name": "Loyalty Program",
            "description": "User's loyalty program data",
            "version": "1.0",
            "api_endpoint": "https://api.brand-xyz.com/v1/users/{user_id}/loyalty",
            "api_method": "GET",
            "api_auth": {
                "type": "bearer_token",
                "token_source": "instance_config"
            },
            "api_timeout_seconds": 10,
            "refresh_strategy": "cached_1hr",
            "cache_ttl_seconds": 3600,
            "keys": [
                {
                    "key_name": "points_balance",
                    "data_type": "number",
                    "required_for_schema": true,
                    "completion_logic": {
                        "type": "number_exists",
                        "validation": "non_negative_number"
                    },
                    "api_field_path": "data.loyalty.points"
                },
                {
                    "key_name": "tier",
                    "data_type": "string",
                    "required_for_schema": false,
                    "completion_logic": {
                        "type": "enum",
                        "allowed_values": ["bronze", "silver", "gold", "platinum"]
                    },
                    "api_field_path": "data.loyalty.tier"
                }
            ],
            "schema_completion_logic": {
                "type": "all_required_keys_complete"
            }
        },
        {
            # SCHEMA 4: Order History
            "schema_id": "order_history",
            "schema_name": "Order History",
            "description": "User's past orders",
            "version": "1.0",
            "api_endpoint": "https://api.brand-xyz.com/v1/users/{user_id}/orders",
            "api_method": "GET",
            "api_auth": {
                "type": "bearer_token",
                "token_source": "instance_config"
            },
            "api_timeout_seconds": 15,
            "refresh_strategy": "cached_5min",
            "cache_ttl_seconds": 300,
            "keys": [
                {
                    "key_name": "total_orders",
                    "data_type": "number",
                    "required_for_schema": true,
                    "completion_logic": {
                        "type": "number_exists"
                    },
                    "api_field_path": "data.orders_count"
                },
                {
                    "key_name": "last_order_date",
                    "data_type": "string",
                    "required_for_schema": false,
                    "completion_logic": {
                        "type": "date_valid",
                        "validation": "iso8601_date"
                    },
                    "api_field_path": "data.last_order.date"
                },
                {
                    "key_name": "lifetime_value",
                    "data_type": "number",
                    "required_for_schema": false,
                    "completion_logic": {
                        "type": "number_greater_than_or_equal",
                        "threshold": 0
                    },
                    "api_field_path": "data.lifetime_value"
                }
            ],
            "schema_completion_logic": {
                "type": "all_required_keys_complete"
            }
        }
    ]
}
```

#### 3.4.3 Key Completion Logic Types

| Type | Description | Example |
|------|-------------|---------|
| `non_empty` | Value exists and is not empty string/null | email: "user@example.com" → complete |
| `enum` | Value matches one of allowed_values | payment_method: "credit_card" → complete |
| `boolean_true` | Value is exactly `true` | kyc_verified: true → complete |
| `number_exists` | Value is a valid number | points_balance: 1500 → complete |
| `number_greater_than` | Value > threshold | total_amount: 2500 (threshold: 0) → complete |
| `number_in_range` | min ≤ value ≤ max | age: 25 (min: 18, max: 120) → complete |
| `array_not_empty` | Array has at least min_length items | items: [{...}, {...}] → complete |
| `nested_keys_complete` | All required nested keys exist and non-empty | address with street, city, postal_code → complete |
| `date_valid` | Valid date in specified format | last_order_date: "2025-10-15" → complete |
| `regex_match` | Value matches regex pattern | Custom validation |

---

### 3.5 SCHEMA STATE TRACKER

**Purpose:** Tracks the computed status of each schema key for each user/session. Fetches data from brand APIs, applies completion logic, caches results.

**Why it exists:** Provides real-time eligibility checking, reduces API calls through caching, separates data fetching from business logic.

#### 3.5.1 Schema State Structure

```python
user_schema_state = {
    "session_id": "abc-123",
    "user_id": "user_12345",
    "brand_id": "brand-xyz",
    "instance_id": "retail-store-001",
    
    "schemas": {
        "profile": {
            "schema_id": "profile",
            "schema_version": "1.0",
            
            # Fetch Metadata
            "last_fetched_at": "2025-10-28T10:05:00Z",
            "cache_expires_at": "2025-10-28T10:10:00Z",
            "next_refresh_at": "2025-10-28T10:10:00Z",
            "api_response_status": "success",
            "api_response_time_ms": 245,
            "api_error": null,
            
            # Keys
            "keys": {
                "email": {
                    "value": "nikunj@example.com",
                    "status": "complete",
                    "computed_at": "2025-10-28T10:05:00Z",
                    "completion_logic_result": {
                        "non_empty": true,
                        "email_format": true
                    },
                    "validation_passed": true,
                    "validation_errors": []
                },
                "phone": {
                    "value": "+919876543210",
                    "status": "complete",
                    "computed_at": "2025-10-28T10:05:00Z",
                    "completion_logic_result": {
                        "non_empty": true,
                        "e164_phone_format": true
                    },
                    "validation_passed": true,
                    "validation_errors": []
                },
                "address": {
                    "value": {
                        "street": "123 Main St",
                        "city": "Mumbai",
                        "postal_code": null,
                        "country": "India"
                    },
                    "status": "incomplete",
                    "computed_at": "2025-10-28T10:05:00Z",
                    "completion_logic_result": {
                        "nested_keys_complete": false,
                        "missing_keys": ["postal_code"],
                        "present_keys": ["street", "city", "country"]
                    },
                    "validation_passed": false,
                    "validation_errors": ["postal_code is missing"]
                },
                "payment_method": {
                    "value": "credit_card",
                    "status": "complete",
                    "computed_at": "2025-10-28T10:05:00Z",
                    "completion_logic_result": {
                        "enum_match": true,
                        "matched_value": "credit_card"
                    },
                    "validation_passed": true,
                    "validation_errors": []
                },
                "kyc_verified": {
                    "value": false,
                    "status": "incomplete",
                    "computed_at": "2025-10-28T10:05:00Z",
                    "completion_logic_result": {
                        "boolean_true": false
                    },
                    "validation_passed": true,
                    "validation_errors": []
                },
                "age": {
                    "value": 28,
                    "status": "complete",
                    "computed_at": "2025-10-28T10:05:00Z",
                    "completion_logic_result": {
                        "number_in_range": true,
                        "min_check": true,
                        "max_check": true
                    },
                    "validation_passed": true,
                    "validation_errors": []
                }
            },
            
            # Schema-Level Status
            "schema_status": "incomplete",
            "schema_completion_percentage": 67,
            "required_keys_complete": 2,
            "required_keys_total": 3,
            "optional_keys_complete": 2,
            "optional_keys_total": 3
        },
        
        "cart": {
            "schema_id": "cart",
            "schema_version": "1.0",
            "last_fetched_at": "2025-10-28T10:06:00Z",
            "cache_expires_at": "2025-10-28T10:07:00Z",
            "api_response_status": "success",
            "api_response_time_ms": 150,
            "api_error": null,
            
            "keys": {
                "items": {
                    "value": [
                        {"product_id": "p123", "name": "T-Shirt", "quantity": 2, "price": 500},
                        {"product_id": "p456", "name": "Jeans", "quantity": 1, "price": 1500}
                    ],
                    "status": "complete",
                    "computed_at": "2025-10-28T10:06:00Z",
                    "completion_logic_result": {
                        "array_not_empty": true,
                        "array_length": 2,
                        "min_length_check": true
                    },
                    "validation_passed": true,
                    "validation_errors": []
                },
                "total_amount": {
                    "value": 2500,
                    "status": "complete",
                    "computed_at": "2025-10-28T10:06:00Z",
                    "completion_logic_result": {
                        "number_greater_than": true,
                        "threshold": 0,
                        "actual_value": 2500
                    },
                    "validation_passed": true,
                    "validation_errors": []
                },
                "discount_code": {
                    "value": null,
                    "status": "none",
                    "computed_at": "2025-10-28T10:06:00Z",
                    "completion_logic_result": {
                        "non_empty": false
                    },
                    "validation_passed": true,
                    "validation_errors": []
                }
            },
            
            "schema_status": "complete",
            "schema_completion_percentage": 100,
            "required_keys_complete": 2,
            "required_keys_total": 2,
            "optional_keys_complete": 0,
            "optional_keys_total": 1
        },
        
        "loyalty": {
            "schema_id": "loyalty",
            "schema_version": "1.0",
            "last_fetched_at": "2025-10-28T09:30:00Z",
            "cache_expires_at": "2025-10-28T10:30:00Z",
            "api_response_status": "success",
            "api_response_time_ms": 180,
            "api_error": null,
            
            "keys": {
                "points_balance": {
                    "value": 1500,
                    "status": "complete",
                    "computed_at": "2025-10-28T09:30:00Z",
                    "completion_logic_result": {
                        "number_exists": true,
                        "non_negative_number": true
                    },
                    "validation_passed": true,
                    "validation_errors": []
                },
                "tier": {
                    "value": "gold",
                    "status": "complete",
                    "computed_at": "2025-10-28T09:30:00Z",
                    "completion_logic_result": {
                        "enum_match": true,
                        "matched_value": "gold",
                        "allowed_values": ["bronze", "silver", "gold", "platinum"]
                    },
                    "validation_passed": true,
                    "validation_errors": []
                }
            },
            
            "schema_status": "complete",
            "schema_completion_percentage": 100,
            "required_keys_complete": 1,
            "required_keys_total": 1,
            "optional_keys_complete": 1,
            "optional_keys_total": 1
        }
    },
    
    # Action Eligibility Cache
    "action_eligibility_cache": {
        "process_payment": {
            "eligible": true,
            "computed_at": "2025-10-28T10:06:30Z",
            "cache_expires_at": "2025-10-28T10:11:30Z",
            "reasons": {
                "user_tier_check": "passed",
                "auth_check": "passed",
                "schema_checks": {
                    "profile.email": "complete",
                    "profile.phone": "complete",
                    "profile.payment_method": "complete",
                    "cart.items": "complete",
                    "cart.total_amount": "complete"
                },
                "blocker_checks": {
                    "insufficient_balance": false,
                    "payment_method_invalid": false
                },
                "dependency_checks": {
                    "create_profile": "completed",
                    "add_to_cart": "completed"
                },
                "opposite_actions": []
            },
            "blocking_reasons": []
        },
        "update_kyc": {
            "eligible": false,
            "computed_at": "2025-10-28T10:05:30Z",
            "cache_expires_at": "2025-10-28T10:10:30Z",
            "reasons": {
                "user_tier_check": "passed",
                "auth_check": "passed",
                "schema_checks": {
                    "profile.kyc_verified": "incomplete"
                },
                "blocker_checks": {
                    "kyc_already_verified": false
                },
                "dependency_checks": {
                    "create_profile": "completed"
                },
                "opposite_actions": []
            },
            "blocking_reasons": [
                "schema_dependency_not_met: profile.kyc_verified is incomplete"
            ]
        }
    },
    
    # State Metadata
    "state_metadata": {
        "created_at": "2025-10-28T09:30:00Z",
        "last_updated_at": "2025-10-28T10:06:30Z",
        "total_api_calls_today": 15,
        "api_call_budget_daily": 1000,
        "cache_hit_rate_today": 0.72,
        "average_api_latency_ms": 195
    }
}
```

#### 3.5.2 Schema State Operations

**Fetch Schema Data:**
```python
async def fetch_schema_data(
    user_id: str,
    schema_id: str,
    force_refresh: bool = False
) -> dict:
    """
    Fetches user data for a schema.
    
    Steps:
    1. Check cache validity
    2. If valid and not force_refresh → return cached
    3. If invalid or force_refresh:
       a. Call brand API
       b. Parse response using api_field_path
       c. Apply completion_logic to each key
       d. Compute key statuses
       e. Compute schema status
       f. Update cache
    4. Return schema state
    """
```

**Compute Key Status:**
```python
def compute_key_status(
    key_config: dict,
    key_value: any
) -> dict:
    """
    Applies completion_logic to determine key status.
    
    Returns:
    {
        "status": "none" | "incomplete" | "complete",
        "completion_logic_result": {...},
        "validation_passed": bool,
        "validation_errors": [...]
    }
    """
```

**Check Action Eligibility:**
```python
def check_action_eligibility(
    session_id: str,
    action_id: str,
    use_cache: bool = True
) -> dict:
    """
    Determines if action is eligible to execute.
    
    Checks:
    1. User tier
    2. Auth requirements
    3. Schema dependencies (key statuses)
    4. Blockers
    5. Action dependencies
    6. Opposite actions
    
    Returns:
    {
        "eligible": bool,
        "reasons": {...},
        "blocking_reasons": [...]
    }
    """
```

**Invalidate Cache:**
```python
def invalidate_schema_cache(
    session_id: str,
    schema_id: str = None
) -> bool:
    """
    Invalidates cached schema data.
    
    If schema_id is None, invalidates ALL schemas.
    Next fetch will call API.
    """
```

---

### 3.6 ACTIVE TASK TRACKER

**Purpose:** Tracks the current task being worked on, including param collection progress and task status.

**Why it exists:** Provides focused context for next turn, enables resumable tasks, supports task progress tracking.

#### 3.6.1 Active Task Structure

```python
active_task = {
    "task_id": "task_001",
    "task_name": "create_profile",
    "task_display_name": "Create Your Profile",
    "task_category": "onboarding",
    
    # Status
    "status": "collecting_params",
    "started_at": "2025-10-28T10:01:00Z",
    "last_updated_at": "2025-10-28T10:02:30Z",
    "expected_completion_at": "2025-10-28T10:05:00Z",
    
    # Parameters
    "params_required": ["name", "email", "phone"],
    "params_optional": ["address", "preferences"],
    "params_collected": {
        "name": "Nikunj",
        "email": "nikunj@example.com",
        "phone": null
    },
    "params_missing": ["phone"],
    "params_validation_errors": {},
    
    # Collection Progress
    "next_param_to_collect": "phone",
    "collection_attempts": {
        "phone": {
            "attempts": 1,
            "last_attempt_at": "2025-10-28T10:02:15Z",
            "validation_failures": 0
        }
    },
    "total_collection_attempts": 1,
    "max_collection_attempts": 5,
    
    # Task Context
    "related_intent_id": "intent_002",
    "related_queue_id": "q_001",
    "workflow_id": "onboarding_flow",
    "workflow_step": 1,
    
    # Progress Tracking
    "progress_percentage": 67,
    "steps_completed": 2,
    "steps_total": 3,
    
    # User Communication
    "last_user_message": "My name is Nikunj and email is nikunj@example.com",
    "last_bot_message": "Got it! What's your phone number?",
    
    # Metadata
    "session_id": "abc-123",
    "user_id": "user_12345",
    "created_at": "2025-10-28T10:01:00Z",
    "updated_at": "2025-10-28T10:02:30Z"
}
```

#### 3.6.2 Task Status Values

| Status | Description | User Experience |
|--------|-------------|-----------------|
| `collecting_params` | Asking user for required params | "What's your phone number?" |
| `validating` | Validating collected params | "Checking your information..." |
| `executing` | Executing the action | "Creating your profile..." |
| `waiting_ack` | Waiting for user confirmation | "Profile created. Is this correct?" |
| `completed` | Task successfully completed | "Your profile is ready!" |
| `failed` | Task failed (exhausted retries) | "Sorry, we couldn't complete this" |
| `blocked` | Task blocked by dependency | "We need X before we can proceed" |
| `cancelled` | User cancelled the task | "Okay, cancelled" |
| `paused` | Task paused (resume later) | "I've paused this. Say 'continue' to resume" |

#### 3.6.3 Active Task Operations

**Create Active Task:**
```python
def create_active_task(
    session_id: str,
    action_id: str,
    params_collected: dict
) -> dict:
    """
    Creates a new active task.
    
    Steps:
    1. Load action config
    2. Determine params_missing
    3. Set status (collecting_params or executing)
    4. Store in sessions.active_task_name/status
    5. Return task object
    """
```

**Update Task Progress:**
```python
def update_task_progress(
    session_id: str,
    params_collected: dict = None,
    status: str = None
) -> dict:
    """
    Updates active task with new params or status.
    
    Returns updated task object.
    """
```

**Clear Active Task:**
```python
def clear_active_task(
    session_id: str,
    reason: str
) -> bool:
    """
    Clears active task (on completion, cancellation, or failure).
    
    Stores in task history for analysis.
    """
```

---

### 3.7 NEXT NARRATIVE GENERATOR

**Purpose:** Creates guidance for the LLM responder on what to communicate to the user. Separates "what to say" (content) from "how to say it" (LLM's natural language generation).

**Why it exists:** Ensures important information is communicated, gives LLM creative freedom in phrasing, maintains conversation focus.

#### 3.7.1 Next Narrative Structure

```python
next_narrative = {
    # Core Communication Requirements
    "must_communicate": [
        "Ask for phone number to complete profile creation",
        "Mention that profile is 80% complete",
        "Emphasize that phone number is required for account security"
    ],
    
    "optional_communicate": [
        "Offer to skip phone number if user prefers email-only",
        "Explain benefits of providing phone number (2FA, order updates)",
        "Mention that we'll never share phone number with third parties"
    ],
    
    # Tone & Style
    "tone": "friendly",
    "urgency": "medium",
    "formality": "casual",
    
    # Action Status Updates
    "action_in_progress": null,
    "estimated_wait_time_seconds": null,
    "show_progress_indicator": false,
    
    # Contextual Information
    "user_name": "Nikunj",
    "conversation_stage": "onboarding",
    "turn_number": 3,
    
    # Error Recovery
    "previous_error": null,
    "retry_count": 0,
    "clarification_needed": false,
    
    # Workflow Guidance
    "workflow_id": "onboarding_flow",
    "current_step": "collect_phone",
    "next_step_preview": "verify_phone",
    "steps_remaining": 2,
    
    # Additional Context
    "related_schemas": {
        "profile": {
            "completion_percentage": 67,
            "missing_keys": ["phone"]
        }
    },
    
    # Metadata
    "generated_at": "2025-10-28T10:02:30Z",
    "valid_until": "2025-10-28T10:03:30Z",
    "session_id": "abc-123"
}
```

#### 3.7.2 Complete Next Narrative Examples

**Example 1: Parameter Collection**
```python
{
    "must_communicate": [
        "Ask for user's phone number",
        "Explain it's needed for profile completion"
    ],
    "optional_communicate": [
        "Mention that phone is used for order updates",
        "Assure privacy protection"
    ],
    "tone": "friendly",
    "urgency": "medium",
    "user_name": "Nikunj",
    "conversation_stage": "param_collection",
    "action_in_progress": null,
    "previous_error": null
}
```

**Example LLM Response:**
> "Thanks Nikunj! To complete your profile, I'll need your phone number. We use it for order updates and account security. Your privacy is important to us - we'll never share it with third parties. What's your phone number?"

---

**Example 2: Long-Running Action**
```python
{
    "must_communicate": [
        "Inform user that payment is being processed",
        "Ask user to wait"
    ],
    "optional_communicate": [
        "Mention typical processing time is 10-15 seconds",
        "Reassure that the page is secure"
    ],
    "tone": "reassuring",
    "urgency": "low",
    "action_in_progress": "process_payment",
    "estimated_wait_time_seconds": 12,
    "show_progress_indicator": true,
    "user_name": "Nikunj"
}
```

**Example LLM Response:**
> "Nikunj, I'm processing your payment now. This usually takes about 10-15 seconds. Please don't refresh the page - I'll let you know as soon as it's done! 💳"

---

**Example 3: Blocker Encountered**
```python
{
    "must_communicate": [
        "Explain that KYC verification is required before payment",
        "Offer to start KYC process"
    ],
    "optional_communicate": [
        "Explain why KYC is needed (regulatory requirement)",
        "Mention KYC typically takes 5 minutes"
    ],
    "tone": "helpful",
    "urgency": "medium",
    "action_in_progress": null,
    "previous_error": {
        "error_type": "blocked",
        "blocker_reason": "kyc_not_verified"
    },
    "user_name": "Nikunj"
}
```

**Example LLM Response:**
> "Nikunj, before we can process your payment, we need to verify your identity (KYC). It's a regulatory requirement that helps keep your account secure. The verification usually takes about 5 minutes. Would you like to start it now?"

---

**Example 4: Task Completion**
```python
{
    "must_communicate": [
        "Confirm profile was created successfully",
        "Welcome user to the platform"
    ],
    "optional_communicate": [
        "Suggest next steps (browse products, set preferences)",
        "Mention support availability"
    ],
    "tone": "celebratory",
    "urgency": "low",
    "action_in_progress": null,
    "workflow_id": "onboarding_flow",
    "current_step": "completed",
    "user_name": "Nikunj"
}
```

**Example LLM Response:**
> "Awesome! Your profile is all set up, Nikunj! 🎉 Welcome to XYZ Retail. You can now browse our products, save favorites, and make purchases. If you need any help, I'm here for you!"

---

**Example 5: Error Recovery**
```python
{
    "must_communicate": [
        "Apologize for the error",
        "Explain what happened (email service timeout)",
        "Inform user we're retrying"
    ],
    "optional_communicate": [
        "Mention this is temporary",
        "Offer alternative (skip email for now)"
    ],
    "tone": "apologetic",
    "urgency": "medium",
    "action_in_progress": "send_email",
    "previous_error": {
        "error_type": "timeout",
        "retry_count": 1
    },
    "retry_count": 1,
    "user_name": "Nikunj"
}
```

**Example LLM Response:**
> "Oops, Nikunj - I had a small hiccup sending your welcome email (our email service timed out). Don't worry, I'm trying again! This is usually temporary. If you'd like, we can skip the email for now and I'll send it later?"

---

#### 3.7.3 Next Narrative Operations

**Generate Narrative:**
```python
def generate_next_narrative(
    session_id: str,
    active_task: dict,
    action_queue: dict,
    schema_state: dict,
    context: dict
) -> dict:
    """
    Generates next narrative based on current state.
    
    Logic:
    1. If active_task exists:
       - If collecting params → narrative for param collection
       - If executing → narrative for wait/progress
       - If blocked → narrative for blocker explanation
    
    2. If no active task but queue has items:
       - Narrative for starting next action
    
    3. If queue empty:
       - Narrative for "anything else?" or closing
    
    Returns next_narrative dict
    """
```

**Validate Narrative:**
```python
def validate_narrative(narrative: dict) -> bool:
    """
    Ensures narrative has required fields.
    
    Required:
    - must_communicate (non-empty list)
    - tone
    """
```

---

### 3.8 WORKFLOW ENGINE

**Purpose:** Manages multi-step workflows where actions are executed in sequence with dependencies.

**Why it exists:** Enables complex business processes (onboarding, checkout) that require multiple coordinated actions.

#### 3.8.1 Workflow Configuration Structure

```python
{
    "workflow_id": "onboarding_flow",
    "workflow_name": "User Onboarding",
    "description": "Complete user onboarding process from signup to first login",
    "version": "1.0",
    "category": "user_lifecycle",
    
    # Workflow Steps
    "steps": [
        {
            "sequence_id": 1,
            "step_name": "Create Profile",
            "action_id": "create_profile",
            "required": true,
            "timeout_seconds": 60,
            "retry_on_failure": true,
            "max_retries": 3,
            "on_success": "continue",
            "on_failure": "abort",
            "on_skip": null
        },
        {
            "sequence_id": 2,
            "step_name": "Verify Email",
            "action_id": "send_verification_email",
            "required": true,
            "timeout_seconds": 30,
            "retry_on_failure": true,
            "max_retries": 5,
            "on_success": "continue",
            "on_failure": "retry",
            "on_skip": null,
            "depends_on": [1]
        },
        {
            "sequence_id": 3,
            "step_name": "Set Preferences",
            "action_id": "set_user_preferences",
            "required": false,
            "timeout_seconds": 45,
            "retry_on_failure": false,
            "on_success": "continue",
            "on_failure": "skip",
            "on_skip": "continue",
            "depends_on": [1]
        },
        {
            "sequence_id": 4,
            "step_name": "Welcome Email",
            "action_id": "send_welcome_email",
            "required": false,
            "timeout_seconds": 30,
            "retry_on_failure": true,
            "max_retries": 3,
            "on_success": "complete",
            "on_failure": "continue",
            "on_skip": "complete",
            "depends_on": [1, 2]
        }
    ],
    
    # Workflow Branching
    "branching_logic": {
        "step_3_condition": {
            "if": "user_tier == 'premium'",
            "then": "execute",
            "else": "skip"
        }
    },
    
    # Workflow Metadata
    "estimated_duration_seconds": 180,
    "success_criteria": {
        "required_steps_completed": [1, 2],
        "min_steps_completed": 2
    },
    "created_at": "2025-10-01T00:00:00Z",
    "updated_at": "2025-10-15T00:00:00Z",
    "is_active": true
}
```

#### 3.8.2 Workflow State Tracker

```python
workflow_state = {
    "workflow_instance_id": "wf_inst_001",
    "workflow_id": "onboarding_flow",
    "session_id": "abc-123",
    "user_id": "user_12345",
    
    # Status
    "status": "in_progress",
    "started_at": "2025-10-28T10:01:00Z",
    "completed_at": null,
    "current_step": 2,
    
    # Step Execution History
    "steps_executed": [
        {
            "sequence_id": 1,
            "action_id": "create_profile",
            "status": "completed",
            "started_at": "2025-10-28T10:01:00Z",
            "completed_at": "2025-10-28T10:01:05Z",
            "execution_id": "exec_001",
            "result": "success",
            "error": null
        },
        {
            "sequence_id": 2,
            "action_id": "send_verification_email",
            "status": "in_progress",
            "started_at": "2025-10-28T10:01:10Z",
            "completed_at": null,
            "execution_id": "exec_002",
            "result": null,
            "error": null
        }
    ],
    
    # Progress
    "progress_percentage": 50,
    "steps_completed": 1,
    "steps_total": 4,
    "steps_remaining": 3,
    
    # Metadata
    "created_at": "2025-10-28T10:01:00Z",
    "updated_at": "2025-10-28T10:01:10Z"
}
```

#### 3.8.3 Complete Workflow Examples

**Workflow 1: Onboarding**
```python
{
    "workflow_id": "onboarding_flow",
    "workflow_name": "User Onboarding",
    "steps": [
        {
            "sequence_id": 1,
            "action_id": "create_profile",
            "required": true,
            "on_success": "continue",
            "on_failure": "abort"
        },
        {
            "sequence_id": 2,
            "action_id": "send_verification_email",
            "required": true,
            "depends_on": [1],
            "on_success": "continue",
            "on_failure": "retry"
        },
        {
            "sequence_id": 3,
            "action_id": "set_user_preferences",
            "required": false,
            "depends_on": [1],
            "on_success": "continue",
            "on_failure": "skip"
        }
    ]
}
```

**Workflow 2: Checkout**
```python
{
    "workflow_id": "checkout_flow",
    "workflow_name": "Purchase Checkout",
    "steps": [
        {
            "sequence_id": 1,
            "action_id": "validate_cart",
            "required": true,
            "on_success": "continue",
            "on_failure": "abort"
        },
        {
            "sequence_id": 2,
            "action_id": "apply_discounts",
            "required": false,
            "depends_on": [1],
            "on_success": "continue",
            "on_failure": "skip"
        },
        {
            "sequence_id": 3,
            "action_id": "process_payment",
            "required": true,
            "depends_on": [1],
            "on_success": "continue",
            "on_failure": "abort"
        },
        {
            "sequence_id": 4,
            "action_id": "create_order",
            "required": true,
            "depends_on": [3],
            "on_success": "continue",
            "on_failure": "rollback"
        },
        {
            "sequence_id": 5,
            "action_id": "send_confirmation_email",
            "required": false,
            "depends_on": [4],
            "on_success": "complete",
            "on_failure": "continue"
        }
    ]
}
```

---

### 3.9 ACTION EXECUTION LOG

**Purpose:** Comprehensive audit trail of all action executions with results, timing, and error details.

**Why it exists:** Enables debugging, analytics, compliance auditing, performance monitoring.

#### 3.9.1 Execution Log Entry Structure

```python
{
    "execution_id": "exec_001",
    "action_id": "create_profile",
    "action_name": "Create User Profile",
    
    # Execution Context
    "session_id": "abc-123",
    "user_id": "user_12345",
    "instance_id": "retail-store-001",
    "brand_id": "brand-xyz",
    "intent_id": "intent_002",
    "queue_id": "q_001",
    "workflow_instance_id": null,
    
    # Timing
    "started_at": "2025-10-28T10:01:00.123Z",
    "completed_at": "2025-10-28T10:01:05.456Z",
    "duration_ms": 5333,
    "timeout_seconds": 30,
    "timed_out": false,
    
    # Status
    "status": "success",
    "retry_attempt": 0,
    "final_retry": false,
    
    # Input
    "params_used": {
        "name": "Nikunj",
        "email": "nikunj@example.com",
        "phone": "+919876543210"
    },
    "params_validated": true,
    "validation_errors": [],
    
    # Output
    "result": {
        "user_id": "user_12345",
        "profile_id": "prof_67890",
        "status": "active"
    },
    "api_response_status": 201,
    "api_response_body": {
        "success": true,
        "data": {
            "user_id": "user_12345",
            "profile_id": "prof_67890"
        }
    },
    
    # Error Details (if failed)
    "error": null,
    "error_type": null,
    "error_message": null,
    "error_code": null,
    "stack_trace": null,
    
    # Rollback
    "rollback_performed": false,
    "rollback_action_id": null,
    "rollback_execution_id": null,
    
    # Acknowledgement
    "requires_acknowledgement": true,
    "acknowledged": true,
    "acknowledged_at": "2025-10-28T10:01:10Z",
    "acknowledgement_timeout": false,
    
    # Idempotency
    "idempotency_key": "session_abc-123_action_create_profile_001",
    "duplicate_execution": false,
    "original_execution_id": null,
    
    # Metadata
    "trace_id": "trace_xyz_789",
    "request_id": "req_abc_123",
    "created_at": "2025-10-28T10:01:05.456Z"
}
```

---

### 3.10 DEAD LETTER QUEUE

**Purpose:** Stores actions that failed permanently (exhausted retries) and require manual intervention.

**Why it exists:** Prevents silent failures, enables error analysis, provides escalation mechanism.

#### 3.10.1 Dead Letter Queue Entry Structure

```python
{
    "dlq_id": "dlq_001",
    "original_queue_id": "q_002",
    
    # Action Details
    "action_id": "charge_credit_card",
    "action_name": "Charge Credit Card",
    "action_category": "financial",
    
    # Context
    "session_id": "abc-123",
    "user_id": "user_12345",
    "instance_id": "retail-store-001",
    "brand_id": "brand-xyz",
    "intent_id": "intent_010",
    "turn_number": 8,
    
    # Timing
    "moved_to_dlq_at": "2025-10-28T09:50:00Z",
    "original_added_at": "2025-10-28T09:45:00Z",
    "time_in_queue_seconds": 300,
    
    # Failure Details
    "original_status": "failed",
    "retry_count": 3,
    "max_retries": 3,
    "final_error": {
        "error_type": "payment_declined",
        "error_code": "insufficient_funds",
        "error_message": "Card declined - insufficient funds",
        "timestamp": "2025-10-28T09:49:55Z",
        "retry_errors_count": 3,
        "api_response": {
            "status": 402,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": {
                "error": "Card declined",
                "code": "insufficient_funds",
                "decline_code": "insufficient_funds",
                "message": "Your card has insufficient funds."
            }
        }
    },
    
    # Parameters
    "params_collected": {
        "card_token": "tok_xxxxxxxxxx",
        "amount": 5000,
        "order_id": "ORD-20251028",
        "currency": "INR"
    },
    
    # Intervention
    "requires_manual_intervention": true,
    "intervention_type": "user_action_required",
    "escalated_to_support": false,
    "escalation_ticket_id": null,
    "escalated_at": null,
    "resolved": false,
    "resolved_at": null,
    "resolution_notes": null,
    
    # User Communication
    "user_notified": true,
    "user_notification_sent_at": "2025-10-28T09:50:05Z",
    "user_notification_message": "We couldn't process your payment. Please update your payment method.",
    
    # Retry History
    "retry_history": [
        {
            "attempt": 1,
            "timestamp": "2025-10-28T09:46:00Z",
            "error_type": "payment_declined",
            "error_code": "insufficient_funds",
            "duration_ms": 1234
        },
        {
            "attempt": 2,
            "timestamp": "2025-10-28T09:47:30Z",
            "error_type": "payment_declined",
            "error_code": "insufficient_funds",
            "duration_ms": 1145
        },
        {
            "attempt": 3,
            "timestamp": "2025-10-28T09:49:55Z",
            "error_type": "payment_declined",
            "error_code": "insufficient_funds",
            "duration_ms": 1201
        }
    ],
    
    # Idempotency
    "idempotency_key": "session_abc-123_action_charge_credit_card_002",
    
    # Metadata
    "created_at": "2025-10-28T09:50:00Z",
    "updated_at": "2025-10-28T09:50:05Z"
}
```

#### 3.10.2 Dead Letter Queue Operations

**Move to DLQ:**
```python
def move_to_dead_letter_queue(
    queue_id: str,
    final_error: dict
) -> str:
    """
    Moves a failed action to dead letter queue.
    
    Steps:
    1. Remove from main queue
    2. Create DLQ entry with full context
    3. Determine intervention_type
    4. Notify user (if applicable)
    5. Create alert/ticket (if escalation needed)
    6. Return dlq_id
    """
```

**Retry from DLQ:**
```python
def retry_from_dead_letter_queue(
    dlq_id: str,
    override_params: dict = None
) -> str:
    """
    Manually retries an action from DLQ.
    
    Used when:
    - User fixes issue (updates payment method)
    - System issue resolved
    - Manual override needed
    
    Returns new queue_id
    """
```

**Resolve DLQ Entry:**
```python
def resolve_dlq_entry(
    dlq_id: str,
    resolution_notes: str
) -> bool:
    """
    Marks DLQ entry as resolved.
    
    Used when:
    - Action successfully retried
    - Issue fixed by alternate means
    - User declined to retry
    """
```

---

## 4. PROCESSING FLOW

### 4.1 Complete Turn Processing Flow

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
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 2. BRAIN RECEIVES INTENTS                                       │
│    Input: List of intents with entities                         │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 3. LOG TO INTENT LEDGER                                         │
│    For each intent:                                              │
│    - Generate intent_id                                          │
│    - Log: type, confidence, turn, timestamp, entities           │
│    - Set initial status = "new"                                  │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 4. FETCH SCHEMA STATE                                           │
│    For each required schema:                                     │
│    - Check cache validity (TTL)                                  │
│    - If expired or force_refresh:                               │
│      a. Call brand API with auth                                │
│      b. Parse response using api_field_path                     │
│      c. Apply completion_logic to each key                      │
│      d. Compute key status (none/incomplete/complete)           │
│      e. Compute schema status                                   │
│      f. Update cache with new expiry                            │
│    - If cached and valid:                                       │
│      a. Return cached state                                     │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 5. MAP INTENTS TO ACTIONS                                       │
│    For each intent:                                              │
│    - Lookup action from instance config                         │
│    - Extract params from entities                               │
│    - Load action config (eligibility, retry policy, etc.)       │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 6. CHECK ACTION ELIGIBILITY                                     │
│    For each action:                                              │
│    a. User Tier Check                                           │
│       - Compare user_tier with eligibility.user_tier            │
│    b. Auth Check                                                │
│       - If requires_auth, verify user authenticated             │
│    c. Schema Dependency Check (NEW - KEY FEATURE)               │
│       - For each schema in schema_dependencies:                 │
│         * For each required key:                                │
│           - Check if key status == "complete"                   │
│           - If not complete → NOT ELIGIBLE                      │
│    d. Blocker Check                                             │
│       - Check if any blockers are active                        │
│    e. Action Dependency Check                                   │
│       - For each dependency action:                             │
│         * Check if completed in execution log                   │
│         * If not completed → NOT ELIGIBLE                       │
│    f. Opposite Action Check                                     │
│       - Check if any opposite actions are in queue/executing    │
│       * If yes → NOT ELIGIBLE                                   │
│                                                                  │
│    If ALL checks pass → ELIGIBLE                                │
│    If ANY check fails → NOT ELIGIBLE (log reason)               │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 7. ADD ELIGIBLE ACTIONS TO QUEUE                                │
│    For each eligible action:                                     │
│    - Generate idempotency_key                                   │
│    - Check if duplicate (same idempotency_key in queue/log)     │
│    - If not duplicate:                                          │
│      a. Create queue entry                                      │
│      b. Set status (pending/collecting_params/ready)            │
│      c. Set priority                                            │
│      d. Store params_collected and params_missing               │
│      e. Persist to database (checkpoint)                        │
│      f. Update intent status = "processing"                     │
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
│ 9. PROCESS ACTION QUEUE                                         │
│    For each item in queue (ordered by priority):                │
│                                                                  │
│    IF status == "pending" or "ready":                           │
│      ┌──────────────────────────────────────────────────────┐  │
│      │ 9a. Check Params Complete                            │  │
│      │     - Compare params_collected vs params_required    │  │
│      │     - If missing params:                             │  │
│      │       * Update active_task                           │  │
│      │       * Generate next_narrative for param collection│  │
│      │       * Set status = "collecting_params"            │  │
│      │       * RETURN (wait for user input)                │  │
│      └──────────────────────────────────────────────────────┘  │
│      ┌──────────────────────────────────────────────────────┐  │
│      │ 9b. Validate Params                                 │  │
│      │     - Apply param_validation rules                  │  │
│      │     - If validation fails:                          │  │
│      │       * Add to params_validation_errors            │  │
│      │       * Generate next_narrative for re-collection  │  │
│      │       * RETURN                                      │  │
│      └──────────────────────────────────────────────────────┘  │
│      ┌──────────────────────────────────────────────────────┐  │
│      │ 9c. Check Idempotency                               │  │
│      │     - Query execution_log for idempotency_key       │  │
│      │     - If found:                                     │  │
│      │       * Set duplicate_execution = true             │  │
│      │       * Return cached result                       │  │
│      │       * Set status = "completed"                   │  │
│      │       * SKIP execution                             │  │
│      └──────────────────────────────────────────────────────┘  │
│      ┌──────────────────────────────────────────────────────┐  │
│      │ 9d. Execute Action                                  │  │
│      │     - Set status = "executing"                     │  │
│      │     - Generate execution_id                        │  │
│      │     - Start timeout timer                          │  │
│      │     - Call action executor:                        │  │
│      │       * Build API request                          │  │
│      │       * Add auth headers                           │  │
│      │       * Call brand API                             │  │
│      │       * Parse response                             │  │
│      │                                                     │  │
│      │     ON SUCCESS:                                     │  │
│      │       - Log to execution_log                       │  │
│      │       - Set status = "completed"                   │  │
│      │       - Update schema state (if action modified data)│ │
│      │       - Update intent status = "completed"         │  │
│      │       - If requires_acknowledgement:               │  │
│      │         * Add to pending_acknowledgements          │  │
│      │         * Generate next_narrative for confirmation│  │
│      │                                                     │  │
│      │     ON TIMEOUT:                                     │  │
│      │       - Increment retry_count                      │  │
│      │       - Check if retry_count < max_retries         │  │
│      │       - If can retry:                              │  │
│      │         * Calculate next_retry_at (backoff)        │  │
│      │         * Set status = "retrying"                  │  │
│      │         * Add error to retry_errors                │  │
│      │         * Update checkpoint                        │  │
│      │       - If cannot retry (exhausted):               │  │
│      │         * Move to dead_letter_queue                │  │
│      │         * Set status = "dead_letter"               │  │
│      │         * Notify user                              │  │
│      │         * Escalate if needed                       │  │
│      │         * Update intent status = "failed"          │  │
│      │                                                     │  │
│      │     ON ERROR:                                       │  │
│      │       - Check error_type                           │  │
│      │       - If in retry_on_errors:                     │  │
│      │         * Same as ON TIMEOUT                       │  │
│      │       - If in no_retry_on_errors:                  │  │
│      │         * Move to dead_letter_queue immediately    │  │
│      │         * Set status = "failed"                    │  │
│      │         * Update intent status = "failed"          │  │
│      └──────────────────────────────────────────────────────┘  │
│                                                                  │
│    IF status == "retrying":                                     │
│      - Check if current_time >= next_retry_at                   │
│      - If yes, execute (same as 9d above)                       │
│      - If no, skip (wait for retry time)                        │
│                                                                  │
│    IF status == "blocked":                                      │
│      - Re-check eligibility (maybe blocker resolved)            │
│      - If now eligible:                                         │
│        * Set status = "pending"                                 │
│        * Process as pending                                     │
│      - If still blocked:                                        │
│        * Generate next_narrative explaining blocker             │
│        * Keep status = "blocked"                                │
│                                                                  │
│    IF status == "collecting_params":                            │
│      - Check if new params provided this turn                   │
│      - If yes, add to params_collected                          │
│      - Re-check if all params complete                          │
│      - If complete, set status = "pending" and reprocess        │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 10. UPDATE SESSION STATE                                        │
│     - active_task_name (from queue or null if queue empty)      │
│     - active_task_status                                        │
│     - last_message_at (current timestamp)                       │
│     - current_turn (increment)                                  │
│     - Checkpoint queue state to database                        │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 11. GENERATE NEXT NARRATIVE                                     │
│     Based on queue state:                                        │
│     - If collecting params → param collection narrative         │
│     - If executing → wait/progress narrative                    │
│     - If blocked → blocker explanation narrative                │
│     - If completed → success confirmation narrative             │
│     - If queue empty → "anything else?" narrative               │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 12. RETURN RESPONSE TO ORCHESTRATOR                             │
│     Response payload:                                            │
│     {                                                            │
│       "response_type": "brain_generated",                       │
│       "next_narrative": {...},                                  │
│       "active_task": {...},                                     │
│       "queue_summary": {...}                                    │
│     }                                                            │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 13. LLM RESPONDER                                               │
│     - Receives next_narrative                                   │
│     - Generates natural language response                       │
│     - Follows must_communicate requirements                     │
│     - Optionally includes optional_communicate items            │
│     - Applies tone, urgency, formality                          │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ 14. USER RECEIVES RESPONSE                                      │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Background Processing (Async)

```
┌─────────────────────────────────────────────────────────────────┐
│ BACKGROUND QUEUE PROCESSOR (runs every 30 seconds)              │
│                                                                  │
│ For each active session:                                         │
│   1. Load action queue from database                            │
│   2. For items with status = "retrying":                        │
│      - Check if next_retry_at has passed                        │
│      - If yes, attempt retry execution                          │
│   3. For items with status = "collecting_params":               │
│      - Check collection_attempts                                │
│      - If > max_attempts → move to dead_letter_queue            │
│   4. For items in dead_letter_queue:                            │
│      - Check if requires escalation                             │
│      - If not escalated, create support ticket                  │
│   5. Update queue checkpoints                                   │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ SCHEMA CACHE REFRESHER (runs every 5 minutes)                   │
│                                                                  │
│ For each active session:                                         │
│   1. Check schema cache expiry                                  │
│   2. If expired and session active:                             │
│      - Proactively refresh schema data                          │
│      - Update cache                                             │
│   3. If refresh fails:                                          │
│      - Mark cache as stale                                      │
│      - Use stale cache with warning                             │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ WORKFLOW MONITOR (runs every 60 seconds)                         │
│                                                                  │
│ For each active workflow:                                        │
│   1. Check if workflow stuck (no progress in 10 minutes)        │
│   2. If stuck:                                                  │
│      - Log alert                                                │
│      - Escalate to support                                      │
│   3. Check workflow timeout                                     │
│   4. If timed out:                                              │
│      - Mark as failed                                           │
│      - Rollback completed steps (if applicable)                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. DATABASE SCHEMA

### 5.1 Intent Ledger Table

```sql
CREATE TABLE intent_ledger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    intent_id VARCHAR(100) UNIQUE NOT NULL,
    session_id UUID NOT NULL REFERENCES sessions(id),
    user_id UUID NOT NULL REFERENCES users(id),
    
    -- Intent Details
    intent_type VARCHAR(50) NOT NULL,
    confidence DECIMAL(3,2) NOT NULL,
    turn_number INT NOT NULL,
    reasoning TEXT,
    entities JSONB DEFAULT '{}',
    
    -- Status
    status VARCHAR(50) NOT NULL DEFAULT 'new',
    blocked_reason VARCHAR(255),
    
    -- Actions
    triggered_actions JSONB DEFAULT '[]',
    response_type VARCHAR(50),
    response_text TEXT,
    
    -- Timestamps
    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    INDEX idx_session_id (session_id),
    INDEX idx_user_id (user_id),
    INDEX idx_status (status),
    INDEX idx_timestamp (timestamp)
);
```

### 5.2 Action Queue Table

```sql
CREATE TABLE action_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    queue_id VARCHAR(100) UNIQUE NOT NULL,
    
    -- Action Details
    action_id VARCHAR(100) NOT NULL,
    action_name VARCHAR(255),
    
    -- Context
    session_id UUID NOT NULL REFERENCES sessions(id),
    user_id UUID NOT NULL REFERENCES users(id),
    instance_id UUID NOT NULL REFERENCES instances(id),
    brand_id VARCHAR(100),
    intent_id VARCHAR(100),
    workflow_instance_id UUID,
    
    -- Status
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    priority INT DEFAULT 1,
    
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
    
    INDEX idx_session_id (session_id),
    INDEX idx_user_id (user_id),
    INDEX idx_status (status),
    INDEX idx_priority (priority),
    INDEX idx_next_retry_at (next_retry_at),
    INDEX idx_idempotency_key (idempotency_key)
);
```

### 5.3 Dead Letter Queue Table

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
    session_id UUID NOT NULL REFERENCES sessions(id),
    user_id UUID NOT NULL REFERENCES users(id),
    instance_id UUID NOT NULL REFERENCES instances(id),
    brand_id VARCHAR(100),
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
    
    INDEX idx_session_id (session_id),
    INDEX idx_user_id (user_id),
    INDEX idx_resolved (resolved),
    INDEX idx_escalated (escalated_to_support),
    INDEX idx_moved_to_dlq_at (moved_to_dlq_at)
);
```

### 5.4 User Schema State Table

```sql
CREATE TABLE user_schema_state (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Context
    session_id UUID NOT NULL REFERENCES sessions(id),
    user_id UUID NOT NULL REFERENCES users(id),
    brand_id VARCHAR(100) NOT NULL,
    instance_id UUID NOT NULL REFERENCES instances(id),
    
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
    
    -- Keys (all key statuses as JSON)
    keys JSONB NOT NULL DEFAULT '{}',
    
    -- Schema Status
    schema_status VARCHAR(50),
    schema_completion_percentage INT,
    required_keys_complete INT DEFAULT 0,
    required_keys_total INT DEFAULT 0,
    optional_keys_complete INT DEFAULT 0,
    optional_keys_total INT DEFAULT 0,
    
    -- Metadata
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    UNIQUE(session_id, schema_id),
    INDEX idx_session_id (session_id),
    INDEX idx_user_id (user_id),
    INDEX idx_schema_id (schema_id),
    INDEX idx_cache_expires_at (cache_expires_at)
);
```

### 5.5 Brand Schemas Table

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
    api_headers JSONB DEFAULT '{}',
    api_timeout_seconds INT DEFAULT 10,
    
    -- Caching
    refresh_strategy VARCHAR(50) DEFAULT 'on_demand',
    cache_ttl_seconds INT DEFAULT 300,
    cache_on_error BOOLEAN DEFAULT TRUE,
    stale_cache_threshold_seconds INT DEFAULT 600,
    
    -- Schema Keys (definitions)
    keys JSONB NOT NULL DEFAULT '[]',
    
    -- Schema Completion Logic
    schema_completion_logic JSONB NOT NULL,
    
    -- Error Handling
    api_error_handling JSONB DEFAULT '{}',
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Metadata
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    UNIQUE(brand_id, schema_id),
    INDEX idx_brand_id (brand_id),
    INDEX idx_schema_id (schema_id),
    INDEX idx_is_active (is_active)
);
```

### 5.6 Action Execution Log Table

```sql
CREATE TABLE action_execution_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    execution_id VARCHAR(100) UNIQUE NOT NULL,
    
    -- Action Details
    action_id VARCHAR(100) NOT NULL,
    action_name VARCHAR(255),
    
    -- Context
    session_id UUID NOT NULL REFERENCES sessions(id),
    user_id UUID NOT NULL REFERENCES users(id),
    instance_id UUID NOT NULL REFERENCES instances(id),
    brand_id VARCHAR(100),
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
    
    INDEX idx_session_id (session_id),
    INDEX idx_user_id (user_id),
    INDEX idx_action_id (action_id),
    INDEX idx_status (status),
    INDEX idx_started_at (started_at),
    INDEX idx_idempotency_key (idempotency_key),
    INDEX idx_trace_id (trace_id)
);
```

### 5.7 Workflow Instances Table

```sql
CREATE TABLE workflow_instances (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workflow_instance_id VARCHAR(100) UNIQUE NOT NULL,
    
    -- Workflow Details
    workflow_id VARCHAR(100) NOT NULL,
    workflow_name VARCHAR(255),
    workflow_version VARCHAR(20),
    
    -- Context
    session_id UUID NOT NULL REFERENCES sessions(id),
    user_id UUID NOT NULL REFERENCES users(id),
    instance_id UUID NOT NULL REFERENCES instances(id),
    
    -- Status
    status VARCHAR(50) NOT NULL DEFAULT 'in_progress',
    current_step INT,
    
    -- Progress
    progress_percentage INT DEFAULT 0,
    steps_completed INT DEFAULT 0,
    steps_total INT,
    steps_remaining INT,
    
    -- Steps Executed (history)
    steps_executed JSONB DEFAULT '[]',
    
    -- Timing
    started_at TIMESTAMP NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMP,
    estimated_completion_at TIMESTAMP,
    
    -- Metadata
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    INDEX idx_session_id (session_id),
    INDEX idx_workflow_id (workflow_id),
    INDEX idx_status (status)
);
```

### 5.8 Action Registry Table

```sql
CREATE TABLE action_registry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    action_id VARCHAR(100) NOT NULL,
    instance_id UUID NOT NULL REFERENCES instances(id),
    brand_id VARCHAR(100) NOT NULL,
    
    -- Action Details
    action_name VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(100),
    
    -- Parameters
    params_required JSONB DEFAULT '[]',
    params_optional JSONB DEFAULT '[]',
    param_validation JSONB DEFAULT '{}',
    
    -- Eligibility
    eligibility_criteria JSONB NOT NULL,
    blockers JSONB DEFAULT '[]',
    dependencies JSONB DEFAULT '[]',
    opposites JSONB DEFAULT '[]',
    
    -- Execution
    timeout_seconds INT DEFAULT 30,
    retry_policy JSONB NOT NULL,
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
    
    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Metadata
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    
    UNIQUE(instance_id, action_id),
    INDEX idx_instance_id (instance_id),
    INDEX idx_brand_id (brand_id),
    INDEX idx_action_id (action_id),
    INDEX idx_is_active (is_active)
);
```

---

## 6. API INTEGRATION PATTERNS

### 6.1 Calling Brand APIs for Schema Data

**Request Pattern:**
```python
import requests
import time

def fetch_brand_api_data(
    api_endpoint: str,
    user_id: str,
    brand_id: str,
    auth_config: dict,
    timeout_seconds: int = 10
) -> dict:
    """
    Fetches data from brand API.
    
    Returns:
    {
        "success": bool,
        "status_code": int,
        "data": dict,
        "error": str,
        "response_time_ms": int
    }
    """
    # Replace placeholders
    url = api_endpoint.replace("{user_id}", user_id)
    url = url.replace("{brand_id}", brand_id)
    
    # Build headers
    headers = {}
    
    if auth_config["type"] == "bearer_token":
        token = get_token_from_config(auth_config["token_source"])
        headers["Authorization"] = f"Bearer {token}"
    
    elif auth_config["type"] == "api_key":
        headers[auth_config["header_name"]] = get_token_from_config(
            auth_config["token_source"]
        )
    
    headers["Content-Type"] = "application/json"
    
    # Make request with timing
    start_time = time.time()
    
    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=timeout_seconds
        )
        
        response_time_ms = int((time.time() - start_time) * 1000)
        
        if response.status_code == 200:
            return {
                "success": True,
                "status_code": 200,
                "data": response.json(),
                "error": None,
                "response_time_ms": response_time_ms
            }
        else:
            return {
                "success": False,
                "status_code": response.status_code,
                "data": None,
                "error": f"HTTP {response.status_code}: {response.text}",
                "response_time_ms": response_time_ms
            }
    
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "status_code": 408,
            "data": None,
            "error": "Request timeout",
            "response_time_ms": timeout_seconds * 1000
        }
    
    except Exception as e:
        return {
            "success": False,
            "status_code": 500,
            "data": None,
            "error": str(e),
            "response_time_ms": int((time.time() - start_time) * 1000)
        }
```

### 6.2 Executing Actions via Brand APIs

**Action Execution Pattern:**
```python
async def execute_action_via_api(
    action_config: dict,
    params: dict,
    auth_config: dict
) -> dict:
    """
    Executes an action by calling brand API.
    
    Returns:
    {
        "success": bool,
        "result": dict,
        "error": str,
        "api_response_status": int,
        "duration_ms": int
    }
    """
    # Build request
    url = action_config["api_endpoint"]
    method = action_config["api_method"]
    
    headers = build_auth_headers(auth_config)
    headers["Content-Type"] = "application/json"
    
    # Make request
    start_time = time.time()
    
    try:
        if method == "POST":
            response = requests.post(
                url,
                json=params,
                headers=headers,
                timeout=action_config["timeout_seconds"]
            )
        elif method == "PUT":
            response = requests.put(
                url,
                json=params,
                headers=headers,
                timeout=action_config["timeout_seconds"]
            )
        elif method == "PATCH":
            response = requests.patch(
                url,
                json=params,
                headers=headers,
                timeout=action_config["timeout_seconds"]
            )
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        duration_ms = int((time.time() - start_time) * 1000)
        
        # Check success
        success_statuses = action_config.get("success_criteria", {}).get(
            "response_status", [200, 201]
        )
        
        if response.status_code in success_statuses:
            return {
                "success": True,
                "result": response.json(),
                "error": None,
                "api_response_status": response.status_code,
                "duration_ms": duration_ms
            }
        else:
            return {
                "success": False,
                "result": None,
                "error": f"API returned {response.status_code}: {response.text}",
                "api_response_status": response.status_code,
                "duration_ms": duration_ms
            }
    
    except requests.exceptions.Timeout:
        return {
            "success": False,
            "result": None,
            "error": "Request timeout",
            "api_response_status": 408,
            "duration_ms": action_config["timeout_seconds"] * 1000
        }
    
    except Exception as e:
        return {
            "success": False,
            "result": None,
            "error": str(e),
            "api_response_status": 500,
            "duration_ms": int((time.time() - start_time) * 1000)
        }
```

---

## 7. ERROR HANDLING & RETRY STRATEGIES

### 7.1 Retry Policy Implementation

```python
import time
import math

def calculate_retry_delay(
    retry_count: int,
    backoff_strategy: str,
    initial_delay_seconds: int,
    max_delay_seconds: int
) -> int:
    """
    Calculates delay before next retry.
    
    Returns delay in seconds.
    """
    if backoff_strategy == "exponential":
        delay = initial_delay_seconds * (2 ** retry_count)
    
    elif backoff_strategy == "linear":
        delay = initial_delay_seconds + (retry_count * 10)
    
    elif backoff_strategy == "fixed":
        delay = initial_delay_seconds
    
    else:
        delay = initial_delay_seconds
    
    # Cap at max_delay
    return min(delay, max_delay_seconds)
```

### 7.2 Error Classification

```python
def classify_error(error: Exception, action_config: dict) -> dict:
    """
    Classifies error to determine if retriable.
    
    Returns:
    {
        "error_type": str,
        "retriable": bool,
        "error_message": str
    }
    """
    error_str = str(error).lower()
    
    # Timeout errors
    if "timeout" in error_str:
        error_type = "timeout"
    
    # Network errors
    elif any(x in error_str for x in ["connection", "network", "dns"]):
        error_type = "network_error"
    
    # API errors
    elif "api" in error_str:
        error_type = "api_error"
    
    # Rate limit
    elif "rate limit" in error_str or "429" in error_str:
        error_type = "rate_limit"
    
    # Auth errors
    elif any(x in error_str for x in ["auth", "unauthorized", "401", "403"]):
        error_type = "auth_error"
    
    # Validation errors
    elif any(x in error_str for x in ["validation", "invalid", "400"]):
        error_type = "validation_error"
    
    # Conflict errors
    elif "409" in error_str or "conflict" in error_str:
        error_type = "conflict_error"
    
    else:
        error_type = "unknown_error"
    
    # Determine if retriable
    retry_on_errors = action_config["retry_policy"]["retry_on_errors"]
    no_retry_on_errors = action_config["retry_policy"]["no_retry_on_errors"]
    
    if "*" in no_retry_on_errors:
        retriable = False
    elif error_type in no_retry_on_errors:
        retriable = False
    elif error_type in retry_on_errors:
        retriable = True
    else:
        retriable = False
    
    return {
        "error_type": error_type,
        "retriable": retriable,
        "error_message": str(error)
    }
```

### 7.3 Retry Execution Logic

```python
async def execute_with_retry(
    queue_item: dict,
    action_config: dict
) -> dict:
    """
    Executes action with retry logic.
    
    Returns:
    {
        "success": bool,
        "result": dict,
        "retry_count": int,
        "final_error": dict
    }
    """
    retry_count = queue_item["retry_count"]
    max_retries = queue_item["max_retries"]
    
    while retry_count <= max_retries:
        try:
            # Execute action
            result = await execute_action_via_api(
                action_config,
                queue_item["params_collected"],
                get_auth_config(action_config)
            )
            
            if result["success"]:
                return {
                    "success": True,
                    "result": result["result"],
                    "retry_count": retry_count,
                    "final_error": None
                }
            else:
                # API returned error
                error_info = classify_error(
                    Exception(result["error"]),
                    action_config
                )
                
                if not error_info["retriable"] or retry_count >= max_retries:
                    # Cannot retry or exhausted retries
                    return {
                        "success": False,
                        "result": None,
                        "retry_count": retry_count,
                        "final_error": {
                            "error_type": error_info["error_type"],
                            "error_message": error_info["error_message"],
                            "api_response": result
                        }
                    }
                else:
                    # Retry
                    retry_count += 1
                    delay = calculate_retry_delay(
                        retry_count,
                        action_config["retry_policy"]["backoff_strategy"],
                        action_config["retry_policy"]["initial_delay_seconds"],
                        action_config["retry_policy"]["max_delay_seconds"]
                    )
                    
                    # Log retry attempt
                    log_retry_attempt(queue_item, error_info, retry_count, delay)
                    
                    # Wait before retry
                    await asyncio.sleep(delay)
        
        except Exception as e:
            # Exception during execution
            error_info = classify_error(e, action_config)
            
            if not error_info["retriable"] or retry_count >= max_retries:
                return {
                    "success": False,
                    "result": None,
                    "retry_count": retry_count,
                    "final_error": {
                        "error_type": error_info["error_type"],
                        "error_message": error_info["error_message"],
                        "stack_trace": traceback.format_exc()
                    }
                }
            else:
                retry_count += 1
                delay = calculate_retry_delay(
                    retry_count,
                    action_config["retry_policy"]["backoff_strategy"],
                    action_config["retry_policy"]["initial_delay_seconds"],
                    action_config["retry_policy"]["max_delay_seconds"]
                )
                
                log_retry_attempt(queue_item, error_info, retry_count, delay)
                await asyncio.sleep(delay)
    
    # Exhausted all retries
    return {
        "success": False,
        "result": None,
        "retry_count": retry_count,
        "final_error": {
            "error_type": "max_retries_exceeded",
            "error_message": "Exhausted all retry attempts",
            "retry_count": retry_count
        }
    }
```

---

## 8. IDEMPOTENCY & CONCURRENCY CONTROL

### 8.1 Idempotency Key Generation

```python
import hashlib
from datetime import datetime

def generate_idempotency_key(
    session_id: str,
    action_id: str,
    params: dict,
    timestamp: datetime = None
) -> str:
    """
    Generates idempotency key for action.
    
    Format: session_{session_id}_action_{action_id}_{timestamp_hash}
    
    Uses timestamp to allow same action to be executed multiple times
    in same session with different params.
    """
    if timestamp is None:
        timestamp = datetime.utcnow()
    
    # Create deterministic hash from params
    params_str = json.dumps(params, sort_keys=True)
    params_hash = hashlib.md5(params_str.encode()).hexdigest()[:8]
    
    # Timestamp component (for uniqueness across multiple invocations)
    timestamp_str = timestamp.strftime("%Y%m%d%H%M%S")
    
    return f"session_{session_id}_action_{action_id}_{timestamp_str}_{params_hash}"
```

### 8.2 Idempotency Check

```python
def check_idempotency(idempotency_key: str, db: Session) -> dict:
    """
    Checks if action with this idempotency key already executed.
    
    Returns:
    {
        "already_executed": bool,
        "execution_id": str,
        "result": dict
    }
    """
    # Check execution log
    existing_execution = db.query(ActionExecutionLog).filter(
        ActionExecutionLog.idempotency_key == idempotency_key,
        ActionExecutionLog.status == "success"
    ).first()
    
    if existing_execution:
        return {
            "already_executed": True,
            "execution_id": existing_execution.execution_id,
            "result": existing_execution.result
        }
    
    # Check action queue (maybe in progress)
    existing_queue_item = db.query(ActionQueue).filter(
        ActionQueue.idempotency_key == idempotency_key,
        ActionQueue.status.in_(["executing", "pending", "ready"])
    ).first()
    
    if existing_queue_item:
        return {
            "already_executed": False,
            "in_progress": True,
            "queue_id": existing_queue_item.queue_id
        }
    
    return {
        "already_executed": False,
        "in_progress": False
    }
```

### 8.3 Concurrency Control with Locks

```python
from redis import Redis
from redis.lock import Lock

redis_client = Redis(host='localhost', port=6379, db=0)

def acquire_action_lock(
    session_id: str,
    action_id: str,
    timeout_seconds: int = 60
) -> Lock:
    """
    Acquires distributed lock for action execution.
    
    Prevents duplicate execution when multiple workers
    process same session simultaneously.
    """
    lock_key = f"action_lock:session_{session_id}:action_{action_id}"
    
    lock = redis_client.lock(
        lock_key,
        timeout=timeout_seconds,
        blocking_timeout=5
    )
    
    acquired = lock.acquire(blocking=True)
    
    if acquired:
        return lock
    else:
        raise Exception(f"Could not acquire lock for {lock_key}")

def release_action_lock(lock: Lock) -> bool:
    """
    Releases distributed lock.
    """
    try:
        lock.release()
        return True
    except Exception as e:
        logger.error(f"Error releasing lock: {e}")
        return False
```

### 8.4 Safe Action Execution with Locking

```python
async def execute_action_safely(
    queue_item: dict,
    action_config: dict,
    db: Session
) -> dict:
    """
    Executes action with idempotency check and locking.
    """
    # Check idempotency first
    idempotency_check = check_idempotency(
        queue_item["idempotency_key"],
        db
    )
    
    if idempotency_check["already_executed"]:
        logger.info(
            f"Action already executed: {queue_item['idempotency_key']}, "
            f"returning cached result"
        )
        return {
            "success": True,
            "result": idempotency_check["result"],
            "duplicate_execution": True,
            "original_execution_id": idempotency_check["execution_id"]
        }
    
    if idempotency_check.get("in_progress"):
        logger.info(
            f"Action already in progress: {queue_item['idempotency_key']}"
        )
        return {
            "success": False,
            "error": "Action already in progress",
            "in_progress": True
        }
    
    # Acquire lock
    lock = None
    try:
        lock = acquire_action_lock(
            queue_item["session_id"],
            queue_item["action_id"],
            timeout_seconds=action_config["timeout_seconds"]
        )
        
        # Execute action
        result = await execute_with_retry(queue_item, action_config)
        
        # Log execution
        log_execution(queue_item, result, db)
        
        return result
    
    finally:
        # Always release lock
        if lock:
            release_action_lock(lock)
```

---

## 9. CONFIGURATION EXAMPLES

### 9.1 Complete Instance Configuration

```json
{
  "instance_id": "retail-store-001",
  "instance_name": "XYZ Retail Main Store",
  "brand_id": "brand-xyz",
  "brand_name": "XYZ Retail",
  "is_active": true,
  
  "actions": [
    {
      "action_id": "create_profile",
      "action_name": "Create User Profile",
      "params_required": ["name", "email", "phone"],
      "params_optional": ["address"],
      "param_validation": {
        "email": {
          "type": "string",
          "regex": "^[\\w\\.-]+@[\\w\\.-]+\\.\\w+$"
        }
      },
      "eligibility_criteria": {
        "user_tier": ["verified", "guest"],
        "schema_dependencies": {}
      },
      "timeout_seconds": 30,
      "retry_policy": {
        "max_retries": 3,
        "backoff_strategy": "exponential",
        "initial_delay_seconds": 2,
        "retry_on_errors": ["timeout", "api_error"]
      }
    }
  ],
  
  "schemas": [
    {
      "schema_id": "profile",
      "schema_name": "User Profile",
      "api_endpoint": "https://api.brand-xyz.com/v1/users/{user_id}/profile",
      "api_method": "GET",
      "api_auth": {
        "type": "bearer_token",
        "token_source": "instance_config"
      },
      "cache_ttl_seconds": 300,
      "keys": [
        {
          "key_name": "email",
          "data_type": "string",
          "required_for_schema": true,
          "completion_logic": {
            "type": "non_empty",
            "validation": "email_format"
          },
          "api_field_path": "data.contact.email"
        }
      ]
    }
  ],
  
  "workflows": [
    {
      "workflow_id": "onboarding_flow",
      "workflow_name": "User Onboarding",
      "steps": [
        {
          "sequence_id": 1,
          "action_id": "create_profile",
          "required": true
        }
      ]
    }
  ]
}
```

---

## 10. IMPLEMENTATION GUIDELINES

### 10.1 Development Phases

**Phase 1: Core Infrastructure (Weeks 1-2)**
- Database schema setup
- Intent Ledger implementation
- Action Queue implementation
- Dead Letter Queue implementation
- Queue persistence and checkpointing

**Phase 2: Schema Management (Weeks 3-4)**
- Brand Schemas configuration
- Schema State Tracker
- API integration for fetching schema data
- Key status computation logic
- Cache management

**Phase 3: Action Orchestration (Weeks 5-7)**
- Action Registry setup
- Action eligibility checking
- Action execution with retry logic
- Idempotency implementation
- Concurrency control with locks

**Phase 4: Workflow Engine (Weeks 8-9)**
- Workflow configuration
- Workflow state tracking
- Step dependency management
- Workflow execution coordination

**Phase 5: Observability & Monitoring (Week 10)**
- Structured logging
- Metrics collection
- Dashboard setup
- Alert configuration

**Phase 6: Testing & Optimization (Weeks 11-12)**
- Unit tests
- Integration tests
- Load testing
- Performance optimization

### 10.2 Critical Success Factors

1. **Queue Persistence:** Ensure action queue survives server crashes
2. **Idempotency:** Prevent duplicate action execution
3. **Schema Caching:** Minimize API calls to brand systems
4. **Error Handling:** Graceful degradation with clear user communication
5. **Observability:** Comprehensive logging and monitoring
6. **Scalability:** Design for horizontal scaling from day one

### 10.3 Performance Targets

- **Action Queue Processing:** < 100ms per item
- **Schema API Calls:** < 500ms per API
- **Cache Hit Rate:** > 80% for schema data
- **Queue Checkpoint:** < 50ms write time
- **Retry Backoff:** Respect API rate limits
- **Dead Letter Queue Processing:** < 5 minutes from failure to escalation

---

**END OF DOCUMENT**