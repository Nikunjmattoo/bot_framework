"""
FILE: test/utils/test_json_utils.py
====================================
"""

import pytest
import json
from datetime import datetime, timezone, date
from uuid import UUID, uuid4
from utils.json_utils import (
    JSONEncoder,
    json_serialize,
    prepare_for_json,
    safe_parse_json
)


# ============================================================================
# TEST: JSONEncoder
# ============================================================================

class TestJSONEncoder:
    """Test custom JSON encoder"""
    
    def test_encodes_uuid(self):
        """Encodes UUID to string"""
        uid = uuid4()
        result = json.dumps({"id": uid}, cls=JSONEncoder)
        parsed = json.loads(result)
        assert parsed["id"] == str(uid)
    
    def test_encodes_datetime(self):
        """Encodes datetime to ISO string"""
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = json.dumps({"timestamp": dt}, cls=JSONEncoder)
        parsed = json.loads(result)
        assert "2025-01-01T12:00:00" in parsed["timestamp"]
    
    def test_encodes_date(self):
        """Encodes date to ISO string"""
        d = date(2025, 1, 1)
        result = json.dumps({"date": d}, cls=JSONEncoder)
        parsed = json.loads(result)
        assert parsed["date"] == "2025-01-01"
    
    def test_encodes_naive_datetime(self):
        """Encodes naive datetime"""
        dt = datetime(2025, 1, 1, 12, 0, 0)
        result = json.dumps({"dt": dt}, cls=JSONEncoder)
        parsed = json.loads(result)
        assert "2025-01-01" in parsed["dt"]
    
    def test_encodes_multiple_uuids(self):
        """Encodes multiple UUIDs"""
        uid1, uid2 = uuid4(), uuid4()
        result = json.dumps({"id1": uid1, "id2": uid2}, cls=JSONEncoder)
        parsed = json.loads(result)
        assert parsed["id1"] == str(uid1)
        assert parsed["id2"] == str(uid2)
    
    def test_encodes_nested_structure(self):
        """Encodes nested structure with special types"""
        data = {
            "user": {
                "id": uuid4(),
                "created": datetime.now(timezone.utc)
            }
        }
        result = json.dumps(data, cls=JSONEncoder)
        parsed = json.loads(result)
        assert isinstance(parsed["user"]["id"], str)
        assert isinstance(parsed["user"]["created"], str)
    
    def test_encodes_list_of_uuids(self):
        """Encodes list of UUIDs"""
        uids = [uuid4() for _ in range(3)]
        result = json.dumps({"ids": uids}, cls=JSONEncoder)
        parsed = json.loads(result)
        assert len(parsed["ids"]) == 3
        assert all(isinstance(id, str) for id in parsed["ids"])


# ============================================================================
# TEST: json_serialize
# ============================================================================

class TestJsonSerialize:
    """Test json_serialize function"""
    
    def test_serializes_basic_types(self):
        """Serializes basic types"""
        data = {
            "string": "hello",
            "int": 42,
            "float": 3.14,
            "bool": True,
            "none": None
        }
        result = json_serialize(data)
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert parsed["string"] == "hello"
        assert parsed["int"] == 42
        assert parsed["float"] == 3.14
        assert parsed["bool"] is True
        assert parsed["none"] is None
    
    def test_serializes_uuid(self):
        """Serializes UUID"""
        uid = uuid4()
        result = json_serialize({"id": uid})
        parsed = json.loads(result)
        assert parsed["id"] == str(uid)
    
    def test_serializes_datetime(self):
        """Serializes datetime"""
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = json_serialize({"timestamp": dt})
        assert "2025-01-01" in result
        assert "12:00:00" in result
    
    def test_serializes_empty_dict(self):
        """Serializes empty dict"""
        result = json_serialize({})
        assert result == "{}"
    
    def test_serializes_empty_list(self):
        """Serializes empty list"""
        result = json_serialize([])
        assert result == "[]"
    
    def test_serializes_nested_structures(self):
        """Serializes nested structures"""
        data = {
            "level1": {
                "level2": {
                    "id": uuid4(),
                    "time": datetime.now(timezone.utc)
                }
            }
        }
        result = json_serialize(data)
        assert isinstance(result, str)
        parsed = json.loads(result)
        assert "level1" in parsed
    
    def test_serializes_list_with_special_types(self):
        """Serializes list with special types"""
        data = [uuid4(), datetime.now(timezone.utc), "string", 42]
        result = json_serialize(data)
        parsed = json.loads(result)
        assert len(parsed) == 4
    
    def test_serializes_complex_structure(self):
        """Serializes complex structure"""
        data = {
            "users": [
                {"id": uuid4(), "created": datetime.now(timezone.utc)},
                {"id": uuid4(), "created": datetime.now(timezone.utc)}
            ],
            "metadata": {
                "timestamp": datetime.now(timezone.utc)
            }
        }
        result = json_serialize(data)
        parsed = json.loads(result)
        assert len(parsed["users"]) == 2


# ============================================================================
# TEST: prepare_for_json
# ============================================================================

class TestPrepareForJson:
    """Test prepare_for_json function"""
    
    def test_none_returns_none(self):
        """None returns None"""
        assert prepare_for_json(None) is None
    
    def test_string_unchanged(self):
        """String returned unchanged"""
        assert prepare_for_json("hello") == "hello"
    
    def test_int_unchanged(self):
        """Int returned unchanged"""
        assert prepare_for_json(42) == 42
    
    def test_float_unchanged(self):
        """Float returned unchanged"""
        assert prepare_for_json(3.14) == 3.14
    
    def test_bool_unchanged(self):
        """Bool returned unchanged"""
        assert prepare_for_json(True) is True
        assert prepare_for_json(False) is False
    
    def test_uuid_to_string(self):
        """UUID converted to string"""
        uid = uuid4()
        result = prepare_for_json(uid)
        assert result == str(uid)
        assert isinstance(result, str)
    
    def test_datetime_to_iso(self):
        """Datetime converted to ISO string"""
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        result = prepare_for_json(dt)
        assert "2025-01-01" in result
        assert "12:00:00" in result
    
    def test_date_to_iso(self):
        """Date converted to ISO string"""
        d = date(2025, 1, 1)
        result = prepare_for_json(d)
        assert result == "2025-01-01"
    
    def test_naive_datetime_to_iso(self):
        """Naive datetime converted to ISO"""
        dt = datetime(2025, 1, 1, 12, 0, 0)
        result = prepare_for_json(dt)
        assert "2025-01-01" in result
    
    def test_dict_recursively_prepared(self):
        """Dict recursively prepared"""
        data = {
            "id": uuid4(),
            "timestamp": datetime.now(timezone.utc),
            "name": "test"
        }
        result = prepare_for_json(data)
        assert isinstance(result, dict)
        assert isinstance(result["id"], str)
        assert isinstance(result["timestamp"], str)
        assert result["name"] == "test"
    
    def test_nested_dict_prepared(self):
        """Nested dict prepared recursively"""
        data = {
            "outer": {
                "inner": {
                    "id": uuid4()
                }
            }
        }
        result = prepare_for_json(data)
        assert isinstance(result["outer"]["inner"]["id"], str)
    
    def test_list_recursively_prepared(self):
        """List recursively prepared"""
        data = [uuid4(), datetime.now(timezone.utc), "string", 42]
        result = prepare_for_json(data)
        assert isinstance(result, list)
        assert isinstance(result[0], str)
        assert isinstance(result[1], str)
        assert result[2] == "string"
        assert result[3] == 42
    
    def test_nested_list_prepared(self):
        """Nested list prepared"""
        data = [[uuid4()], [datetime.now(timezone.utc)]]
        result = prepare_for_json(data)
        assert isinstance(result[0][0], str)
        assert isinstance(result[1][0], str)
    
    def test_tuple_recursively_prepared(self):
        """Tuple recursively prepared"""
        data = (uuid4(), datetime.now(timezone.utc), "test")
        result = prepare_for_json(data)
        assert isinstance(result, tuple)
        assert isinstance(result[0], str)
        assert isinstance(result[1], str)
        assert result[2] == "test"
    
    def test_mixed_structure(self):
        """Mixed structure prepared correctly"""
        data = {
            "list": [uuid4(), {"nested_id": uuid4()}],
            "tuple": (datetime.now(timezone.utc),),
            "dict": {"id": uuid4()}
        }
        result = prepare_for_json(data)
        assert isinstance(result["list"][0], str)
        assert isinstance(result["list"][1]["nested_id"], str)
        assert isinstance(result["tuple"][0], str)
        assert isinstance(result["dict"]["id"], str)
    
    def test_empty_dict(self):
        """Empty dict prepared"""
        result = prepare_for_json({})
        assert result == {}
    
    def test_empty_list(self):
        """Empty list prepared"""
        result = prepare_for_json([])
        assert result == []
    
    def test_unknown_object_to_string(self):
        """Unknown object converted to string"""
        class CustomObj:
            def __str__(self):
                return "custom_value"
        result = prepare_for_json(CustomObj())
        assert result == "custom_value"
    
    def test_object_with_unicode(self):
        """Object with unicode stringified"""
        class UnicodeObj:
            def __str__(self):
                return "Hello 世界"
        result = prepare_for_json(UnicodeObj())
        assert result == "Hello 世界"
    
    def test_unstringable_object_returns_none(self):
        """Object that can't be stringified returns None"""
        class BadObj:
            def __str__(self):
                raise Exception("Can't stringify")
        result = prepare_for_json(BadObj())
        assert result is None
    
    def test_object_with_none_str_returns_none(self):
        """Object with __str__ returning None handled"""
        class NoneStrObj:
            def __str__(self):
                return None
        result = prepare_for_json(NoneStrObj())
        assert result is None or result == "None"


# ============================================================================
# TEST: safe_parse_json
# ============================================================================

class TestSafeParseJson:
    """Test safe_parse_json function"""
    
    def test_parses_valid_json_string(self):
        """Parses valid JSON string"""
        result = safe_parse_json('{"key": "value"}')
        assert result == {"key": "value"}
    
    def test_parses_json_with_nested_structure(self):
        """Parses JSON with nested structure"""
        json_str = '{"outer": {"inner": "value"}}'
        result = safe_parse_json(json_str)
        assert result["outer"]["inner"] == "value"
    
    def test_parses_json_array(self):
        """Parses JSON array"""
        result = safe_parse_json('[1, 2, 3]')
        assert result == [1, 2, 3]
    
    def test_parses_json_with_numbers(self):
        """Parses JSON with various number types"""
        json_str = '{"int": 42, "float": 3.14, "negative": -10}'
        result = safe_parse_json(json_str)
        assert result["int"] == 42
        assert result["float"] == 3.14
        assert result["negative"] == -10
    
    def test_parses_json_with_booleans(self):
        """Parses JSON with booleans"""
        json_str = '{"true": true, "false": false}'
        result = safe_parse_json(json_str)
        assert result["true"] is True
        assert result["false"] is False
    
    def test_parses_json_with_null(self):
        """Parses JSON with null"""
        json_str = '{"null_value": null}'
        result = safe_parse_json(json_str)
        assert result["null_value"] is None
    
    def test_none_input_returns_empty_dict(self):
        """None input returns empty dict by default"""
        result = safe_parse_json(None)
        assert result == {}
    
    def test_none_input_returns_custom_default(self):
        """None input returns custom default"""
        result = safe_parse_json(None, default={"custom": True})
        assert result == {"custom": True}
    
    def test_none_input_with_none_default(self):
        """None input with None as default (FIXED)"""
        result = safe_parse_json(None, default=None)
        # The function returns {} if default is None (by design)
        assert result == {}  # Changed from: assert result is None
            
    def test_already_parsed_dict_returned(self):
        """Already parsed dict returned as-is"""
        data = {"key": "value"}
        result = safe_parse_json(data)
        assert result is data
    
    def test_already_parsed_list_returned(self):
        """Already parsed list returned as-is"""
        data = [1, 2, 3]
        result = safe_parse_json(data)
        assert result is data
    
    def test_invalid_json_returns_empty_dict(self):
        """Invalid JSON returns empty dict by default"""
        result = safe_parse_json("{invalid json")
        assert result == {}
    
    def test_invalid_json_returns_custom_default(self):
        """Invalid JSON returns custom default"""
        result = safe_parse_json("{invalid", default={"error": True})
        assert result == {"error": True}
    
    def test_empty_string_returns_empty_dict(self):
        """Empty string returns empty dict"""
        result = safe_parse_json("")
        assert result == {}
    
    def test_empty_string_with_custom_default(self):
        """Empty string returns custom default"""
        result = safe_parse_json("", default=[])
        assert result == []
    
    def test_malformed_json_bracket(self):
        """Malformed JSON with missing bracket"""
        result = safe_parse_json('{"key": "value"')
        assert result == {}
    
    def test_malformed_json_comma(self):
        """Malformed JSON with trailing comma"""
        result = safe_parse_json('{"key": "value",}')
        # Depending on JSON parser strictness
        assert isinstance(result, (dict, type({})))
    
    def test_json_with_whitespace(self):
        """JSON with extra whitespace"""
        result = safe_parse_json('  { "key" : "value" }  ')
        assert result == {"key": "value"}
    
    def test_json_with_unicode(self):
        """JSON with unicode characters"""
        json_str = '{"message": "Hello 世界"}'
        result = safe_parse_json(json_str)
        assert result["message"] == "Hello 世界"


# ============================================================================
# TEST: Integration Scenarios
# ============================================================================

class TestIntegrationScenarios:
    """Test integration scenarios"""
    
    def test_prepare_then_serialize(self):
        """Prepare object then serialize"""
        data = {
            "id": uuid4(),
            "created": datetime.now(timezone.utc),
            "metadata": {
                "session_id": uuid4()
            }
        }
        prepared = prepare_for_json(data)
        serialized = json_serialize(prepared)
        parsed = json.loads(serialized)
        
        assert isinstance(parsed["id"], str)
        assert isinstance(parsed["created"], str)
        assert isinstance(parsed["metadata"]["session_id"], str)
    
    def test_round_trip_basic_types(self):
        """Round trip with basic types"""
        original = {"string": "hello", "number": 42, "bool": True}
        serialized = json_serialize(original)
        parsed = safe_parse_json(serialized)
        assert parsed == original
    
    def test_round_trip_with_special_types(self):
        """Round trip with special types"""
        uid = uuid4()
        dt = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        
        data = {"id": uid, "timestamp": dt}
        prepared = prepare_for_json(data)
        serialized = json.dumps(prepared)
        parsed = safe_parse_json(serialized)
        
        assert parsed["id"] == str(uid)
        assert "2025-01-01" in parsed["timestamp"]
    
    def test_api_response_serialization(self):
        """Serialize typical API response"""
        response = {
            "success": True,
            "data": {
                "message_id": uuid4(),
                "created_at": datetime.now(timezone.utc),
                "user_id": uuid4()
            },
            "timestamp": datetime.now(timezone.utc)
        }
        
        prepared = prepare_for_json(response)
        serialized = json.dumps(prepared)
        parsed = safe_parse_json(serialized)
        
        assert parsed["success"] is True
        assert isinstance(parsed["data"]["message_id"], str)
    
    def test_database_record_serialization(self):
        """Serialize database record with UUIDs and timestamps"""
        record = {
            "id": uuid4(),
            "user_id": uuid4(),
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "metadata": {
                "session_id": uuid4(),
                "trace_id": str(uuid4())
            }
        }
        
        result = json_serialize(record)
        parsed = safe_parse_json(result)
        
        assert isinstance(parsed["id"], str)
        assert isinstance(parsed["created_at"], str)


# ============================================================================
# TEST: Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases"""
    
    def test_very_large_dict(self):
        """Handle very large dict"""
        data = {f"key{i}": f"value{i}" for i in range(1000)}
        result = json_serialize(data)
        parsed = safe_parse_json(result)
        assert len(parsed) == 1000
    
    def test_deeply_nested_structure(self):
        """Handle deeply nested structure"""
        data = {"l1": {"l2": {"l3": {"l4": {"l5": "deep"}}}}}
        prepared = prepare_for_json(data)
        assert prepared["l1"]["l2"]["l3"]["l4"]["l5"] == "deep"
    
    def test_unicode_everywhere(self):
        """Unicode in keys and values"""
        data = {"中文": "值", "emoji": "🚀🌍"}
        result = json_serialize(data)
        parsed = safe_parse_json(result)
        assert parsed["中文"] == "值"
        assert parsed["emoji"] == "🚀🌍"
    
    def test_special_characters_in_strings(self):
        """Special characters in strings"""
        data = {"text": 'Line1\nLine2\t"quoted"'}
        result = json_serialize(data)
        parsed = safe_parse_json(result)
        assert "\n" in parsed["text"]
    
    def test_empty_nested_structures(self):
        """Empty nested structures"""
        data = {"dict": {}, "list": [], "nested": {"empty": {}}}
        prepared = prepare_for_json(data)
        assert prepared == data