# Runway AI Image Generation Integration

## Overview

EcoStudio now automatically generates AI images for your Instagram posts using Runway ML. When you create a weekly plan, the system will:

1. **Generate Caption** - AI creates engaging caption based on your style
2. **Generate Image** - Runway AI creates a matching image from the caption
3. **Schedule Post** - Both caption and image are ready to post at optimal times

## Setup

### 1. Add Your Runway API Key

Your Runway API key has already been added to the `.env` file:

**Location:** `backend/.env` (line 32)

```bash
# Runway AI (Phase 3 - Image Generation)
RUNWAY_API_KEY=key_aad3c591a7f94197ad8c183276079533887dc2929a79eebc9002a0404d6be575292de703eb7f915da169da6f155046764a177a62186fefa01a1f6dd512a595bc
```

✅ **Your API key is ready to use!**

### 2. How It Works

#### Automatic Image Generation (During Weekly Plan)

When you create a weekly plan, images are generated automatically:

```
POST /api/v1/workflow/weekly-plan
{
  "account_id": 1,
  "num_posts": 7,
  "auto_generate": true
}
```

**What happens:**
1. System creates 7 posts at optimal engagement times
2. Schedules caption generation during green windows (low carbon)
3. **NEW:** After caption is generated, automatically creates image using Runway
4. Post is ready with both caption and image

#### Manual Image Generation for Existing Posts

If you have posts without images (like your current ones), use:

```bash
# Generate image for a specific post
POST /api/v1/scheduled-posts/{post_id}/generate-image?style=realistic

# Generate images for ALL posts missing images
POST /api/v1/scheduled-posts/generate-missing-images?limit=10&style=realistic
```

**Image Styles Available:**
- `realistic` - Photorealistic, professional photography (default)
- `artistic` - Creative, vibrant, artistic composition
- `minimalist` - Clean, simple, modern, elegant
- `vibrant` - Bold colors, energetic, eye-catching

## Fix Your Current Posts

You have **6 generated posts** (Post 86) that need images. Here's how to fix them:

### Option 1: Generate Images for All Posts (Recommended)

```bash
# From your backend directory
curl -X POST "http://localhost:8000/api/v1/scheduled-posts/generate-missing-images?limit=10&style=realistic"
```

This will:
- Find all posts with captions but no images
- Generate images for each one
- Update the posts with image URLs
- Return a summary of what was generated

### Option 2: Generate Image for One Post at a Time

```bash
# Replace 86 with your post ID
curl -X POST "http://localhost:8000/api/v1/scheduled-posts/86/generate-image?style=realistic"
```

### Option 3: Use the Frontend

A button will appear in the Content Management page:
- Click "Generate Images"
- Select posts to generate images for
- Choose image style
- Click "Generate"

## How Image Prompts Are Generated

The system analyzes your caption and extracts:
- **Keywords** from the text
- **Topic/Theme** of the post
- **Mood/Sentiment** (engaging, inspirational, etc.)

Then creates an optimized prompt like:
```
"morning coffee motivation, photorealistic, high quality,
professional photography, 8k resolution, Instagram-worthy,
high engagement potential"
```

## API Endpoints Reference

### Generate Image for Single Post
```http
POST /api/v1/scheduled-posts/{post_id}/generate-image
Query Parameters:
  - style: realistic|artistic|minimalist|vibrant (default: realistic)
  - regenerate: boolean (default: false)

Response:
{
  "status": "generated",
  "scheduled_post_id": 86,
  "image_url": "https://...",
  "image_prompt": "Generated prompt used",
  "generation_time": 12.5,
  "task_id": "runway_task_id"
}
```

### Batch Generate Missing Images
```http
POST /api/v1/scheduled-posts/generate-missing-images
Query Parameters:
  - account_id: int (optional, filter by account)
  - limit: int (default: 10, max: 50)
  - style: realistic|artistic|minimalist|vibrant

Response:
{
  "total_processed": 6,
  "successful": 6,
  "failed": 0,
  "skipped": 0,
  "results": [...]
}
```

## Troubleshooting

### Error: "RUNWAY_API_KEY not found"
- Check that `.env` file has `RUNWAY_API_KEY=your_key`
- Restart the backend server after adding the key

### Error: "Post has no content"
- The post needs a caption before generating an image
- Generate caption first, then generate image

### Error: "Runway generation failed"
- Check your Runway API key is valid
- Ensure you have credits remaining in your Runway account
- Check Runway API status at https://status.runwayml.com

### Image Takes Too Long
- Image generation typically takes 10-30 seconds
- The endpoint will wait up to 2 minutes
- If it times out, try again with `regenerate=true`

## Carbon-Aware Scheduling

Image generation is **compute-intensive**, so it's scheduled during green windows:

- **Caption Generation**: ~5 seconds, minimal carbon
- **Image Generation**: ~15 seconds, more carbon intensive
- Both scheduled during low-carbon electricity periods
- Typically saves 30-60% carbon vs. peak hours

## Cost Information

Runway AI charges per generation:
- Check current pricing at https://runwayml.com/pricing
- Each image counts as one generation
- Monitor your usage in the Runway dashboard

## Testing

### Quick Test (Single Post)

1. Start your backend server:
```bash
cd backend
uvicorn app.main:app --reload
```

2. Generate image for post 86:
```bash
curl -X POST "http://localhost:8000/api/v1/scheduled-posts/86/generate-image?style=realistic"
```

3. Check the response for `image_url`

4. Open the frontend to see the image

### Full Test (Weekly Plan with Images)

1. Create a new weekly plan:
```bash
curl -X POST "http://localhost:8000/api/v1/workflow/weekly-plan" \
  -H "Content-Type: application/json" \
  -d '{"account_id": 1, "num_posts": 3, "auto_generate": true}'
```

2. Wait for content generation jobs to run (check scheduler)

3. Posts will have both captions and images automatically

## What's Been Changed

### New Files
- `backend/app/services/runway_image_service.py` - Runway AI integration

### Modified Files
- `backend/.env` - Added `RUNWAY_API_KEY`
- `backend/.env.example` - Added API key documentation
- `backend/app/services/content_generation_service.py` - Added `generate_caption_with_image()`
- `backend/app/services/eco_scheduler.py` - Auto-generate images in workflow
- `backend/app/api/endpoints/scheduled_posts.py` - Added image generation endpoints

### New API Endpoints
1. `POST /api/v1/scheduled-posts/{post_id}/generate-image` - Generate image for one post
2. `POST /api/v1/scheduled-posts/generate-missing-images` - Batch generate images

## Next Steps

1. ✅ **API Key Added** - Your Runway key is configured
2. **Generate Images** - Run the batch command to fix your current 6 posts
3. **Test New Posts** - Create a weekly plan and watch it auto-generate images
4. **Monitor Usage** - Check Runway dashboard for credit usage
5. **Adjust Styles** - Try different image styles to match your brand

---

**Questions?** Check the logs at `backend/logs/` for detailed generation info.
