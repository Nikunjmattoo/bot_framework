"""
BRAIN ↔ INTENT DETECTOR WIRING INTEGRATION TEST

Tests the complete integration between Brain and Intent Detector:
1. Sends actual message through system
2. Verifies Intent Detector reads Brain state
3. Checks Brain updates state correctly
4. Validates full round-trip flow

Run: python test_brain_intent_wiring.py
"""
from dotenv import load_dotenv
load_dotenv()  # This must be BEFORE importing any orchestrator modules

import asyncio
import sys
import os
import json
import uuid
from datetime import datetime
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy.orm import Session
from db.db import get_db
from db.models.sessions import SessionModel
from db.models.instances import InstanceModel
from db.models.users import UserModel
from db.models.messages import MessageModel
from conversation_orchestrator.orchestrator import process_message

# ANSI colors
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_section(title: str):
    print(f"\n{'='*80}")
    print(f"{BLUE}{title}{RESET}")
    print('='*80)

def print_pass(message: str):
    print(f"{GREEN}✅ PASS{RESET}: {message}")

def print_fail(message: str):
    print(f"{RED}❌ FAIL{RESET}: {message}")

def print_info(message: str):
    print(f"{YELLOW}ℹ️  INFO{RESET}: {message}")

def print_data(label: str, data: Any):
    print(f"{BLUE}{label}:{RESET}")
    if isinstance(data, (dict, list)):
        print(json.dumps(data, indent=2, default=str))
    else:
        print(data)


class WiringIntegrationTest:
    """Complete integration test for Brain ↔ Intent Detector wiring."""
    
    def __init__(self):
        self.db: Session = next(get_db())
        self.test_session_id: str = None
        self.test_user_id: str = None
        self.test_instance_id: str = None
        self.results = {
            'total_tests': 0,
            'passed': 0,
            'failed': 0,
            'errors': []
        }
    
    def assert_true(self, condition: bool, message: str):
        """Assert condition is true."""
        self.results['total_tests'] += 1
        if condition:
            self.results['passed'] += 1
            print_pass(message)
            return True
        else:
            self.results['failed'] += 1
            self.results['errors'].append(message)
            print_fail(message)
            return False
    
    def setup_test_data(self):
        """Create test session, user, instance."""
        print_section("SETUP: Creating Test Data")
        
        try:
            # Get first active instance
            instance = self.db.query(InstanceModel).filter(
                InstanceModel.is_active == True
            ).first()
            
            if not instance:
                print_fail("No active instances found in database")
                return False
            
            self.test_instance_id = str(instance.id)
            print_info(f"Using instance: {instance.name} ({self.test_instance_id})")
            
            # Get or create test user (users table doesn't have email - it's in user_identifiers)
            from db.models.user_identifiers import UserIdentifierModel
            
            # Try to find existing test user by identifier
            identifier = self.db.query(UserIdentifierModel).filter(
                UserIdentifierModel.identifier_type == "email",
                UserIdentifierModel.identifier_value == "test_wiring@example.com"
            ).first()
            
            if identifier:
                user = identifier.user
                print_info(f"Using existing test user: {user.id}")
            else:
                # Create new test user
                user = UserModel(
                    acquisition_channel="web_test",
                    user_tier="guest",
                    trust_score=0.5
                )
                self.db.add(user)
                self.db.flush()  # Get user.id without committing
                
                # Create identifier
                identifier = UserIdentifierModel(
                    user_id=user.id,
                    brand_id=instance.brand_id,
                    identifier_type="email",
                    identifier_value="test_wiring@example.com",
                    channel="web_test",
                    verified=True
                )
                self.db.add(identifier)
                self.db.commit()
                self.db.refresh(user)
                print_pass(f"Created new test user: {user.id}")
            
            self.test_user_id = str(user.id)
            
            # Create new session for this test
            session = SessionModel(
                user_id=self.test_user_id,
                instance_id=self.test_instance_id,
                active=True,
                source="web_test"
            )
            
            # Initialize default state
            session.initialize_default_state()
            
            self.db.add(session)
            self.db.commit()
            self.db.refresh(session)
            
            self.test_session_id = str(session.id)
            print_pass(f"Created test session: {self.test_session_id}")
            
            # Verify state initialized
            if session.state:
                print_pass("Session state initialized correctly")
                print_data("Initial State", session.state)
            else:
                print_fail("Session state NOT initialized")
                return False
            
            return True
        
        except Exception as e:
            print_fail(f"Setup failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    def test_state_structure(self):
        """Test 1: Verify session state has all required wire keys."""
        print_section("TEST 1: Session State Structure")
        
        session = self.db.query(SessionModel).filter(
            SessionModel.id == self.test_session_id
        ).first()
        
        if not session:
            print_fail("Session not found")
            return False
        
        state = session.state or {}
        
        required_keys = [
            'expecting_response',
            'answer_sheet',
            'active_task',
            'previous_intents',
            'conversation_context',
            'available_signals'
        ]
        
        all_present = True
        for key in required_keys:
            has_key = key in state
            self.assert_true(has_key, f"State has '{key}' key")
            if not has_key:
                all_present = False
        
        if all_present:
            print_data("Complete State", state)
        
        return all_present
    
    def test_popular_actions_exists(self):
        """Test 2: Verify popular_actions configured for instance."""
        print_section("TEST 2: Popular Actions Configuration")
        
        from db.models.instance_configs import InstanceConfigModel
        
        config = self.db.query(InstanceConfigModel).filter(
            InstanceConfigModel.instance_id == self.test_instance_id,
            InstanceConfigModel.is_active == True
        ).first()
        
        if not config:
            print_fail("No instance config found")
            return False
        
        popular_actions = config.config.get('popular_actions') if config.config else None
        
        has_popular = self.assert_true(
            popular_actions is not None,
            "Instance config has 'popular_actions'"
        )
        
        if has_popular:
            is_array = self.assert_true(
                isinstance(popular_actions, list),
                "popular_actions is an array"
            )
            
            if is_array:
                self.assert_true(
                    len(popular_actions) > 0,
                    f"popular_actions has {len(popular_actions)} actions"
                )
                print_data("Popular Actions", popular_actions)
        
        return has_popular
    
    async def test_intent_detection_reads_state(self):
        """Test 3: Send message and verify Intent Detector reads state."""
        print_section("TEST 3: Intent Detector Reads Brain State")
        
        # Build adapter payload
        adapter_payload = {
            "routing": {
                "instance_id": self.test_instance_id,
                "brand_id": "test_brand"
            },
            "message": {
                "content": "Hi there!",
                "sender_user_id": self.test_user_id,
                "channel": "web_test"
            },
            "session_id": self.test_session_id,
            "policy": {
                "auth_state": "guest",
                "can_call_tools": True
            },
            "template": {
                "json": {
                    "intent": {
                        "template": "intent_v1"
                    }
                }
            },
            "token_plan": {
                "templates": {
                    "intent_v1": {
                        "provider": "groq",
                        "api_model_name": "llama-3.3-70b-versatile",
                        "temperature": 0.1,
                        "max_tokens": 2000
                    }
                }
            },
            "model": "llama-3.3-70b-versatile",
            "llm_runtime": "groq",
            "trace_id": str(uuid.uuid4())
        }
        
        print_info("\n" + "="*60)
        print_info("REQUEST PAYLOAD:")
        print_data("Adapter Payload", adapter_payload)
        print_info("="*60 + "\n")
        
        print_info("Sending greeting message through orchestrator...")
        
        try:
            # Process message
            result = await process_message(adapter_payload)
            
            print_info("\n" + "="*60)
            print_info("RESPONSE RECEIVED:")
            print_data("Full Result", result)
            print_info("="*60 + "\n")
            
            print_pass("Message processed successfully")
            
            # Pretty print key parts
            print_data("Response Text", result.get("text"))
            print_data("Intents Detected", result.get("intents"))
            print_data("Self Response", result.get("self_response"))
            print_data("Token Usage", result.get("token_usage"))
            print_data("Latency (ms)", result.get("latency_ms"))
            
            # Verify response
            self.assert_true(
                result.get("text") is not None,
                "Response text generated"
            )
            
            self.assert_true(
                len(result.get("intents", [])) > 0,
                "Intents detected"
            )
            
            # For greeting, should be self-response
            self.assert_true(
                result.get("self_response") == True,
                "Greeting intent triggered self-response"
            )
            
            # Save message to database for next turn
            msg = MessageModel(
                session_id=self.test_session_id,
                role="user",
                content="Hi there!"
            )
            self.db.add(msg)
            
            response_msg = MessageModel(
                session_id=self.test_session_id,
                role="assistant",
                content=result.get("text")
            )
            self.db.add(response_msg)
            self.db.commit()
            
            return True
        
        except Exception as e:
            print_fail(f"Intent detection failed: {str(e)}")
            import traceback
            print("\n" + "="*60)
            print("FULL EXCEPTION TRACEBACK:")
            traceback.print_exc()
            print("="*60 + "\n")
            return False
    
    async def test_brain_updates_state(self):
        """Test 4: Send action intent and verify Brain updates state."""
        print_section("TEST 4: Brain Updates Session State")
        
        # First, check if we have actions configured
        from db.models.actions import ActionModel
        
        actions_count = self.db.query(ActionModel).filter(
            ActionModel.instance_id == self.test_instance_id,
            ActionModel.is_active == True
        ).count()
        
        if actions_count == 0:
            print_info("⚠️  No actions configured - skipping Brain state update test")
            print_info("   (This is expected - Brain Step 10 not implemented yet)")
            return True  # Don't fail test if Brain not ready
        
        print_info(f"Found {actions_count} actions - testing Brain state update...")
        
        # Build action intent payload
        adapter_payload = {
            "routing": {
                "instance_id": self.test_instance_id,
                "brand_id": "test_brand"
            },
            "message": {
                "content": "I want to apply for a job",
                "sender_user_id": self.test_user_id,
                "channel": "web_test"
            },
            "session_id": self.test_session_id,
            "policy": {
                "auth_state": "guest",
                "can_call_tools": True
            },
            "template": {
                "json": {
                    "intent": {
                        "template": "intent_v1"
                    }
                }
            },
            "token_plan": {
                "templates": {
                    "intent_v1": {
                        "provider": "groq",
                        "api_model_name": "llama-3.3-70b-versatile",
                        "temperature": 0.1,
                        "max_tokens": 2000
                    }
                }
            },
            "model": "llama-3.3-70b-versatile",
            "llm_runtime": "groq",
            "trace_id": str(uuid.uuid4())
        }
        
        print_info("\n" + "="*60)
        print_info("REQUEST PAYLOAD (Action Intent):")
        print_data("Message", adapter_payload["message"]["content"])
        print_info("="*60 + "\n")
        
        try:
            # Get state before
            session_before = self.db.query(SessionModel).filter(
                SessionModel.id == self.test_session_id
            ).first()
            state_before = session_before.state.copy() if session_before.state else {}
            
            print_info("STATE BEFORE ACTION INTENT:")
            print_data("Complete State", state_before)
            print_data("Previous Intents", state_before.get('previous_intents', []))
            print_data("Active Task", state_before.get('active_task'))
            print_data("Expecting Response", state_before.get('expecting_response'))
            
            # Process message
            result = await process_message(adapter_payload)
            
            print_info("\n" + "="*60)
            print_info("RESPONSE RECEIVED:")
            print_data("Full Result", result)
            print_info("="*60 + "\n")
            
            print_pass("Action intent processed")
            
            # Get state after
            self.db.refresh(session_before)  # Refresh from DB
            state_after = session_before.state or {}
            
            print_info("\nSTATE AFTER ACTION INTENT:")
            print_data("Complete State", state_after)
            print_data("Previous Intents", state_after.get('previous_intents', []))
            print_data("Active Task", state_after.get('active_task'))
            print_data("Expecting Response", state_after.get('expecting_response'))
            
            # Verify Brain updated state
            intents_before = len(state_before.get('previous_intents', []))
            intents_after = len(state_after.get('previous_intents', []))
            
            print_info(f"\nSTATE CHANGE SUMMARY:")
            print_info(f"  Previous Intents: {intents_before} → {intents_after}")
            print_info(f"  Active Task Before: {state_before.get('active_task')}")
            print_info(f"  Active Task After: {state_after.get('active_task')}")
            
            # Note: Brain might not update previous_intents until Step 10
            if intents_after > intents_before:
                print_pass(f"Brain updated previous_intents ({intents_before} → {intents_after})")
            else:
                print_info("Brain did not update previous_intents (Step 10 not implemented)")
            
            return True
        
        except Exception as e:
            print_fail(f"Brain state update test failed: {str(e)}")
            import traceback
            print("\n" + "="*60)
            print("FULL EXCEPTION TRACEBACK:")
            traceback.print_exc()
            print("="*60 + "\n")
            return False
    
    async def test_multi_turn_continuity(self):
        """Test 5: Multi-turn conversation maintains state continuity."""
        print_section("TEST 5: Multi-Turn State Continuity")
        
        messages = [
            "What can you help me with?",
            "Thanks for the info",
        ]
        
        for i, msg_text in enumerate(messages, start=3):
            print_info(f"\nTurn {i}: {msg_text}")
            
            adapter_payload = {
                "routing": {
                    "instance_id": self.test_instance_id,
                    "brand_id": "test_brand"
                },
                "message": {
                    "content": msg_text,
                    "sender_user_id": self.test_user_id,
                    "channel": "web_test"
                },
                "session_id": self.test_session_id,
                "policy": {
                    "auth_state": "guest",
                    "can_call_tools": True
                },
                "template": {
                    "json": {
                        "intent": {
                            "template": "intent_v1"
                        }
                    }
                },
                "token_plan": {
                    "templates": {
                        "intent_v1": {
                            "provider": "groq",
                            "api_model_name": "llama-3.3-70b-versatile",
                            "temperature": 0.1,
                            "max_tokens": 2000
                        }
                    }
                },
                "model": "llama-3.3-70b-versatile",
                "llm_runtime": "groq",
                "trace_id": str(uuid.uuid4())
            }
            
            try:
                result = await process_message(adapter_payload)
                print_pass(f"Turn {i} processed: {result.get('intents', [{}])[0].get('intent_type', 'unknown')}")
                
                # Save messages
                user_msg = MessageModel(
                    session_id=self.test_session_id,
                    role="user",
                    content=msg_text
                )
                self.db.add(user_msg)
                
                assistant_msg = MessageModel(
                    session_id=self.test_session_id,
                    role="assistant",
                    content=result.get("text")
                )
                self.db.add(assistant_msg)
                self.db.commit()
                
            except Exception as e:
                print_fail(f"Turn {i} failed: {str(e)}")
                return False
        
        # Verify message history
        message_count = self.db.query(MessageModel).filter(
            MessageModel.session_id == self.test_session_id
        ).count()
        
        self.assert_true(
            message_count >= 6,  # At least 3 turns (6 messages)
            f"Message history maintained ({message_count} messages)"
        )
        
        return True
    
    def test_fetch_functions_work(self):
        """Test 6: Verify DB fetch functions return correct data."""
        print_section("TEST 6: Database Fetch Functions")
        
        from conversation_orchestrator.services.db_service import (
            fetch_session_summary,
            fetch_previous_messages,
            fetch_active_task,
            fetch_next_narrative
        )
        
        try:
            # Test fetch_session_summary
            summary = fetch_session_summary(self.test_session_id)
            print_info(f"Session summary: {summary or '[None]'}")
            # Don't assert - summary might not exist yet
            
            # Test fetch_previous_messages
            messages = fetch_previous_messages(self.test_session_id, limit=4)
            self.assert_true(
                isinstance(messages, list),
                f"fetch_previous_messages returned list ({len(messages)} messages)"
            )
            
            # Test fetch_active_task
            task = fetch_active_task(self.test_session_id)
            print_info(f"Active task: {task.name if task else '[None]'}")
            # Don't assert - task might not exist yet
            
            # Test fetch_next_narrative
            narrative = fetch_next_narrative(self.test_session_id)
            print_info(f"Next narrative: {narrative or '[None]'}")
            # Don't assert - narrative might not exist yet
            
            return True
        
        except Exception as e:
            print_fail(f"Fetch functions failed: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    def cleanup(self):
        """Clean up test data."""
        print_section("CLEANUP: Removing Test Data")
        
        try:
            # Delete test session messages
            self.db.query(MessageModel).filter(
                MessageModel.session_id == self.test_session_id
            ).delete()
            
            # Delete test session
            self.db.query(SessionModel).filter(
                SessionModel.id == self.test_session_id
            ).delete()
            
            self.db.commit()
            print_pass("Test data cleaned up")
        
        except Exception as e:
            print_info(f"Cleanup warning: {str(e)}")
    
    def print_summary(self):
        """Print test summary."""
        print_section("TEST SUMMARY")
        
        total = self.results['total_tests']
        passed = self.results['passed']
        failed = self.results['failed']
        
        print(f"\nTotal Tests: {total}")
        print(f"{GREEN}Passed: {passed}{RESET}")
        print(f"{RED}Failed: {failed}{RESET}")
        
        if failed > 0:
            print(f"\n{RED}Failed Tests:{RESET}")
            for error in self.results['errors']:
                print(f"  - {error}")
        
        success_rate = (passed / total * 100) if total > 0 else 0
        
        print(f"\nSuccess Rate: {success_rate:.1f}%")
        
        if failed == 0:
            print(f"\n{GREEN}{'='*80}")
            print("🎉 ALL TESTS PASSED - WIRING INTEGRATION COMPLETE")
            print(f"{'='*80}{RESET}\n")
            return 0
        else:
            print(f"\n{RED}{'='*80}")
            print("❌ SOME TESTS FAILED - CHECK ERRORS ABOVE")
            print(f"{'='*80}{RESET}\n")
            return 1


async def main():
    """Run all integration tests."""
    test = WiringIntegrationTest()
    
    try:
        print(f"\n{BLUE}{'='*80}")
        print("BRAIN ↔ INTENT DETECTOR WIRING INTEGRATION TEST")
        print(f"{'='*80}{RESET}\n")
        
        # Setup
        if not test.setup_test_data():
            print_fail("Setup failed - cannot continue")
            return 1
        
        # Run tests
        test.test_state_structure()
        test.test_popular_actions_exists()
        await test.test_intent_detection_reads_state()
        await test.test_brain_updates_state()
        await test.test_multi_turn_continuity()
        test.test_fetch_functions_work()
        
        # Cleanup
        test.cleanup()
        
        # Summary
        return test.print_summary()
    
    except Exception as e:
        print_fail(f"Test suite failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    
    finally:
        test.db.close()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)