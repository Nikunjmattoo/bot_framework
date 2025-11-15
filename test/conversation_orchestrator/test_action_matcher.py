"""
Tests for action matcher fuzzy search.
"""
import pytest
from uuid import uuid4

from conversation_orchestrator.brain.action_matcher import (
    find_action_fuzzy,
    _exact_match,
    _fuzzy_match,
    _synonym_match
)
from db.models.actions import ActionModel


class TestActionMatcher:
    """Test action fuzzy matching strategies."""
    
    def test_exact_match_finds_action(self, db_session, test_instance, test_actions):
        """✓ Exact match finds action by canonical_name"""
        candidates = ["apply_job", "submit_application"]
        action, match_type = find_action_fuzzy(db_session, str(test_instance.id), candidates)
        
        assert action is not None
        assert action.canonical_name == "apply_job"
        assert match_type == "exact"
    
    def test_exact_match_case_sensitive(self, db_session, test_instance, test_actions):
        """✓ Exact match is case-sensitive"""
        candidates = ["Apply_Job"]  # Wrong case
        action, match_type = find_action_fuzzy(db_session, str(test_instance.id), candidates)
        
        # Should not find exact match, but fuzzy should catch it
        assert match_type in ["fuzzy", "not_found"]  # Depends on similarity threshold
    
    def test_fuzzy_match_finds_typo(self, db_session, test_instance, test_actions):
        """✓ Fuzzy match finds action with typo"""
        candidates = ["aply_job", "unknown"]  # Typo: aply instead of apply
        action, match_type = find_action_fuzzy(db_session, str(test_instance.id), candidates)
        
        assert action is not None
        assert action.canonical_name == "apply_job"
        assert match_type == "fuzzy"
    
    def test_fuzzy_match_respects_cutoff(self, db_session, test_instance, test_actions):
        """✓ Fuzzy match respects 0.8 cutoff threshold"""
        candidates = ["xyz", "completely_different"]
        action, match_type = find_action_fuzzy(db_session, str(test_instance.id), candidates)
        
        assert action is None
        assert match_type == "not_found"
    
    def test_synonym_match_finds_action(self, db_session, test_instance, test_actions):
        """✓ Synonym match finds action via config.synonyms"""
        # "submit_job_application" is in apply_job's synonyms
        candidates = ["submit_job_application", "unknown"]
        action, match_type = find_action_fuzzy(db_session, str(test_instance.id), candidates)
        
        assert action is not None
        assert action.canonical_name == "apply_job"
        assert match_type == "synonym"
    
    def test_synonym_match_case_insensitive(self, db_session, test_instance, test_actions):
        """✓ Synonym match is case-insensitive"""
        candidates = ["SUBMIT_JOB_APPLICATION"]  # All caps
        action, match_type = find_action_fuzzy(db_session, str(test_instance.id), candidates)
        
        assert action is not None
        assert match_type == "synonym"
    
    def test_tries_primary_candidate_first(self, db_session, test_instance, test_actions):
        """✓ Tries primary candidate before alternative"""
        candidates = ["apply_job", "view_profile"]
        action, match_type = find_action_fuzzy(db_session, str(test_instance.id), candidates)
        
        # Should match first candidate
        assert action.canonical_name == "apply_job"
        assert match_type == "exact"
    
    def test_falls_back_to_alternative(self, db_session, test_instance, test_actions):
        """✓ Falls back to alternative if primary not found"""
        candidates = ["unknown_action", "view_profile"]
        action, match_type = find_action_fuzzy(db_session, str(test_instance.id), candidates)
        
        # Should match second candidate
        assert action.canonical_name == "view_profile"
        assert match_type == "exact"
    
    def test_returns_not_found_when_no_match(self, db_session, test_instance, test_actions):
        """✓ Returns not_found when all strategies fail"""
        candidates = ["completely_unknown", "also_unknown"]
        action, match_type = find_action_fuzzy(db_session, str(test_instance.id), candidates)
        
        assert action is None
        assert match_type == "not_found"
    
    def test_handles_empty_candidates_list(self, db_session, test_instance, test_actions):
        """✓ Handles empty candidates list gracefully"""
        candidates = []
        action, match_type = find_action_fuzzy(db_session, str(test_instance.id), candidates)
        
        assert action is None
        assert match_type == "not_found"
    
    def test_handles_no_actions_for_instance(self, db_session, test_instance):
        """✓ Handles instance with no actions"""
        # Don't create test_actions
        candidates = ["apply_job"]
        action, match_type = find_action_fuzzy(db_session, str(test_instance.id), candidates)
        
        assert action is None
        assert match_type == "not_found"


# Fixtures needed for tests
@pytest.fixture
def test_actions(db_session, test_instance):
    """Create test actions for fuzzy matching tests."""
    actions = [
        ActionModel(
            instance_id=test_instance.id,
            canonical_name="apply_job",
            display_name="Apply for Job",
            action_type="BRAND_API",
            is_active=True,
            config={
                "synonyms": ["submit_job_application", "create_application"]
            },
            requires_auth=True,
            min_trust_score=0.0,
            timeout_ms=30000,
            is_undoable=False,
            is_repeatable=True
        ),
        ActionModel(
            instance_id=test_instance.id,
            canonical_name="view_profile",
            display_name="View Profile",
            action_type="SYSTEM_API",
            is_active=True,
            config={},
            requires_auth=True,
            min_trust_score=0.0,
            timeout_ms=30000,
            is_undoable=False,
            is_repeatable=True
        )
    ]
    
    db_session.add_all(actions)
    db_session.commit()
    
    for action in actions:
        db_session.refresh(action)
    
    return actions