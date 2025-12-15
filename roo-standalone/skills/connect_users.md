---
name: connect_users
description: Find community members with relevant expertise using vector search
trigger_keywords:
  - who knows
  - expert in
  - connect me
  - looking for someone
  - anyone working on
  - recommend someone
requires_auth: false
---

## Parameters
- **query**: The expertise or topic the user is looking for (required)
- **exclude_user_id**: Slack user ID to exclude from results (optional)
- **limit**: Maximum number of users to suggest (default: 5)

## Actions

### 1. Extract Topics
Use the user's query to identify the specific expertise areas they're looking for.
Parse phrases like "who knows about X" or "anyone working on Y" to extract X and Y.

### 2. Vector Search
Search the user_expertise table using cosine similarity to find users with matching expertise.

```sql
SELECT u.id, u.name, u.slack_id, e.topic, e.relationship,
       1 - (e.embedding <=> $query_embedding) as similarity
FROM users u
JOIN user_expertise e ON u.id = e.user_id
WHERE 1 - (e.embedding <=> $query_embedding) > 0.7
ORDER BY similarity DESC
LIMIT 5;
```

### 3. Format Response
Generate a warm, friendly response suggesting the matched users.

Response style:
- Start with an acknowledgment of what they're looking for
- Suggest users with their expertise areas
- Use casual Australian language occasionally (mate, no worries, etc.)
- Mention the relationship type (expert, working on, interested)
- If no users found, offer alternative suggestions

Example:
"G'day! Looking for folks in AI research, eh? Here are some legends who might help:

• **@sam** - Expert in machine learning and neural networks
• **@jane** - Currently working on computer vision projects

Feel free to reach out to them! 🦘"
