#!/usr/bin/env python3
"""
DIY Tutorial to TTS-Ready Scene Generator Protocol
Multi-agent system that converts structured DIY tutorials into FLUX Pro 2 scene arrays

This system creates specialized AI agents that:
1. Analyze tutorial structure and identify key moments
2. Generate TTS-optimized dialogue (max 2 sentences, proper punctuation)
3. Create matching FLUX Pro 2 visual prompts
4. Coordinate scenes for logical flow and dialogue-visual alignment
5. Validate TTS readiness (commas, pauses, natural speech)
6. Output final scene array ready for video generation
"""

import json
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import requests


class AgentRole(Enum):
    """Different agent roles in scene generation"""

    SCRIPT_ANALYZER = "script_analyzer"  # Analyzes tutorial structure
    DIALOGUE_WRITER = "dialogue_writer"  # Creates TTS-ready dialogue
    VISUAL_PROMPTER = "visual_prompter"  # Generates FLUX prompts
    TTS_OPTIMIZER = "tts_optimizer"  # Ensures TTS compatibility
    SCENE_COORDINATOR = "scene_coordinator"  # Orchestrates final output


@dataclass
class Agent:
    """Represents a specialized agent"""

    role: AgentRole
    name: str
    expertise: str
    system_prompt: str

    def __str__(self):
        return f"[{self.role.value.upper()}] {self.name}"


@dataclass
class Scene:
    """Single scene in the output array"""

    start_time: float
    end_time: float
    duration: float
    dialogue: str
    prompt: str

    def to_dict(self):
        return {
            "start_time": round(self.start_time, 2),
            "end_time": round(self.end_time, 2),
            "duration": round(self.duration, 2),
            "dialogue": self.dialogue,
            "prompt": self.prompt
        }


class ChatMockAgent:
    """Agent that uses ChatMock for specialized tasks"""

    def __init__(self, agent: Agent, base_url: str = "http://localhost:5000"):
        self.agent = agent
        self.base_url = base_url.rstrip("/")
        self.api_url = f"{self.base_url}/v1/chat/completions"

    def call_chatmock(self, user_prompt: str, temperature: float = 0.7) -> str:
        """Call ChatMock with agent's specialized system prompt"""

        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer mock-key"
        }

        payload = {
            "model": "gpt-5.2",
            "messages": [
                {"role": "system", "content": self.agent.system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": temperature,
            "max_tokens": 3000,
            "stream": False
        }

        try:
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=120)
            if response.status_code == 200:
                data = response.json()
                if "choices" in data and data["choices"]:
                    return data["choices"][0]["message"]["content"]
            return f"Error: {response.status_code} - {response.text}"
        except Exception as e:
            return f"Exception: {str(e)}"


class DIYSceneGeneratorProtocol:
    """Orchestrates multi-agent scene generation"""

    def __init__(self, base_url: str = "http://localhost:5000"):
        self.base_url = base_url
        self.agents = self._create_agents()
        self.tutorial_data = None
        self.scenes = []

    def _create_agents(self) -> Dict[AgentRole, ChatMockAgent]:
        """Create all specialized agents"""

        agents_config = {
            AgentRole.SCRIPT_ANALYZER: Agent(
                role=AgentRole.SCRIPT_ANALYZER,
                name="Script Analyzer",
                expertise="Tutorial structure analysis and key moment identification",
                system_prompt="""You are a Script Analyzer specializing in DIY tutorial content.

Your task: Analyze the tutorial structure and identify key narrative moments.

For each section (hook, welcome, materials, steps, showcase, outro):
- Identify 1-2 key sentences that capture the essence
- Note visual opportunities (hands, tools, materials, workspace)
- Suggest natural speech breakpoints
- Flag complex terms that need pronunciation care

Output JSON:
{
  "key_moments": [
    {
      "section": "hook",
      "text": "sentence",
      "visual_focus": "what to show",
      "tts_notes": "pronunciation or pacing notes"
    }
  ],
  "total_estimated_scenes": number,
  "narrative_flow": "description of overall pacing"
}"""
            ),

            AgentRole.DIALOGUE_WRITER: Agent(
                role=AgentRole.DIALOGUE_WRITER,
                name="Dialogue Writer",
                expertise="TTS-optimized scriptwriting",
                system_prompt="""You are a Dialogue Writer specializing in TTS-ready scripts.

CRITICAL RULES:
- Maximum 2 sentences per dialogue block
- Use commas for natural pauses
- Avoid abbreviations (use "and" not "&")
- Spell out numbers under 100
- Use periods for full stops, commas for breath pauses
- No special characters that confuse TTS (%, $, @, etc.)
- Natural, conversational tone
- Each sentence should be speakable in one breath

Input: Key moments with narrative context
Output: TTS-ready dialogue blocks

Output JSON array:
[
  {
    "dialogue": "First sentence with natural comma pauses, if needed. Second sentence for emphasis or detail.",
    "tts_quality_score": 0-100,
    "estimated_duration_seconds": 3.0
  }
]"""
            ),

            AgentRole.VISUAL_PROMPTER: Agent(
                role=AgentRole.VISUAL_PROMPTER,
                name="Visual Prompter",
                expertise="FLUX Pro 2 prompt generation",
                system_prompt="""You are a Visual Prompter specializing in FLUX Pro 2 image generation.

FLUX Pro 2 REQUIREMENTS:
- Photorealistic, indoor workshop/instructional settings only
- Emphasize: hands (anatomically correct), tools, materials, workspace
- Natural lighting (window light, workshop lighting)
- Realistic depth of field
- Vertical 9:16 aspect ratio
- NO text overlays, captions, logos, watermarks, UI elements
- NO CGI, illustration, cartoon, stylization
- NO motion blur

PROMPT STRUCTURE:
"[Main subject and action], [hand/tool details], [materials visible], [lighting description], [depth of field notes], [specific hand anatomy details], photorealistic, vertical 9:16"

Input: Dialogue text and scene context
Output: FLUX Pro 2 optimized prompt

Each prompt must:
- Match the dialogue content exactly
- Show hands performing relevant actions
- Include specific tool/material details
- End with "photorealistic, vertical 9:16"

Output JSON:
{
  "prompt": "single paragraph visual description",
  "visual_elements": ["hands", "tools", "materials"],
  "lighting": "description",
  "matches_dialogue": true/false
}"""
            ),

            AgentRole.TTS_OPTIMIZER: Agent(
                role=AgentRole.TTS_OPTIMIZER,
                name="TTS Optimizer",
                expertise="TTS compatibility and natural speech flow",
                system_prompt="""You are a TTS Optimizer ensuring perfect text-to-speech output.

CHECK FOR:
✓ Proper comma placement for breath pauses
✓ No run-on sentences
✓ Numbers spelled out correctly
✓ Abbreviations expanded
✓ Natural speech rhythm
✓ Correct punctuation (. ! ?)
✓ No special characters
✓ Pronunciation-friendly phrasing

COMMON TTS GOTCHAS:
❌ "DIY" → ✓ "D I Y" or "do it yourself"
❌ "10x better" → ✓ "ten times better"
❌ "Use a 2x4" → ✓ "Use a two by four"
❌ "$5" → ✓ "five dollars"
❌ "3/4 inch" → ✓ "three quarter inch"

Input: Dialogue text
Output: Optimized dialogue with quality score

Output JSON:
{
  "original": "text",
  "optimized": "corrected text",
  "changes_made": ["list of fixes"],
  "tts_ready": true/false,
  "quality_score": 0-100
}"""
            ),

            AgentRole.SCENE_COORDINATOR: Agent(
                role=AgentRole.SCENE_COORDINATOR,
                name="Scene Coordinator",
                expertise="Scene assembly and dialogue-visual alignment",
                system_prompt="""You are a Scene Coordinator ensuring perfect scene assembly.

RESPONSIBILITIES:
- Verify dialogue and visual prompts match
- Ensure logical scene order
- Calculate accurate timing (3.00s per scene)
- Validate no gaps or overlaps in timing
- Confirm each scene is self-contained
- Check narrative flow

TIMING RULES:
- Each scene: duration = 3.00
- Scene 1: start_time = 0.00, end_time = 3.00
- Scene N: start_time = (N-1) * 3.00, end_time = N * 3.00
- No gaps, no overlaps

VALIDATION:
- Dialogue matches visual content
- Scenes follow tutorial structure order
- All required keys present
- No null values
- Proper decimal formatting (X.00)

Output: Final scene array ready for video generation"""
            )
        }

        return {
            role: ChatMockAgent(agent, self.base_url)
            for role, agent in agents_config.items()
        }

    def load_tutorial(self, tutorial_json: Dict[str, Any]):
        """Load tutorial data"""
        self.tutorial_data = tutorial_json
        print(f"✓ Loaded tutorial: {tutorial_json.get('title', 'Untitled')}")

    def step_1_analyze_structure(self) -> Dict[str, Any]:
        """Step 1: Analyze tutorial structure"""
        print("\n[STEP 1] Analyzing tutorial structure...")

        analyzer = self.agents[AgentRole.SCRIPT_ANALYZER]

        prompt = f"""Analyze this DIY tutorial and identify key moments for scene generation:

{json.dumps(self.tutorial_data, indent=2)}

Identify key sentences from each section that should become scenes. Focus on:
- Hook (1 scene)
- Welcome (1 scene)
- Project intro (2-3 scenes)
- Materials (1 scene per 2-3 materials)
- Steps (1 scene per step)
- Showcase (2-3 scenes)
- Outro (1 scene)

Return JSON only."""

        response = analyzer.call_chatmock(prompt, temperature=0.5)

        try:
            analysis = json.loads(response)
            print(f"✓ Identified {analysis.get('total_estimated_scenes', 0)} scenes")
            return analysis
        except json.JSONDecodeError:
            print(f"✗ Failed to parse analysis: {response[:200]}")
            return {"key_moments": [], "total_estimated_scenes": 0}

    def step_2_generate_dialogue(self, analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Step 2: Generate TTS-ready dialogue"""
        print("\n[STEP 2] Generating TTS-ready dialogue...")

        writer = self.agents[AgentRole.DIALOGUE_WRITER]

        prompt = f"""Create TTS-ready dialogue for each key moment:

{json.dumps(analysis['key_moments'], indent=2)}

For each moment, write 1-2 sentences max. Follow TTS best practices.

Return JSON array of dialogue blocks."""

        response = writer.call_chatmock(prompt, temperature=0.7)

        try:
            dialogues = json.loads(response)
            print(f"✓ Generated {len(dialogues)} dialogue blocks")
            return dialogues
        except json.JSONDecodeError:
            print(f"✗ Failed to parse dialogues: {response[:200]}")
            return []

    def step_3_optimize_tts(self, dialogues: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Step 3: Optimize dialogue for TTS"""
        print("\n[STEP 3] Optimizing for TTS...")

        optimizer = self.agents[AgentRole.TTS_OPTIMIZER]
        optimized = []

        for idx, dialogue_block in enumerate(dialogues):
            prompt = f"""Optimize this dialogue for TTS:

{dialogue_block['dialogue']}

Check for TTS gotchas and return optimized version."""

            response = optimizer.call_chatmock(prompt, temperature=0.3)

            try:
                result = json.loads(response)
                optimized.append({
                    "dialogue": result['optimized'],
                    "quality_score": result['quality_score']
                })
            except json.JSONDecodeError:
                # Fallback: use original
                optimized.append(dialogue_block)

        print(f"✓ Optimized {len(optimized)} dialogue blocks")
        return optimized

    def step_4_generate_visuals(self, dialogues: List[Dict[str, Any]], analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Step 4: Generate FLUX Pro 2 visual prompts"""
        print("\n[STEP 4] Generating FLUX Pro 2 visual prompts...")

        prompter = self.agents[AgentRole.VISUAL_PROMPTER]
        scenes_with_visuals = []

        for idx, dialogue_block in enumerate(dialogues):
            context = analysis['key_moments'][idx] if idx < len(analysis['key_moments']) else {}

            prompt = f"""Generate FLUX Pro 2 prompt for this dialogue:

Dialogue: {dialogue_block['dialogue']}
Context: {json.dumps(context)}

Create a matching visual prompt following FLUX Pro 2 requirements."""

            response = prompter.call_chatmock(prompt, temperature=0.7)

            try:
                visual = json.loads(response)
                scenes_with_visuals.append({
                    "dialogue": dialogue_block['dialogue'],
                    "prompt": visual['prompt']
                })
            except json.JSONDecodeError:
                # Fallback: generic prompt
                scenes_with_visuals.append({
                    "dialogue": dialogue_block['dialogue'],
                    "prompt": f"Indoor workshop setting, close-up of hands working, tools and materials visible, natural lighting, photorealistic, vertical 9:16"
                })

        print(f"✓ Generated {len(scenes_with_visuals)} visual prompts")
        return scenes_with_visuals

    def step_5_coordinate_scenes(self, scenes_data: List[Dict[str, Any]]) -> List[Scene]:
        """Step 5: Assemble final scene array"""
        print("\n[STEP 5] Coordinating scenes and timing...")

        scenes = []
        for idx, scene_data in enumerate(scenes_data):
            scene = Scene(
                start_time=idx * 3.0,
                end_time=(idx + 1) * 3.0,
                duration=3.0,
                dialogue=scene_data['dialogue'],
                prompt=scene_data['prompt']
            )
            scenes.append(scene)

        print(f"✓ Assembled {len(scenes)} scenes with proper timing")
        return scenes

    def generate_scenes(self) -> List[Dict[str, Any]]:
        """Run full pipeline"""
        print("\n" + "="*60)
        print("DIY SCENE GENERATOR - Multi-Agent Pipeline")
        print("="*60)

        if not self.tutorial_data:
            print("✗ No tutorial loaded")
            return []

        # Step 1: Analyze structure
        analysis = self.step_1_analyze_structure()

        # Step 2: Generate dialogue
        dialogues = self.step_2_generate_dialogue(analysis)

        # Step 3: Optimize for TTS
        optimized_dialogues = self.step_3_optimize_tts(dialogues)

        # Step 4: Generate visual prompts
        scenes_with_visuals = self.step_4_generate_visuals(optimized_dialogues, analysis)

        # Step 5: Coordinate scenes
        self.scenes = self.step_5_coordinate_scenes(scenes_with_visuals)

        print("\n" + "="*60)
        print(f"✓ COMPLETE: Generated {len(self.scenes)} scenes")
        print("="*60)

        return [scene.to_dict() for scene in self.scenes]

    def save_output(self, filename: str = "scene_output.json"):
        """Save scene array to file"""
        output = [scene.to_dict() for scene in self.scenes]
        with open(filename, 'w') as f:
            json.dump(output, f, indent=2)
        print(f"\n✓ Saved to {filename}")


def main():
    """Example usage"""

    # Example tutorial JSON (abbreviated for demo)
    tutorial = {
        "title": "Build a Simple Wooden Shelf",
        "hook": "Learn to build a custom shelf in under an hour!",
        "welcome": "Hey there! Today we're building a beginner-friendly wooden shelf.",
        "project_intro": {
            "what": "A simple wall-mounted shelf using basic tools.",
            "benefit": "You'll learn fundamental woodworking skills.",
            "who_is_this_for": "Perfect for complete beginners."
        },
        "materials": [
            {
                "item": "1x8 pine board (6 feet)",
                "why": "Main shelf material - easy to cut and finish",
                "sourcing": "Any home improvement store",
                "budget_tip": "Check the scrap bin for smaller pieces",
                "common_substitute": "Plywood or MDF for budget builds"
            }
        ],
        "steps": [
            {
                "step": 1,
                "action": "Measure and mark your cuts",
                "detail": "Use a measuring tape and mark cut lines with a pencil at 24 inches and 48 inches.",
                "safety": "Wear safety glasses when measuring and marking",
                "common_mistake": "Not measuring twice before cutting",
                "quality_check": "Ensure marks are straight and at the correct measurements"
            }
        ],
        "showcase": {
            "visual": "Show the finished shelf mounted on the wall with decorative items",
            "test": "Place books or items on the shelf to test load capacity",
            "finish_tip": "Apply a second coat of finish for better durability"
        },
        "outro": "Great job! You've built your first shelf!",
        "estimated_runtime_seconds": 180
    }

    # Initialize protocol
    protocol = DIYSceneGeneratorProtocol(base_url="http://localhost:5000")

    # Load tutorial
    protocol.load_tutorial(tutorial)

    # Generate scenes
    scenes = protocol.generate_scenes()

    # Print results
    print("\n" + "="*60)
    print("GENERATED SCENES:")
    print("="*60)
    print(json.dumps(scenes, indent=2))

    # Save output
    protocol.save_output("diy_scenes.json")


if __name__ == "__main__":
    main()
