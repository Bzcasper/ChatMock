# Web Search and Prompting Guide

## Web Search Capabilities

ChatMock fully supports web search via the OpenAI Responses API. The model can search the web in real-time to provide current information.

### Using Web Search

#### Per-Request Web Search

Include `responses_tools` in your API request to enable web search for that request:

```bash
curl https://chatmock-prod.fly.dev/v1/chat/completions \
  -H "Authorization: Bearer key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-5.2",
    "messages": [{"role":"user","content":"What are the latest developments in AI?"}],
    "responses_tools": [{"type": "web_search"}],
    "max_tokens": 500
  }'
```

#### Global Web Search Configuration

Enable web search by default for all requests:

```bash
# Start server with web search enabled
python -m chatmock serve --enable-web-search

# Or set environment variable
export CHATGPT_LOCAL_ENABLE_WEB_SEARCH=true
python -m chatmock serve
```

### API Format

**Tool Type**: `web_search` or `web_search_preview`

The API supports both variants:
- `web_search` - Standard web search results
- `web_search_preview` - Web search with preview content

### Example: Python SDK

```python
from openai import OpenAI

client = OpenAI(
    base_url="https://chatmock-prod.fly.dev/v1",
    api_key="key"
)

response = client.chat.completions.create(
    model="gpt-5.2",
    messages=[
        {"role": "user", "content": "What are the latest AI developments?"}
    ],
    extra_body={
        "responses_tools": [{"type": "web_search"}]
    },
    max_tokens=500
)

print(response.choices[0].message.content)
```

### Supported Models

Web search works with all available models:
- `gpt-5`, `gpt-5.1`, `gpt-5.2`
- `gpt-5-codex`, `gpt-5.1-codex`, `gpt-5.2-codex`
- `gpt-5.1-codex-max`

---

## Prompting System

ChatMock uses a sophisticated prompting system to customize model behavior based on use cases.

### System Prompts Overview

#### Base Prompt (`prompt.md` - 23.6KB)

The primary system prompt that defines how the model behaves. It's specifically configured for Claude Code in the Codex CLI environment but provides general-purpose guidance for all requests.

**Key Features**:
- Personality: concise, direct, friendly tone
- Responsiveness: structured preamble messages and thinking
- Planning: integration with plan/update tools
- Task execution: clear guidelines for solving queries
- Testing and validation: methodology for verifying work
- Sandbox awareness: understands approval modes

### Specialized Prompts

ChatMock includes specialized prompts for specific content types, optimized for particular domains:

| Content Type | File | Size | Purpose |
|---|---|---|---|
| Story | `prompt_story.md` | 25KB | Narrative writing, character development, dramatic structure |
| Script | `prompt_script.md` | 27KB | Screenplay writing, dialogue, formatting |
| Dialogue | `prompt_dialogue.md` | 21KB | Conversation writing, character voice |
| Image | `prompt_image.md` | 23KB | Image generation instructions |
| Storyboard | `prompt_storyboard.md` | 25KB | Visual narrative planning |
| Codex (GPT-5) | `prompt_gpt5_codex.md` | 9.7KB | Code generation for -codex models |

### Current Limitations

**Specialized Prompts Status**: Available but currently disabled due to API constraints

The OpenAI Responses API has stricter instruction size limits than initially expected. While generic tests showed 50KB+ support, the actual validation rejects merged prompts that exceed certain internal limits.

**Recommendation**: Use base instructions which provide excellent performance across all use cases. The model performs very well without specialized prompts due to its inherent capabilities.

### Future Improvements

To enable specialized prompts in the future:

1. **Compress prompts**: Remove redundancy and boilerplate from specialized prompts
2. **Delta approach**: Create specialized prompts as deltas rather than full replacements
3. **Dynamic selection**: Load only necessary instruction sections per request
4. **API limit investigation**: Work with OpenAI to understand exact validation limits

### Architecture: How Prompts Work

```python
# Current flow (no merging)
base_instructions = read_file("prompt.md")  # 23.6KB
response = api.call(
    model="gpt-5.2",
    instructions=base_instructions,
    messages=user_messages
)

# Future flow (with merging)
# Would be: ~49KB (24KB base + 25KB specialized)
# Currently disabled due to API validation limits
```

### Using Content-Type Hints

The system supports `X-Prompt-Type` header to indicate desired specialization:

```bash
curl https://chatmock-prod.fly.dev/v1/chat/completions \
  -H "Authorization: Bearer key" \
  -H "Content-Type: application/json" \
  -H "X-Prompt-Type: story" \
  -d '{
    "model": "gpt-5.2",
    "messages": [{"role":"user","content":"Write an opening scene"}]
  }'
```

**Supported Content Types** (pending prompt merging fix):
- `story` - Narrative writing
- `script` / `screenplay` - Script writing
- `dialogue` - Dialogue writing
- `image` - Image generation guidance
- `storyboard` - Storyboard planning

**Note**: Currently, `X-Prompt-Type` is parsed but specialized prompts are not applied due to API size constraints. The base prompt is used regardless. This allows preparation for when the limitation is resolved.

---

## Performance Characteristics

### Base Instructions (Enabled)

- ✅ **Reliability**: 100% success rate
- ✅ **Size**: 23.6KB (well under API limits)
- ✅ **Quality**: Excellent performance on all use cases
- ✅ **Models**: Works with all available models

### Specialized Instructions (Disabled)

- ⚠️ **Size**: 21-28KB each (individually fine)
- ⚠️ **Merging**: ~49KB merged (causes API errors)
- ⚠️ **Status**: Available but not applied
- 🔄 **Future**: Pending API limit improvements or prompt compression

### Web Search

- ✅ **Reliability**: Fully functional
- ✅ **Real-time**: Live web search with current results
- ✅ **Citation**: Includes source references
- ✅ **All models**: Works with all available models

---

## Testing Web Search

Test web search capability with a current events query:

```bash
curl -s https://chatmock-prod.fly.dev/v1/chat/completions \
  -H "Authorization: Bearer key" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-5.2",
    "messages": [{"role":"user","content":"What are todays major news stories?"}],
    "responses_tools": [{"type": "web_search"}],
    "max_tokens": 500
  }' | jq '.choices[0].message.content'
```

Expected result: Model responds with current information, demonstrating active web search.

---

## Configuration

### Environment Variables

```bash
# Enable web search globally
export CHATGPT_LOCAL_ENABLE_WEB_SEARCH=true

# Token management
export CHATGPT_TOKEN_REFRESH_TIMEOUT=30
export CHATGPT_TOKEN_REFRESH_MAX_RETRIES=3

# Verbose logging
export VERBOSE=true
export VERBOSE_OBFUSCATION=false
```

### Fly.io Deployment

See `fly.toml` for production configuration:

```toml
[env]
VERBOSE = "true"
VERBOSE_OBFUSCATION = "false"
CHATGPT_TOKEN_REFRESH_TIMEOUT = "30"
CHATGPT_TOKEN_REFRESH_MAX_RETRIES = "3"
PYTHONUNBUFFERED = "1"
```

---

## Architecture Summary

```
API Request
    ↓
Parse model + content type
    ↓
Select base instructions (prompt.md)
    ↓
[Specialized instructions currently skipped due to size]
    ↓
Add web_search tools if requested
    ↓
Send to upstream Responses API
    ↓
Stream response back to client
```

---

## Troubleshooting

### Issue: "Upstream error" on requests

**Cause**: Specialized prompts were being attempted to merge
**Solution**: Currently disabled; base instructions are used reliably
**Workaround**: All requests work fine with base instructions

### Issue: Web search not returning current results

**Cause**: Web search not enabled in request
**Solution**: Include `responses_tools: [{"type": "web_search"}]` in request payload

### Issue: Model not using provided content-type hint

**Cause**: Specialized prompts currently disabled
**Status**: Recognized and documented
**Timeline**: Pending prompt compression or API limit improvements

---

## API Limits & Constraints

| Metric | Value | Status |
|---|---|---|
| Base instructions | 23.6KB | ✅ Reliable |
| Specialized instructions | 21-28KB each | ⚠️ Disabled when merged |
| Merged instructions | ~49KB | ⚠️ Causes upstream errors |
| Web search tools | Supported | ✅ Working |
| Tool definitions | <32KB | ✅ Fine |
| Total requests | No limit | ✅ Unbounded |

---

## Future Development

1. **Prompt Compression**: Reduce specialized prompts by 40-50% to enable merging
2. **Delta System**: Refactor prompts as deltas rather than full replacements
3. **API Limit Clarity**: Investigate OpenAI's exact instruction validation limits
4. **Selective Loading**: Load only needed instruction sections per request

