"""
Working test for summarizer - uses your actual project structure.
Run: python test_summarizer_final.py
"""

import asyncio
import sys
import os
from dotenv import load_dotenv
load_dotenv()
# Add to path
sys.path.insert(0, os.path.abspath('.'))

# Use YOUR actual imports
from conversation_orchestrator.services.summarizer_service import summarize_conversation
from conversation_orchestrator.services.db_service import fetch_template_config, save_session_summary


async def test_summarizer():
    """Test the summarizer with a sample conversation."""
    print("\n" + "="*60)
    print("SUMMARIZER TEST")
    print("="*60)
    
    messages = [
        {"role": "user", "content": "Hi, I'm looking for a software engineer job"},
        {"role": "assistant", "content": "Great! What's your experience level?"},
        {"role": "user", "content": "I have 5 years of Python experience"},
        {"role": "assistant", "content": "What type of company interests you?"},
        {"role": "user", "content": "I prefer startups with remote work"},
    ]
    
    print("\nTest Conversation:")
    for msg in messages:
        print(f"  {msg['role']}: {msg['content']}")
    
    print("\n" + "-"*60)
    print("Calling summarizer...")
    print("-"*60)
    
    try:
        summary = await summarize_conversation(
            messages=messages,
            goal="key facts about user intent and requirements",
            max_tokens=150,
            actions=None,
            trace_id="test-run"
        )
        
        if summary:
            print("\n✅ SUCCESS!")
            print("\nGenerated Summary:")
            print("-"*60)
            print(summary)
            print("-"*60)
            print(f"\nLength: {len(summary)} characters")
            return True
        else:
            print("\n❌ FAILED - Empty summary returned")
            print("Check if Groq API key is set")
            return False
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        print("\nFull error:")
        import traceback
        traceback.print_exc()
        return False


async def test_template_config():
    """Test fetching template config."""
    print("\n" + "="*60)
    print("TEMPLATE CONFIG TEST")
    print("="*60)
    
    try:
        config = await fetch_template_config('session_summary_v1')
        print("\n✅ Template config loaded:")
        print(f"  Provider: {config['provider']}")
        print(f"  Model: {config['model']}")
        print(f"  Temperature: {config['temperature']}")
        return True
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return False


async def main():
    """Run tests."""
    print("\n" + "="*60)
    print("SUMMARIZER TEST SUITE")
    print("="*60)
    
    # Test 1: Template config
    result1 = await test_template_config()
    
    # Test 2: Summarizer
    result2 = await test_summarizer()
    
    # Results
    print("\n" + "="*60)
    print("RESULTS")
    print("="*60)
    
    if result1:
        print("✅ Template config works")
    else:
        print("❌ Template config failed")
    
    if result2:
        print("✅ Summarizer works")
    else:
        print("❌ Summarizer failed")
    
    if result1 and result2:
        print("\n🎉 ALL TESTS PASSED - Summarizer is ready!")
    else:
        print("\n⚠️  Some tests failed - check errors above")


if __name__ == "__main__":
    asyncio.run(main())