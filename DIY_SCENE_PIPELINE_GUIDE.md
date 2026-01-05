# DIY Tutorial → TTS-Ready Scene Array Pipeline

Complete guide for converting DIY tutorial scripts into TTS-optimized scene arrays with FLUX Pro 2 visual prompts.

## Overview

This pipeline takes structured DIY tutorial JSON and converts it into an array of scenes, each with:
- **TTS-ready dialogue** (max 2 sentences, proper punctuation, numbers spelled out)
- **FLUX Pro 2 visual prompt** (photorealistic, hands/tools focus, vertical 9:16)
- **Precise timing** (3.00s per scene, no gaps/overlaps)
- **Dialogue-visual alignment** (each visual matches its dialogue)

## Two Methods

### Method 1: Single-Prompt (Recommended for n8n)
Use ChatMock's content-type header for direct conversion.

### Method 2: Multi-Agent Protocol
Use Python script with multiple specialized agents (higher quality, slower).

---

## Method 1: Single-Prompt Pipeline (n8n)

### Step 1: Generate Tutorial Script

**Node 1: ChatMock - Generate DIY Script**

```bash
curl -X POST https://chatmock-prod.fly.dev/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "model": "gpt-5.2",
    "messages": [
      {
        "role": "system",
        "content": "You are a professional DIY tutorial scriptwriter for automated video pipelines. You must output valid JSON only."
      },
      {
        "role": "user",
        "content": "Write a complete DIY tutorial script for: Build a simple wooden shelf"
      }
    ],
    "temperature": 0.7,
    "max_tokens": 2500
  }'
```

**Output**: Structured tutorial JSON with title, hook, materials, steps, etc.

### Step 2: Convert to Scene Array

**Node 2: ChatMock - Generate Scene Array**

```bash
curl -X POST https://chatmock-prod.fly.dev/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-Content-Type: diy-scene" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "model": "gpt-5.2",
    "messages": [
      {
        "role": "user",
        "content": "<PASTE TUTORIAL JSON FROM STEP 1>"
      }
    ],
    "temperature": 0.7,
    "max_tokens": 4000
  }'
```

**Key Points**:
- Use `X-Content-Type: diy-scene` (or `scene-array` or `tts-scene`)
- This activates the specialized prompt
- Output is ready-to-use scene array

---

## n8n Workflow Configuration

### Node 1: HTTP Request - Generate Tutorial

**URL**: `https://chatmock-prod.fly.dev/v1/chat/completions`

**Method**: POST

**Headers**:
```json
{
  "Content-Type": "application/json",
  "Authorization": "Bearer mock-key"
}
```

**Body** (JSON):
```json
{
  "model": "gpt-5.2",
  "messages": [
    {
      "role": "system",
      "content": "You are a professional DIY tutorial scriptwriter for automated video pipelines. You must output valid JSON only. Do not include reasoning, analysis, commentary, markdown, tags, or explanatory text."
    },
    {
      "role": "user",
      "content": "Write a complete DIY tutorial script for this video idea.\n\nvideo_idea: {{ $('Postgres Pick Next Opportunity').item.json.video_idea }}\nvideo_hook: {{ $('Postgres Pick Next Opportunity').item.json.video_hook }}\ndiy_category: {{ $('Postgres Pick Next Opportunity').item.json.diy_category }}\n\nReturn valid JSON matching the tutorial schema. Include at least eight steps with safety notes."
    }
  ],
  "temperature": 0.7,
  "max_tokens": 2500,
  "stream": false
}
```

**Output Path**: `$.choices[0].message.content`

---

### Node 2: Code - Parse Tutorial JSON

**JavaScript**:
```javascript
const tutorialText = $input.item.json.choices[0].message.content;

// Parse the JSON string
const tutorial = JSON.parse(tutorialText);

// Return structured data
return {
  json: {
    tutorial: tutorial
  }
};
```

---

### Node 3: HTTP Request - Generate Scene Array

**URL**: `https://chatmock-prod.fly.dev/v1/chat/completions`

**Method**: POST

**Headers**:
```json
{
  "Content-Type": "application/json",
  "X-Content-Type": "diy-scene",
  "Authorization": "Bearer mock-key"
}
```

**Body** (JSON):
```json
{
  "model": "gpt-5.2",
  "messages": [
    {
      "role": "user",
      "content": "{{ JSON.stringify($('Code - Parse Tutorial').item.json.tutorial) }}"
    }
  ],
  "temperature": 0.7,
  "max_tokens": 4000,
  "stream": false
}
```

**Output Path**: `$.choices[0].message.content`

---

### Node 4: Code - Parse Scene Array

**JavaScript**:
```javascript
const sceneText = $input.item.json.choices[0].message.content;

// Parse the scene array
const scenes = JSON.parse(sceneText);

// Validate structure
if (!Array.isArray(scenes) || scenes.length === 0) {
  throw new Error('Invalid scene array returned');
}

// Validate each scene has required fields
scenes.forEach((scene, idx) => {
  const required = ['start_time', 'end_time', 'duration', 'dialogue', 'prompt'];
  const missing = required.filter(key => !(key in scene));

  if (missing.length > 0) {
    throw new Error(`Scene ${idx} missing: ${missing.join(', ')}`);
  }
});

return {
  json: {
    scenes: scenes,
    total_scenes: scenes.length,
    total_duration: scenes[scenes.length - 1].end_time
  }
};
```

---

### Node 5: Loop Over Scenes - Generate Images

**For Each Scene**:

```javascript
// Access current scene
const scene = $item('0').json;

// Send to FLUX Pro 2
const fluxPayload = {
  prompt: scene.prompt,
  width: 576,  // 9:16 vertical
  height: 1024,
  num_inference_steps: 40,
  guidance_scale: 7.5,
  seed: -1
};

// Return for next node
return {
  json: {
    scene_number: $itemIndex,
    dialogue: scene.dialogue,
    start_time: scene.start_time,
    end_time: scene.end_time,
    flux_payload: fluxPayload
  }
};
```

---

## Example Output

**Input Tutorial** (abbreviated):
```json
{
  "title": "Build a Simple Shelf",
  "hook": "Learn to build a shelf in one hour!",
  "welcome": "Hey there! Today we're building a beginner-friendly shelf.",
  "steps": [
    {
      "step": 1,
      "action": "Measure and mark",
      "detail": "Use measuring tape to mark at 24 inches"
    }
  ]
}
```

**Output Scene Array**:
```json
[
  {
    "start_time": 0.00,
    "end_time": 3.00,
    "duration": 3.00,
    "dialogue": "Learn to build a shelf in one hour!",
    "prompt": "Indoor workshop with warm natural lighting, wooden workbench in background, various woodworking tools organized on wall-mounted pegboard, close-up of hands gesturing excitedly toward camera, realistic depth of field with blurred workshop background, anatomically correct hands with visible skin texture, photorealistic, vertical 9:16"
  },
  {
    "start_time": 3.00,
    "end_time": 6.00,
    "duration": 3.00,
    "dialogue": "Hey there! Today we're building a beginner-friendly shelf.",
    "prompt": "Indoor workspace with wooden shelf components laid out on workbench, close-up of hands gesturing welcomingly, tools and materials visible in organized arrangement, natural window lighting from left side, soft focus background showing workshop setting, anatomically correct hands with natural positioning, photorealistic, vertical 9:16"
  },
  {
    "start_time": 6.00,
    "end_time": 9.00,
    "duration": 3.00,
    "dialogue": "Step one: Measure and mark. Use measuring tape to mark at twenty four inches.",
    "prompt": "Close-up of hands holding yellow measuring tape extended along wooden board, pencil in right hand marking exact measurement point, wooden workbench surface visible, natural overhead workshop lighting, sharp focus on hands and measuring tape with blurred background, anatomically correct fingers gripping tools, visible wood grain texture, photorealistic, vertical 9:16"
  }
]
```

---

## Method 2: Multi-Agent Protocol (Python)

For higher quality output with specialized agents.

### Installation

```bash
pip install requests
```

### Usage

```python
from diy_scene_generator_protocol import DIYSceneGeneratorProtocol
import json

# Load your tutorial JSON
with open('tutorial.json', 'r') as f:
    tutorial = json.load(f)

# Initialize protocol (point to your ChatMock instance)
protocol = DIYSceneGeneratorProtocol(base_url="https://chatmock-prod.fly.dev")

# Load tutorial
protocol.load_tutorial(tutorial)

# Generate scenes (runs multi-agent pipeline)
scenes = protocol.generate_scenes()

# Save output
protocol.save_output("scenes_output.json")

# Print results
print(json.dumps(scenes, indent=2))
```

### Multi-Agent Steps

The protocol runs 5 specialized agents:

1. **Script Analyzer** - Identifies key moments in tutorial
2. **Dialogue Writer** - Creates TTS-ready dialogue (2 sentences max)
3. **TTS Optimizer** - Fixes gotchas (numbers, abbreviations, punctuation)
4. **Visual Prompter** - Generates FLUX Pro 2 prompts matching dialogue
5. **Scene Coordinator** - Assembles final array with perfect timing

---

## TTS Optimization Examples

### Numbers

❌ **Bad**: "Use a 2x4 board"
✅ **Good**: "Use a two by four board"

❌ **Bad**: "Drill 3/4 inch holes"
✅ **Good**: "Drill three quarter inch holes"

❌ **Bad**: "This costs $5"
✅ **Good**: "This costs five dollars"

### Abbreviations

❌ **Bad**: "Today's DIY project"
✅ **Good**: "Today's D I Y project" or "Today's do it yourself project"

❌ **Bad**: "Use PVC pipe"
✅ **Good**: "Use P V C pipe" or "Use plastic pipe"

### Punctuation

❌ **Bad**: "Measure the board then cut it then sand it"
✅ **Good**: "Measure the board, then cut it and sand it."

❌ **Bad**: "First check if you have these items: wood glue sandpaper and a brush"
✅ **Good**: "First, check if you have these items. Wood glue, sandpaper, and a brush."

### Sentence Length

❌ **Bad**: "In this step we're going to carefully measure the exact length of the board using a measuring tape and then we'll mark it with a pencil making sure to double check before we cut."
✅ **Good**: "In this step, measure the board carefully with a measuring tape. Then mark it with a pencil, and double check before cutting."

---

## FLUX Pro 2 Prompt Guidelines

### Structure

```
[Main subject], [hand details], [tool/material details], [lighting], [depth of field], [hand anatomy notes], photorealistic, vertical 9:16
```

### Required Elements

✅ **Hands**: Always include hand descriptions
✅ **Tools**: Specific tool names (saw, drill, measuring tape, etc.)
✅ **Materials**: Wood grain, metal surface, texture details
✅ **Lighting**: Natural (window from left/right) or overhead workshop
✅ **Depth of field**: Blurred background, sharp focus on subject
✅ **Ending**: MUST end with "photorealistic, vertical 9:16"

### Forbidden Elements

❌ Text overlays, captions, subtitles
❌ Logos, watermarks, brand names
❌ UI elements, buttons
❌ CGI, cartoon, illustration
❌ Motion blur
❌ Multiple exposures

### Example Prompts

**Measuring Scene**:
```
Close-up of hands holding yellow measuring tape extended along wooden board, right hand pressing tape firmly at starting point, left hand extending tape to twenty four inch mark, pencil visible in shirt pocket, wooden workbench surface with visible grain, natural overhead workshop lighting, realistic depth of field with sharp focus on measuring tape numbers and blurred background, anatomically correct fingers with natural skin tone and texture, photorealistic, vertical 9:16
```

**Cutting Scene**:
```
Indoor workshop with hands positioning circular saw against marked cut line on wooden board, left hand steadying board edge, right hand gripping saw handle with proper form, safety glasses visible on workbench beside hands, natural window lighting from right side casting soft shadows, realistic depth of field with sharp focus on saw blade and hands, blurred workshop background, anatomically correct hand positioning showing proper grip technique, photorealistic, vertical 9:16
```

---

## Troubleshooting

### Empty Array `[]`

**Cause**: Input validation failed

**Solutions**:
- Verify tutorial JSON has all required fields (title, hook, steps, etc.)
- Ensure steps array has at least 1 step
- Check JSON is valid (no syntax errors)

### Dialogue Not TTS-Ready

**Symptoms**: Numbers as digits, abbreviations, run-on sentences

**Solution**: Set temperature lower (0.5-0.6) for more consistent formatting

### Visual Prompts Don't Match Dialogue

**Symptom**: Prompt describes different action than dialogue

**Solution**: Increase max_tokens to 4000+ to give model more space for detailed prompts

### Timing Gaps/Overlaps

**Symptom**: Scenes have incorrect start/end times

**Solution**: This should never happen with the system prompt, but verify output with:
```javascript
scenes.forEach((scene, idx) => {
  const expected_start = idx * 3.0;
  const expected_end = (idx + 1) * 3.0;

  if (scene.start_time !== expected_start || scene.end_time !== expected_end) {
    console.error(`Scene ${idx} timing error`);
  }
});
```

---

## Testing

### Quick Test

```bash
curl -X POST http://localhost:5000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "X-Content-Type: diy-scene" \
  -d '{
    "model": "gpt-5.2",
    "messages": [
      {
        "role": "user",
        "content": "{\"title\":\"Test\",\"hook\":\"Quick test.\",\"welcome\":\"Hello there.\",\"steps\":[{\"step\":1,\"action\":\"Test action\"}]}"
      }
    ]
  }'
```

Expected: JSON array with 3+ scenes

---

## Production Deployment

### Environment Variables

```bash
# If using ChatMock Pro (deployed)
export CHATMOCK_URL="https://chatmock-prod.fly.dev"
export CHATMOCK_API_KEY="your-api-key"

# If using local development
export CHATMOCK_URL="http://localhost:5000"
```

### n8n Environment Setup

1. Create credentials for ChatMock
2. Set base URL to your deployed instance
3. Use `X-Content-Type: diy-scene` header in all scene generation requests

---

## Performance Tips

1. **Batch Processing**: Generate scenes for multiple tutorials in parallel
2. **Caching**: Cache tutorial → scene conversions to avoid regeneration
3. **Temperature**: Use 0.6-0.7 for consistent output
4. **Max Tokens**: Set to 4000+ for complex tutorials with 10+ steps
5. **Retry Logic**: Implement retry with exponential backoff for API timeouts

---

## Complete n8n Workflow Summary

```
[Postgres: Get Video Idea]
    ↓
[ChatMock: Generate Tutorial Script]
    ↓
[Code: Parse Tutorial JSON]
    ↓
[ChatMock: Generate Scene Array] ← X-Content-Type: diy-scene
    ↓
[Code: Parse & Validate Scenes]
    ↓
[Loop: For Each Scene]
    ↓
[FLUX Pro 2: Generate Image]
    ↓
[TTS: Generate Audio from Dialogue]
    ↓
[FFmpeg: Combine Image + Audio]
    ↓
[Concatenate All Scenes]
    ↓
[Upload Final Video]
```

---

## Support

For issues or questions:
- Check FLUX_VISUAL_PROMPT_GUIDE.md for FLUX-specific details
- Review diy_scene_generator_protocol.py for multi-agent implementation
- Test with simple tutorial first before complex 10+ step tutorials

---

## License

MIT
