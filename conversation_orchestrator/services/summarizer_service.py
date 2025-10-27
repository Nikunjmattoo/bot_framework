"""
Summarizer service for generating conversation summaries.

Provides generic summarization functionality that can be used by:
- Cold path (session summary generation)
- Brain (task summaries, decision logs)
- Any component needing conversation compression
"""

import logging
from typing import List, Dict, Any, Optional

from conversation_orchestrator.services.db_service import fetch_template_string, fetch_template_config
from conversation_orchestrator.services.template_service import fill_template
from conversation_orchestrator.services.llm_service import call_llm_async

logger = logging.getLogger(__name__)


async def summarize_conversation(
    messages: List[Dict[str, str]],
    goal: str,
    max_tokens: int,
    actions: Optional[List[Dict[str, Any]]] = None,
    max_input_tokens: int = 2000,
    template_key: str = "session_summary_v1",
    trace_id: Optional[str] = None
) -> str:
    """
    Summarize conversation with optional backend actions.
    
    This is a generic summarizer that compresses conversations while preserving
    key information. It can optionally include backend actions (e.g., profile_created,
    payment_processed) to provide complete context.
    
    Args:
        messages: List of conversation messages
            Format: [{"role": "user/assistant", "content": "..."}]
        goal: What to focus on in summary
            Examples: "key facts and user intent", "conversation progress"
        max_tokens: Target summary length (typically 100-150 tokens)
        actions: Optional backend actions to include in summary
            Format: [{"action": "profile_created", "data": {...}, "turn": 5}]
            Note: Brain will populate this later via its ledger system
        max_input_tokens: Max tokens for input (truncates if exceeded)
        template_key: Template to use for summarization
        trace_id: Trace ID for logging
    
    Returns:
        Summary string (past tense, factual, concise)
    
    Example:
        summary = await summarize_conversation(
            messages=[
                {"role": "user", "content": "I want to create a profile"},
                {"role": "assistant", "content": "What's your name?"},
                {"role": "user", "content": "Nikunj"}
            ],
            goal="key facts about user intent",
            max_tokens=150,
            actions=[
                {"action": "profile_created", "data": {"user_id": "12345"}, "turn": 3}
            ]
        )
        # Output: "User created profile. Provided name (Nikunj). 
        #          System completed profile creation (user_id=12345)."
    """
    try:
        logger.info(
            "summarizer:started",
            extra={
                "trace_id": trace_id,
                "message_count": len(messages),
                "has_actions": actions is not None,
                "goal": goal
            }
        )
        
        # Step 1: Fetch template and config
        template_string = await fetch_template_string(template_key)
        template_config = await fetch_template_config(template_key)
        
        # Step 2: Format messages
        formatted_messages = format_messages_for_summary(messages)
        
        # Step 3: Format actions (if provided)
        formatted_actions = format_actions_for_summary(actions) if actions else "[No backend actions recorded]"
        
        # Step 4: Check input token limit and truncate if needed
        estimated_tokens = estimate_tokens(formatted_messages) + estimate_tokens(formatted_actions)
        
        if estimated_tokens > max_input_tokens:
            logger.warning(
                "summarizer:truncating_input",
                extra={
                    "trace_id": trace_id,
                    "estimated_tokens": estimated_tokens,
                    "max_tokens": max_input_tokens
                }
            )
            # Keep recent messages (most relevant)
            messages = truncate_messages_to_token_limit(messages, max_input_tokens - 300)
            formatted_messages = format_messages_for_summary(messages)
        
        # Step 5: Fill template
        variables = {
            "goal": goal,
            "messages": formatted_messages,
            "actions": formatted_actions
        }
        
        prompt = fill_template(template_string, variables)
        
        logger.info(
            "summarizer:template_filled",
            extra={
                "trace_id": trace_id,
                "prompt_length": len(prompt),
                "estimated_tokens": estimate_tokens(prompt)
            }
        )
        
        # Step 6: Call LLM (CORRECT PARAMETER ORDER)
        response = await call_llm_async(
            prompt=prompt,
            model=template_config["model"],
            runtime=template_config["provider"],
            max_tokens=max_tokens,
            temperature=0.1,
            trace_id=trace_id
        )
        
        summary = response["content"].strip()
        
        logger.info(
            "summarizer:completed",
            extra={
                "trace_id": trace_id,
                "summary_length": len(summary),
                "summary_tokens": estimate_tokens(summary),
                "tokens_used": response.get("token_usage", {}).get("total", 0)
            }
        )
        
        return summary
    
    except Exception as e:
        logger.error(
            "summarizer:error",
            extra={
                "trace_id": trace_id,
                "error": str(e),
                "error_type": type(e).__name__
            }
        )
        
        # Return empty string on failure (don't break cold path)
        return ""


def format_messages_for_summary(messages: List[Dict[str, str]]) -> str:
    """
    Format conversation messages for summarization prompt.
    
    Args:
        messages: List of message dicts with 'role' and 'content'
    
    Returns:
        Formatted string suitable for LLM prompt
    
    Example:
        Input: [
            {"role": "user", "content": "Hi"},
            {"role": "assistant", "content": "Hello!"}
        ]
        Output: "User: Hi\nAssistant: Hello!"
    """
    if not messages:
        return "[No conversation yet]"
    
    formatted = []
    for msg in messages:
        role = msg.get("role", "unknown").capitalize()
        content = msg.get("content", "").strip()
        
        if content:  # Skip empty messages
            formatted.append(f"{role}: {content}")
    
    return "\n".join(formatted)


def format_actions_for_summary(actions: Optional[List[Dict[str, Any]]]) -> str:
    """
    Format backend actions for summarization prompt.
    
    Args:
        actions: List of action dicts with 'action', 'data', 'turn'
    
    Returns:
        Formatted string suitable for LLM prompt
    
    Example:
        Input: [
            {"action": "profile_created", "data": {"user_id": "123"}, "turn": 5},
            {"action": "email_sent", "data": {"to": "user@example.com"}, "turn": 5}
        ]
        Output: "- Turn 5: profile_created (user_id=123)\n
                 - Turn 5: email_sent (to=user@example.com)"
    """
    if not actions:
        return "[No backend actions recorded]"
    
    formatted = []
    for action in actions:
        action_name = action.get("action", "unknown_action")
        turn = action.get("turn", "?")
        data = action.get("data", {})
        
        # Format data as key=value pairs
        data_str = ", ".join(f"{k}={v}" for k, v in data.items()) if data else "no data"
        
        formatted.append(f"- Turn {turn}: {action_name} ({data_str})")
    
    return "\n".join(formatted)


def estimate_tokens(text: str) -> int:
    """
    Estimate token count using character-based approximation.
    
    Rule of thumb: 1 token ≈ 4 characters
    
    Args:
        text: Input text
    
    Returns:
        Estimated token count
    
    Note:
        This is a rough estimate. Actual tokenization may vary by ±20%.
        Good enough for input truncation decisions.
    """
    return len(text) // 4


def truncate_messages_to_token_limit(
    messages: List[Dict[str, str]],
    max_tokens: int
) -> List[Dict[str, str]]:
    """
    Truncate messages to fit within token limit.
    
    Strategy: Keep most recent messages (they're most relevant).
    
    Args:
        messages: List of message dicts
        max_tokens: Maximum tokens allowed
    
    Returns:
        Truncated list of messages
    
    Example:
        Input: 50 messages, max_tokens=1000
        Output: Last ~30 messages that fit in 1000 tokens
    """
    if not messages:
        return []
    
    # Start from end (most recent) and work backwards
    truncated = []
    current_tokens = 0
    
    for msg in reversed(messages):
        msg_text = f"{msg.get('role', '')}: {msg.get('content', '')}"
        msg_tokens = estimate_tokens(msg_text)
        
        if current_tokens + msg_tokens > max_tokens:
            break
        
        truncated.insert(0, msg)  # Add to beginning to maintain order
        current_tokens += msg_tokens
    
    return truncated