# Quick Fly.io Deployment Instructions

Your ChatMock application is now ready for deployment to Fly.io with the prompt header routing system fully integrated!

## Pre-Deployment Setup

### 1. Install Fly CLI
```bash
curl -L https://fly.io/install.sh | sh
flyctl auth login
```

### 2. Create Fly App
```bash
cd /home/trapgod/projects/ChatMock
flyctl app create chatmock-prod
```

### 3. Create Persistent Volume
```bash
flyctl volumes create chatmock_data --size 1 --region ord -a chatmock-prod
```

### 4. Deploy Application
```bash
flyctl deploy -a chatmock-prod
```

### 5. Copy Auth Tokens to Fly Volume

Once deployment is successful, copy your auth tokens to the Fly volume:

```bash
# SSH into the machine
flyctl ssh console -a chatmock-prod

# Create auth directory and file
mkdir -p /app/data
cat > /app/data/auth.json << 'EOFAUTH'
{
  "OPENAI_API_KEY": null,
  "tokens": {
    "id_token": "YOUR_ID_TOKEN_HERE",
    "access_token": "YOUR_ACCESS_TOKEN_HERE",
    "refresh_token": "YOUR_REFRESH_TOKEN_HERE",
    "account_id": "YOUR_ACCOUNT_ID_HERE"
  },
  "last_refresh": "2025-12-26T16:40:19.441045Z"
}
EOFAUTH

# Verify the file was created
cat /app/data/auth.json
exit
```

### 6. Verify Deployment
```bash
flyctl logs -a chatmock-prod --follow
```

### 7. Test the Application
```bash
# Test basic health
curl https://chatmock-prod.fly.dev/health

# Test token health
curl https://chatmock-prod.fly.dev/health/tokens

# Test with prompt type header
curl -X POST https://chatmock-prod.fly.dev/v1/chat/completions \
  -H "X-Prompt-Type: story" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-5.2",
    "messages": [{"role": "user", "content": "Write a short story about"}]
  }'
```

## Available Prompt Types (X-Prompt-Type Header)

- **story**: Story/narrative writing with character development and pacing
- **script** / **screenplay**: Professional screenplay formatting and structure
- **dialogue**: Authentic dialogue writing with character voices
- **storyboard**: Visual shot descriptions for video production
- **image**: AI image prompt engineering for DALL-E/Midjourney

## Example Usage with Header Routing

```bash
# Story generation
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "X-Prompt-Type: story" \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-5.2", "messages": [{"role": "user", "content": "Create a cyberpunk noir story..."}]}'

# Screenplay generation
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "X-Prompt-Type: script" \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-5.2", "messages": [{"role": "user", "content": "Write a short film script about..."}]}'

# Image prompt generation for AI art
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "X-Prompt-Type: image" \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-5.2", "messages": [{"role": "user", "content": "Generate DALL-E prompts for a futuristic city..."}]}'
```

## Monitoring Token Refresh

The application automatically refreshes tokens with:
- **Exponential backoff**: Up to 3 retry attempts (1s, 4s, 16s delays)
- **Thread safety**: Mutex prevents concurrent refresh race conditions
- **Configurable timeout**: `CHATGPT_TOKEN_REFRESH_TIMEOUT` env var

Monitor in logs:
```bash
flyctl logs -a chatmock-prod | grep "Token refresh"
```

## Production Ready!

Your ChatMock application is now:
✅ **Deployed to Fly.io** with persistent storage
✅ **Token refresh automated** with robust retry logic
✅ **Health monitored** with deep token validation
✅ **Header routing active** for specialized content generation
✅ **Ready for professional use** with GPT-5.2 optimization
