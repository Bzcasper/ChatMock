# Private Fork Setup Guide

This guide explains how to set up a **private fork** for your ChatMock development work while maintaining ability to contribute back to the main repository.

---

## 🎯 Why a Private Fork?

Your private fork allows you to:

✅ **Keep development private** - Work in your own repository
✅ **Manage secrets safely** - Store credentials locally without exposure
✅ **Maintain clean history** - Keep public main branch free of sensitive data
✅ **Contribute back** - Submit clean Pull Requests to upstream when ready
✅ **Branch freely** - Use private/* branches for experimental work

---

## Setup Steps

### Step 1: Create a Private Fork on GitHub

**Option A: Using GitHub UI (Recommended)**

1. Go to the main repository: [https://github.com/trapgod/ChatMock](https://github.com/trapgod/ChatMock)
2. Click **Fork** button (top right)
3. In the fork dialog:
   - Owner: Select your personal GitHub account
   - Repository name: Keep as `ChatMock`
   - Description: "Private development fork"
   - **Check "Copy the main branch only"** (keeps it minimal)
   - **IMPORTANT: Check "Private"** to make it private
4. Click **Create fork**

**Option B: Using GitHub CLI (Faster)**

```bash
# If you have gh CLI installed
gh repo fork trapgod/ChatMock --private --clone=false

# Output will show your fork URL, e.g.:
# https://github.com/yourusername/ChatMock
```

### Step 2: Configure Git Remotes

Your local repo currently points to the main repository. Update it to use your private fork:

```bash
# Check current remotes
git remote -v

# Output should show:
# origin      https://github.com/trapgod/ChatMock.git (fetch)
# origin      https://github.com/trapgod/ChatMock.git (push)
# upstream    https://github.com/trapgod/ChatMock.git (fetch)
# upstream    https://github.com/trapgod/ChatMock.git (push)
```

Now update them:

```bash
# Change origin to point to YOUR private fork
git remote set-url origin https://github.com/YOUR_USERNAME/ChatMock.git

# Keep upstream pointing to the original repo
git remote set-url upstream https://github.com/trapgod/ChatMock.git

# Verify the changes
git remote -v

# Should now show:
# origin      https://github.com/YOUR_USERNAME/ChatMock.git (fetch)
# origin      https://github.com/YOUR_USERNAME/ChatMock.git (push)
# upstream    https://github.com/trapgod/ChatMock.git (fetch)
# upstream    https://github.com/trapgod/ChatMock.git (push)
```

### Step 3: Sync with Upstream

Ensure your fork is up-to-date with the original repository:

```bash
# Fetch latest from upstream
git fetch upstream

# Switch to main
git checkout main

# Update main to match upstream
git rebase upstream/main

# Push main to your private fork
git push origin main --force-with-lease
```

### Step 4: Push Private Branch

Push your private development branch to your fork:

```bash
# Make sure you're on private/chatmock-dev
git checkout private/chatmock-dev

# Push to your private fork
git push -u origin private/chatmock-dev

# Verify it's there
git branch -r

# Should show:
# origin/private/chatmock-dev
# origin/main
# upstream/main
```

---

## Your Fork Workflow

### Daily Development

```bash
# 1. Start on private branch (already created)
git checkout private/chatmock-dev

# 2. Create local feature branches as needed
git checkout -b private/feature-name

# 3. Add your .env.local with secrets (ignored by git)
echo "OPENAI_ID_TOKEN=..." > .env.local

# 4. Work and commit normally
# Secrets stay local, never leave your machine
git add .
git commit -m "feature: Add new feature"

# 5. Push feature branch to your PRIVATE fork
git push origin private/feature-name

# 6. When feature is done, merge to private/chatmock-dev
git checkout private/chatmock-dev
git merge private/feature-name
git push origin private/chatmock-dev
```

### Keeping Secrets Private

```bash
# Your .env.local is automatically ignored
git status  # Won't show .env.local

# Verify no secrets in your commits
git show HEAD
# Should only show code/config, NOT tokens

# Before pushing, double-check
git diff --cached
# Should not contain any credentials
```

---

## Contributing Back (Creating PRs)

When your work is ready to contribute back to the main repository:

### Step 1: Ensure Clean History

```bash
# Make sure your private branch has no secrets
git log --all -p -S "eyJ" | head  # Should find nothing
git log --all -p -S "rt_" | head  # Should find nothing

# Make sure main branch is in sync with upstream
git checkout main
git rebase upstream/main
git push origin main
```

### Step 2: Create Clean Branch for PR

```bash
# Create a new branch from main (without any secrets)
git checkout main
git checkout -b feature/my-feature

# Cherry-pick commits from private branch (optional)
# OR manually copy over the code changes (safest)

# Ensure NO .env.local or secrets in commits
git status
git log --oneline -5
```

### Step 3: Create Pull Request

```bash
# Push your clean feature branch
git push origin feature/my-feature

# Go to GitHub and create PR from:
# FROM: trapgod/ChatMock main branch
# TO: your feature/my-feature on your fork

# In the PR description, explain your changes
# The project maintainers will review and merge
```

### Step 4: Sync After Merge

```bash
# After PR is merged to main repo
git fetch upstream
git checkout main
git rebase upstream/main
git push origin main
```

---

## Managing Multiple Private Branches

For different projects or experimental features:

```bash
# Create separate private branches
git checkout main
git checkout -b private/experiment-1
git checkout main
git checkout -b private/experiment-2

# Work on each independently
# Push to your fork
git push origin private/experiment-1
git push origin private/experiment-2

# Your fork stays private, all branches are safe
```

---

## Safety Checklist

Before pushing anything to your fork:

```bash
# ✅ Check 1: No secrets in git status
git status
# Should NOT show: .env.local, auth.json, *.secret

# ✅ Check 2: No tokens in staged changes
git diff --cached | grep -i "token\|secret\|key\|jwt"
# Should find nothing

# ✅ Check 3: No tokens in commits
git log -1 --oneline
git show HEAD | grep -i "eyJ\|rt_"
# Should find nothing

# ✅ Check 4: .env.local is protected
git check-ignore .env.local
# Should output: .env.local

# ✅ Check 5: Secrets file is not tracked
git ls-files | grep -i ".env\|auth\|secret"
# Should show nothing for local files
```

---

## Troubleshooting

### Problem: Accidentally Pushed Secrets

```bash
# IMMEDIATELY revoke those tokens in OpenAI account
# https://platform.openai.com/account/auth -> Revoke all tokens

# If committed but not pushed:
git reset HEAD~1  # Undo the commit
git remove .env.local credentials.json auth.json
git commit -m "Remove secrets"

# If already pushed to your private fork:
# Contact GitHub support or delete the branch
git push origin :branch-with-secrets  # Delete remote branch
git branch -D branch-with-secrets     # Delete local branch
```

### Problem: Upstream is Ahead

```bash
# Your main is behind upstream
git fetch upstream
git checkout main
git rebase upstream/main
git push origin main --force-with-lease

# Now you're in sync
```

### Problem: Merge Conflicts

```bash
# When pulling upstream changes
git fetch upstream
git rebase upstream/main

# Resolve conflicts in your editor
# Then continue
git rebase --continue
git push origin main --force-with-lease
```

---

## Your Current Setup

Your repo is already configured as follows:

```
LOCAL REPOSITORY
├── main branch (clean, no secrets)
│   ├── Commit: 3260694 - Routing + Fly.io (clean)
│   └── Commit: b2b26bb - Professional prompts
│
├── private/chatmock-dev branch (for development)
│   ├── All of above
│   └── Commit: 37df4cf - Secrets management guide
│
└── Remotes:
    ├── origin → YOUR private fork (when set up)
    └── upstream → Original ChatMock repo
```

### Next: Set Up Your Private Fork

Follow Steps 1-4 above to:
1. Create private fork on GitHub
2. Configure git remotes
3. Sync with upstream
4. Push your branches

---

## Git Command Reference

```bash
# View current remotes
git remote -v

# Update remotes
git remote set-url origin <your-fork-url>
git remote set-url upstream <original-repo-url>

# Sync with upstream
git fetch upstream
git checkout main
git rebase upstream/main

# Push to your fork
git push origin main
git push origin private/chatmock-dev

# Create feature from private branch
git checkout private/chatmock-dev
git checkout -b private/feature-name

# Push feature branch
git push -u origin private/feature-name

# View all branches
git branch -a

# Delete branch
git branch -d branch-name
git push origin :branch-name

# Cherry-pick commits
git checkout target-branch
git cherry-pick source-commit-hash
```

---

## Questions?

If you have questions about setting up your private fork:

1. **Check this document** - Review the steps above
2. **Review SECRETS_MANAGEMENT.md** - For secure practices
3. **Check git status** - Always verify nothing sensitive is staged
4. **Contact GitHub support** - For fork-specific issues

---

## Summary

✅ **You now have:**
- Clean main branch (safe to contribute back)
- Private development branch for your work
- Private fork (on GitHub) for secure storage
- Secrets management guide for safe practices
- Ability to contribute clean PRs when ready

🔒 **Your workflow is secure:**
- Secrets stay in `.env.local` (ignored by git)
- Private fork protects your development
- Main branch stays clean for PRs
- Private branches for experimental work

🚀 **Ready to proceed with development!**
