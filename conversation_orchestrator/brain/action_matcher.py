"""
Action matcher with fuzzy search.

Finds actions using 3 strategies: exact → fuzzy → synonym matching.
"""
from typing import List, Tuple, Optional
from sqlalchemy.orm import Session
from difflib import SequenceMatcher

from db.models.actions import ActionModel


def find_action_fuzzy(
    db: Session,
    instance_id: str,
    canonical_intent_candidates: List[str]
) -> Tuple[Optional[ActionModel], str]:
    """
    Find action using fuzzy matching on up to 2 candidates.
    
    Tries 3 strategies in order for each candidate:
    1. Exact match on canonical_name
    2. Fuzzy match using SequenceMatcher (cutoff 0.8)
    3. Synonym match in action.config['synonyms']
    
    Args:
        db: Database session
        instance_id: Instance UUID string
        canonical_intent_candidates: List of 1-2 candidates [primary, alternative]
    
    Returns:
        Tuple of (ActionModel or None, match_type)
        match_type is one of: "exact", "fuzzy", "synonym", "not_found"
    """
    # Get all active actions for this instance
    actions = db.query(ActionModel).filter(
        ActionModel.instance_id == instance_id,
        ActionModel.is_active == True
    ).all()
    
    if not actions:
        return (None, "not_found")
    
    # Try each candidate in order
    for candidate in canonical_intent_candidates:
        # Strategy 1: Exact match
        action = _exact_match(actions, candidate)
        if action:
            return (action, "exact")
        
        # Strategy 2: Fuzzy match
        action = _fuzzy_match(actions, candidate, cutoff=0.8)
        if action:
            return (action, "fuzzy")
        
        # Strategy 3: Synonym match
        action = _synonym_match(actions, candidate)
        if action:
            return (action, "synonym")
    
    # All strategies failed for all candidates
    return (None, "not_found")


def _exact_match(actions: List[ActionModel], candidate: str) -> Optional[ActionModel]:
    """
    Exact match on canonical_name.
    
    Args:
        actions: List of ActionModel objects
        candidate: Candidate name to match
    
    Returns:
        ActionModel if exact match found, else None
    """
    for action in actions:
        if action.canonical_name == candidate:
            return action
    return None


def _fuzzy_match(
    actions: List[ActionModel], 
    candidate: str, 
    cutoff: float = 0.8
) -> Optional[ActionModel]:
    """
    Fuzzy match using SequenceMatcher.
    
    Args:
        actions: List of ActionModel objects
        candidate: Candidate name to match
        cutoff: Minimum similarity ratio (0.0-1.0)
    
    Returns:
        ActionModel with highest similarity >= cutoff, else None
    """
    best_match = None
    best_score = 0.0
    
    for action in actions:
        ratio = SequenceMatcher(
            None, 
            candidate.lower(), 
            action.canonical_name.lower()
        ).ratio()
        
        if ratio >= cutoff and ratio > best_score:
            best_match = action
            best_score = ratio
    
    return best_match


def _synonym_match(actions: List[ActionModel], candidate: str) -> Optional[ActionModel]:
    """
    Match against synonyms in action.config['synonyms'].
    
    Args:
        actions: List of ActionModel objects
        candidate: Candidate name to match
    
    Returns:
        ActionModel if synonym match found, else None
    """
    candidate_lower = candidate.lower()
    
    for action in actions:
        synonyms = action.config.get('synonyms', [])
        # Convert all synonyms to lowercase for case-insensitive matching
        synonyms_lower = [s.lower() for s in synonyms]
        
        if candidate_lower in synonyms_lower:
            return action
    
    return None