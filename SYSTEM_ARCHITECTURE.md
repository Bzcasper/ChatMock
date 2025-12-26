# ChatMock System Architecture

Complete technical documentation of how ChatMock works, how requests flow through the system, how the prompting system works, and how Fly.io is configured.

---

## 🏗️ System Overview

**Purpose**: ChatMock is an OpenAI/Ollama-compatible API server that routes requests to ChatGPT using your authenticated ChatGPT Plus/Pro account.

```
CLIENT REQUEST
    ↓
    ├─ HTTP POST to /v1/chat/completions
    ├─ Headers: X-Prompt-Type (optional), Content-Type: application/json
    ├─ Body: {"model": "gpt-5.2", "messages": [...], ...}
    ↓
CHATMOCK SERVER (Flask)
    ├─ Extract X-Prompt-Type header (story|script|dialogue|storyboard|image)
    ├─ Load appropriate base instructions + specialized prompt
    ├─ Merge user messages with system instructions
    ├─ Ensure tokens are fresh (auto-refresh if needed)
    ↓
OPENAI API (via OAuth)
    ├─ Send merged request to ChatGPT API endpoint
    ├─ Receive response with thinking, completion, etc.
    ↓
RESPONSE FORMATTING
    ├─ Convert OpenAI response to standard API format
    ├─ Stream or return full response
    ↓
CLIENT
```

---

## 🔑 Core Components

### 1. Token Management (`chatmock/utils.py`)

**Primary Function**: `load_chatgpt_tokens(ensure_fresh: bool = True)`

#### Token Storage
```
Location: ~/.chatgpt-local/auth.json (or $CHATGPT_LOCAL_HOME)

Structure:
{
  "OPENAI_API_KEY": null,
  "tokens": {
    "id_token": "eyJ...",           # JWT for identity
    "access_token": "eyJ...",       # Primary API token
    "refresh_token": "rt_...",      # Used to get new access tokens
    "account_id": "c7cd..."         # ChatGPT account identifier
  },
  "last_refresh": "2025-12-26T16:40:19.441045Z"
}
```

#### Token Refresh Mechanism

**Automatic & Dynamic Token Refresh**:

```python
def load_chatgpt_tokens(ensure_fresh: bool = True):
    1. Read auth.json from disk
    2. Extract tokens from auth.json
    3. Check if ensure_fresh=True and we have refresh_token:
        ├─ Check if access_token needs refresh (using _should_refresh_access_token)
        ├─ If needs refresh OR no access_token exists:
        │   ├─ ACQUIRE MUTEX LOCK (_TOKEN_REFRESH_LOCK)
        │   ├─ Double-check again (thread-safe pattern)
        │   ├─ If still needs refresh:
        │   │   ├─ Call _refresh_chatgpt_tokens_with_retry()
        │   │   │   ├─ Attempt 1: Try immediately
        │   │   │   ├─ Attempt 2: Wait 1 second, try again
        │   │   │   ├─ Attempt 3: Wait 4 seconds, try again
        │   │   │   └─ Attempt 4: Wait 16 seconds, try again (max 3 retries)
        │   │   └─ If refresh succeeds:
        │   │       ├─ Extract new tokens from response
        │   │       ├─ Update in-memory token structure
        │   │       └─ Persist to auth.json
        │   └─ RELEASE MUTEX LOCK
    4. Return (access_token, account_id, id_token)
```

**Key Security Features**:
- ✅ Thread-safe mutex lock prevents race conditions
- ✅ Double-check pattern (checks twice: before and after lock)
- ✅ Exponential backoff retry: 1s, 4s, 16s delays
- ✅ Configurable timeout: `CHATGPT_TOKEN_REFRESH_TIMEOUT` (default: 30s)
- ✅ Max retries: 3 (configurable)

**Thread Safety**:
```python
_TOKEN_REFRESH_LOCK = threading.Lock()

# Pseudocode of double-check pattern:
if needs_refresh:  # First check (without lock)
    with _TOKEN_REFRESH_LOCK:  # Acquire lock
        if needs_refresh:  # Second check (with lock)
            _refresh_tokens()  # Safe to refresh now
```

This ensures:
- ✅ Only ONE thread refreshes at a time
- ✅ Other threads wait for the lock
- ✅ No duplicate refresh requests to OpenAI
- ✅ All threads get fresh tokens

#### Token Expiry Checking

```python
def _should_refresh_access_token(access_token, last_refresh):
    """Check if token needs refresh based on expiry time"""
    - Parse JWT claims from access_token
    - Get 'exp' field (expiration timestamp)
    - If token expires in < 5 minutes: refresh needed
    - If token already expired: refresh needed
    - Otherwise: token is still valid
```

---

### 2. Prompting System (`chatmock/config.py`)

**Architecture**:
```
PROMPTING HIERARCHY

┌─ BASE_INSTRUCTIONS (prompt.md)
│  └─ Default system prompt for all requests
│
├─ GPT5_CODEX_INSTRUCTIONS (prompt_gpt5_codex.md)
│  └─ Specialized prompt for gpt-5-codex, gpt-5.1-codex, gpt-5.2-codex models
│
└─ CONTENT_TYPE_PROMPTS (specialized prompts)
   ├─ story → prompt_story.md (narrative/storytelling)
   ├─ script/screenplay → prompt_script.md (screenwriting)
   ├─ dialogue → prompt_dialogue.md (dialogue writing)
   ├─ storyboard → prompt_storyboard.md (visual descriptions)
   └─ image → prompt_image.md (DALL-E/Midjourney prompts)
```

#### How Prompts Load

```python
def load_content_type_prompts():
    """Load all 5 specialized content prompts at startup"""
    for content_type, filename in [
        ('story', 'prompt_story.md'),
        ('script', 'prompt_script.md'),
        ('screenplay', 'prompt_script.md'),  # Alias
        ('dialogue', 'prompt_dialogue.md'),
        ('storyboard', 'prompt_storyboard.md'),
        ('image', 'prompt_image.md'),
    ]:
        content = _read_prompt_text(filename)
        if content is valid:
            CONTENT_TYPE_PROMPTS[content_type] = content
    return CONTENT_TYPE_PROMPTS
```

**Search Order for Prompt Files**:
```
1. /project/root/prompt_story.md
2. /project/root/chatmock/prompt_story.md
3. $MEIPASS/prompt_story.md (if bundled executable)
4. Current working directory/prompt_story.md
```

This allows:
- ✅ Flexible deployment (local files or bundled)
- ✅ Override prompts without recompiling
- ✅ Works in Docker (mounts at /app)

---

### 3. Request Routing (`chatmock/routes_openai.py` & `routes_ollama.py`)

#### HTTP Request Flow

**Step 1: Extract Headers**
```python
@app.post("/v1/chat/completions")
def chat_completions():
    # Get X-Prompt-Type header (case-insensitive, optional)
    content_type = request.headers.get("X-Prompt-Type", "").strip().lower() or None
    # Example values: "story", "script", "dialogue", "storyboard", "image", None
```

**Step 2: Select Instructions**
```python
def _instructions_for_model(model: str, content_type: str | None = None) -> str:
    # 1. Start with base instructions
    base = BASE_INSTRUCTIONS

    # 2. If codex model, use codex-specific instructions
    if model.startswith("gpt-5-codex") or model.startswith("gpt-5.1-codex") or model.startswith("gpt-5.2-codex"):
        base = GPT5_CODEX_INSTRUCTIONS

    # 3. If content_type provided (from X-Prompt-Type header):
    if content_type:
        specialized = _get_specialized_instructions(content_type)
        if specialized:
            base = _merge_instructions(base, specialized)

    return base  # Final system prompt
```

**Step 3: Merge Instructions**
```python
def _merge_instructions(base: str, specialized: str | None) -> str:
    """Combine base + specialized prompts"""
    return f"""{base}

## SPECIALIZED INSTRUCTIONS FOR {specialized.split()[0].upper()}:

{specialized}"""
```

**Step 4: Build System Message**
```python
# Process incoming messages:
messages = payload.get("messages")  # User messages

# Remove any user-provided system messages
if any message has role="system":
    remove it  # We'll use our generated system message instead

# Build final messages for API call:
final_messages = [
    {"role": "user", "content": system_prompt_we_generated},
    ...original messages...
]
```

**Step 5: Call ChatGPT API**
```python
# Get fresh tokens (auto-refreshes if needed)
access_token, account_id, id_token = load_chatgpt_tokens(ensure_fresh=True)

# Prepare API call to OpenAI
request_to_api = {
    "model": model,
    "messages": final_messages,  # Includes our system instructions
    "stream": is_stream,
    # ... other OpenAI parameters ...
}

# Send to ChatGPT backend
response = requests.post(
    CHATGPT_RESPONSES_URL,
    headers={"Authorization": f"Bearer {access_token}"},
    json=request_to_api,
    timeout=...
)
```

---

### 4. Example Request Flow

#### Request Without Content Type

```
CLIENT REQUEST:
POST /v1/chat/completions
Content-Type: application/json

{
    "model": "gpt-5.2",
    "messages": [
        {"role": "user", "content": "What is the capital of France?"}
    ]
}

CHATMOCK PROCESSING:
1. Extract content_type: None (no X-Prompt-Type header)
2. Select instructions: BASE_INSTRUCTIONS (prompt.md)
3. Build final messages:
   - System: [BASE_INSTRUCTIONS from prompt.md]
   - User: "What is the capital of France?"
4. Load tokens: access_token (auto-refreshes if needed)
5. Call OpenAI API
6. Return response
```

#### Request With Content Type (Story)

```
CLIENT REQUEST:
POST /v1/chat/completions
X-Prompt-Type: story
Content-Type: application/json

{
    "model": "gpt-5.2",
    "messages": [
        {"role": "user", "content": "Write a sci-fi short story about..."}
    ]
}

CHATMOCK PROCESSING:
1. Extract content_type: "story"
2. Select instructions:
   - Base: BASE_INSTRUCTIONS
   - Specialized: CONTENT_TYPE_PROMPTS["story"] (from prompt_story.md)
   - Merged: BASE_INSTRUCTIONS + professional story-writing framework
3. Build final messages:
   - System: [MERGED specialized instructions]
   - User: "Write a sci-fi short story about..."
4. Load tokens: access_token (auto-refreshes if needed)
5. Call OpenAI API with story-optimized system prompt
6. Return story response
```

---

## 🚀 Fly.io Configuration

### Container Architecture

```
Dockerfile:
├─ Base Image: python:3.13-slim (lightweight, secure)
├─ Working Dir: /app
├─ Volumes:
│  └─ /app/data (persistent volume for auth.json)
├─ Port: 8080
└─ Entry: CMD ["chatmock", "serve", ...]
```

### Fly.io Configuration (`fly.toml`)

```toml
[build]
dockerfile = "Dockerfile"

[env]
# Token refresh settings
CHATGPT_TOKEN_REFRESH_TIMEOUT = "30"       # Timeout for refresh requests
CHATGPT_TOKEN_REFRESH_MAX_RETRIES = "3"    # Max retry attempts
CHATGPT_LOCAL_HOME = "/app/data"           # Where auth.json is stored

# Python settings
PYTHONUNBUFFERED = "1"                     # Unbuffered output (important for logs)

[processes]
app = "chatmock serve --host 0.0.0.0 --port 8080"

[[services]]
protocol = "tcp"
internal_port = 8080
auto_stop_machines = false
auto_start_machines = true
min_machines_running = 1

[[services.ports]]
port = 80      # HTTP
handlers = ["http"]

[[services.ports]]
port = 443     # HTTPS (automatic TLS)
handlers = ["tls", "http"]

[services.http_checks]
interval = 10000  # Check every 10 seconds
timeout = 5000    # Wait max 5 seconds
grace_period = 5000  # Wait 5 seconds before first check
method = "GET"
path = "/health"

[mounts]
source = "chatmock_data"
destination = "/app/data"

[[checks]]
type = "http"
grace_period = "30s"
interval = "30s"
method = "GET"
path = "/health/tokens"    # Deep check: validates token is fresh
timeout = "5s"
```

### Health Checks

**Basic Health Check** (`/health`):
```
GET /health
Response: {"status": "ok"}
Purpose: Confirm server is running
Fly.io: Uses this to auto-start machines
```

**Token Health Check** (`/health/tokens`):
```
GET /health/tokens
Response:
  - If healthy: {
      "status": "healthy",
      "expires_in_seconds": 3600,
      "account_id": "c7cd...",
      "timestamp": "2025-12-26T..."
    }
  - If expiring soon: {
      "status": "warning",
      "reason": "Token expiring soon",
      "expires_in_seconds": 250,
      ...
    }
  - If expired: {
      "status": "unhealthy",
      "reason": "Token has expired",
      ...
    }

Purpose:
  ✅ Verify token is fresh before serving requests
  ✅ Warn if token expiring soon
  ✅ Fail if token is invalid
```

### Persistent Volume

**Fly.io Persistent Volumes**:
```
Volume: chatmock_data
Location: /app/data (inside container)

Contains:
  - auth.json (OpenAI tokens + account info)
  - Survives container restarts
  - Automatically mounted on every start
  - Updated whenever tokens refresh
```

**Token Injection on First Deployment**:
```bash
# 1. Deploy container (without tokens)
$ flyctl deploy -a chatmock-prod

# 2. SSH into running machine
$ flyctl ssh console -a chatmock-prod

# 3. Create auth.json with tokens
$ mkdir -p /app/data
$ cat > /app/data/auth.json << 'EOF'
{
  "tokens": {
    "id_token": "YOUR_ID_TOKEN",
    "access_token": "YOUR_ACCESS_TOKEN",
    "refresh_token": "YOUR_REFRESH_TOKEN",
    "account_id": "YOUR_ACCOUNT_ID"
  }
}
EOF

# 4. Verify
$ cat /app/data/auth.json
$ exit

# 5. Restart app to reload tokens
$ flyctl restart -a chatmock-prod
```

---

## ⚡ Error Handling & Edge Cases

### Token Refresh Failures

**Scenario 1: Refresh Fails 3 Times**
```
Attempt 1: Connection timeout
Wait 1 second
Attempt 2: HTTP 401 Unauthorized (refresh_token invalid)
Wait 4 seconds
Attempt 3: Rate limited (too many requests)

Result:
  ✅ Continue with old token (if still valid)
  ❌ If no valid token: Return 503 error to client

Log: "Token refresh failed after 3 attempts"
```

**Scenario 2: Token Expires Mid-Request**
```
1. Token was valid when refresh check happened
2. Long-running request started
3. Token expires during the request
4. OpenAI rejects request with 401

Result:
  - Request fails with 401 error
  - Client retries automatically
  - On retry: Token refresh triggers
  - Fresh token fetched
  - Request succeeds on second attempt
```

### Concurrency Issues

**Scenario: Two Requests Simultaneously**
```
Request 1                          Request 2
├─ Check token                     ├─ Check token
├─ Both need refresh               ├─ Both need refresh
├─ Request 1 acquires lock         ├─ Request 2 waits
├─ Request 1 refreshes token       │
├─ Request 1 releases lock         │
│                                  ├─ Request 2 acquires lock
│                                  ├─ Check again: token is fresh now!
│                                  ├─ Skip refresh (saves API call)
│                                  └─ Release lock
└─ Both requests proceed
```

**Result**: Only ONE refresh happens, both requests use fresh token. ✅

### Invalid/Expired Tokens

**Scenario: refresh_token Expired**
```
1. User's ChatGPT subscription ended
2. refresh_token is no longer valid
3. Token refresh fails with "invalid_grant"
4. access_token expires
5. No valid tokens exist

Result:
  - /health/tokens returns 503 "unhealthy"
  - Requests return 503 "Token unavailable"
  - User must re-authenticate and update auth.json
```

**Fix**:
```bash
# User re-authenticates
$ python chatmock.py login

# New tokens are written to auth.json
# On Fly.io: SSH in and update /app/data/auth.json
$ flyctl ssh console -a chatmock-prod
$ cat > /app/data/auth.json << 'EOF'
...new tokens...
EOF
```

---

## 📊 Performance Optimizations

### Token Refresh Strategy

**Current Implementation**:
```
✅ Refresh when: token expires in < 5 minutes
✅ Retry with backoff: 1s, 4s, 16s delays
✅ Thread-safe: Mutex prevents concurrent refreshes
✅ Lazy loading: Only refresh when needed (not on schedule)
✅ Persistent: Save refreshed tokens to disk
```

**Result**:
- Minimal API calls to OpenAI
- Always fresh tokens
- No wasteful scheduled refreshes
- Handles burst traffic efficiently

### Request Processing

```
Per Request:
├─ Parse JSON: ~1ms
├─ Load tokens: ~5ms (usually from cache)
├─ Check if refresh needed: ~2ms
├─ Build messages: ~3ms
├─ Send to OpenAI: 100-2000ms (depends on model/reasoning)
└─ Stream response back: Varies

Total: 100-2000ms per request (mostly waiting for OpenAI)
```

### Memory Usage

```
At Startup:
├─ Load BASE_INSTRUCTIONS: ~10KB
├─ Load GPT5_CODEX_INSTRUCTIONS: ~5KB
├─ Load 5 CONTENT_TYPE_PROMPTS: ~100KB
├─ Python Flask framework: ~20MB
└─ Total: ~20MB

Per Request:
├─ Parse + process request: ~5MB
├─ Response buffering: Varies
└─ Cleanup: Garbage collected

Fly.io Default: 256MB RAM (sufficient)
```

---

## 🔒 Security Architecture

### Token Security

```
Storage:
  ✅ On Disk: /app/data/auth.json (persistent volume, not in container image)
  ✅ In Memory: Loaded into RAM only when needed
  ❌ NOT in: Environment variables, git history, container image
  ❌ NOT in: Logs or debug output (unless verbose_obfuscation=false)

Access:
  ✅ Only /app/data/auth.json has access
  ✅ File permissions: 0o600 (read/write by owner only)
  ✅ Not accessible from outside container
  ✅ HTTPS/TLS for all client communication
```

### Request Validation

```
Every request validates:
  ✅ JSON syntax
  ✅ Required fields present (model, messages)
  ✅ Model name is valid/supported
  ✅ Messages are properly formatted
  ✅ Tools/functions are valid OpenAI format
  ❌ Invalid requests: Return 400 error immediately
```

### Token Validation

```
/health/tokens endpoint:
  ✅ Validates JWT format (must have 2 dots)
  ✅ Decodes JWT claims (no signature verification, just payload)
  ✅ Checks 'exp' field (expiration timestamp)
  ✅ Compares against current time
  ✅ Returns detailed status
```

---

## 🎯 Production Readiness Checklist

### Fly.io Deployment

- ✅ Dockerfile uses Python 3.13 (secure, latest)
- ✅ Port 8080 configured correctly
- ✅ /health endpoint responds (for load balancer checks)
- ✅ /health/tokens endpoint validates tokens every 30s
- ✅ Persistent volume mounted at /app/data
- ✅ Environment variables set correctly
- ✅ Auto-restart enabled (min_machines_running = 1)
- ✅ HTTPS/TLS enabled (via Fly.io)

### Token Management

- ✅ Automatic refresh with exponential backoff
- ✅ Thread-safe mutex prevents race conditions
- ✅ Double-check pattern for safe refresh
- ✅ Tokens persisted to disk after refresh
- ✅ Health check validates token freshness
- ✅ Graceful fallback if refresh fails

### Request Handling

- ✅ X-Prompt-Type header routing implemented
- ✅ 5 specialized content-type prompts available
- ✅ Base instructions apply to all requests
- ✅ Codex models use specialized instructions
- ✅ Error responses are well-formatted
- ✅ Streaming and non-streaming both supported

### Monitoring

- ✅ Health check endpoint: /health
- ✅ Token health endpoint: /health/tokens
- ✅ Verbose logging (optional, can be enabled)
- ✅ Error logging with timestamps
- ✅ Performance metrics available

---

## 🔧 Troubleshooting Guide

### Problem: "Token has expired"

```
Symptoms: /health/tokens returns 503, requests fail

Solution:
1. SSH into Fly.io machine: flyctl ssh console -a chatmock-prod
2. Update /app/data/auth.json with new tokens:
   - Run: python chatmock.py login (locally)
   - Get new tokens
   - Copy to /app/data/auth.json on Fly.io
3. Restart: flyctl restart -a chatmock-prod
```

### Problem: "Requests timeout"

```
Symptoms: Requests hang or take >30 seconds

Possible causes:
1. OpenAI API is slow (check OpenAI status)
2. Timeout too short (increase CHATGPT_TOKEN_REFRESH_TIMEOUT)
3. Network issue (check Fly.io logs: flyctl logs -a chatmock-prod)
4. Request is streaming (may take minutes for long responses)

Solution:
1. Check Fly.io logs for errors
2. Try /health to confirm app is running
3. Increase timeout: Set CHATGPT_TOKEN_REFRESH_TIMEOUT=60
```

### Problem: "Token refresh keeps failing"

```
Symptoms: Logs show "Token refresh failed after 3 attempts"

Possible causes:
1. refresh_token is invalid/expired
2. Network connection issue
3. OpenAI auth service is down
4. Too many refresh attempts in short time (rate limited)

Solution:
1. Check refresh_token in auth.json is valid
2. Re-authenticate: python chatmock.py login
3. Update tokens on Fly.io and restart
4. Wait a few minutes if rate limited, then retry
```

---

## 📈 Scalability Considerations

### Current Architecture

```
Single Machine (Fly.io):
  ├─ 256MB RAM (default)
  ├─ 1-3 CPUs (shared container)
  ├─ 20GB storage (for code + volume)
  └─ Suitable for: 1-10 concurrent requests
```

### Limitations

```
Per Fly.io Machine:
  ❌ Can't exceed OpenAI API rate limits
  ❌ Long-running requests block other requests
  ❌ Single point of failure (no redundancy)
  ✅ Auto-scales up to multiple machines (with Fly.io paid)
```

### Future Improvements

```
To Scale to 100+ concurrent requests:
1. Use Fly.io autoscaling (multiple machines)
2. Use Fly.io Postgres for shared token cache
3. Implement request queueing (Redis)
4. Add load balancing between machines
5. Cache responses for repeated requests
```

---

## Summary

**ChatMock is Production-Ready** for:
- ✅ 1-10 concurrent users
- ✅ Automatic token refresh with exponential backoff
- ✅ Specialized content-type prompts via X-Prompt-Type header
- ✅ Thread-safe request handling
- ✅ Persistent token storage
- ✅ Health monitoring and alerts
- ✅ Secure token management

**Key Features**:
- 🔐 Thread-safe mutex prevents refresh race conditions
- 🚀 Exponential backoff retry strategy (1s, 4s, 16s)
- 📝 5 specialized prompts (story, script, dialogue, storyboard, image)
- 🔄 Automatic token refresh when expiring
- 📊 Deep health checks for token validity
- 🐳 Fly.io optimized with persistent volume for tokens

**Do Not Break By**:
- ❌ Modifying token refresh logic without understanding concurrency
- ❌ Changing file paths without updating config search order
- ❌ Deploying without persistent volume for tokens
- ❌ Hardcoding tokens (use /app/data/auth.json only)
- ❌ Removing health check endpoints (Fly.io needs them)

You now have a comprehensive understanding of the entire system! 🚀
