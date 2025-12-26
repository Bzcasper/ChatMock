# Fly.io Deployment Guide for ChatMock

## Prerequisites

1. **Fly.io account**: https://fly.io (free tier available)
2. **Fly CLI installed**:
   ```bash
   curl -L https://fly.io/install.sh | sh
   ```
3. **Authenticated with Fly**:
   ```bash
   flyctl auth login
   ```
4. **ChatGPT Plus/Pro account** with API access
5. **Refresh token** from local ChatMock login

## Quick Start

### 1. Clone and Prepare

```bash
git clone https://github.com/RayBytes/ChatMock.git
cd ChatMock

# Verify local setup works first
python3 chatmock.py login --no-browser
python3 chatmock.py info
```

### 2. Create Fly App

```bash
# Create the app
flyctl app create chatmock

# Create persistent volume for auth storage
flyctl volumes create chatmock_data --size 1 --region ord
```

### 3. Authenticate ChatMock

**Option A: Login locally, then deploy tokens**

```bash
# 1. Run login locally (you should have done this already)
python3 chatmock.py login --no-browser

# 2. Deploy app
flyctl deploy

# 3. Copy your local tokens to Fly volume via SSH
flyctl ssh console -a chatmock

# Once in the SSH session:
# Paste your auth.json contents to /app/data/auth.json
# You can use: cat > /app/data/auth.json << 'EOF'
# Then paste your local ~/.chatgpt-local/auth.json contents
```

**Option B: Deploy first, then login in cloud**

```bash
# 1. Deploy app first (without auth)
flyctl deploy

# 2. SSH into the machine
flyctl ssh console -a chatmock

# 3. Run login from within the machine
cd /app
python3 chatmock.py login --no-browser

# 4. Follow the browser prompt on localhost:1455
# Note: Port may need SSH tunneling for remote access
```

### 4. Deploy to Fly.io

```bash
# Deploy the application
flyctl deploy

# Watch deployment logs
flyctl logs -a chatmock --follow

# Check status
flyctl status -a chatmock
```

### 5. Test the Deployment

```bash
# Get your app's URL
flyctl info -a chatmock

# Test health endpoints
curl https://chatmock.fly.dev/health
curl https://chatmock.fly.dev/health/tokens

# Make a test API call
curl -X POST https://chatmock.fly.dev/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-5",
    "messages": [{"role": "user", "content": "test"}]
  }'
```

## Token Management

### Initial Setup

ChatMock needs valid ChatGPT tokens in `/app/data/auth.json` to function.

**Recommended approach**:
1. Login locally first (ensures tokens work)
2. Deploy app
3. Copy your `~/.chatgpt-local/auth.json` to Fly volume

### Token Refresh

The application automatically refreshes tokens with:
- **Frequency**: Every 55 minutes or when 5 minutes from expiry
- **Retry logic**: Up to 3 attempts with exponential backoff (1s, 4s, 16s)
- **Timeout**: 30 seconds (configurable via `CHATGPT_TOKEN_REFRESH_TIMEOUT`)

### Monitoring Token Health

```bash
# Check token status
curl https://chatmock.fly.dev/health/tokens

# Response example (healthy):
{
  "status": "healthy",
  "expires_in_seconds": 3600,
  "account_id": "user-xxx",
  "timestamp": "2025-12-26T12:00:00+00:00"
}

# Response example (warning - expires soon):
{
  "status": "warning",
  "reason": "Token expiring soon",
  "expires_in_seconds": 240,
  "timestamp": "2025-12-26T12:00:00+00:00"
}
```

## Configuration

### Environment Variables

Key environment variables (set in `fly.toml`):

```toml
[env]
# Token refresh settings
CHATGPT_TOKEN_REFRESH_TIMEOUT = "30"      # HTTP request timeout
CHATGPT_TOKEN_REFRESH_MAX_RETRIES = "3"   # Retry attempts

# Reasoning models
REASONING_EFFORT = "medium"                # low|medium|high|xhigh
REASONING_SUMMARY = "auto"                 # auto|concise|detailed|none
REASONING_COMPAT = "think-tags"            # think-tags|o3|legacy

# Optional: Custom OAuth client ID
# CHATGPT_LOCAL_CLIENT_ID = "your-client-id"

# Logging
VERBOSE = "false"
VERBOSE_OBFUSCATION = "false"
```

### Secrets (Optional)

```bash
# Set custom OAuth client ID as secret
flyctl secrets set CHATGPT_LOCAL_CLIENT_ID="your-client-id" -a chatmock

# View secrets
flyctl secrets list -a chatmock
```

## Troubleshooting

### "Missing ChatGPT credentials"

**Problem**: App throws auth error on first request

**Solution**:
```bash
# SSH into the machine
flyctl ssh console -a chatmock

# Check if auth.json exists
ls -la /app/data/

# If missing, manually copy tokens
# Or run login: python3 chatmock.py login --no-browser
```

### "Token refresh failed"

**Check logs**:
```bash
flyctl logs -a chatmock -l error --follow
```

**Increase timeout**:
```bash
flyctl secrets set CHATGPT_TOKEN_REFRESH_TIMEOUT="60" -a chatmock
flyctl deploy -a chatmock
```

### "Port already in use" error locally

The app defaults to port 8080. If running multiple instances:
```bash
flyctl scale count 0 -a chatmock   # Stop the app
flyctl scale count 1 -a chatmock   # Restart it
```

### Health check failing

```bash
# Check what the health endpoint returns
curl https://chatmock.fly.dev/health/tokens -v

# SSH in and test locally
flyctl ssh console -a chatmock
curl http://localhost:8080/health/tokens
```

## Monitoring & Operations

### View Logs

```bash
# Real-time logs
flyctl logs -a chatmock --follow

# Last 100 lines
flyctl logs -a chatmock --tail 100

# Filter by level
flyctl logs -a chatmock | grep ERROR
```

### Check Machine Status

```bash
# Machine list
flyctl machines list -a chatmock

# Detailed status
flyctl status -a chatmock

# Machine metrics
flyctl metrics -a chatmock
```

### Scaling

```bash
# Scale up to 2 replicas (for redundancy)
flyctl scale count 2 -a chatmock

# Scale down
flyctl scale count 1 -a chatmock

# Scale to zero (pause the app)
flyctl scale count 0 -a chatmock
```

### Volume Management

```bash
# List volumes
flyctl volumes list -a chatmock

# Backup volume data
flyctl ssh sftp get /app/data/auth.json auth.json

# Connect to volume directly
flyctl ssh console -a chatmock
```

## Deployment Checklist

- [ ] Local ChatMock login successful (`python3 chatmock.py info` shows account)
- [ ] Dockerfile updated to Python 3.13
- [ ] fly.toml configured correctly
- [ ] Fly app created (`flyctl app create`)
- [ ] Volume created (`flyctl volumes create`)
- [ ] Auth tokens copied to volume
- [ ] Initial deployment successful (`flyctl deploy`)
- [ ] Health check passes (`/health` endpoint)
- [ ] Token health check passes (`/health/tokens` endpoint)
- [ ] Test API call works (`/v1/chat/completions` endpoint)
- [ ] Logs reviewed for errors (`flyctl logs`)
- [ ] Monitoring set up (optional)

## Common Endpoints

All endpoints are available at: `https://chatmock.fly.dev`

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/health` | GET | Basic health check |
| `/health/tokens` | GET | Token validity check |
| `/v1/chat/completions` | POST | OpenAI-compatible chat API |
| `/v1/models` | GET | List available models |
| `/api/chat` | POST | Ollama-compatible API |
| `/api/tags` | GET | Ollama model list |

## Security Notes

- Auth tokens stored in encrypted Fly volume
- HTTPS enforced (free certificates via Fly.io)
- No secrets logged to console
- Health checks verify token validity
- Rate limiting inherited from ChatGPT account limits

## Advanced Configuration

### Custom OAuth Client

```bash
flyctl secrets set CHATGPT_LOCAL_CLIENT_ID="your-client-id" -a chatmock
```

### Different Region

Edit `fly.toml`:
```toml
primary_region = "lhr"  # London
# OR
primary_region = "syd"  # Sydney
```

Then redeploy:
```bash
flyctl deploy
```

### High Availability

```bash
# Deploy to 3 regions
flyctl regions add lhr syd -a chatmock

# Monitor replicas
flyctl machines list -a chatmock
```

## Stopping & Cleanup

```bash
# Pause the app (keeps data)
flyctl scale count 0 -a chatmock

# Resume the app
flyctl scale count 1 -a chatmock

# Destroy app and volumes
flyctl destroy -a chatmock
```

## Support

For issues:
1. Check `/health/tokens` endpoint
2. Review logs: `flyctl logs -a chatmock`
3. Verify tokens are valid locally
4. Check ChatGPT account status
5. Ensure network connectivity

## Links

- Fly.io Dashboard: https://fly.io/dashboard
- ChatMock GitHub: https://github.com/RayBytes/ChatMock
- OpenAI API Docs: https://platform.openai.com/docs
