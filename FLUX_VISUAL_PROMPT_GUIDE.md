# FLUX-2-Pro Visual Prompt Generator Guide

This guide shows you how to use the FLUX-2-Pro visual prompt generator in ChatMock.

## Overview

The FLUX visual prompt generator converts structured content (like storyboard data) into a JSON array of visual scene descriptions optimized for FLUX-2-Pro image generation.

## How to Use

### Via HTTP Header

Use the `X-Content-Type` or `Content-Type` header with value `flux-visual` or `visual-prompt`:

```bash
curl -X POST https://chatmock-prod.fly.dev/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-Content-Type: flux-visual" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "model": "gpt-5.2",
    "messages": [
      {
        "role": "user",
        "content": "Title: Build a Wooden Shelf\n\nHook: Learn to build a custom shelf in under an hour.\n\nWelcome: Welcome to this DIY woodworking tutorial.\n\nProject overview: We will build a simple wooden shelf. This project teaches basic joinery skills. Perfect for beginners.\n\nSteps: Step 1: Measure and cut the wood. Use a measuring tape and mark cut lines with a pencil. Safety note: Wear safety glasses. Common mistake: Not measuring twice. Quality check: Ensure all pieces are equal length."
      }
    ],
    "temperature": 0.7,
    "max_tokens": 2500
  }'
```

### With Structured Input (Recommended)

For best results, format your input data as structured JSON interpolation:

```json
{
  "model": "gpt-5.2",
  "messages": [
    {
      "role": "user",
      "content": "Title: {{ title }}\n\nHook: {{ hook }}\n\nWelcome: {{ welcome }}\n\nProject overview:\n{{ project_intro.what }}\n{{ project_intro.benefit }}\n{{ project_intro.who_is_this_for }}\n\nMaterials:\n{{ materials.map(m => `Material: ${m.item}. Purpose: ${m.why}. Sourcing: ${m.sourcing}. Budget tip: ${m.budget_tip}. Substitute: ${m.common_substitute}.`).join('\\n') }}\n\nSteps:\n{{ steps.map(s => `Step ${s.step}: ${s.action}. ${s.detail}. Safety note: ${s.safety}. Common mistake: ${s.common_mistake}. Quality check: ${s.quality_check}.`).join('\\n') }}\n\nShowcase:\n{{ showcase.visual }}\n{{ showcase.test }}\n{{ showcase.finish_tip }}\n\nOutro:\n{{ outro }}"
    }
  ],
  "temperature": 0.7,
  "max_tokens": 2500
}
```

## Workflow: Storyboard → Visual Prompts

### Step 1: Generate Storyboard

```bash
curl -X POST https://chatmock-prod.fly.dev/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-Content-Type: storyboard" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "model": "gpt-5.2",
    "messages": [
      {
        "role": "user",
        "content": "Create a DIY tutorial for building a wooden shelf"
      }
    ]
  }'
```

**Response:** Structured JSON with title, hook, materials, steps, etc.

### Step 2: Generate Visual Prompts from Storyboard

```bash
curl -X POST https://chatmock-prod.fly.dev/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-Content-Type: flux-visual" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "model": "gpt-5.2",
    "messages": [
      {
        "role": "user",
        "content": "<PASTE STORYBOARD OUTPUT HERE>"
      }
    ],
    "temperature": 0.7,
    "max_tokens": 2500
  }'
```

**Response:** JSON array of scene objects with timing and visual prompts

## Output Format

The generator returns a JSON array of scenes:

```json
[
  {
    "start_time": 0.00,
    "end_time": 3.00,
    "duration": 3.00,
    "dialogue": "Welcome to this DIY tutorial.",
    "prompt": "Indoor workshop setting with warm natural lighting, wooden workbench in background, various woodworking tools organized on wall-mounted pegboard, close-up of hands gesturing welcomingly toward camera, realistic depth of field with blurred background, anatomically correct hands with visible texture and natural skin tones, photorealistic, vertical 9:16"
  },
  {
    "start_time": 3.00,
    "end_time": 6.00,
    "duration": 3.00,
    "dialogue": "Today we'll build a wooden shelf.",
    "prompt": "Indoor workspace with assembled wooden shelf components laid out on workbench, close-up of hands pointing to various pre-cut wooden pieces, measuring tape and pencil visible, natural window lighting from left side, realistic wood grain texture visible on boards, photorealistic, vertical 9:16"
  }
]
```

## Scene Properties

Each scene object contains:

- **start_time** (decimal): Start time in seconds (0.00, 3.00, 6.00, ...)
- **end_time** (decimal): End time in seconds (3.00, 6.00, 9.00, ...)
- **duration** (decimal): Always 3.00 seconds
- **dialogue** (string): Exact sentence from input (verbatim)
- **prompt** (string): Visual description optimized for FLUX-2-Pro

## Visual Prompt Characteristics

All generated prompts include:

- ✅ Indoor, real-world instructional setting
- ✅ Emphasis on hands, tools, materials, workspace
- ✅ Photorealistic rendering instructions
- ✅ Natural lighting specifications
- ✅ Realistic depth of field
- ✅ Anatomically correct hands
- ✅ Vertical 9:16 aspect ratio
- ❌ No text overlays, captions, logos, watermarks
- ❌ No UI elements, CGI, illustration effects
- ❌ No motion blur or stylization

## Integration Examples

### Python

```python
import requests

# Step 1: Generate storyboard
storyboard_response = requests.post(
    "https://chatmock-prod.fly.dev/v1/chat/completions",
    headers={
        "Content-Type": "application/json",
        "X-Content-Type": "storyboard",
        "Authorization": "Bearer YOUR_TOKEN"
    },
    json={
        "model": "gpt-5.2",
        "messages": [{"role": "user", "content": "Create DIY shelf tutorial"}]
    }
)

storyboard_data = storyboard_response.json()

# Step 2: Generate visual prompts
visual_response = requests.post(
    "https://chatmock-prod.fly.dev/v1/chat/completions",
    headers={
        "Content-Type": "application/json",
        "X-Content-Type": "flux-visual",
        "Authorization": "Bearer YOUR_TOKEN"
    },
    json={
        "model": "gpt-5.2",
        "messages": [
            {"role": "user", "content": format_storyboard(storyboard_data)}
        ],
        "temperature": 0.7,
        "max_tokens": 2500
    }
)

scenes = visual_response.json()["choices"][0]["message"]["content"]
```

### JavaScript/Node.js

```javascript
const axios = require('axios');

// Step 1: Generate storyboard
const storyboard = await axios.post(
  'https://chatmock-prod.fly.dev/v1/chat/completions',
  {
    model: 'gpt-5.2',
    messages: [{ role: 'user', content: 'Create DIY shelf tutorial' }]
  },
  {
    headers: {
      'Content-Type': 'application/json',
      'X-Content-Type': 'storyboard',
      'Authorization': 'Bearer YOUR_TOKEN'
    }
  }
);

// Step 2: Generate visual prompts
const visual = await axios.post(
  'https://chatmock-prod.fly.dev/v1/chat/completions',
  {
    model: 'gpt-5.2',
    messages: [
      { role: 'user', content: formatStoryboard(storyboard.data) }
    ],
    temperature: 0.7,
    max_tokens: 2500
  },
  {
    headers: {
      'Content-Type': 'application/json',
      'X-Content-Type': 'flux-visual',
      'Authorization': 'Bearer YOUR_TOKEN'
    }
  }
);

const scenes = JSON.parse(visual.data.choices[0].message.content);
```

## Troubleshooting

### Empty Array Output

If you receive `[]`, the input didn't meet validation requirements. Check:
- Input contains complete sentences
- All required fields are present
- Input is properly formatted

### Invalid JSON

If output isn't valid JSON:
- Increase `max_tokens` (try 3000-4000 for long inputs)
- Reduce input complexity
- Check temperature setting (0.7 recommended)

### Missing Scenes

If some sentences are skipped:
- Check that input uses proper sentence boundaries (periods)
- Avoid merged or run-on sentences
- Each sentence should be on its own line or clearly separated

## Configuration

The prompt is loaded from `prompt_flux_visual.md` in your project root. You can customize:
- Visual style preferences
- Timing defaults (currently 3.00s per scene)
- Output format requirements
- Failsafe behavior

## Testing

Test the prompt with a simple input:

```bash
curl -X POST http://localhost:5000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-Content-Type: flux-visual" \
  -d '{
    "model": "gpt-5.2",
    "messages": [
      {
        "role": "user",
        "content": "Title: Test\n\nWelcome: Hello world. This is a test."
      }
    ]
  }'
```

Expected output:
```json
[
  {
    "start_time": 0.00,
    "end_time": 3.00,
    "duration": 3.00,
    "dialogue": "Hello world.",
    "prompt": "..."
  },
  {
    "start_time": 3.00,
    "end_time": 6.00,
    "duration": 3.00,
    "dialogue": "This is a test.",
    "prompt": "..."
  }
]
```
