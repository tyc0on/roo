"""
Skill Executor

Executes skill actions based on the skill definition.
"""
import re
from dataclasses import dataclass
from typing import Any, Optional

from .loader import Skill
from ..llm import chat, embed
from ..database import get_db


@dataclass
class SkillResult:
    """Result from skill execution."""
    success: bool
    message: str
    data: Optional[Any] = None
    error: Optional[str] = None


class SkillExecutor:
    """
    Executes skills based on their markdown definitions.
    
    The executor parses the skill content to determine:
    1. What parameters to extract from the user's message
    2. What database queries to run (including vector search)
    3. How to format the final response
    """
    
    async def execute(
        self,
        skill: Skill,
        text: str,
        user_id: str,
        channel_id: Optional[str] = None,
        thread_ts: Optional[str] = None,
        **kwargs
    ) -> SkillResult:
        """
        Execute a skill with the given context.
        
        Args:
            skill: The skill to execute
            text: User's message
            user_id: Slack user ID
            channel_id: Channel ID
            thread_ts: Thread timestamp
            **kwargs: Additional context
        
        Returns:
            SkillResult with message and optional data
        """
        print(f"🎯 Executing skill: {skill.name}")
        
        try:
            # Extract parameters using LLM
            params = await self._extract_parameters(skill, text)
            print(f"   Extracted params: {params}")
            
            # Execute skill-specific logic
            # For now, use a generic LLM-based execution
            result = await self._execute_with_llm(skill, text, params, user_id)
            
            return SkillResult(
                success=True,
                message=result,
                data=params
            )
            
        except Exception as e:
            print(f"❌ Skill execution failed: {e}")
            import traceback
            traceback.print_exc()
            
            return SkillResult(
                success=False,
                message="Sorry, I ran into a problem executing that skill. Can you try again?",
                error=str(e)
            )
    
    async def _extract_parameters(self, skill: Skill, text: str) -> dict:
        """Extract parameters from user message based on skill definition."""
        # Parse parameter definitions from skill content
        param_section = self._find_section(skill.content, "Parameters")
        
        if not param_section:
            return {}
        
        prompt = f"""Extract parameters from the user's message based on these definitions:

{param_section}

User message: "{text}"

Return a JSON object with the extracted parameters. Only include parameters that are clearly present.
Example: {{"query": "machine learning", "limit": 5}}

JSON:"""

        response = await chat([
            {"role": "system", "content": "You extract structured parameters from text. Return valid JSON only."},
            {"role": "user", "content": prompt}
        ])
        
        # Parse JSON from response
        import json
        try:
            # Clean up response - extract JSON if wrapped in markdown
            content = response.content.strip()
            if content.startswith("```"):
                content = re.sub(r'^```\w*\n?', '', content)
                content = re.sub(r'\n?```$', '', content)
            return json.loads(content)
        except json.JSONDecodeError:
            return {}
    
    async def _execute_with_llm(
        self,
        skill: Skill,
        text: str,
        params: dict,
        user_id: str
    ) -> str:
        """Execute the skill using LLM to follow the skill's instructions."""
        
        # Check if skill has vector search action
        has_vector_search = "vector" in skill.content.lower() or "embedding" in skill.content.lower()
        
        context = ""
        if has_vector_search and params.get("query"):
            # Perform vector search
            try:
                db = get_db()
                search_results = await db.vector_search(
                    query=params["query"],
                    table="user_expertise",
                    limit=params.get("limit", 5)
                )
                if search_results:
                    context = f"\n\nVector search results:\n{search_results}"
            except Exception as e:
                print(f"   Vector search failed: {e}")
        
        prompt = f"""You are Roo, executing the "{skill.name}" skill.

Skill description: {skill.description}

Skill instructions:
{skill.content}

User's original request: "{text}"
Extracted parameters: {params}
Requesting user ID: {user_id}
{context}

Follow the skill instructions to generate an appropriate response.
Be helpful, friendly, and use casual Australian expressions occasionally.
Keep the response concise but informative."""

        response = await chat([
            {"role": "system", "content": "You are Roo, a friendly AI assistant for the MLAI community."},
            {"role": "user", "content": prompt}
        ])
        
        return response.content
    
    def _find_section(self, content: str, section_name: str) -> Optional[str]:
        """Find a section in the markdown content."""
        pattern = rf'##\s*{section_name}\s*\n(.*?)(?=\n##|\Z)'
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None
