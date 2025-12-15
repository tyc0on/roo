"""
Content Factory Client

HTTP client for the Content Factory article generation service.
"""
import time
from typing import Optional, Callable

import httpx

from ..config import get_settings


class ContentFactoryClient:
    """Client for Content Factory API."""
    
    def __init__(self):
        settings = get_settings()
        self.base_url = settings.CONTENT_FACTORY_URL
        self.api_key = settings.CONTENT_FACTORY_API_KEY
        
        if not self.base_url:
            raise ValueError("CONTENT_FACTORY_URL not configured")
    
    @property
    def headers(self) -> dict:
        return {
            "X-API-Key": self.api_key or "",
            "Content-Type": "application/json"
        }
    
    async def generate_article(
        self,
        domain: str,
        topic: str,
        target_keyword: str,
        context: Optional[str] = None
    ) -> str:
        """
        Start article generation job.
        
        Returns:
            job_id: The ID of the generation job
        """
        payload = {
            "domain": domain,
            "topic": topic,
            "target_keyword": target_keyword,
        }
        if context:
            payload["context"] = context
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/pipeline/generate",
                json=payload,
                headers=self.headers,
                timeout=30.0
            )
            response.raise_for_status()
            
            data = response.json()
            job_id = data.get("job_id")
            
            if not job_id:
                raise Exception("No job_id returned from generate endpoint")
            
            print(f"📝 Content generation started: {job_id}")
            return job_id
    
    async def get_job_status(self, job_id: str) -> dict:
        """Get current job status."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/pipeline/status/{job_id}",
                headers=self.headers,
                timeout=10.0
            )
            response.raise_for_status()
            return response.json()
    
    async def get_job_result(self, job_id: str) -> dict:
        """Get completed job result."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/api/pipeline/result/{job_id}",
                headers=self.headers,
                timeout=10.0
            )
            response.raise_for_status()
            return response.json().get("result", {})
    
    async def poll_and_wait(
        self,
        job_id: str,
        on_progress: Optional[Callable[[dict], None]] = None,
        poll_interval: float = 5.0
    ) -> dict:
        """
        Poll job until completion.
        
        Args:
            job_id: Job ID to poll
            on_progress: Optional callback for progress updates
            poll_interval: Seconds between polls
        
        Returns:
            Final job result
        """
        while True:
            status_data = await self.get_job_status(job_id)
            state = status_data["status"]
            progress = status_data.get("progress", 0)
            step = status_data.get("current_step", "unknown")
            
            print(f"   Status: {state} ({progress}%) - {step}")
            
            if on_progress:
                try:
                    on_progress(status_data)
                except Exception as e:
                    print(f"   Progress callback error: {e}")
            
            if state == "completed":
                break
            elif state == "failed":
                raise Exception(f"Job failed: {status_data.get('error', 'Unknown')}")
            
            await asyncio.sleep(poll_interval)
        
        return await self.get_job_result(job_id)
    
    async def publish_article(self, job_id: str) -> dict:
        """Publish a completed article."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/pipeline/publish/{job_id}",
                headers=self.headers,
                timeout=60.0
            )
            response.raise_for_status()
            
            data = response.json()
            
            if data.get("status") == "success":
                return {
                    "success": True,
                    **data.get("data", {})
                }
            else:
                raise Exception(f"Publish failed: {data.get('error')}")


import asyncio  # Import at bottom to avoid circular issues
