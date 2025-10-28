"""
LLM service for calling language models.

Supports multiple providers:
- Groq (FREE, fast)
- Gemini (Google, FREE tier)
- Anthropic Claude (paid)
- Ollama (local Llama)
- OpenAI (paid)
"""

import logging
import asyncio
import json
import os
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

from conversation_orchestrator.exceptions import LLMError


class LLMService:
    """LLM service supporting multiple providers."""
    
    def __init__(self):
        """Initialize LLM service."""
        self.groq_client = None
        self.gemini_client = None
        self.anthropic_client = None
        self.ollama_client = None
        self.openai_client = None
    
    def _get_groq_client(self):
        """Get or create Groq client."""
        if self.groq_client is None:
            from groq import Groq
            api_key = os.environ.get("GROQ_API_KEY")
            if not api_key:
                raise LLMError(
                    message="GROQ_API_KEY not found in environment",
                    error_code="MISSING_API_KEY"
                )
            self.groq_client = Groq(api_key=api_key)
        return self.groq_client
    
    def _get_gemini_client(self):
        """Get or create Gemini client."""
        if self.gemini_client is None:
            import google.generativeai as genai
            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                raise LLMError(
                    message="GEMINI_API_KEY not found in environment",
                    error_code="MISSING_API_KEY"
                )
            genai.configure(api_key=api_key)
            self.gemini_client = genai
        return self.gemini_client
    
    def _get_anthropic_client(self):
        """Get or create Anthropic client."""
        if self.anthropic_client is None:
            from anthropic import Anthropic
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                raise LLMError(
                    message="ANTHROPIC_API_KEY not found in environment",
                    error_code="MISSING_API_KEY"
                )
            self.anthropic_client = Anthropic(api_key=api_key)
        return self.anthropic_client
    
    def _get_ollama_client(self):
        """Get or create Ollama client."""
        if self.ollama_client is None:
            import ollama
            self.ollama_client = ollama
        return self.ollama_client
    
    async def call_groq(
        self,
        prompt: str,
        model: str,
        max_tokens: int,
        temperature: float = 0.1,
        response_format: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Call Groq API.
        
        Models:
        - llama-3.3-70b-versatile (best quality)
        - llama-3.1-8b-instant (fast)
        - mixtral-8x7b-32768
        """
        try:
            client = self._get_groq_client()
            
            logger.info(
                "llm_service:calling_groq",
                extra={"model": model, "max_tokens": max_tokens}
            )
            
            # Build request parameters
            kwargs = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": max_tokens,
                "temperature": temperature
            }
            
            # Only add response_format if explicitly requested
            if response_format:
                kwargs["response_format"] = response_format
            
            response = client.chat.completions.create(**kwargs)
            
            content = response.choices[0].message.content
            token_usage = {
                "input": response.usage.prompt_tokens,
                "output": response.usage.completion_tokens,
                "total": response.usage.total_tokens
            }
            
            logger.info(
                "llm_service:groq_success",
                extra={"tokens_used": token_usage["total"]}
            )
            
            return {
                "content": content,
                "token_usage": token_usage,
                "model": response.model
            }
        
        except Exception as e:
            logger.error(
                "llm_service:groq_error",
                extra={"error": str(e)}
            )
            raise LLMError(
                message=f"Groq API error: {str(e)}",
                error_code="GROQ_API_ERROR"
            ) from e
    
    async def call_gemini(
        self,
        prompt: str,
        model: str,
        max_tokens: int,
        temperature: float = 0.1,
        response_format: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Call Gemini API.
        
        Models:
        - gemini-2.0-flash-exp (latest, fast)
        - gemini-1.5-flash (stable)
        - gemini-1.5-pro (best quality)
        """
        try:
            genai = self._get_gemini_client()
            
            logger.info(
                "llm_service:calling_gemini",
                extra={"model": model, "max_tokens": max_tokens}
            )
            
            # Create model
            gemini_model = genai.GenerativeModel(model)
            
            # Build generation config
            gen_config = {
                "max_output_tokens": max_tokens,
                "temperature": temperature
            }
            
            # Only add JSON format if explicitly requested
            if response_format:
                gen_config["response_mime_type"] = "application/json"
            
            # Generate
            response = gemini_model.generate_content(
                prompt,
                generation_config=gen_config
            )
            
            content = response.text
            
            # Gemini doesn't provide token counts in free tier
            # Estimate tokens
            token_usage = {
                "input": len(prompt) // 4,
                "output": len(content) // 4,
                "total": (len(prompt) + len(content)) // 4
            }
            
            logger.info(
                "llm_service:gemini_success",
                extra={"tokens_used": token_usage["total"]}
            )
            
            return {
                "content": content,
                "token_usage": token_usage,
                "model": model
            }
        
        except Exception as e:
            logger.error(
                "llm_service:gemini_error",
                extra={"error": str(e)}
            )
            raise LLMError(
                message=f"Gemini API error: {str(e)}",
                error_code="GEMINI_API_ERROR"
            ) from e
    
    async def call_anthropic(
        self,
        prompt: str,
        model: str,
        max_tokens: int,
        temperature: float = 0.1,
        response_format: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Call Anthropic API.
        
        Models:
        - claude-3-5-sonnet-20241022 (best)
        - claude-3-haiku-20240307 (fast, cheap)
        """
        try:
            client = self._get_anthropic_client()
            
            logger.info(
                "llm_service:calling_anthropic",
                extra={"model": model, "max_tokens": max_tokens}
            )
            
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": prompt}]
            )
            
            content = response.content[0].text
            token_usage = {
                "input": response.usage.input_tokens,
                "output": response.usage.output_tokens,
                "total": response.usage.input_tokens + response.usage.output_tokens
            }
            
            logger.info(
                "llm_service:anthropic_success",
                extra={"tokens_used": token_usage["total"]}
            )
            
            return {
                "content": content,
                "token_usage": token_usage,
                "model": response.model
            }
        
        except Exception as e:
            logger.error(
                "llm_service:anthropic_error",
                extra={"error": str(e)}
            )
            raise LLMError(
                message=f"Anthropic API error: {str(e)}",
                error_code="ANTHROPIC_API_ERROR"
            ) from e
    
    async def call_ollama(
        self,
        prompt: str,
        model: str,
        max_tokens: int,
        temperature: float = 0.1,
        response_format: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Call Ollama (local).
        
        Models:
        - llama3.2:3b (fast, 3B params)
        - llama3.1:8b (better, 8B params)
        - llama3.1:70b (best, 70B params, slow)
        """
        try:
            ollama = self._get_ollama_client()
            
            logger.info(
                "llm_service:calling_ollama",
                extra={"model": model, "max_tokens": max_tokens}
            )
            
            # Build options
            options = {
                "temperature": temperature,
                "num_predict": max_tokens
            }
            
            kwargs = {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "options": options
            }
            
            # Only add JSON format if explicitly requested
            if response_format:
                kwargs["format"] = "json"
            
            response = ollama.chat(**kwargs)
            
            content = response['message']['content']
            
            # Ollama provides token counts
            token_usage = {
                "input": response.get('prompt_eval_count', 0),
                "output": response.get('eval_count', 0),
                "total": response.get('prompt_eval_count', 0) + response.get('eval_count', 0)
            }
            
            logger.info(
                "llm_service:ollama_success",
                extra={"tokens_used": token_usage["total"]}
            )
            
            return {
                "content": content,
                "token_usage": token_usage,
                "model": model
            }
        
        except Exception as e:
            logger.error(
                "llm_service:ollama_error",
                extra={"error": str(e)}
            )
            raise LLMError(
                message=f"Ollama error: {str(e)}",
                error_code="OLLAMA_ERROR"
            ) from e


# Global service instance
_llm_service = LLMService()


async def call_llm_async(
    prompt: str,
    model: str,
    runtime: str,
    max_tokens: int,
    temperature: float = 0.1,
    trace_id: str = None,
    response_format: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """
    Call LLM asynchronously.
    
    Args:
        prompt: Prompt text
        model: Model name
        runtime: Runtime ('groq', 'gemini', 'anthropic', 'ollama')
        max_tokens: Maximum output tokens
        temperature: Temperature (default: 0.1)
        trace_id: Trace ID for logging
        response_format: Response format dict (e.g., {"type": "json_object"})
                        Only used if caller explicitly requests JSON
    
    Returns:
        Dict with content and token_usage
    
    Raises:
        LLMError: If runtime not supported or call fails
    """
    runtime = runtime.lower()
    
    # Route to appropriate provider
    if runtime == "groq":
        return await _llm_service.call_groq(prompt, model, max_tokens, temperature, response_format)
    elif runtime == "gemini":
        return await _llm_service.call_gemini(prompt, model, max_tokens, temperature, response_format)
    elif runtime == "anthropic":
        return await _llm_service.call_anthropic(prompt, model, max_tokens, temperature, response_format)
    elif runtime == "ollama":
        return await _llm_service.call_ollama(prompt, model, max_tokens, temperature, response_format)
    else:
        raise LLMError(
            message=f"Unsupported LLM runtime: {runtime}",
            error_code="UNSUPPORTED_RUNTIME",
            details={"runtime": runtime}
        )