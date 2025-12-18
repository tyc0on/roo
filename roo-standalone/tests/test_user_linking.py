"""
Test User Linking Logic

Tests that when awarding points to a user, the executor:
1. Checks if the Slack ID is already known via API
2. If not, fetches the user's email from Slack
3. Attempts to link the Slack ID to an existing user by email via API
"""
import sys
from unittest.mock import MagicMock

# MOCK DEPENDENCIES BEFORE IMPORT
sys.modules["sqlalchemy"] = MagicMock()
sys.modules["sqlalchemy.ext.asyncio"] = MagicMock()
sys.modules["httpx"] = MagicMock()
sys.modules["frontmatter"] = MagicMock()
sys.modules["pydantic"] = MagicMock()
sys.modules["pydantic_settings"] = MagicMock()
sys.modules["openai"] = MagicMock()
sys.modules["tenacity"] = MagicMock()
sys.modules["slack_sdk"] = MagicMock()
sys.modules["roo.config"] = MagicMock()

import asyncio
import unittest
from unittest.mock import patch, AsyncMock
import os
sys.path.append(os.getcwd())

# Verify we can import SkillExecutor
try:
    from roo.skills.executor import SkillExecutor
except ImportError as e:
    print(f"Import failed: {e}")
    sys.exit(1)

# Mock data
MOCK_SLACK_ID = "U12345"
MOCK_EMAIL = "test@example.com"
MOCK_DB_USER_ID = 42


class TestUserLinking(unittest.IsolatedAsyncioTestCase):
    
    async def test_user_linking_logic(self):
        """
        Test that the executor:
        1. Checks for Slack ID via API (fails)
        2. Fetches Slack info (gets email)
        3. Links Slack ID to user via API
        """
        
        # Mock API Client (used for user linking AND awarding)
        mock_client = AsyncMock()
        # 1. get_user_by_slack_id returns None (User not found by ID)
        mock_client.get_user_by_slack_id.return_value = None
        # 3. link_slack_user returns the user ID (linking succeeded)
        mock_client.link_slack_user.return_value = MOCK_DB_USER_ID
        # Award succeeds
        mock_client.award_points.return_value = {"new_balance": 100}
        
        # Mock Slack Client
        with patch("roo.skills.executor.SkillExecutor._execute_with_llm"), \
             patch("roo.skills.executor.post_message"), \
             patch("roo.slack_client.get_user_info") as mock_get_user_info:
            
            # 2. Setup Slack Mock to return email
            mock_get_user_info.return_value = {"email": MOCK_EMAIL}
            
            # Setup Executor
            executor = SkillExecutor()
            
            params = {
                "action": "award_points", 
                "points": 10, 
                "target_users": [MOCK_SLACK_ID],
                "reason": "Test linking"
            }
            
            mock_skill = MagicMock()
            mock_skill.name = "mlai-points"
            
            # Execute
            await executor._handle_points_action(
                client=mock_client,
                action="award_points",
                params=params,
                text=f"award 10 points to <@{MOCK_SLACK_ID}>",
                user_id="ADMIN_ID",
                channel_id="C1",
                thread_ts="t1",
                skill=mock_skill
            )
            
            # ASSERTIONS
            
            # 1. Verify get_user_by_slack_id was called
            mock_client.get_user_by_slack_id.assert_called_with(MOCK_SLACK_ID)
            
            # 2. Verify Slack email lookup happened
            mock_get_user_info.assert_called_with(MOCK_SLACK_ID)
            
            # 3. Verify link_slack_user was called with Slack ID and email
            mock_client.link_slack_user.assert_called_with(MOCK_SLACK_ID, MOCK_EMAIL)
            
            print("\n✅ Test Passed: User logic correctly identified email and linked Slack ID via API.")


if __name__ == "__main__":
    unittest.main()
