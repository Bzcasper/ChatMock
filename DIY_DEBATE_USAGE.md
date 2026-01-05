# DIY Scene Debate - Quick Start Guide

## What This Does

**Input**: Video idea + hook + category
**Process**: Multi-agent debate refines dialogue and visuals
**Output**: Perfect scene array JSON

## Debate Agents

### Round 1: Dialogue Critics
- **TTS Critic** - Finds TTS gotchas (numbers, abbreviations, punctuation)
- **Flow Critic** - Natural speech patterns
- **Sentence Critic** - Enforces 2-sentence max

### Round 2: Visual Critics
- **FLUX Critic** - FLUX Pro 2 compliance
- **Hand Anatomy Critic** - Hand detail quality
- **Lighting Critic** - Lighting descriptions

### Round 3: Coherence Critics
- **Alignment Critic** - Dialogue-visual match
- **Flow Critic** - Scene sequence logic
- **Timing Critic** - Timing validation

### Final: Synthesizer
- Combines all feedback
- Applies improvements
- Outputs final JSON

---

## Usage: One HTTP Request

### Run Locally

```bash
# Terminal 1: Start ChatMock
cd /home/trapgod/projects/ChatMock
python -m chatmock.app

# Terminal 2: Start Debate Service
python app_diy_scene_debate.py
```

### Single API Call

```bash
curl -X POST http://localhost:5001/api/debate/quick \
  -H "Content-Type: application/json" \
  -d '{
    "video_idea": "Build a simple wooden shelf for beginners",
    "video_hook": "Learn to build a custom shelf in under an hour!",
    "diy_category": "Woodworking",
    "chatmock_url": "http://localhost:5000"
  }'
```

**Response**:
```json
{
  "final_scenes": [
    {
      "start_time": 0.00,
      "end_time": 3.00,
      "duration": 3.00,
      "dialogue": "Learn to build a custom shelf in under an hour!",
      "prompt": "Indoor workshop with warm natural lighting, wooden workbench in background, various woodworking tools organized on wall-mounted pegboard, close-up of hands gesturing excitedly toward camera, realistic depth of field with blurred workshop background, anatomically correct hands with visible skin texture, photorealistic, vertical 9:16"
    }
  ],
  "tutorial": { ... },
  "stats": {
    "total_scenes": 15,
    "total_versions": 2,
    "debate_rounds": 3
  }
}
```

---

## n8n Integration

### Node: HTTP Request

**URL**: `http://localhost:5001/api/debate/quick`

**Method**: POST

**Headers**:
```json
{
  "Content-Type": "application/json"
}
```

**Body** (JSON):
```json
{
  "video_idea": "{{ $('Postgres Pick Next Opportunity').item.json.video_idea }}",
  "video_hook": "{{ $('Postgres Pick Next Opportunity').item.json.video_hook }}",
  "diy_category": "{{ $('Postgres Pick Next Opportunity').item.json.diy_category }}",
  "chatmock_url": "https://chatmock-prod.fly.dev"
}
```

**Output Path**: `$.final_scenes`

---

## Production Deployment

### Deploy Debate Service to Fly.io

```bash
# Create fly.toml for debate service
cat > fly-debate.toml << EOF
app = "diy-scene-debate"

[http_service]
  internal_port = 5001
  force_https = true
  auto_stop_machines = false
  auto_start_machines = true
  min_machines_running = 1

[[vm]]
  size = "shared-cpu-1x"
  memory = "512mb"
EOF

# Deploy
flyctl deploy -c fly-debate.toml
```

### n8n Production Setup

**URL**: `https://diy-scene-debate.fly.dev/api/debate/quick`

**Body**:
```json
{
  "video_idea": "{{ $json.video_idea }}",
  "video_hook": "{{ $json.video_hook }}",
  "diy_category": "{{ $json.diy_category }}",
  "chatmock_url": "https://chatmock-prod.fly.dev"
}
```

---

## Direct Python Usage

```python
from diy_scene_debate_protocol import DIYSceneDebateProtocol
import json

# Initialize
protocol = DIYSceneDebateProtocol(base_url="http://localhost:5000")

# Run debate
final_scenes = protocol.run_full_debate(
    video_idea="Build a simple wooden shelf",
    video_hook="Learn in under an hour!",
    diy_category="Woodworking"
)

# Print result
print(json.dumps(final_scenes, indent=2))

# Save
protocol.save_output("final_scenes.json")
protocol.save_full_report("debate_report.json")
```

---

## Output Structure

**Exact JSON format** (ready for FLUX + TTS):

```json
[
  {
    "start_time": 0.00,
    "end_time": 3.00,
    "duration": 3.00,
    "dialogue": "TTS-ready text with proper punctuation, spelled out numbers.",
    "prompt": "Detailed FLUX Pro 2 prompt with hands, tools, lighting, photorealistic, vertical 9:16"
  }
]
```

---

## Debate Process Flow

```
Video Idea Input
    ↓
[Step 1] Generate Tutorial JSON
    ↓
[Step 2] Generate Initial Scene Draft
    ↓
[Round 1] TTS Critics + Flow Critics + Sentence Critics
    ↓
[Round 2] FLUX Critics + Hand Critics + Lighting Critics
    ↓
[Round 3] Alignment Critics + Flow Critics + Timing Critics
    ↓
[Step 4] Synthesize & Apply Improvements
    ↓
Final Scene Array JSON ✅
```

---

## Quality Improvements

**Before Debate**:
```json
{
  "dialogue": "Use a 2x4 and drill 3/4\" holes",
  "prompt": "Person drilling wood"
}
```

**After Debate**:
```json
{
  "dialogue": "Use a two by four board, and drill three quarter inch holes.",
  "prompt": "Close-up of hands holding cordless drill positioned above wooden two by four board, right hand gripping drill handle with index finger on trigger, left hand steadying board edge, three quarter inch drill bit visible in chuck, pencil marks indicating hole positions on wood surface, natural overhead workshop lighting, realistic depth of field with sharp focus on drill bit and hands, blurred workbench background, anatomically correct hand positioning showing proper grip technique, visible wood grain texture on board, photorealistic, vertical 9:16"
}
```

---

## Testing

### Quick Test

```bash
curl -X POST http://localhost:5001/api/debate/quick \
  -H "Content-Type: application/json" \
  -d '{
    "video_idea": "Test project",
    "video_hook": "Quick test",
    "diy_category": "Testing"
  }' | jq '.final_scenes | length'
```

Expected: Number of scenes (e.g., `5`)

---

## Comparison: Single-Prompt vs Debate

| Feature | Single-Prompt | Debate System |
|---------|--------------|---------------|
| Speed | ~30 seconds | ~2-3 minutes |
| Quality | Good | Excellent |
| TTS Optimization | Basic | Perfect |
| FLUX Compliance | Good | Perfect |
| Dialogue-Visual Alignment | Fair | Excellent |
| Hand Details | Minimal | Comprehensive |
| Iterations | 1 | 3-4 rounds |
| Best For | Quick drafts | Production videos |

---

## When to Use Each

**Use Single-Prompt** (`X-Content-Type: diy-scene`):
- Rapid prototyping
- Draft generation
- Simple tutorials
- Budget constraints

**Use Debate System** (`/api/debate/quick`):
- Production videos
- High-quality content
- Complex tutorials
- TTS critical accuracy
- FLUX photorealism critical

---

## Troubleshooting

### Debate Takes Too Long

**Solution**: Reduce debate rounds by modifying agent_roles in step_3

### Quality Not Improving

**Solution**: Check ChatMock logs - ensure all agents are running

### Scenes Don't Match

**Solution**: Increase temperature in synthesis step (line 567)

### API Timeout

**Solution**: Increase timeout in requests.post (default: 120s)

---

## Support

- Multi-agent protocol: `diy_scene_debate_protocol.py`
- Flask API wrapper: `app_diy_scene_debate.py`
- Single-prompt fallback: `prompt_diy_scene_array.md`

---

## License

MIT
