"""
Runway AI Image Generation Service

Handles AI-powered image generation for social media posts using Runway ML API.
Generates images based on captions and topics.
"""

import os
import asyncio
from typing import Dict, Optional, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging
from runwayml import RunwayML, TaskFailedError

from app.api.models.scheduled_posts import ScheduledPost
from app.api.models.job_queue import Job, JobType, JobStatus

logger = logging.getLogger(__name__)


class RunwayImageService:
    """Service for generating images using Runway ML API."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.api_key = os.getenv("RUNWAY_API_KEY")
        if not self.api_key:
            raise ValueError("RUNWAY_API_KEY environment variable not set")

        self.client = RunwayML(api_key=self.api_key)

    async def generate_image_prompt(
        self,
        caption: str,
        topic: Optional[str] = None,
        style: str = "realistic",
        aspect_ratio: str = "1:1"
    ) -> str:
        """
        Generate an optimized image generation prompt based on the post caption.

        Args:
            caption: The post caption/text
            topic: Optional topic/theme
            style: Image style (realistic, artistic, minimalist, vibrant)
            aspect_ratio: Aspect ratio (1:1 for Instagram posts)

        Returns:
            Optimized prompt for Runway image generation
        """
        # Extract key themes from caption
        words = caption.lower().split()

        # Common words to exclude
        stop_words = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'your', 'you', 'is', 'are', 'was', 'were'}
        keywords = [w.strip('.,!?#') for w in words if w not in stop_words and len(w) > 3][:5]

        # Build base prompt
        if topic:
            base_prompt = f"{topic}, "
        else:
            base_prompt = ""

        # Add caption context
        base_prompt += f"{' '.join(keywords[:3])}"

        # Style modifiers
        style_modifiers = {
            "realistic": "photorealistic, high quality, professional photography, 8k resolution",
            "artistic": "artistic, creative, beautiful composition, vibrant colors",
            "minimalist": "minimalist, clean, simple, elegant, modern",
            "vibrant": "vibrant colors, energetic, eye-catching, bold, dynamic"
        }

        # Combine into full prompt
        full_prompt = f"{base_prompt}, {style_modifiers.get(style, style_modifiers['realistic'])}, Instagram-worthy, high engagement potential"

        logger.info(f"Generated image prompt: {full_prompt}")
        return full_prompt

    async def generate_image(
        self,
        prompt: str,
        model: str = "gen4_image",
        ratio: str = "1024:1024"
    ) -> Dict:
        """
        Generate an image using Runway ML API.

        Args:
            prompt: The text prompt for image generation
            model: Runway model to use (gen4_image recommended)
            ratio: Image aspect ratio (1:1 for Instagram square)

        Returns:
            Dict containing:
                - image_url: URL of generated image
                - task_id: Runway task ID
                - generation_time: Time taken to generate
                - model: Model used
        """
        start_time = datetime.now()

        try:
            logger.info(f"Submitting Runway image generation for prompt: {prompt}")

            # Use Runway SDK to generate image
            # Run the blocking SDK call in a thread pool to keep it async
            loop = asyncio.get_event_loop()
            task = await loop.run_in_executor(
                None,
                lambda: self.client.text_to_image.create(
                    model=model,
                    ratio=ratio,
                    prompt_text=prompt
                ).wait_for_task_output()
            )

            generation_time = (datetime.now() - start_time).total_seconds()

            # Extract image URL from task output
            image_url = task.output[0] if task.output else None
            if not image_url:
                raise ValueError("No image URL in task output")

            logger.info(f"Image generated successfully: {image_url}")

            return {
                "image_url": image_url,
                "task_id": task.id,
                "generation_time": round(generation_time, 2),
                "model": model,
                "prompt": prompt
            }

        except TaskFailedError as e:
            logger.error(f"Runway task failed: {e.task_details}")
            raise RuntimeError(f"Runway generation failed: {e.task_details}")
        except Exception as e:
            logger.error(f"Error generating image with Runway: {str(e)}")
            raise

    async def generate_image_for_post(
        self,
        scheduled_post_id: int,
        style: str = "realistic",
        regenerate: bool = False
    ) -> Dict:
        """
        Generate an image for a scheduled post based on its caption.

        Args:
            scheduled_post_id: ID of the scheduled post
            style: Image style preference
            regenerate: Whether to regenerate even if image exists

        Returns:
            Dict containing image generation result and updated post
        """
        # Get the post
        stmt = select(ScheduledPost).where(ScheduledPost.id == scheduled_post_id)
        result = await self.db.execute(stmt)
        post = result.scalar_one_or_none()

        if not post:
            raise ValueError(f"Scheduled post {scheduled_post_id} not found")

        # Check if image already exists
        if post.image_url and not regenerate:
            logger.info(f"Post {scheduled_post_id} already has image, skipping generation")
            return {
                "status": "skipped",
                "reason": "Image already exists",
                "image_url": post.image_url
            }

        # Check if post has content
        if not post.content:
            raise ValueError(f"Post {scheduled_post_id} has no content/caption to generate image from")

        # Generate image prompt from caption
        image_prompt = await self.generate_image_prompt(
            caption=post.content,
            topic=post.topic if hasattr(post, 'topic') else None,
            style=style
        )

        # Generate image
        result = await self.generate_image(
            prompt=image_prompt,
            model="gen4_image",
            ratio="1024:1024"
        )

        # Update post with image URL
        post.image_url = result["image_url"]
        await self.db.commit()
        await self.db.refresh(post)

        logger.info(f"Updated post {scheduled_post_id} with generated image: {result['image_url']}")

        return {
            "status": "generated",
            "scheduled_post_id": scheduled_post_id,
            "image_url": result["image_url"],
            "image_prompt": image_prompt,
            "task_id": result["task_id"],
            "generation_time": result["generation_time"],
            "model": result["model"]
        }

    async def generate_images_for_pending_posts(
        self,
        account_id: Optional[int] = None,
        limit: int = 10,
        style: str = "realistic"
    ) -> List[Dict]:
        """
        Generate images for all posts that have captions but no images.

        Args:
            account_id: Optional filter by account ID
            limit: Maximum number of posts to process
            style: Image style preference

        Returns:
            List of generation results
        """
        # Query posts with content but no image
        stmt = select(ScheduledPost).where(
            ScheduledPost.content.isnot(None),
            ScheduledPost.image_url.is_(None)
        )

        if account_id:
            stmt = stmt.where(ScheduledPost.account_id == account_id)

        stmt = stmt.limit(limit)

        result = await self.db.execute(stmt)
        posts = result.scalars().all()

        logger.info(f"Found {len(posts)} posts needing images")

        results = []
        for post in posts:
            try:
                result = await self.generate_image_for_post(
                    scheduled_post_id=post.id,
                    style=style,
                    regenerate=False
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to generate image for post {post.id}: {str(e)}")
                results.append({
                    "status": "failed",
                    "scheduled_post_id": post.id,
                    "error": str(e)
                })

        return results
