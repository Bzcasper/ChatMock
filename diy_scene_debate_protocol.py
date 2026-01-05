#!/usr/bin/env python3
"""
DIY Scene Debate Protocol - Multi-Agent Refinement System
Similar to image debate, but for dialogue and FLUX prompts

Workflow:
1. Generate initial tutorial from video idea
2. Convert tutorial to draft scenes
3. DEBATE ROUND 1: Critique dialogue (TTS readiness)
4. DEBATE ROUND 2: Critique image prompts (FLUX Pro 2 quality)
5. DEBATE ROUND 3: Critique coherence (dialogue-visual alignment)
6. Synthesize improvements
7. Generate refined scene array
8. Optional: Iterate until perfect
9. Output final JSON
"""

import json
import time
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
import requests


class DebateRole(Enum):
    """Agent roles in the debate"""

    # Round 1: Dialogue Critics
    TTS_CRITIC = "tts_critic"                    # Finds TTS issues
    DIALOGUE_FLOW_CRITIC = "dialogue_flow"       # Checks natural flow
    SENTENCE_CRITIC = "sentence_critic"           # Max 2 sentences rule

    # Round 2: Visual Critics
    FLUX_CRITIC = "flux_critic"                  # FLUX Pro 2 compliance
    HAND_ANATOMY_CRITIC = "hand_anatomy"         # Hand detail quality
    LIGHTING_CRITIC = "lighting_critic"          # Lighting descriptions

    # Round 3: Coherence Critics
    ALIGNMENT_CRITIC = "alignment_critic"        # Dialogue-visual match
    FLOW_CRITIC = "flow_critic"                  # Scene sequence logic
    TIMING_CRITIC = "timing_critic"              # Timing validation

    # Final Synthesis
    SYNTHESIZER = "synthesizer"                  # Combines all feedback


@dataclass
class Agent:
    """Debate agent with specialized expertise"""

    role: DebateRole
    name: str
    expertise: str
    critique_prompt: str

    def __str__(self):
        return f"[{self.role.value.upper()}] {self.name}"


@dataclass
class DebateRound:
    """Single round of debate"""

    round_number: int
    focus: str  # "dialogue", "visuals", "coherence"
    critiques: List[Dict[str, Any]]
    synthesis: str
    improvements: List[str]


@dataclass
class SceneVersion:
    """Version of scene array at different stages"""

    version: int
    scenes: List[Dict[str, Any]]
    quality_scores: Dict[str, float]
    timestamp: str


class ChatMockDebateAgent:
    """Agent that uses ChatMock for debate"""

    def __init__(self, agent: Agent, base_url: str = "http://localhost:5000"):
        self.agent = agent
        self.base_url = base_url.rstrip("/")
        self.api_url = f"{self.base_url}/v1/chat/completions"

    def critique(self, scenes: List[Dict[str, Any]], focus: str) -> Dict[str, Any]:
        """Generate critique based on agent's expertise"""

        prompt = f"""{self.agent.critique_prompt}

FOCUS: {focus}

CURRENT SCENES:
{json.dumps(scenes, indent=2)}

Provide critique in JSON format:
{{
  "agent": "{self.agent.name}",
  "role": "{self.agent.role.value}",
  "issues_found": [
    {{
      "scene_index": 0,
      "issue": "description",
      "severity": "high/medium/low",
      "suggestion": "how to fix"
    }}
  ],
  "overall_quality_score": 0-100,
  "key_improvements": ["improvement 1", "improvement 2"]
}}
"""

        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer mock-key"
        }

        payload = {
            "model": "gpt-5.2",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.6,
            "max_tokens": 2000,
            "stream": False
        }

        try:
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=120)
            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                return json.loads(content)
            return {"error": f"Status {response.status_code}"}
        except Exception as e:
            return {"error": str(e)}


class DIYSceneDebateProtocol:
    """Orchestrates multi-round debate for scene refinement"""

    def __init__(self, base_url: str = "http://localhost:5000", max_rounds: int = 3):
        self.base_url = base_url
        self.max_rounds = max_rounds
        self.agents = self._create_agents()
        self.video_idea = None
        self.tutorial_json = None
        self.scene_versions = []
        self.debate_rounds = []

    def _create_agents(self) -> Dict[DebateRole, ChatMockDebateAgent]:
        """Create all debate agents"""

        agents_config = {
            # === ROUND 1: DIALOGUE CRITICS ===

            DebateRole.TTS_CRITIC: Agent(
                role=DebateRole.TTS_CRITIC,
                name="TTS Quality Critic",
                expertise="Text-to-speech optimization and gotchas",
                critique_prompt="""You are a TTS Quality Critic.

FIND THESE ISSUES:
❌ Numbers as digits (3, 24, 3/4) instead of spelled out
❌ Abbreviations (DIY, PVC, etc.) not expanded
❌ Special characters ($, %, &, @)
❌ Missing commas for breath pauses
❌ Run-on sentences
❌ Awkward phrasing for speech

RATE: 0-100 for TTS readiness
SUGGEST: Exact corrected dialogue for each issue"""
            ),

            DebateRole.DIALOGUE_FLOW_CRITIC: Agent(
                role=DebateRole.DIALOGUE_FLOW_CRITIC,
                name="Dialogue Flow Critic",
                expertise="Natural speech patterns and conversational tone",
                critique_prompt="""You are a Dialogue Flow Critic.

CHECK:
- Does dialogue sound natural when read aloud?
- Are transitions between scenes smooth?
- Is tone consistent (friendly, instructional)?
- Are sentences varied (not all same structure)?
- Does each sentence serve a purpose?

RATE: 0-100 for natural flow
SUGGEST: Rewrites for awkward phrases"""
            ),

            DebateRole.SENTENCE_CRITIC: Agent(
                role=DebateRole.SENTENCE_CRITIC,
                name="Sentence Length Critic",
                expertise="Enforcing 2-sentence maximum rule",
                critique_prompt="""You are a Sentence Length Critic.

STRICT RULE: Maximum 2 sentences per scene dialogue

COUNT:
- Count sentences in each dialogue
- Flag any with 3+ sentences
- Check if sentences can be combined or split

RATE: 0-100 for rule compliance
SUGGEST: How to consolidate to 2 sentences max"""
            ),

            # === ROUND 2: VISUAL CRITICS ===

            DebateRole.FLUX_CRITIC: Agent(
                role=DebateRole.FLUX_CRITIC,
                name="FLUX Pro 2 Compliance Critic",
                expertise="FLUX Pro 2 prompt requirements and best practices",
                critique_prompt="""You are a FLUX Pro 2 Compliance Critic.

REQUIRED ELEMENTS:
✓ "photorealistic, vertical 9:16" at end
✓ Indoor workshop/instructional setting
✓ Hand descriptions (anatomically correct)
✓ Specific tool names
✓ Material details (wood grain, texture)
✓ Lighting description
✓ Depth of field notes

FORBIDDEN:
❌ Text overlays, captions, logos
❌ UI elements, buttons
❌ CGI, cartoon, illustration
❌ Motion blur

RATE: 0-100 for FLUX compliance
SUGGEST: Missing elements or forbidden items to remove"""
            ),

            DebateRole.HAND_ANATOMY_CRITIC: Agent(
                role=DebateRole.HAND_ANATOMY_CRITIC,
                name="Hand Anatomy Detail Critic",
                expertise="Anatomically correct hand descriptions for image generation",
                critique_prompt="""You are a Hand Anatomy Detail Critic.

HANDS ARE CRITICAL FOR DIY VISUALS

CHECK:
- Are hands mentioned in EVERY prompt?
- Are hand positions described (gripping, holding, pointing)?
- Are fingers mentioned specifically?
- Is skin texture/tone noted?
- Are hand-tool interactions clear?
- Are both hands described if relevant?

RATE: 0-100 for hand detail quality
SUGGEST: Specific hand anatomy additions"""
            ),

            DebateRole.LIGHTING_CRITIC: Agent(
                role=DebateRole.LIGHTING_CRITIC,
                name="Lighting Description Critic",
                expertise="Lighting descriptions for photorealistic rendering",
                critique_prompt="""You are a Lighting Description Critic.

LIGHTING MAKES OR BREAKS PHOTOREALISM

CHECK:
- Is lighting source specified?
- Is direction mentioned (from left, overhead, etc.)?
- Is quality described (warm, natural, soft)?
- Are shadows or highlights mentioned?
- Is depth of field related to lighting?

RATE: 0-100 for lighting detail
SUGGEST: Specific lighting improvements"""
            ),

            # === ROUND 3: COHERENCE CRITICS ===

            DebateRole.ALIGNMENT_CRITIC: Agent(
                role=DebateRole.ALIGNMENT_CRITIC,
                name="Dialogue-Visual Alignment Critic",
                expertise="Ensuring dialogue and visuals match",
                critique_prompt="""You are a Dialogue-Visual Alignment Critic.

CRITICAL: Dialogue and prompt MUST match

CHECK EACH SCENE:
- If dialogue says "measure", does prompt show measuring?
- If dialogue mentions tool, does prompt show that tool?
- If dialogue says "Step 1", does visual show step 1 action?
- Are materials mentioned in dialogue visible in prompt?

RATE: 0-100 for alignment
SUGGEST: Specific mismatches to fix"""
            ),

            DebateRole.FLOW_CRITIC: Agent(
                role=DebateRole.FLOW_CRITIC,
                name="Scene Flow Logic Critic",
                expertise="Logical sequence and narrative progression",
                critique_prompt="""You are a Scene Flow Logic Critic.

SCENES SHOULD TELL A STORY

CHECK:
- Do scenes follow logical order (hook → steps → outro)?
- Are transitions smooth?
- Is there a clear beginning, middle, end?
- Do steps build on each other?
- Is pacing appropriate?

RATE: 0-100 for flow quality
SUGGEST: Scene reordering or transition improvements"""
            ),

            DebateRole.TIMING_CRITIC: Agent(
                role=DebateRole.TIMING_CRITIC,
                name="Timing Validation Critic",
                expertise="Timing accuracy and validation",
                critique_prompt="""You are a Timing Validation Critic.

VALIDATE:
- All scenes are exactly 3.00 duration
- start_time = (scene_index × 3.00)
- end_time = start_time + 3.00
- No gaps between scenes
- No overlaps
- Proper decimal formatting (X.00)

RATE: 0-100 for timing accuracy
SUGGEST: Timing corrections if needed"""
            ),

            # === SYNTHESIZER ===

            DebateRole.SYNTHESIZER: Agent(
                role=DebateRole.SYNTHESIZER,
                name="Feedback Synthesizer",
                expertise="Combining all critiques into actionable improvements",
                critique_prompt="""You are the Feedback Synthesizer.

INPUT: All critiques from debate rounds

OUTPUT: Unified improvement plan

PRIORITIZE:
1. Critical issues (TTS errors, FLUX violations, misalignment)
2. Quality improvements (flow, detail, coherence)
3. Polish (minor refinements)

Return JSON:
{
  "priority_fixes": [
    {
      "scene_index": 0,
      "fix": "description",
      "applies_to": "dialogue/prompt/both"
    }
  ],
  "quality_score_before": 0-100,
  "estimated_score_after": 0-100,
  "synthesis": "overall summary"
}"""
            )
        }

        return {
            role: ChatMockDebateAgent(agent, self.base_url)
            for role, agent in agents_config.items()
        }

    def step_1_generate_tutorial(self, video_idea: str, video_hook: str, diy_category: str) -> Dict[str, Any]:
        """Step 1: Generate tutorial from video idea"""
        print("\n" + "="*60)
        print("[STEP 1] GENERATING TUTORIAL FROM VIDEO IDEA")
        print("="*60)

        self.video_idea = {
            "idea": video_idea,
            "hook": video_hook,
            "category": diy_category
        }

        # Call ChatMock to generate tutorial
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer mock-key"
        }

        system_prompt = """You are a professional DIY tutorial scriptwriter for automated video pipelines. You must output valid JSON only. Do not include reasoning, analysis, commentary, markdown, tags, or explanatory text. Do not include any keys outside the provided schema. JSON must be directly parseable."""

        user_prompt = f"""Write a complete DIY tutorial script for this video idea.

video_idea: {video_idea}
video_hook: {video_hook}
diy_category: {diy_category}

Return valid JSON only matching this schema exactly:

{{
"title": "string",
"hook": "string",
"welcome": "string",
"project_intro": {{
  "what": "string",
  "benefit": "string",
  "who_is_this_for": "string"
}},
"materials": [
  {{
    "item": "string",
    "why": "string",
    "sourcing": "string",
    "budget_tip": "string",
    "common_substitute": "string"
  }}
],
"steps": [
  {{
    "step": "integer",
    "action": "string",
    "detail": "string",
    "safety": "string",
    "common_mistake": "string",
    "quality_check": "string"
  }}
],
"showcase": {{
  "visual": "string",
  "test": "string",
  "finish_tip": "string"
}},
"outro": "string",
"estimated_runtime_seconds": "integer"
}}

Constraints:
Include at least eight steps. Include safety and common_mistake fields for every step. Keep everything beginner friendly. Do not mention brand names, prices, or links. Return JSON only."""

        payload = {
            "model": "gpt-5.2",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 2500,
            "stream": False
        }

        try:
            response = requests.post(
                f"{self.base_url}/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=120
            )

            if response.status_code == 200:
                data = response.json()
                tutorial_text = data["choices"][0]["message"]["content"]
                self.tutorial_json = json.loads(tutorial_text)
                print(f"✓ Generated tutorial: {self.tutorial_json['title']}")
                print(f"✓ Steps: {len(self.tutorial_json['steps'])}")
                return self.tutorial_json
            else:
                raise Exception(f"API error: {response.status_code}")

        except Exception as e:
            print(f"✗ Failed to generate tutorial: {e}")
            return {}

    def step_2_initial_scenes(self) -> List[Dict[str, Any]]:
        """Step 2: Convert tutorial to initial scene draft"""
        print("\n" + "="*60)
        print("[STEP 2] GENERATING INITIAL SCENE DRAFT")
        print("="*60)

        headers = {
            "Content-Type": "application/json",
            "X-Content-Type": "diy-scene",
            "Authorization": "Bearer mock-key"
        }

        payload = {
            "model": "gpt-5.2",
            "messages": [
                {"role": "user", "content": json.dumps(self.tutorial_json)}
            ],
            "temperature": 0.7,
            "max_tokens": 4000,
            "stream": False
        }

        try:
            response = requests.post(
                f"{self.base_url}/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=120
            )

            if response.status_code == 200:
                data = response.json()
                scenes_text = data["choices"][0]["message"]["content"]
                scenes = json.loads(scenes_text)

                self.scene_versions.append(SceneVersion(
                    version=0,
                    scenes=scenes,
                    quality_scores={},
                    timestamp=time.strftime("%Y-%m-%d %H:%M:%S")
                ))

                print(f"✓ Generated {len(scenes)} initial scenes")
                return scenes
            else:
                raise Exception(f"API error: {response.status_code}")

        except Exception as e:
            print(f"✗ Failed to generate scenes: {e}")
            return []

    def step_3_debate_round(self, round_num: int, focus: str, agent_roles: List[DebateRole]) -> DebateRound:
        """Step 3: Run a debate round with specific critics"""
        print("\n" + "="*60)
        print(f"[DEBATE ROUND {round_num}] FOCUS: {focus.upper()}")
        print("="*60)

        current_scenes = self.scene_versions[-1].scenes
        critiques = []

        for role in agent_roles:
            agent = self.agents[role]
            print(f"\n  → {agent}...")

            critique = agent.critique(current_scenes, focus)
            critiques.append(critique)

            if "overall_quality_score" in critique:
                print(f"    Quality Score: {critique['overall_quality_score']}/100")
            if "issues_found" in critique:
                print(f"    Issues Found: {len(critique['issues_found'])}")

        # Synthesize feedback
        print(f"\n  → [SYNTHESIZER] Combining feedback...")
        synthesizer = self.agents[DebateRole.SYNTHESIZER]

        synthesis_prompt = f"""Combine these critiques into a unified improvement plan:

{json.dumps(critiques, indent=2)}

Return synthesis JSON."""

        synthesis = synthesizer.agents.agent.critique_prompt  # Using synthesizer

        debate_round = DebateRound(
            round_number=round_num,
            focus=focus,
            critiques=critiques,
            synthesis="Combined feedback ready",
            improvements=[]
        )

        self.debate_rounds.append(debate_round)

        print(f"\n✓ Round {round_num} complete")
        return debate_round

    def step_4_apply_improvements(self) -> List[Dict[str, Any]]:
        """Step 4: Apply synthesized improvements"""
        print("\n" + "="*60)
        print("[STEP 4] APPLYING IMPROVEMENTS")
        print("="*60)

        # Collect all improvement suggestions
        all_improvements = []
        for debate in self.debate_rounds:
            for critique in debate.critiques:
                if "issues_found" in critique:
                    all_improvements.extend(critique["issues_found"])

        print(f"  Total improvements to apply: {len(all_improvements)}")

        # Generate improved scenes with all feedback
        current_scenes = self.scene_versions[-1].scenes

        improvement_prompt = f"""Apply these improvements to the scenes:

CURRENT SCENES:
{json.dumps(current_scenes, indent=2)}

IMPROVEMENTS NEEDED:
{json.dumps(all_improvements, indent=2)}

Return the complete improved scene array in the exact same JSON format."""

        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer mock-key"
        }

        payload = {
            "model": "gpt-5.2",
            "messages": [
                {"role": "user", "content": improvement_prompt}
            ],
            "temperature": 0.6,
            "max_tokens": 5000,
            "stream": False
        }

        try:
            response = requests.post(
                f"{self.base_url}/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=120
            )

            if response.status_code == 200:
                data = response.json()
                improved_text = data["choices"][0]["message"]["content"]
                improved_scenes = json.loads(improved_text)

                self.scene_versions.append(SceneVersion(
                    version=len(self.scene_versions),
                    scenes=improved_scenes,
                    quality_scores={},
                    timestamp=time.strftime("%Y-%m-%d %H:%M:%S")
                ))

                print(f"✓ Generated version {len(self.scene_versions) - 1} with improvements")
                return improved_scenes

        except Exception as e:
            print(f"✗ Failed to apply improvements: {e}")
            return current_scenes

    def run_full_debate(self, video_idea: str, video_hook: str, diy_category: str) -> List[Dict[str, Any]]:
        """Run complete debate protocol"""
        print("\n" + "="*70)
        print("DIY SCENE DEBATE PROTOCOL - MULTI-AGENT REFINEMENT")
        print("="*70)

        # Step 1: Generate tutorial
        self.step_1_generate_tutorial(video_idea, video_hook, diy_category)

        # Step 2: Initial scene draft
        self.step_2_initial_scenes()

        # Step 3: Debate rounds
        self.step_3_debate_round(
            round_num=1,
            focus="dialogue_quality",
            agent_roles=[
                DebateRole.TTS_CRITIC,
                DebateRole.DIALOGUE_FLOW_CRITIC,
                DebateRole.SENTENCE_CRITIC
            ]
        )

        self.step_3_debate_round(
            round_num=2,
            focus="visual_quality",
            agent_roles=[
                DebateRole.FLUX_CRITIC,
                DebateRole.HAND_ANATOMY_CRITIC,
                DebateRole.LIGHTING_CRITIC
            ]
        )

        self.step_3_debate_round(
            round_num=3,
            focus="coherence",
            agent_roles=[
                DebateRole.ALIGNMENT_CRITIC,
                DebateRole.FLOW_CRITIC,
                DebateRole.TIMING_CRITIC
            ]
        )

        # Step 4: Apply all improvements
        final_scenes = self.step_4_apply_improvements()

        print("\n" + "="*70)
        print("✓ DEBATE COMPLETE")
        print(f"  Initial scenes: {len(self.scene_versions[0].scenes)}")
        print(f"  Final scenes: {len(final_scenes)}")
        print(f"  Total versions: {len(self.scene_versions)}")
        print(f"  Debate rounds: {len(self.debate_rounds)}")
        print("="*70)

        return final_scenes

    def save_output(self, filename: str = "final_scenes.json"):
        """Save final scene array"""
        final_scenes = self.scene_versions[-1].scenes
        with open(filename, 'w') as f:
            json.dump(final_scenes, f, indent=2)
        print(f"\n✓ Saved final scenes to {filename}")

    def save_full_report(self, filename: str = "debate_report.json"):
        """Save complete debate report"""
        report = {
            "video_idea": self.video_idea,
            "tutorial": self.tutorial_json,
            "versions": [
                {
                    "version": v.version,
                    "scene_count": len(v.scenes),
                    "timestamp": v.timestamp
                }
                for v in self.scene_versions
            ],
            "debate_rounds": [
                {
                    "round": d.round_number,
                    "focus": d.focus,
                    "critique_count": len(d.critiques)
                }
                for d in self.debate_rounds
            ],
            "final_scenes": self.scene_versions[-1].scenes
        }

        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"✓ Saved full debate report to {filename}")


def main():
    """Example usage"""

    # Initialize protocol
    protocol = DIYSceneDebateProtocol(base_url="http://localhost:5000")

    # Run full debate
    final_scenes = protocol.run_full_debate(
        video_idea="Build a simple wooden shelf for beginners",
        video_hook="Learn to build a custom shelf in under an hour!",
        diy_category="Woodworking"
    )

    # Save outputs
    protocol.save_output("final_scenes.json")
    protocol.save_full_report("debate_report.json")

    # Print final result
    print("\n" + "="*70)
    print("FINAL SCENE ARRAY:")
    print("="*70)
    print(json.dumps(final_scenes, indent=2))


if __name__ == "__main__":
    main()
