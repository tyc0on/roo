"""
Skill Executor

Executes skill actions based on the skill definition.
Follows Anthropic's Agent Skills pattern for execution.
"""
import re
import asyncio
from dataclasses import dataclass
from typing import Any, Optional

from .loader import Skill
from ..llm import chat, embed
from ..database import get_db
from ..slack_client import post_message
from ..config import get_settings


@dataclass
class SkillResult:
    """Result from skill execution."""
    success: bool
    message: str
    data: Optional[Any] = None
    error: Optional[str] = None


class SkillExecutor:
    """
    Executes skills based on their SKILL.md definitions.
    
    The executor:
    1. Extracts parameters from the user's message using LLM
    2. Routes to skill-specific handlers if available
    3. Falls back to generic LLM execution with skill instructions
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
            
            # Check for skill-specific implementation
            if skill.name == "content-factory":
                result = await self._execute_content_factory(skill, text, params, user_id, channel_id, thread_ts)
            elif skill.name == "connect-users":
                result = await self._execute_connect_users(skill, text, params, user_id)
            else:
                # Generic LLM-based execution
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
    
    async def _execute_connect_users(
        self,
        skill: Skill,
        text: str,
        params: dict,
        user_id: str
    ) -> str:
        """Execute the connect_users skill with vector search."""
        query = params.get("query", "")
        
        if not query:
            # Try to extract from the text directly
            query = text
        
        try:
            db = get_db()
            search_results = await db.vector_search(
                query=query,
                table="user_expertise",
                limit=params.get("limit", 5)
            )
            
            # Let LLM format the response with the results
            return await self._execute_with_llm(skill, text, {**params, "search_results": search_results}, user_id)
            
        except Exception as e:
            print(f"   Connect users search failed: {e}")
            return await self._execute_with_llm(skill, text, params, user_id)
    
    async def _execute_content_factory(
        self,
        skill: Skill,
        text: str,
        params: dict,
        user_id: str,
        channel_id: Optional[str],
        thread_ts: Optional[str]
    ) -> str:
        """Execute the content factory generation workflow."""
        domain = params.get("domain")
        topic = params.get("topic")
        target_keyword = params.get("target_keyword", "")
        
        if not domain or not topic:
            missing = []
            if not domain: missing.append("domain name (e.g., mlai.au)")
            if not topic: missing.append("topic for the article")
            
            return f"I can help write that article! To get started, I just need to know the {' and '.join(missing)}."
        
        # Get client from skill's implementation module
        ClientClass = skill.get_client_class("ContentFactoryClient")
        
        if ClientClass is None:
            return "Sorry mate, the Content Factory skill isn't properly configured. Missing implementation."
        
        try:
            settings = get_settings()
            client = ClientClass(
                base_url=settings.CONTENT_FACTORY_URL,
                api_key=settings.CONTENT_FACTORY_API_KEY
            )
            
            # Start generation
            job_id = await client.generate_article(
                domain=domain,
                topic=topic,
                target_keyword=target_keyword,
                context=text
            )
            
            # Launch background monitoring task
            if channel_id:
                asyncio.create_task(
                    self._monitor_generation(client, job_id, channel_id, thread_ts)
                )
            
            return f"You beauty! I've started writing the article '{topic}' for {domain}. (Job ID: {job_id})\nI'll keep you posted on the progress right here! 🚀"
            
        except Exception as e:
            print(f"Content Factory Error: {e}")
            return f"Sorry mate, I had trouble connecting to the Content Factory: {str(e)}"

    async def _monitor_generation(
        self,
        client,
        job_id: str,
        channel_id: str,
        thread_ts: Optional[str]
    ):
        """Monitor job progress and post updates to Slack."""
        last_progress = -1
        last_step = ""
        
        def on_progress(status):
            nonlocal last_progress, last_step
            progress = status.get("progress", 0)
            step = status.get("current_step", "")
            
            # Only update on meaningful change (every 20% or step change)
            should_update = (
                progress >= last_progress + 20 or 
                (step != last_step and step in ["researching", "writing", "optimizing", "publishing"])
            )
            
            if should_update:
                msg = f"📝 *Status Update*: {step.title()}... ({progress}%)"
                try:
                    post_message(channel_id, msg, thread_ts)
                    last_progress = progress
                    last_step = step
                except Exception as e:
                    print(f"Failed to post progress: {e}")

        try:
            # Poll until completion
            result = await client.poll_and_wait(job_id, on_progress)
            
            # Publish
            post_message(channel_id, "✨ Article generated! Publishing now...", thread_ts)
            
            publish_result = await client.publish_article(job_id)
            
            preview_url = publish_result.get("preview_url")
            pr_url = publish_result.get("pr_url")
            
            final_msg = (
                f"🎉 *Article Published!* \n\n"
                f"👀 *Preview:* {preview_url}\n"
                f"💻 *Pull Request:* {pr_url}\n\n"
                f"Review the content and merge the PR when you're ready!"
            )
            
            post_message(channel_id, final_msg, thread_ts)
            
        except Exception as e:
            error_msg = f"❌ Something went wrong with the article generation: {str(e)}"
            post_message(channel_id, error_msg, thread_ts)
    
    def _find_section(self, content: str, section_name: str) -> Optional[str]:
        """Find a section in the markdown content."""
        pattern = rf'##\s*{section_name}\s*\n(.*?)(?=\n##|\Z)'
        match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return None
