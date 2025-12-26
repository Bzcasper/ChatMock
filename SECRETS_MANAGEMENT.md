# Secrets Management Guide

This document explains how to safely manage sensitive credentials (API tokens, keys, etc.) in ChatMock development and deployment.

## 🔒 Golden Rules

1. **NEVER commit secrets to git** - Not even in comments or examples
2. **NEVER push credentials to remote repositories** - Even private ones
3. **NEVER store tokens in environment variable files that are tracked**
4. **ALWAYS use .gitignore** to prevent accidental commits
5. **ALWAYS use SSH console or platform secrets** for production deployment

---

## Local Development Setup

### Step 1: Create Your Local Secrets File

```bash
# Create .env.local in your project root
# (This file is ignored by git and stays local only)
cp .env.local.example .env.local
```

### Step 2: Fill in Your Actual Secrets

Edit `.env.local` with your REAL OpenAI tokens:

```bash
# Edit the file
nano .env.local

# Add your actual tokens (example format only):
OPENAI_ID_TOKEN=eyJhbGciOiJSUzI1NiIsImtpZCI6ImIxZGQz...
OPENAI_ACCESS_TOKEN=eyJhbGciOiJSUzI1NiIsImtpZCI6IjE5MzQ0...
OPENAI_REFRESH_TOKEN=rt_WUjJ6viNSUHaXEDDQ1aljl3EfFhRbVSB...
OPENAI_ACCOUNT_ID=c7cdaaca-de90-4dea-8244-1c3881c8851b
```

### Step 3: Verify .gitignore Protection

```bash
# Check that .env.local is in .gitignore
grep -n "\.env\.local" .gitignore

# Output should show:
# .env.local
```

### Step 4: Load Secrets in Your App

In your Python code, load from `.env.local`:

```python
from dotenv import load_dotenv
import os

# Load from .env.local (not committed to git)
load_dotenv('.env.local')

# Access secrets safely
id_token = os.getenv('OPENAI_ID_TOKEN')
access_token = os.getenv('OPENAI_ACCESS_TOKEN')
refresh_token = os.getenv('OPENAI_REFRESH_TOKEN')
account_id = os.getenv('OPENAI_ACCOUNT_ID')

if not id_token:
    raise ValueError("OPENAI_ID_TOKEN not found in .env.local")
```

---

## Protected Files (Never Commit)

Files automatically protected by `.gitignore`:

```
.env.local              # Your local development secrets
.env.*.local            # Environment-specific secrets
auth.json              # Local auth token storage
*.secret               # Any file ending with .secret
credentials.json       # Service account credentials
deploy.local.md        # Local deployment notes with tokens
```

---

## Production Deployment (Fly.io)

### For Fly.io: Use SSH Console (SAFEST METHOD)

```bash
# 1. Deploy the application (without secrets)
flyctl deploy -a chatmock-prod

# 2. SSH into the running machine
flyctl ssh console -a chatmock-prod

# 3. Create the data directory
mkdir -p /app/data

# 4. Inject your tokens via cat/heredoc (NOT via environment)
cat > /app/data/auth.json << 'EOFAUTH'
{
  "OPENAI_API_KEY": null,
  "tokens": {
    "id_token": "YOUR_ACTUAL_ID_TOKEN",
    "access_token": "YOUR_ACTUAL_ACCESS_TOKEN",
    "refresh_token": "YOUR_ACTUAL_REFRESH_TOKEN",
    "account_id": "YOUR_ACTUAL_ACCOUNT_ID"
  },
  "last_refresh": "2025-12-26T16:40:19.441045Z"
}
EOFAUTH

# 5. Verify the file exists
cat /app/data/auth.json

# 6. Exit the console
exit

# 7. Restart the app if needed
flyctl restart -a chatmock-prod
```

### Why SSH Console is Safer

✅ Secrets entered directly into the running machine
✅ Never stored in git, environment variables, or config files
✅ Encrypted in transit via SSH
✅ Tokens stay in persistent volume, not in container image
✅ No accidental git exposure risk

---

## Development Workflow

### Creating a Feature Branch with Secrets

```bash
# Create private feature branch
git checkout -b private/feature-name

# Add your .env.local (automatically ignored)
echo "OPENAI_ID_TOKEN=..." > .env.local
echo "OPENAI_ACCESS_TOKEN=..." >> .env.local
echo "OPENAI_REFRESH_TOKEN=..." >> .env.local
echo "OPENAI_ACCOUNT_ID=..." >> .env.local

# Verify it won't be committed
git status  # Should NOT show .env.local

# Work on your features
# When committing, secrets stay local and safe
git add .
git commit -m "feature: Add new feature"

# Your .env.local stays local, never pushed
git push origin private/feature-name
```

---

## Verifying Your Setup is Secure

### Check 1: Verify .env.local is Ignored

```bash
git check-ignore .env.local
# Should output: .env.local

# OR check the .gitignore file
grep "\.env\.local" .gitignore
```

### Check 2: Verify No Tokens in Git History

```bash
# Search for JWT token patterns (should find nothing)
git log -p -S "eyJ" | head -20

# Search for refresh tokens (should find nothing)
git log -p -S "rt_" | head -20

# If either returns results, tokens are exposed!
```

### Check 3: Verify File Permissions

```bash
# Your .env.local should have restrictive permissions
ls -la .env.local
# Should show: -rw------- (600) or -rw-r--r-- (644) at minimum

# Set restrictive permissions
chmod 600 .env.local
```

---

## What NOT To Do ❌

```bash
# ❌ DO NOT: Store secrets in .env (committed file)
echo "OPENAI_TOKEN=secret" > .env
git add .env  # WRONG!

# ❌ DO NOT: Hardcode in Python files
API_TOKEN = "eyJhbGciOiJS..."  # WRONG!

# ❌ DO NOT: Use environment variables for development
export OPENAI_TOKEN="eyJhbGciOiJS..."  # Will be in bash history

# ❌ DO NOT: Pass tokens as command line arguments
python app.py --token "eyJhbGciOiJS..."  # WRONG!

# ❌ DO NOT: Store in .git/config or git attributes
git config --global user.password "token"  # WRONG!
```

---

## What TO Do ✅

```bash
# ✅ DO: Use .env.local (protected by .gitignore)
cp .env.local.example .env.local
# Edit .env.local with your actual secrets
# Verify: git check-ignore .env.local

# ✅ DO: Load from .env.local at runtime
# In your app: load_dotenv('.env.local')

# ✅ DO: Use platform secrets for production
# Fly.io: flyctl ssh console
# GitHub: Settings > Secrets and variables
# AWS: Secrets Manager
# GCP: Secret Manager

# ✅ DO: Keep tokens in persistent volumes
# Mount /app/data as persistent volume
# Store auth.json there (not in container image)

# ✅ DO: Rotate tokens regularly
# Set calendar reminders to refresh tokens
# Monitor token expiry with /health/tokens endpoint

# ✅ DO: Use HTTPS everywhere
# Environment variables transmitted over HTTPS only
# SSH console for sensitive data entry
```

---

## Emergency: Tokens Compromised

If you believe your tokens have been exposed:

### Immediate Actions

1. **Revoke compromised tokens immediately**
   ```bash
   # Visit: https://platform.openai.com/account/auth
   # Click "Revoke" on all active tokens
   ```

2. **Get new tokens**
   ```bash
   # Follow OpenAI's authentication flow to get new tokens
   ```

3. **Update all deployments**
   ```bash
   # Via SSH console on Fly.io
   flyctl ssh console -a chatmock-prod

   # Update the auth.json with new tokens
   cat > /app/data/auth.json << 'EOF'
   { "tokens": { "id_token": "NEW_TOKEN", ... } }
   EOF
   ```

4. **Audit git history** (if exposed in git)
   ```bash
   # Check if tokens ever made it to git
   git log -p -S "old_token_pattern" | head

   # If found, you need to rewrite history or create new repo
   ```

5. **Notify relevant parties** if tokens were in shared repos

---

## Monitoring & Maintenance

### Health Check Endpoint

Monitor token expiry and validity:

```bash
# Check token health
curl https://chatmock-prod.fly.dev/health/tokens

# Response shows:
# {
#   "status": "healthy|warning|unhealthy",
#   "expires_in_seconds": 123456,
#   "account_id": "...",
#   "timestamp": "2025-12-26T..."
# }
```

### Set Reminders

- **Token refresh**: Every 30 days (automatic in app)
- **Token rotation**: Every 90 days (manual refresh recommended)
- **Security audit**: Monthly review of access

---

## Reference Documentation

- [Python-dotenv Documentation](https://python-dotenv.readthedocs.io/)
- [OpenAI Authentication](https://platform.openai.com/docs/guides/authentication)
- [Fly.io Secrets Management](https://fly.io/docs/reference/secrets/)
- [OWASP Secrets Management](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)

---

## Questions?

If you have questions about secrets management in this project:
1. Check this document
2. Review `.env.local.example` for format
3. Verify `.gitignore` protection
4. Test with `git check-ignore`
