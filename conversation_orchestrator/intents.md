# 📋 **FROZEN DOCUMENTATION**

---

## **PART 1: INTENT TYPES**

### **Final Intent Types (8 Total)**

```
Self-Respond Intents (4):
├─ greeting
├─ goodbye
├─ gratitude
└─ chitchat

Brain-Required Intents (4):
├─ action
├─ help
├─ response
└─ unknown
```

---

### **Intent 1: greeting**

**Purpose:** User initiates conversation

**Auto-Response:** ✅ YES  
**Brain Required:** ❌ NO

**Examples:**
```
- "Hi"
- "Hello"
- "Good morning"
- "Hey there"
- "Yo"
- "Namaste"
```

**Bot Behavior:**
```
Self-respond: TRUE
Response Template: "Hi! I'm [Bot Name]. I can help you with [X, Y, Z]. What can I do for you?"
Brain Needed: NO
Signal Map: NO (not applicable)
Session Action: None
```

**Why Global:**
- Every bot needs to greet users
- Response is template-based (customizable per instance)
- No business logic needed

---

### **Intent 2: goodbye**

**Purpose:** User ends conversation

**Auto-Response:** ✅ YES  
**Brain Required:** ❌ NO

**Examples:**
```
- "Bye"
- "Thanks, goodbye"
- "That's all"
- "See you later"
- "Exit"
- "I'm done"
```

**Bot Behavior:**
```
Self-respond: TRUE
Response Template: "Goodbye! Feel free to reach out anytime."
Brain Needed: NO
Signal Map: Clear (if active)
Session Action: Mark as ended
```

**Why Global:**
- Universal across all bots
- Signals end of conversation
- Cleanup action (clear state)

---

### **Intent 3: gratitude**

**Purpose:** User thanks the bot

**Auto-Response:** ✅ YES  
**Brain Required:** ❌ NO

**Examples:**
```
- "Thank you"
- "Thanks"
- "Appreciate it"
- "That was helpful"
- "Perfect, thanks!"
- "Thanks a lot"
```

**Bot Behavior:**
```
Self-respond: TRUE
Response Template: "You're welcome! Anything else I can help with?"
Brain Needed: NO
Signal Map: Keep active (user might continue)
Session Action: None
```

**Why Global:**
- Polite acknowledgment
- Keeps conversation flowing naturally
- No business logic needed

---

### **Intent 4: chitchat**

**Purpose:** User wants casual conversation (off-topic)

**Auto-Response:** ✅ YES  
**Brain Required:** ❌ NO (mostly)

**Examples:**
```
- "How are you?"
- "What's your name?"
- "Are you a robot?"
- "Tell me a joke"
- "Who made you?"
- "What can AI do?"
```

**Bot Behavior:**
```
Self-respond: TRUE (mostly)
Response: Casual, friendly response
Brain Needed: Sometimes (edge cases only)
Signal Map: Clear (off-topic, breaks context)
Session Action: None
```

**Special Cases:**
```
"How are you?" 
→ Self-respond: "I'm doing great! How can I help you?"

"Tell me a joke" 
→ Self-respond with canned response

"What's the weather?" 
→ Could trigger FACTUAL_API if implemented
→ Otherwise: "I can't check weather, but I can help with [domain]"
```

**Why Global:**
- Humanizes the bot
- Handles off-topic gracefully
- Prevents "I don't understand" for common questions

---

### **Intent 5: action**

**Purpose:** User wants to DO something (core intent)

**Auto-Response:** ❌ NO  
**Brain Required:** ✅ YES

**Examples:**

**Job Portal:**
```
- "Apply to this job"
- "Apply to the Google role"
- "Upload my resume"
- "Schedule interview"
- "Search for software engineer jobs"
- "Show me my applications"
```

**E-commerce:**
```
- "Order this product"
- "Track my order"
- "Return this item"
- "Add to cart"
- "Checkout"
```

**Appointment Booking:**
```
- "Book an appointment"
- "Reschedule my booking"
- "Cancel appointment"
- "Show available slots"
```

**Bot Behavior:**
```
Self-respond: FALSE
Response: Depends on Brain processing
Brain Needed: YES
  - Resolves canonical_action
  - Checks params_required
  - Executes or queues action
Signal Map: May create (if collecting params)

Brain Resolves:
- canonical_action: "apply_job", "book_appointment", etc.
- action_type: BRAND_API / SYSTEM_API / FACTUAL_API
- params_required: ["job_id", "resume_url"]
- params_collected: {...}
- params_missing: [...]
```

**Why Global:**
- Every bot has actions
- Action details are instance-specific
- Intent type is universal
- Brain handles all complexity

---

### **Intent 6: help**

**OH SHIT! That's wild. Pure coincidence.** 😂

Alright, let me document the **help intent** specification in the same format as your original frozen documentation.

---

# 📋 **HELP INTENT SPECIFICATION - ADDENDUM TO FROZEN DOCUMENTATION**

---

## **HELP INTENT: COMPLETE SPECIFICATION**

### **Intent Type: help**

**Purpose:** User needs guidance, clarification, or information about the system, process, or current task

**Auto-Response:** ❌ NO  
**Brain Required:** ✅ YES  
**RAG Required:** ✅ YES (almost always)

---

### **Help Intent Examples:**

```
Parameter Clarification:
- "What do you mean by job title?"
- "What should I enter for experience?"
- "I don't understand this field"

Process Overview:
- "How does profile creation work?"
- "What are the steps to apply?"
- "Can you explain the application process?"

Feature Inquiry:
- "Can I schedule interviews?"
- "What features do you have?"
- "How do I track my applications?"

Stuck/Confused:
- "I don't know what to do"
- "I'm confused"
- "Help me"
- "This isn't working"
```

---

## **HELP INTENT OUTPUT SCHEMA**

### **Base Structure:**

```json
{
    "intent_type": "help",
    "confidence": 0.0-1.0,
    "sequence": 1,
    
    "help_context": {
        "type": "parameter_clarification | process_overview | feature_inquiry | stuck",
        "related_to_active_task": true | false,
        "specificity": "high | medium | low"
    },
    
    "rag_source": {
        "source_hierarchy": ["brand", "instance", "domain", "feature", "entity"],
        "canonical_topic": "string",
        "search_levels": [...],
        "entity_context": {...}
    },
    
    "rag_query": {
        "primary_query": "string",
        "fallback_queries": ["string"],
        "search_scope": "knowledge_base | faq | documentation",
        "filter_context": {...}
    }
}
```

---

## **HELP CONTEXT TYPES**

### **Type 1: parameter_clarification**

**When:** User needs clarification about a specific parameter/field they're being asked for

**Examples:**
```
"What do you mean by job title?"
"What should I enter for experience?"
"I don't understand the phone number format"
```

**Output:**
```json
{
    "help_context": {
        "type": "parameter_clarification",
        "related_to_active_task": true,
        "specificity": "high",
        "parameter": "job_title",
        "current_action": "build_profile",
        "current_step": "collecting_job_title"
    }
}
```

---

### **Type 2: process_overview**

**When:** User wants to understand a workflow or multi-step process

**Examples:**
```
"How does profile creation work?"
"What are the steps to apply for a job?"
"Walk me through the booking process"
```

**Output:**
```json
{
    "help_context": {
        "type": "process_overview",
        "related_to_active_task": true,
        "specificity": "medium",
        "process": "profile_creation",
        "current_action": "build_profile"
    }
}
```

---

### **Type 3: feature_inquiry**

**When:** User asks about capabilities, features, or what the bot can do

**Examples:**
```
"Can I schedule interviews?"
"Do you support payment?"
"What can you help me with?"
"Can I upload documents?"
```

**Output:**
```json
{
    "help_context": {
        "type": "feature_inquiry",
        "related_to_active_task": false,
        "specificity": "medium",
        "feature": "schedule_interview"
    }
}
```

---

### **Type 4: stuck**

**When:** User is confused, blocked, or doesn't know what to do next

**Examples:**
```
"I don't know what to do"
"I'm stuck"
"Help"
"This isn't working"
```

**Output:**
```json
{
    "help_context": {
        "type": "stuck",
        "related_to_active_task": true,
        "specificity": "low",
        "user_state": "confused"
    }
}
```

---

## **RAG SOURCE STRUCTURE**

### **Purpose:** 
Enable multi-resolution hierarchical RAG search across knowledge base

### **Source Hierarchy Levels:**

```
Level 1: brand       - Brand-wide knowledge (global FAQs, policies)
Level 2: instance    - Instance-specific content (bot capabilities)
Level 3: domain      - Domain knowledge (job_search, e_commerce, healthcare)
Level 4: feature     - Feature-specific (profile, application, payment)
Level 5: entity      - Entity-level (parameter, field, button)
```

### **Full RAG Source Structure:**

```json
{
    "rag_source": {
        "source_hierarchy": [
            "brand",
            "instance", 
            "domain",
            "feature",
            "entity"
        ],
        
        "canonical_topic": "job_title_definition",
        
        "search_levels": [
            {
                "level": 5,
                "path": ["brand", "instance", "domain", "feature", "entity"],
                "entity_filter": {
                    "brand_id": "acme_corp",
                    "instance_id": "uuid-123",
                    "domain": "job_search",
                    "feature": "profile_creation",
                    "entity_type": "parameter",
                    "entity_name": "job_title"
                },
                "priority": 1
            },
            {
                "level": 4,
                "path": ["brand", "instance", "domain", "feature"],
                "entity_filter": {
                    "brand_id": "acme_corp",
                    "instance_id": "uuid-123",
                    "domain": "job_search",
                    "feature": "profile_creation"
                },
                "priority": 2
            },
            {
                "level": 3,
                "path": ["brand", "instance", "domain"],
                "entity_filter": {
                    "brand_id": "acme_corp",
                    "instance_id": "uuid-123",
                    "domain": "job_search"
                },
                "priority": 3
            },
            {
                "level": 2,
                "path": ["brand", "instance"],
                "entity_filter": {
                    "brand_id": "acme_corp",
                    "instance_id": "uuid-123"
                },
                "priority": 4
            },
            {
                "level": 1,
                "path": ["brand"],
                "entity_filter": {
                    "brand_id": "acme_corp"
                },
                "priority": 5
            }
        ],
        
        "entity_context": {
            "brand_id": "acme_corp",
            "instance_id": "uuid-123",
            "domain": "job_search",
            "feature": "profile_creation",
            "current_action": "build_profile",
            "current_step": "collecting_job_title",
            "entity_type": "parameter",
            "entity_name": "job_title"
        }
    }
}
```

---

## **RAG QUERY STRUCTURE**

### **Purpose:**
Provide formatted queries for RAG search with fallback strategies

### **Structure:**

```json
{
    "rag_query": {
        "primary_query": "what does job_title parameter mean in profile creation",
        
        "fallback_queries": [
            "job_title definition profile",
            "profile creation required fields job title",
            "how to fill job title in profile"
        ],
        
        "search_scope": "knowledge_base",
        
        "filter_context": {
            "brand_id": "acme_corp",
            "instance_id": "uuid-123",
            "domain": "job_search",
            "feature": "profile_creation",
            "content_types": ["faq", "guide", "documentation"],
            "visibility": "all_users"
        }
    }
}
```

---

## **COMPLETE HELP INTENT EXAMPLES**

### **Example 1: Parameter Clarification**

**User Message:**
```
"What do you mean by job title?"
```

**Context:**
```
active_task: {
    "canonical_action": "build_profile",
    "status": "collecting_params",
    "params_missing": ["job_title"]
}
expecting_response: true
```

**Intent Detector Output:**
```json
{
    "intents": [
        {
            "intent_type": "help",
            "confidence": 0.93,
            "sequence": 1,
            
            "help_context": {
                "type": "parameter_clarification",
                "related_to_active_task": true,
                "specificity": "high",
                "parameter": "job_title",
                "current_action": "build_profile",
                "current_step": "collecting_job_title"
            },
            
            "rag_source": {
                "source_hierarchy": ["brand", "instance", "domain", "feature", "entity"],
                "canonical_topic": "job_title_definition",
                "search_levels": [
                    {
                        "level": 5,
                        "path": ["brand", "instance", "domain", "feature", "entity"],
                        "entity_filter": {
                            "brand_id": "recruitment_bot_brand",
                            "instance_id": "rec_bot_001",
                            "domain": "job_search",
                            "feature": "profile_creation",
                            "entity_type": "parameter",
                            "entity_name": "job_title"
                        }
                    }
                ]
            },
            
            "rag_query": {
                "primary_query": "what does job_title parameter mean in profile creation",
                "fallback_queries": [
                    "job_title definition",
                    "profile creation fields explanation"
                ],
                "search_scope": "knowledge_base",
                "filter_context": {
                    "brand_id": "recruitment_bot_brand",
                    "instance_id": "rec_bot_001",
                    "domain": "job_search"
                }
            }
        }
    ]
}
```

---

### **Example 2: Process Overview**

**User Message:**
```
"How does the application process work?"
```

**Intent Detector Output:**
```json
{
    "intents": [
        {
            "intent_type": "help",
            "confidence": 0.89,
            "sequence": 1,
            
            "help_context": {
                "type": "process_overview",
                "related_to_active_task": false,
                "specificity": "medium",
                "process": "job_application"
            },
            
            "rag_source": {
                "source_hierarchy": ["brand", "instance", "domain", "feature"],
                "canonical_topic": "job_application_workflow",
                "search_levels": [
                    {
                        "level": 4,
                        "path": ["brand", "instance", "domain", "feature"],
                        "entity_filter": {
                            "brand_id": "recruitment_bot_brand",
                            "instance_id": "rec_bot_001",
                            "domain": "job_search",
                            "feature": "job_application"
                        }
                    }
                ]
            },
            
            "rag_query": {
                "primary_query": "job application process workflow steps",
                "fallback_queries": [
                    "how to apply for jobs",
                    "application workflow"
                ],
                "search_scope": "documentation"
            }
        }
    ]
}
```

---

### **Example 3: Feature Inquiry**

**User Message:**
```
"Can I schedule interviews?"
```

**Intent Detector Output:**
```json
{
    "intents": [
        {
            "intent_type": "help",
            "confidence": 0.87,
            "sequence": 1,
            
            "help_context": {
                "type": "feature_inquiry",
                "related_to_active_task": false,
                "specificity": "high",
                "feature": "schedule_interview"
            },
            
            "rag_source": {
                "source_hierarchy": ["brand", "instance", "domain", "feature"],
                "canonical_topic": "interview_scheduling_capability",
                "search_levels": [
                    {
                        "level": 4,
                        "path": ["brand", "instance", "domain", "feature"],
                        "entity_filter": {
                            "brand_id": "recruitment_bot_brand",
                            "instance_id": "rec_bot_001",
                            "domain": "job_search",
                            "feature": "interview_scheduling"
                        }
                    }
                ]
            },
            
            "rag_query": {
                "primary_query": "interview scheduling feature capabilities",
                "fallback_queries": [
                    "schedule interview",
                    "interview booking"
                ],
                "search_scope": "knowledge_base"
            }
        }
    ]
}
```

---

### **Example 4: Stuck/Confused**

**User Message:**
```
"I don't know what to do"
```

**Context:**
```
active_task: {
    "canonical_action": "build_profile",
    "status": "collecting_params",
    "params_missing": ["phone", "email", "resume"]
}
```

**Intent Detector Output:**
```json
{
    "intents": [
        {
            "intent_type": "help",
            "confidence": 0.91,
            "sequence": 1,
            
            "help_context": {
                "type": "stuck",
                "related_to_active_task": true,
                "specificity": "low",
                "user_state": "confused",
                "current_action": "build_profile"
            },
            
            "rag_source": {
                "source_hierarchy": ["brand", "instance", "domain", "feature"],
                "canonical_topic": "profile_creation_help",
                "search_levels": [
                    {
                        "level": 4,
                        "path": ["brand", "instance", "domain", "feature"],
                        "entity_filter": {
                            "brand_id": "recruitment_bot_brand",
                            "instance_id": "rec_bot_001",
                            "domain": "job_search",
                            "feature": "profile_creation"
                        }
                    }
                ]
            },
            
            "rag_query": {
                "primary_query": "help with profile creation when stuck",
                "fallback_queries": [
                    "profile creation guide",
                    "what to do in profile creation",
                    "profile building steps"
                ],
                "search_scope": "faq"
            }
        }
    ]
}
```

---

## **BRAIN PROCESSING OF HELP INTENT**

### **Flow:**

```
1. Brain receives help intent from Orchestrator
    ↓
2. Brain extracts rag_source and rag_query
    ↓
3. Brain calls RAG service with multi-level search:
   - Try Level 5 (most specific) first
   - If confidence < 0.7, try Level 4
   - If confidence < 0.7, try Level 3
   - Continue until answer found or Level 1 exhausted
    ↓
4. If RAG returns answer (confidence > 0.7):
   - Brain generates response using RAG content
   - Brain keeps active_task intact
   - Brain maintains expecting_response state
    ↓
5. If RAG returns no answer:
   - Brain generates fallback: "I don't have information on that. Let me connect you to support."
   - Brain may escalate to human
    ↓
6. Brain returns response + next_narrative
```

---

## **KNOWLEDGE BASE STRUCTURE FOR HELP**

### **Table Schema:**

```sql
CREATE TABLE knowledge_base (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Hierarchical topic paths (multi-resolution)
    topic_paths JSONB NOT NULL,
    -- Example: ["brand", "instance", "domain", "feature", "entity"]
    
    -- Canonical topic for exact matching
    canonical_topic VARCHAR(255),
    -- Example: "job_title_definition"
    
    -- Entity metadata (brand/instance/domain filters)
    entity_metadata JSONB DEFAULT '{}',
    -- Example: {"brand_id": "xyz", "instance_id": "abc", "domain": "job_search"}
    
    -- Content
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    content_type VARCHAR(50), -- faq, guide, documentation, policy
    
    -- Search optimization
    search_vector TSVECTOR,
    
    -- Visibility
    visibility VARCHAR(50) DEFAULT 'all_users',
    -- Options: all_users, registered_only, premium_only
    
    -- Metadata
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    created_by VARCHAR(100),
    
    -- Indexes
    INDEX idx_topic_paths USING GIN (topic_paths),
    INDEX idx_canonical_topic (canonical_topic),
    INDEX idx_entity_metadata USING GIN (entity_metadata),
    INDEX idx_search_vector USING GIN (search_vector)
);
```

### **Example Knowledge Base Entry:**

```json
{
    "id": "kb_12345",
    "topic_paths": ["brand", "instance", "domain", "feature", "entity"],
    "canonical_topic": "job_title_definition",
    "entity_metadata": {
        "brand_id": "recruitment_bot_brand",
        "instance_id": "rec_bot_001",
        "domain": "job_search",
        "feature": "profile_creation",
        "entity_type": "parameter",
        "entity_name": "job_title"
    },
    "title": "What is Job Title?",
    "content": "Job title is your official role designation at your current or most recent company. Examples include: Software Engineer, Product Manager, Sales Director, Marketing Specialist. This should match what appears on your business card or LinkedIn profile. This field is required for profile completion.",
    "content_type": "faq",
    "visibility": "all_users",
    "created_at": "2025-10-01T10:00:00Z"
}
```

---

## **KEY DESIGN PRINCIPLES**

### **1. Multi-Resolution Search**
- Start with most specific (Level 5)
- Progressively broaden to Level 1
- Return best match with confidence score

### **2. Entity-Aware Filtering**
- Filter by brand_id (company-specific knowledge)
- Filter by instance_id (bot-specific knowledge)
- Filter by domain (job_search vs e_commerce)

### **3. Fallback Strategy**
- Primary query on exact canonical_topic
- Fallback queries for semantic search
- Final fallback to human escalation

### **4. Context Preservation**
- Help intent does NOT break active_task
- Maintains expecting_response state
- Returns to original flow after answering

---

### **Intent 7: response**

**Purpose:** User responds to bot's question

**Auto-Response:** ❌ NO  
**Brain Required:** ✅ YES

**Examples:**

**Confirmation:**
```
Bot: "Do you want to apply to Google?"
User: "Yes" / "Yeah" / "Sure" / "Confirm"
User: "No" / "Nope" / "Cancel"
```

**Selection (Single):**
```
Bot: "Which job? #1 Google or #2 Meta"
User: "The first one" / "1" / "Google" / "#1"
```

**Selection (Multiple):**
```
Bot: "Which skills? A) Python B) React C) AWS"
User: "A and C" / "Python and AWS"
```

**Entity Capture:**
```
Bot: "What's your email?"
User: "john@example.com"

Bot: "What's your experience?"
User: "I worked at Google for 5 years as a senior engineer..."
```

**Bot Behavior:**
```
Self-respond: FALSE
Response: Depends on Brain processing
Brain Needed: YES
  - Matches against answer_sheet
  - Extracts entities
  - Continues active_task
Signal Map: Uses answer_sheet for matching

Conditions for Detection:
1. expecting_response: true
2. answer_sheet exists (or active_task context)
3. User message matches OR continues context
```

**Orchestrator Handling:**
```python
if intent_type == "response":
    if answer_sheet_exists:
        # Match signal
        matched = match_signal(user_message, answer_sheet)
        
        if matched:
            # Signal interaction
            pass_to_brain(matched_signal)
        else:
            # No match - possible topic change
            redetect_as_action_or_unknown()
    else:
        # Contextual response (param collection)
        pass_to_brain(active_task_context)
```

**Why This Intent Exists:**
- Different from ACTION (user initiates vs responds)
- Enables answer_sheet matching
- Handles param collection elegantly
- LLM can distinguish based on expecting_response flag

---

### **Intent 8: unknown**

**Purpose:** Cannot understand user's message (outside universe)

**Auto-Response:** ❌ NO  
**Brain Required:** ✅ YES

**Examples:**
```
- "asdfkjh" (gibberish)
- "???" (unclear)
- "that thing" (ambiguous without context)
- "it" (no referent)
- "yes" (when no question pending)
```

**Bot Behavior:**
```
Self-respond: FALSE
Response: Brain generates fallback message
Brain Needed: YES
  - Generates: "I didn't understand. Could you rephrase?"
  - Offers help or guidance
Cold Path: Triggers async topic classification

Triggers When:
- All intents have confidence < 0.4
- LLM returns empty intents list
- Message is genuinely incomprehensible
```

**Flow:**
```
User: "asdfkjh"
    ↓
Intent Detector: confidence < 0.4 → unknown
    ↓
Orchestrator: Passes to Brain
    ↓
Brain: Generates fallback response
    ↓
Response: "I didn't understand. Could you rephrase?"
    ↓
Cold Path (ASYNC):
  - Topic classification
  - Thread detection
  - Store in messages.topic_paths
  - Analytics
```

**Why "unknown" (not "fallback"):**
- Clear semantic meaning to LLM
- "I don't know what this is" vs "fallback to what?"
- Natural language fit
- No confusion with system states

---

## **Intent Type Routing Table**

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

## **Multi-Intent Examples**

### **Example 1: Gratitude + Action**
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
        "confidence": 0.94,
        "sequence": 2,
        "auto_response": false,
        "canonical_action": "apply_job",
        "entities": {"company": "Google"}
    }
]

Orchestrator:
1. Auto-respond: "You're welcome!"
2. Pass action to Brain
3. Combine: "You're welcome! I'll help you apply to Google..."
```

### **Example 2: Greeting + Help**
```
User: "Hi! What can you do?"

Detected Intents:
[
    {
        "intent_type": "greeting",
        "confidence": 0.98,
        "sequence": 1,
        "auto_response": true
    },
    {
        "intent_type": "help",
        "confidence": 0.93,
        "sequence": 2,
        "auto_response": false
    }
]

Orchestrator:
1. Greeting (auto): "Hi!"
2. Brain generates help content
3. Combine: "Hi! I can help you with job search, applications, and profile management..."
```

---

# **PART 2: BRAIN WIRES TO INTENT DETECTOR**

---

## **Wire Overview**

**Brain Produces (7 wires):**
```
1. expecting_response      (boolean)
2. answer_sheet           (object)
3. active_task            (object)
4. previous_intents       (array)
5. available_signals      (array, derived)
6. conversation_context   (object)
7. popular_actions        (array)
```

**Cold Path Produces (1 wire):**
```
8. session_summary        (string, async after turn)
```

---

### **Wire 1: expecting_response**

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

**When Brain Sets:**
```python
# Brain generates question
if next_narrative.contains_question:
    sessions.state["expecting_response"] = True
    sessions.state["answer_sheet"] = {...}
else:
    sessions.state["expecting_response"] = False
    sessions.state["answer_sheet"] = None
```

**Storage:** `sessions.state (JSONB) → {"expecting_response": true}`

**Used By:** Intent Detector to prefer `response` intent when true

---

### **Wire 2: answer_sheet**

**Type:** `object (JSONB)`  
**Source:** Brain creates when asking structured question  
**Purpose:** Maps expected answers to actions/signals

**Structure:**
```javascript
{
    "type": "confirmation" | "single_choice" | "multiple_choice" | "entity",
    "options": {...},
    "context": "string describing what question is about"
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

**When Brain Creates:**
```python
# Brain determines next step needs user input
if action_needs_param("job_id"):
    # Create answer sheet for job selection
    answer_sheet = {
        "type": "single_choice",
        "options": {
            "#1": ["1", "first", "google", "#1"],
            "#2": ["2", "second", "meta", "#2"]
        },
        "context": "job_selection"
    }
    sessions.state["answer_sheet"] = answer_sheet
    sessions.state["expecting_response"] = True
```

**Storage:** `sessions.state (JSONB) → {"answer_sheet": {...}}`

**Used By:** Intent Detector to match user response against valid options

---

### **Wire 3: active_task**

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

**Example 1: Job Application (In Progress)**
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
    "created_at": "2025-10-30T10:00:00Z",
    "updated_at": "2025-10-30T10:02:00Z"
}
```

**Example 2: Profile View (Ready)**
```json
{
    "task_id": "e5f6g7h8",
    "canonical_action": "view_profile",
    "action_type": "SYSTEM_API",
    "params_required": [],
    "params_collected": {},
    "params_missing": [],
    "status": "ready_to_execute",
    "created_at": "2025-10-30T10:05:00Z",
    "updated_at": "2025-10-30T10:05:00Z"
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

**When Brain Updates:**
```python
# User provides param
if intent_type == "response" and matched_signal:
    active_task["params_collected"]["job_id"] = matched_signal
    active_task["params_missing"].remove("job_id")
    
    if not active_task["params_missing"]:
        active_task["status"] = "ready_to_execute"
    
    sessions.state["active_task"] = active_task
```

**Storage:** `sessions.state (JSONB) → {"active_task": {...}}`

**Used By:** Intent Detector for context about what user is doing

---

### **Wire 4: previous_intents**

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
        "timestamp": "2025-10-30T10:00:00Z",
        "turn": 1
    },
    {
        "intent_type": "action",
        "canonical_action": "search_jobs",
        "confidence": 0.95,
        "entities": {"role": "software engineer"},
        "timestamp": "2025-10-30T10:01:00Z",
        "turn": 2
    },
    {
        "intent_type": "response",
        "matched_signal": "#1",
        "confidence": 0.92,
        "timestamp": "2025-10-30T10:02:00Z",
        "turn": 3
    },
    {
        "intent_type": "action",
        "canonical_action": "apply_job",
        "confidence": 0.94,
        "timestamp": "2025-10-30T10:03:00Z",
        "turn": 4
    },
    {
        "intent_type": "response",
        "matched_signal": "yes",
        "confidence": 0.96,
        "timestamp": "2025-10-30T10:04:00Z",
        "turn": 5
    }
]
```

**Max Items:** Last 5 intents (rolling window)

**When Brain Updates:**
```python
# After intent detection
previous_intents = sessions.state.get("previous_intents", [])

# Add new intent
previous_intents.append({
    "intent_type": detected_intent.intent_type,
    "canonical_action": detected_intent.canonical_action,
    "confidence": detected_intent.confidence,
    "timestamp": datetime.utcnow().isoformat(),
    "turn": current_turn
})

# Keep only last 5
previous_intents = previous_intents[-5:]

sessions.state["previous_intents"] = previous_intents
```

**Storage:** `sessions.state (JSONB) → {"previous_intents": [...]}`

**Used By:** Intent Detector to understand conversation flow and context

---

### **Wire 5: available_signals**

**Type:** `array (derived from answer_sheet)`  
**Source:** Brain generates from answer_sheet  
**Purpose:** Quick list for Intent Detector matching

**Structure:**
```javascript
["signal1", "signal2", "signal3", ...]
```

**Example 1: From Confirmation**
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

**Example 2: From Selection**
```javascript
answer_sheet: {
    "type": "single_choice",
    "options": {
        "#1": ["1", "first", "google"],
        "#2": ["2", "second", "meta"]
    }
}

available_signals: ["1", "first", "google", "#1", "2", "second", "meta", "#2"]
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

---

### **Wire 6: conversation_context**

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

**Example 1: Browsing Jobs**
```json
{
    "domain": "job_search",
    "user_state": "browsing",
    "last_action": "searched_jobs",
    "pending_confirmation": false
}
```

**Example 2: Applying to Job**
```json
{
    "domain": "job_search",
    "user_state": "actively_applying",
    "last_action": "selected_job",
    "pending_confirmation": true,
    "awaiting": "resume_upload"
}
```

**Example 3: Completed Application**
```json
{
    "domain": "job_search",
    "user_state": "post_application",
    "last_action": "applied_to_google",
    "pending_confirmation": false,
    "awaiting": "interview_scheduling"
}
```

**User State Values:**
```
"new"                // First interaction
"browsing"           // Exploring options
"actively_applying"  // In process of action
"waiting"            // Waiting for response (confirmation, etc.)
"post_application"   // After completing action
"stuck"              // User seems confused or blocked
```

**When Brain Updates:**
```python
# After each turn
conversation_context = {
    "domain": instance.domain,
    "user_state": determine_user_state(active_task, previous_intents),
    "last_action": previous_intents[-1].get("canonical_action"),
    "pending_confirmation": expecting_response and answer_sheet_type == "confirmation"
}

sessions.state["conversation_context"] = conversation_context
```

**Storage:** `sessions.state (JSONB) → {"conversation_context": {...}}`

**Used By:** Intent Detector to understand user's current situation

---

### **Wire 7: popular_actions**

**Type:** `array`  
**Source:** Brain loads from instance_config OR analytics  
**Purpose:** Tell Intent Detector what popular actions are available

**Structure:**
```javascript
{
    "actions": ["action1", "action2", "action3"],
    "total_count": 47
}
```

**Example:**
```json
{
    "actions": [
        "apply_job",
        "search_jobs",
        "view_profile",
        "upload_resume",
        "schedule_interview"
    ],
    "total_count": 23
}
```

**Selection Strategy:**

**Option 1: Manual Curation**
```python
# Per domain, manually define top 5
JOB_SEARCH_POPULAR = [
    "apply_job",
    "search_jobs",
    "view_profile",
    "upload_resume",
    "schedule_interview"
]
```

**Option 2: Usage-Based**
```sql
SELECT canonical_action, COUNT(*) as usage_count
FROM intent_ledger
WHERE instance_id = ?
  AND created_at > NOW() - INTERVAL '30 days'
GROUP BY canonical_action
ORDER BY usage_count DESC
LIMIT 5
```

**Why Popular Only (Not All):**
- ✅ Keeps Intent Detector prompt short
- ✅ LLM focuses on common patterns
- ✅ Rare actions still work (Brain resolves from full registry)
- ✅ Improves accuracy on frequent operations

**Max Items:** 3-7 actions

**When Brain Loads:**
```python
# During session initialization or adapter building
popular_actions = instance_config.get("popular_actions", [])

# Or fetch from analytics
popular_actions = get_popular_actions(instance_id, limit=5)
```

**Storage:** `instance_configs.config (JSONB)` OR derived from analytics

**Used By:** Intent Detector to classify common actions accurately

---

### **Wire 8: session_summary**

**Type:** `string`  
**Source:** **Cold Path generates AFTER Intent Detection LLM call** (NOT after Brain)  
**Purpose:** Compressed history for LLM context

**Max Length:** ~500 tokens (~150 words)

**Example:**
```
User is looking for software engineer jobs in San Francisco. 
Applied to Google (application pending, uploaded resume). 
Viewed Meta job posting. 
Next: Waiting to schedule interview with Google recruiter.
User has 5 years Python experience, prefers remote work.
```

**Generation Flow:**
```
Turn N:
Message arrives
    ↓
Intent Detector LLM call
    ├─ Reads: session_summary (from Turn N-1) ← Historical context
    ├─ Reads: active_task (Turn N fresh) ← Current state
    └─ Detects intent
    ↓
Cold Path triggers IMMEDIATELY (ASYNC, fire-and-forget):
    ├─ session_summary_generator ✅
    ├─ judge_topic (future)
    ├─ judge_tone (future)
    └─ judge_state_of_mind (future)
    ↓
Brain processes intent (parallel with Cold Path)
    ├─ Updates: active_task
    ├─ Updates: answer_sheet
    └─ Generates response
    ↓
Response sent to user
    ↓
Cold Path completes in background:
    └─ Saves Turn N summary to sessions.session_summary
    ↓
Turn N+1:
    Intent Detector reads:
    ├─ session_summary: Turn N summary ✅
    └─ active_task: Turn N+1 current state ✅
```

**Why This Timing:**
```
session_summary = Historical context (narrative)
  - "User wants to apply to Google"
  - "User uploaded resume"
  - -1 turn delay is ACCEPTABLE

active_task = Current execution state (ledger)
  - task_id, params_collected, params_missing, status
  - ALWAYS fresh (no delay)

Intent Detector needs:
  ✅ Past context → session_summary (Turn N-1 is fine)
  ✅ Current state → active_task (Turn N, always fresh)
```

**Summarizer Call:**
```python
# conversation_orchestrator/cold_path/session_summary_generator.py

async def generate_session_summary(...):
    # TODO: When brain is built, fetch actions from brain's ledger
    actions = None  # Brain will populate later
    
    # Generate summary using GROQ
    summary = await summarize_conversation(
        messages=conversation_history,
        goal="key facts about user, their intent, conversation progress, and any backend actions",
        max_tokens=150,
        actions=actions,  # Brain populates this
        max_input_tokens=2000,
        template_key="session_summary_v1",
        trace_id=trace_id
    )
    
    # Save to database
    save_session_summary(session_id, summary)
```

**With Brain Actions (Future):**
```python
# Brain will provide actions via ledger
actions = [
    {
        "action": "profile_created",
        "data": {"user_id": "12345"},
        "turn": 3
    },
    {
        "action": "job_application_submitted",
        "data": {"job_id": "67890", "company": "Google"},
        "turn": 5
    }
]

# Summary will include:
# "User created profile (user_id=12345 at turn 3). 
#  Applied to Google software engineer role (turn 5)."
```

**Storage:** `sessions.session_summary (text field)`

**Used By:** Intent Detector in turn N+1 for conversation context

**Key Points:**
- ✅ Generated ASYNC by Cold Path
- ✅ Triggered AFTER Intent Detection, NOT after Brain
- ✅ -1 turn delay is acceptable (historical context, not current state)
- ✅ Current state comes from `active_task` (always fresh)

## **Complete Wire Summary**

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

## **Intent Detection Prompt Receives These**

```
# SYSTEM PROMPT
You are an intent detector for a [domain] assistant.

# CONTEXT FROM BRAIN
Session Summary: {session_summary}
Expecting Response: {expecting_response}
Answer Sheet: {answer_sheet}
Active Task: {active_task}
Previous Intents: {previous_intents}
Available Signals: {available_signals}
Conversation Context: {conversation_context}
Popular Actions: {popular_actions}

# USER MESSAGE
{user_message}

# INTENT TYPES
Detect one of: greeting, goodbye, gratitude, chitchat, action, help, response, unknown

# OUTPUT FORMAT (JSON)
{
    "intents": [
        {
            "intent_type": "action",
            "confidence": 0.95,
            "canonical_action": "apply_job",
            "entities": {"company": "Google"}
        }
    ]
}
```

---

**END OF DOCUMENTATION**