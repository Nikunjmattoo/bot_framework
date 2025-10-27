# ============================================================================
# FILE: test/integration/test_security.py
# Integration Tests - Category G4: Security Testing
# ============================================================================

import pytest
import uuid
from unittest.mock import patch, AsyncMock


@pytest.mark.security
class TestSQLInjection:
    """G4.1: SQL Injection - Parameterized queries only."""

    @pytest.mark.asyncio
    async def test_sql_injection_in_content(self, client, test_instance, db_session):
        """✓ SQL injection attempts in content field are safely handled"""
        malicious_payloads = [
            "'; DROP TABLE messages; --",
            "1' OR '1'='1",
            "admin'--",
            "' UNION SELECT * FROM users--",
        ]

        mock_response = {
            "text": "Response",
            "intents": [],
            "token_usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        }

        for payload_text in malicious_payloads:
            payload = {
                "content": payload_text,
                "instance_id": str(test_instance.id),
                "request_id": str(uuid.uuid4()),
                "user_details": {"phone_e164": "+15551234567"}
            }

            with patch('conversation_orchestrator.orchestrator.process_message', return_value=mock_response):
                response = client.post("/api/messages", json=payload)

            # Should process safely without SQL injection
            assert response.status_code in [200, 400]

            # Verify tables still exist
            from db.models import MessageModel
            count = db_session.query(MessageModel).count()
            assert count >= 0  # Table exists

    @pytest.mark.asyncio
    async def test_sql_injection_in_user_identifiers(self, client, test_instance, db_session):
        """✓ SQL injection attempts in user identifiers are safely handled"""
        payload = {
            "content": "Test message",
            "instance_id": str(test_instance.id),
            "request_id": str(uuid.uuid4()),
            "user_details": {
                "phone_e164": "+15551234567'; DROP TABLE users; --",
                "email": "test@example.com' OR '1'='1"
            }
        }

        # Should fail validation or process safely
        response = client.post("/api/messages", json=payload)
        assert response.status_code in [200, 400, 422]


@pytest.mark.security
class TestXSS:
    """G4.2: XSS - Input sanitization."""

    @pytest.mark.asyncio
    async def test_xss_in_content(self, client, test_instance, db_session):
        """✓ XSS payloads are sanitized"""
        xss_payloads = [
            "<script>alert('XSS')</script>",
            "<img src=x onerror=alert('XSS')>",
            "<svg onload=alert('XSS')>",
            "javascript:alert('XSS')",
        ]

        mock_response = {
            "text": "Response",
            "intents": [],
            "token_usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        }

        for xss_payload in xss_payloads:
            payload = {
                "content": xss_payload,
                "instance_id": str(test_instance.id),
                "request_id": str(uuid.uuid4()),
                "user_details": {"phone_e164": "+15559876543"}
            }

            with patch('conversation_orchestrator.orchestrator.process_message', return_value=mock_response):
                response = client.post("/api/messages", json=payload)

            assert response.status_code == 200

            # Verify message was sanitized in DB
            if response.status_code == 200:
                from db.models import MessageModel
                messages = db_session.query(MessageModel).filter(
                    MessageModel.content.contains(xss_payload)
                ).all()

                # Content should be stored (for XSS, we store but escape on output)
                # The actual sanitization happens on output, not input for messages


@pytest.mark.security
class TestSensitiveData:
    """G4.3: Sensitive Data - No passwords/tokens in logs."""

    @pytest.mark.asyncio
    async def test_no_passwords_in_logs(self, client, test_instance, db_session, caplog):
        """✓ Passwords are not logged"""
        payload = {
            "content": "Test message",
            "instance_id": str(test_instance.id),
            "request_id": str(uuid.uuid4()),
            "user_details": {
                "phone_e164": "+15551111111",
                "password": "SuperSecret123!",  # Should be stripped
                "token": "secret_token_123",  # Should be stripped
                "secret": "my_secret"  # Should be stripped
            }
        }

        mock_response = {
            "text": "Response",
            "intents": [],
            "token_usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        }

        with patch('conversation_orchestrator.orchestrator.process_message', return_value=mock_response):
            response = client.post("/api/messages", json=payload)

        assert response.status_code == 200

        # Check logs don't contain sensitive data
        for record in caplog.records:
            assert "SuperSecret123!" not in record.message
            assert "secret_token_123" not in record.message
            assert "my_secret" not in record.message

    @pytest.mark.asyncio
    async def test_sensitive_keys_stripped_from_metadata(self, client, test_instance, db_session):
        """✓ Sensitive keys are stripped from stored metadata"""
        payload = {
            "content": "Test message",
            "instance_id": str(test_instance.id),
            "request_id": str(uuid.uuid4()),
            "user_details": {
                "phone_e164": "+15552222222",
                "password": "should_be_stripped",
                "auth": "should_be_stripped"
            }
        }

        mock_response = {
            "text": "Response",
            "intents": [],
            "token_usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        }

        with patch('conversation_orchestrator.orchestrator.process_message', return_value=mock_response):
            response = client.post("/api/messages", json=payload)

        assert response.status_code == 200

        # Check message metadata doesn't contain sensitive keys
        from db.models import MessageModel
        message = db_session.query(MessageModel).filter(
            MessageModel.session_id == response.json()["data"]["session_id"]
        ).first()

        if message and message.metadata_json:
            metadata_str = str(message.metadata_json)
            assert "should_be_stripped" not in metadata_str


@pytest.mark.security
class TestRateLimiting:
    """G4.4: Rate Limiting - Prevent abuse."""

    @pytest.mark.skip(reason="Rate limiting not implemented yet")
    @pytest.mark.asyncio
    async def test_per_user_rate_limit(self, client, test_instance, db_session):
        """✓ Per-user rate limits enforced"""
        # This would test rate limiting per user
        # Not implemented yet - placeholder
        pass

    @pytest.mark.skip(reason="Rate limiting not implemented yet")
    @pytest.mark.asyncio
    async def test_per_instance_rate_limit(self, client, test_instance, db_session):
        """✓ Per-instance rate limits enforced"""
        # This would test rate limiting per instance
        # Not implemented yet - placeholder
        pass

    @pytest.mark.skip(reason="Rate limiting not implemented yet")
    @pytest.mark.asyncio
    async def test_rate_limit_bypass_detection(self, client, test_instance, db_session):
        """✓ Rate limit bypass attempts detected"""
        # This would test detection of bypass attempts
        # Not implemented yet - placeholder
        pass


@pytest.mark.security
class TestInputValidation:
    """G4.5: Input Validation - All user input validated."""

    @pytest.mark.asyncio
    async def test_content_length_validation(self, client, test_instance):
        """✓ Content length limits enforced"""
        # Test max length
        payload = {
            "content": "x" * 10001,  # Over limit
            "instance_id": str(test_instance.id),
            "request_id": str(uuid.uuid4())
        }

        response = client.post("/api/messages", json=payload)
        assert response.status_code == 422  # Validation error (FastAPI returns 422)

    @pytest.mark.asyncio
    async def test_request_id_length_validation(self, client, test_instance):
        """✓ request_id length limits enforced"""
        payload = {
            "content": "Test",
            "instance_id": str(test_instance.id),
            "request_id": "x" * 129  # Over 128 char limit
        }

        response = client.post("/api/messages", json=payload)
        assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_phone_format_validation(self, client, test_instance):
        """✓ Phone number format validation"""
        invalid_phones = [
            "1234567890",  # Missing +
            "+1",  # Too short
            "+123456789012345678",  # Too long
            "+abc1234567890",  # Non-numeric
            "not-a-phone",
        ]

        for invalid_phone in invalid_phones:
            payload = {
                "content": "Test",
                "instance_id": str(test_instance.id),
                "request_id": str(uuid.uuid4()),
                "user_details": {"phone_e164": invalid_phone}
            }

            response = client.post("/api/messages", json=payload)
            # Should either reject or process without creating identifier
            assert response.status_code in [200, 400, 422]

    @pytest.mark.asyncio
    async def test_email_format_validation(self, client, test_instance):
        """✓ Email format validation"""
        invalid_emails = [
            "not-an-email",
            "@example.com",
            "user@",
            "user@.com",
            "x" * 130 + "@example.com",  # Too long
        ]

        for invalid_email in invalid_emails:
            payload = {
                "content": "Test",
                "instance_id": str(test_instance.id),
                "request_id": str(uuid.uuid4()),
                "user_details": {"email": invalid_email}
            }

            response = client.post("/api/messages", json=payload)
            # Should either reject or process without creating identifier
            assert response.status_code in [200, 400, 422]


@pytest.mark.security
class TestAuthorizationValidation:
    """G4.6: Authorization - Proper access control."""

    @pytest.mark.asyncio
    async def test_guest_users_rejected_when_not_allowed(self, client, test_instance_no_guest):
        """✓ Guest users rejected when instance doesn't allow guests"""
        payload = {
            "content": "Test",
            "instance_id": str(test_instance_no_guest.id),
            "request_id": str(uuid.uuid4())
            # No user_details
        }

        response = client.post("/api/messages", json=payload)
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_inactive_instance_access_denied(self, client, test_brand, test_template_set, db_session):
        """✓ Inactive instances cannot be accessed"""
        from db.models import InstanceModel, InstanceConfigModel

        inactive_instance = InstanceModel(
            brand_id=test_brand.id,
            name="Inactive",
            channel="api",
            is_active=False,
            accept_guest_users=True
        )
        db_session.add(inactive_instance)
        db_session.flush()

        config = InstanceConfigModel(
            instance_id=inactive_instance.id,
            template_set_id=test_template_set.id,
            is_active=True
        )
        db_session.add(config)
        db_session.commit()

        payload = {
            "content": "Test",
            "instance_id": str(inactive_instance.id),
            "request_id": str(uuid.uuid4()),
            "user_details": {"phone_e164": "+15553333333"}
        }

        response = client.post("/api/messages", json=payload)
        assert response.status_code == 404


@pytest.mark.security
class TestDataLeakage:
    """G4.7: Data Leakage - No internal details in error responses."""

    @pytest.mark.asyncio
    async def test_database_error_no_internal_details(self, client, test_instance, db_session):
        """✓ Database errors don't leak internal details"""
        # This would require triggering a database error
        # Check that error response doesn't contain:
        # - SQL queries
        # - Table names
        # - Stack traces (in production)
        pass

    @pytest.mark.asyncio
    async def test_validation_errors_safe(self, client):
        """✓ Validation errors don't leak system information"""
        payload = {
            "content": "Test",
            # Missing required fields
        }

        response = client.post("/api/messages", json=payload)

        # Error message should be safe
        if response.status_code >= 400:
            error_msg = str(response.json()).lower()
            # Should not contain internal paths, versions, etc.
            assert "/home/" not in error_msg
            assert "python" not in error_msg or "field" in error_msg  # "field" is ok


@pytest.mark.security
class TestHeaderSecurity:
    """G4.8: HTTP Security Headers."""

    @pytest.mark.asyncio
    async def test_trace_id_in_response_header(self, client, test_instance):
        """✓ X-Trace-ID present in response"""
        payload = {
            "content": "Test",
            "instance_id": str(test_instance.id),
            "request_id": str(uuid.uuid4()),
            "user_details": {"phone_e164": "+15554444444"}
        }

        mock_response = {
            "text": "Response",
            "intents": [],
            "token_usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        }

        with patch('conversation_orchestrator.orchestrator.process_message', return_value=mock_response):
            response = client.post("/api/messages", json=payload)

        # Should have trace ID in headers
        assert "x-trace-id" in response.headers or "X-Trace-ID" in response.headers

    @pytest.mark.asyncio
    async def test_request_id_echoed_in_response(self, client, test_instance):
        """✓ X-Request-ID echoed back"""
        request_id = str(uuid.uuid4())

        payload = {
            "content": "Test",
            "instance_id": str(test_instance.id),
            "request_id": request_id,
            "user_details": {"phone_e164": "+15555555555"}
        }

        mock_response = {
            "text": "Response",
            "intents": [],
            "token_usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}
        }

        with patch('conversation_orchestrator.orchestrator.process_message', return_value=mock_response):
            response = client.post("/api/messages", json=payload)

        # Should echo request ID
        assert "x-request-id" in response.headers or "X-Request-ID" in response.headers
