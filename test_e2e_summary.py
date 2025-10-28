"""
End-to-end test: Send messages and verify summary generation.

This simulates:
1. Creating a session
2. Sending messages
3. Triggering cold path
4. Checking if summary was saved to DB
"""

import asyncio
import sys
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment
load_dotenv()
sys.path.insert(0, os.path.abspath('.'))

from db.db import get_db
from db.models.sessions import SessionModel
from db.models.messages import MessageModel
from conversation_orchestrator.cold_path.session_summary_generator import generate_session_summary


async def test_full_flow():
    """Test complete message flow with summary generation."""
    
    print("\n" + "="*60)
    print("END-TO-END SUMMARY TEST")
    print("="*60)
    
    db = next(get_db())
    
    try:
        # Step 1: Get or create a test session
        print("\n[Step 1] Getting test session...")
        
        session = db.query(SessionModel).first()
        
        if not session:
            print("❌ No sessions found in DB. Create a session first.")
            return False
        
        session_id = str(session.id)
        print(f"✅ Using session: {session_id}")
        
        # Step 2: Clear old summary
        print("\n[Step 2] Clearing old summary...")
        session.session_summary = None
        db.commit()
        print("✅ Old summary cleared")
        
        # Step 3: Create test conversation
        print("\n[Step 3] Creating test conversation...")
        
        test_messages = [
            {"role": "user", "content": "Hi, I need help finding an apartment in Austin"},
            {"role": "assistant", "content": "I'd be happy to help! What's your budget?"},
            {"role": "user", "content": "Around $1500 per month"},
            {"role": "assistant", "content": "Great! How many bedrooms do you need?"},
            {"role": "user", "content": "2 bedrooms would be perfect"},
        ]
        
        # Delete old messages for this session
        db.query(MessageModel).filter(MessageModel.session_id == session_id).delete()
        db.commit()
        
        # Add test messages
        for msg in test_messages:
            message = MessageModel(
                session_id=session_id,
                role=msg["role"],
                content=msg["content"],
                created_at=datetime.utcnow()
            )
            db.add(message)
        
        db.commit()
        print(f"✅ Added {len(test_messages)} messages to session")
        
        # Step 4: Fetch conversation history
        print("\n[Step 4] Fetching conversation history...")
        
        messages = db.query(MessageModel).filter(
            MessageModel.session_id == session_id
        ).order_by(MessageModel.created_at).all()
        
        conversation_history = [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]
        
        print(f"✅ Fetched {len(conversation_history)} messages")
        print("\nConversation:")
        for msg in conversation_history:
            print(f"  {msg['role']}: {msg['content'][:60]}...")
        
        # Step 5: Trigger summary generation (cold path)
        print("\n[Step 5] Generating summary...")
        print("-" * 60)
        
        await generate_session_summary(
            session_id=session_id,
            conversation_history=conversation_history,
            trace_id="end-to-end-test"
        )
        
        print("-" * 60)
        print("✅ Summary generation completed")
        
        # Step 6: Check if summary was saved
        print("\n[Step 6] Checking if summary was saved...")
        
        db.expire_all()  # Refresh from DB
        
        updated_session = db.query(SessionModel).filter(
            SessionModel.id == session_id
        ).first()
        
        if updated_session and updated_session.session_summary:
            print("✅ SUCCESS - Summary saved to database!")
            print("\n" + "="*60)
            print("GENERATED SUMMARY:")
            print("="*60)
            print(updated_session.session_summary)
            print("="*60)
            print(f"\nSummary length: {len(updated_session.session_summary)} characters")
            print(f"Updated at: {updated_session.updated_at}")
            return True
        else:
            print("❌ FAILED - Summary NOT saved to database")
            print("\nPossible issues:")
            print("  1. Cold path didn't run")
            print("  2. Summarizer returned empty string")
            print("  3. DB save failed")
            return False
    
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    finally:
        db.close()


async def main():
    """Run the test."""
    print("\n" + "="*60)
    print("TESTING SUMMARIZER IN PRODUCTION FLOW")
    print("="*60)
    print(f"Started at: {datetime.now()}")
    
    success = await test_full_flow()
    
    print("\n" + "="*60)
    if success:
        print("🎉 TEST PASSED - Summarizer is working end-to-end!")
    else:
        print("❌ TEST FAILED - Check errors above")
    print("="*60)
    print(f"Completed at: {datetime.now()}")


if __name__ == "__main__":
    asyncio.run(main())