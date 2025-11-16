"""
AI-powered content generation service.
Analyzes user's Instagram style and generates matching captions using OpenAI.
"""

import re
import time
from collections import Counter
from datetime import datetime
from typing import Dict, Optional, List
from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
import os

from app.api.models.posts import Post
from app.api.models.scheduled_posts import ScheduledPost
from app.services.runway_image_service import RunwayImageService


class ContentGenerationService:
    """Service for AI-powered content generation."""

    def __init__(self, db: AsyncSession):
        """
        Initialize content generation service.

        Args:
            db: Database session
        """
        self.db = db
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")

        self.client = AsyncOpenAI(api_key=self.openai_api_key)
        self.model = os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
        self.max_tokens = int(os.getenv('OPENAI_MAX_TOKENS', '300'))

    async def analyze_user_style(self, account_id: int) -> Dict:
        """
        Analyze user's Instagram style from top-performing posts.

        Args:
            account_id: Social account ID

        Returns:
            Dictionary with style characteristics:
            {
                "tone": "casual" | "professional" | "inspirational",
                "avg_caption_length": 150,
                "common_hashtags": ["#ai", "#tech"],
                "emoji_frequency": 0.3,
                "avg_hashtag_count": 5,
                "sample_captions": ["...", "..."]
            }
        """
        # Fetch top-performing posts
        query = (
            select(Post)
            .where(Post.account_id == account_id)
            .where(Post.content.isnot(None))
            .order_by(desc(Post.engagement_score))
            .limit(20)
        )
        result = await self.db.execute(query)
        top_posts = result.scalars().all()

        if not top_posts:
            return self._default_style()

        # Analyze patterns
        total_posts = len(top_posts)
        captions = [p.content for p in top_posts if p.content]

        # Calculate average caption length
        avg_length = sum(len(c) for c in captions) / len(captions) if captions else 120

        # Extract and count hashtags
        all_hashtags = []
        for caption in captions:
            hashtags = re.findall(r'#\w+', caption)
            all_hashtags.extend(hashtags)

        avg_hashtag_count = len(all_hashtags) / len(captions) if captions else 3
        common_hashtags = [tag for tag, _ in Counter(all_hashtags).most_common(10)]

        # Check emoji usage
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "]+", flags=re.UNICODE
        )
        posts_with_emoji = sum(1 for c in captions if emoji_pattern.search(c))
        emoji_frequency = posts_with_emoji / len(captions) if captions else 0.3

        # Determine tone (simplified heuristic)
        tone = "casual"
        if avg_length > 300:
            tone = "professional"
        elif avg_length > 200:
            tone = "inspirational"

        return {
            "tone": tone,
            "avg_caption_length": int(avg_length),
            "common_hashtags": common_hashtags,
            "emoji_frequency": round(emoji_frequency, 2),
            "avg_hashtag_count": int(avg_hashtag_count),
            "sample_captions": captions[:3]  # Use top 3 as examples
        }

    async def generate_post_idea(self, account_id: int, content_type: str = "IMAGE") -> Dict:
        """
        Generate a creative post idea/topic based on user's content style.

        Args:
            account_id: Social account ID
            content_type: IMAGE, VIDEO, CAROUSEL, REEL

        Returns:
            {
                "topic": "Post topic/idea",
                "description": "Brief description",
                "suggested_sentiment": "engaging/inspirational/educational/funny"
            }
        """
        style = await self.analyze_user_style(account_id)

        # Extract themes from user's top posts
        sample_themes = []
        if style.get('sample_captions'):
            for caption in style['sample_captions'][:3]:
                # Extract first few words as theme indicators
                words = caption.split()[:10]
                sample_themes.append(' '.join(words))

        prompt = f"""Based on this Instagram account's style, generate ONE creative and specific post idea.

Account Style:
- Tone: {style['tone']}
- Common hashtags: {', '.join(style['common_hashtags'][:5])}
- Sample content themes: {'; '.join(sample_themes) if sample_themes else 'lifestyle and inspiration'}

Generate a SPECIFIC, CREATIVE post idea for a {content_type}. Make it:
1. Unique and interesting (not generic)
2. Aligned with the account's style
3. Actionable and visual
4. Engaging for followers

Respond ONLY in this format:
Topic: [One sentence post topic]
Description: [2-3 sentence description of what the post would show/say]
Sentiment: [engaging/inspirational/educational/funny]

Post Idea:"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_completion_tokens=200
            )

            result = response.choices[0].message.content.strip()

            # Parse the response
            lines = result.split('\n')
            topic = ""
            description = ""
            sentiment = "engaging"

            for line in lines:
                if line.startswith('Topic:'):
                    topic = line.replace('Topic:', '').strip()
                elif line.startswith('Description:'):
                    description = line.replace('Description:', '').strip()
                elif line.startswith('Sentiment:'):
                    sentiment = line.replace('Sentiment:', '').strip().lower()

            return {
                "topic": topic or "Lifestyle moment",
                "description": description or "Share a moment from your day",
                "suggested_sentiment": sentiment
            }

        except Exception as e:
            # Fallback to simple idea
            return {
                "topic": "Share your story",
                "description": "A authentic moment from your life",
                "suggested_sentiment": "engaging"
            }

    async def generate_caption(
        self,
        account_id: int,
        content_type: str = "IMAGE",
        topic: Optional[str] = None,
        target_sentiment: str = "engaging",
        custom_instructions: Optional[str] = None
    ) -> Dict:
        """
        Generate Instagram caption matching user's style.

        Args:
            account_id: Social account ID
            content_type: IMAGE, VIDEO, CAROUSEL, REEL
            topic: Optional topic/theme for the post
            target_sentiment: engaging, inspirational, educational, funny
            custom_instructions: Additional generation instructions

        Returns:
            {
                "caption": "Generated caption text",
                "hashtags": ["#tag1", "#tag2"],
                "tokens_used": 150,
                "generation_time": 1.2,
                "style_used": {...},
                "model": "gpt-4o-mini"
            }
        """
        start_time = time.time()

        # Get user's style
        style = await self.analyze_user_style(account_id)

        # Build system prompt
        system_prompt = """You are an expert Instagram content creator specializing in creating
engaging, authentic captions that drive audience interaction. You adapt to match each user's
unique voice and style while maximizing engagement potential."""

        # Build user prompt with specific post content
        if not topic:
            topic = "Share an authentic moment or story from your life"

        custom_text = f"\nAdditional Instructions: {custom_instructions}" if custom_instructions else ""

        # Include sample captions for style reference
        sample_captions_text = ""
        if style.get('sample_captions'):
            sample_captions_text = "\n\nExamples of user's top-performing captions:\n"
            for i, caption in enumerate(style['sample_captions'][:2], 1):
                sample_captions_text += f"{i}. {caption[:150]}...\n"

        user_prompt = f"""Create an Instagram caption for a {content_type} post about: {topic}

Style to Match:
- Tone: {style['tone']}
- Target length: approximately {style['avg_caption_length']} characters
- Sentiment: {target_sentiment}
- Emoji usage: {'Use emojis naturally throughout' if style['emoji_frequency'] > 0.3 else 'Use emojis sparingly'}
- Hashtags: Include approximately {style['avg_hashtag_count']} relevant hashtags

Successful Content from This Account:
- Popular hashtags: {', '.join(style['common_hashtags'][:5])}{sample_captions_text}

IMPORTANT - Create SPECIFIC content about the topic "{topic}":
1. Reference the specific topic/idea in the caption (don't be generic)
2. Tell a micro-story or share a specific insight related to the topic
3. Use concrete details and imagery (not abstract platitudes)
4. Include a call-to-action or question that relates to the topic
5. Make it feel authentic and personal{custom_text}

Write ONLY the caption text (no explanations, just the caption):"""

        # Call OpenAI
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_completion_tokens=self.max_tokens
            )

            caption = response.choices[0].message.content.strip() if response.choices[0].message.content else ""
            tokens_used = response.usage.total_tokens

        except Exception as e:
            raise Exception(f"OpenAI API error: {str(e)}")

        generation_time = time.time() - start_time

        # Extract hashtags from generated caption
        hashtags = re.findall(r'#\w+', caption)

        # VALIDATION: Enforce Instagram's 30 hashtag limit
        if len(hashtags) > 30:
            # Remove excess hashtags from caption
            excess_hashtags = hashtags[30:]
            for tag in excess_hashtags:
                # Remove the first occurrence of each excess hashtag
                caption = caption.replace(tag, '', 1)
            # Update hashtag list
            hashtags = hashtags[:30]

        # VALIDATION: Enforce Instagram's 2,200 character caption limit
        if len(caption) > 2200:
            # Truncate caption to 2,197 characters and add ellipsis
            caption = caption[:2197] + "..."
            # Re-extract hashtags after truncation
            hashtags = re.findall(r'#\w+', caption)

        return {
            "caption": caption,
            "hashtags": hashtags,
            "tokens_used": tokens_used,
            "generation_time": round(generation_time, 2),
            "style_used": style,
            "model": self.model
        }

    async def regenerate_caption(
        self,
        scheduled_post_id: int,
        topic: Optional[str] = None,
        custom_instructions: Optional[str] = None
    ) -> Dict:
        """
        Regenerate caption for an existing scheduled post.

        Args:
            scheduled_post_id: ID of scheduled post
            topic: Optional new topic
            custom_instructions: Additional instructions for regeneration

        Returns:
            Same as generate_caption()
        """
        # Get scheduled post
        query = select(ScheduledPost).where(ScheduledPost.id == scheduled_post_id)
        result = await self.db.execute(query)
        post = result.scalar_one_or_none()

        if not post:
            raise ValueError(f"Scheduled post {scheduled_post_id} not found")

        # Generate new caption
        return await self.generate_caption(
            account_id=post.account_id,
            content_type=post.content_type or "IMAGE",
            topic=topic,
            custom_instructions=custom_instructions
        )

    async def suggest_hashtags(
        self,
        account_id: int,
        caption: str,
        max_hashtags: int = 5
    ) -> List[str]:
        """
        Suggest relevant hashtags based on caption content and user's history.

        Args:
            account_id: Social account ID
            caption: Caption text
            max_hashtags: Maximum number of hashtags to suggest

        Returns:
            List of suggested hashtags
        """
        # VALIDATION: Ensure max_hashtags doesn't exceed Instagram's limit
        if max_hashtags > 30:
            max_hashtags = 30

        style = await self.analyze_user_style(account_id)
        common_hashtags = style.get('common_hashtags', [])

        # Use OpenAI to suggest contextual hashtags
        prompt = f"""Given this Instagram caption and the user's commonly used hashtags,
suggest {max_hashtags} relevant, trending hashtags that would maximize reach and engagement.

Caption: {caption}

User's successful hashtags: {', '.join(common_hashtags[:10])}

Respond with ONLY a comma-separated list of hashtags (including the # symbol), no explanations.
Example format: #hashtag1, #hashtag2, #hashtag3

Hashtags:"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_completion_tokens=100
            )

            suggested = response.choices[0].message.content.strip()
            # Parse hashtags
            hashtags = [tag.strip() for tag in suggested.split(',')]
            # Ensure they start with #
            hashtags = [tag if tag.startswith('#') else f"#{tag}" for tag in hashtags]

            return hashtags[:max_hashtags]

        except Exception as e:
            # Fallback to user's common hashtags
            return common_hashtags[:max_hashtags]

    def _default_style(self) -> Dict:
        """
        Return default style when no posts are available for analysis.

        Returns:
            Default style dictionary
        """
        return {
            "tone": "casual",
            "avg_caption_length": 120,
            "common_hashtags": ["#instagood", "#photooftheday", "#instagram"],
            "emoji_frequency": 0.3,
            "avg_hashtag_count": 3,
            "sample_captions": []
        }

    async def generate_caption_with_image(
        self,
        account_id: int,
        content_type: str = "IMAGE",
        topic: Optional[str] = None,
        target_sentiment: str = "engaging",
        custom_instructions: Optional[str] = None,
        image_style: str = "realistic"
    ) -> Dict:
        """
        Generate both caption and image for a post.

        Args:
            account_id: Social account ID
            content_type: IMAGE, VIDEO, CAROUSEL, REEL
            topic: Optional topic/theme for the post
            target_sentiment: engaging, inspirational, educational, funny
            custom_instructions: Additional generation instructions
            image_style: Image style (realistic, artistic, minimalist, vibrant)

        Returns:
            {
                "caption": "Generated caption text",
                "hashtags": ["#tag1", "#tag2"],
                "image_url": "https://...",
                "image_prompt": "The prompt used for image generation",
                "tokens_used": 150,
                "generation_time": 1.2,
                "image_generation_time": 5.5,
                "style_used": {...},
                "model": "gpt-4o-mini"
            }
        """
        # First, generate the caption
        caption_result = await self.generate_caption(
            account_id=account_id,
            content_type=content_type,
            topic=topic,
            target_sentiment=target_sentiment,
            custom_instructions=custom_instructions
        )

        # Then, generate the image based on the caption
        try:
            runway_service = RunwayImageService(self.db)

            # Generate image prompt from the caption
            image_prompt = await runway_service.generate_image_prompt(
                caption=caption_result["caption"],
                topic=topic,
                style=image_style,
                aspect_ratio="1:1"
            )

            # Generate the image
            image_result = await runway_service.generate_image(
                prompt=image_prompt,
                model="gen3a_turbo",
                width=1024,
                height=1024,
                num_images=1
            )

            # Combine results
            return {
                **caption_result,
                "image_url": image_result["image_url"],
                "image_prompt": image_prompt,
                "image_task_id": image_result["task_id"],
                "image_generation_time": image_result["generation_time"],
                "image_model": image_result["model"]
            }

        except Exception as e:
            # If image generation fails, still return the caption
            return {
                **caption_result,
                "image_url": None,
                "image_error": str(e)
            }

    async def schedule_generation_job(
        self,
        scheduled_post_id: int,
        generate_before: datetime
    ) -> int:
        """
        Schedule content generation in a green window before post time.

        Args:
            scheduled_post_id: ID of scheduled post
            generate_before: Must generate before this time

        Returns:
            job_id
        """
        from app.api.models.job_queue import Job, JobType, JobStatus
        from datetime import timedelta

        # Get scheduled post
        query = select(ScheduledPost).where(ScheduledPost.id == scheduled_post_id)
        result = await self.db.execute(query)
        post = result.scalar_one_or_none()

        if not post:
            raise ValueError(f"Scheduled post {scheduled_post_id} not found")

        # Find optimal green window for content generation
        from app.services.green_window_finder import GreenWindowFinder
        from app.core.database import SessionLocal

        duration_minutes = 5  # Content generation is quick
        optimal_window = None

        # GreenWindowFinder requires sync session
        sync_db = SessionLocal()
        try:
            window_finder = GreenWindowFinder(sync_db)
            optimal_window = window_finder.find_optimal_window(
                before_time=generate_before,
                duration_minutes=duration_minutes,
                job_type='generate_content'
            )
        finally:
            sync_db.close()

        # Set scheduled time based on green window or immediately
        now = datetime.utcnow()
        if optimal_window:
            scheduled_for = optimal_window['window_start']
            optimal_start = optimal_window['window_start']
            optimal_end = optimal_window['window_end']
            carbon_intensity = optimal_window['carbon_intensity']
            carbon_score = optimal_window['score']
        else:
            # No green window found, schedule immediately
            scheduled_for = now
            optimal_start = None
            optimal_end = None
            carbon_intensity = None
            carbon_score = None

        # Create job with proper fields
        job = Job(
            job_type=JobType.GENERATE_CONTENT,
            account_id=post.account_id,
            status=JobStatus.QUEUED,
            scheduled_for=scheduled_for,
            estimated_duration_minutes=duration_minutes,
            optimal_window_start=optimal_start,
            optimal_window_end=optimal_end,
            carbon_intensity=carbon_intensity,
            carbon_score=carbon_score,
            priority=3,  # Medium-high priority for content generation
            result={
                'scheduled_post_id': scheduled_post_id,
                'content_type': post.content_type,
                'post_time': post.scheduled_time.isoformat()
            }
        )

        self.db.add(job)
        await self.db.commit()
        await self.db.refresh(job)

        return job.id
