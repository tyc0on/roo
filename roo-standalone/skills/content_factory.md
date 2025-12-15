---
name: content_factory
description: Generate blog articles using the Content Factory pipeline
trigger_keywords:
  - write an article
  - create content
  - generate a blog
  - write a post
  - content for my site
  - blog post about
requires_auth: false
---

## Parameters
- **domain**: The user's website domain (required)
- **topic**: The article topic or title (required)
- **target_keyword**: SEO target keyword (optional)

## Actions

### 1. Extract Parameters
Parse the user's request to identify:
- Their domain (from previous messages or ask if not provided)
- The topic they want to write about
- Any specific keywords they mentioned

### 2. Confirm Details
Before starting generation, confirm the details with the user:
- Domain
- Topic
- Target keyword

### 3. Start Generation
Call the Content Factory API to start article generation:
```
POST /api/pipeline/generate
{
    "domain": "<domain>",
    "topic": "<topic>",
    "target_keyword": "<keyword>"
}
```

### 4. Monitor Progress
Poll the job status and update the user with progress:
- Research phase (0-20%)
- Strategy phase (20-40%)
- Writing phase (40-80%)
- Publishing phase (80-100%)

### 5. Report Success
When complete, provide the user with:
- Preview URL
- PR URL for review
- Article title and summary

Response style:
- Use encouraging language during progress updates
- Celebrate completion with enthusiasm
- Provide clear links and next steps
