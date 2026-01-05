#!/usr/bin/env python3
"""
Flask Web App for DIY Scene Debate Protocol
Run multi-agent debate to refine tutorial scenes
"""

from flask import Flask, request, jsonify
import json
from diy_scene_debate_protocol import DIYSceneDebateProtocol

app = Flask(__name__)

# Store active sessions
sessions = {}


@app.route('/health', methods=['GET'])
def health():
    """Health check"""
    return jsonify({"status": "ok", "service": "diy-scene-debate"})


@app.route('/api/debate/start', methods=['POST'])
def start_debate():
    """
    Start a new debate session

    POST /api/debate/start
    {
      "video_idea": "Build a wooden shelf",
      "video_hook": "Learn in under an hour!",
      "diy_category": "Woodworking",
      "chatmock_url": "http://localhost:5000"
    }

    Returns:
    {
      "session_id": "abc123",
      "status": "started"
    }
    """
    data = request.json

    video_idea = data.get('video_idea')
    video_hook = data.get('video_hook')
    diy_category = data.get('diy_category')
    chatmock_url = data.get('chatmock_url', 'http://localhost:5000')

    if not video_idea or not video_hook or not diy_category:
        return jsonify({
            "error": "Missing required fields: video_idea, video_hook, diy_category"
        }), 400

    # Create session
    import uuid
    session_id = str(uuid.uuid4())

    protocol = DIYSceneDebateProtocol(base_url=chatmock_url)
    sessions[session_id] = {
        "protocol": protocol,
        "status": "initialized",
        "video_idea": video_idea,
        "video_hook": video_hook,
        "diy_category": diy_category
    }

    return jsonify({
        "session_id": session_id,
        "status": "initialized",
        "message": "Debate session created. Use /api/debate/run to execute."
    })


@app.route('/api/debate/run', methods=['POST'])
def run_debate():
    """
    Run the full debate protocol

    POST /api/debate/run
    {
      "session_id": "abc123"
    }

    Returns:
    {
      "session_id": "abc123",
      "status": "complete",
      "final_scenes": [...],
      "stats": {...}
    }
    """
    data = request.json
    session_id = data.get('session_id')

    if not session_id or session_id not in sessions:
        return jsonify({"error": "Invalid session_id"}), 404

    session = sessions[session_id]
    protocol = session["protocol"]

    # Run debate
    session["status"] = "running"

    try:
        final_scenes = protocol.run_full_debate(
            video_idea=session["video_idea"],
            video_hook=session["video_hook"],
            diy_category=session["diy_category"]
        )

        session["status"] = "complete"
        session["final_scenes"] = final_scenes

        return jsonify({
            "session_id": session_id,
            "status": "complete",
            "final_scenes": final_scenes,
            "stats": {
                "total_scenes": len(final_scenes),
                "total_versions": len(protocol.scene_versions),
                "debate_rounds": len(protocol.debate_rounds)
            }
        })

    except Exception as e:
        session["status"] = "error"
        return jsonify({
            "session_id": session_id,
            "status": "error",
            "error": str(e)
        }), 500


@app.route('/api/debate/quick', methods=['POST'])
def quick_debate():
    """
    One-shot debate: start + run in single request

    POST /api/debate/quick
    {
      "video_idea": "Build a wooden shelf",
      "video_hook": "Learn in under an hour!",
      "diy_category": "Woodworking",
      "chatmock_url": "http://localhost:5000"
    }

    Returns:
    {
      "final_scenes": [...],
      "stats": {...}
    }
    """
    data = request.json

    video_idea = data.get('video_idea')
    video_hook = data.get('video_hook')
    diy_category = data.get('diy_category')
    chatmock_url = data.get('chatmock_url', 'http://localhost:5000')

    if not video_idea or not video_hook or not diy_category:
        return jsonify({
            "error": "Missing required fields: video_idea, video_hook, diy_category"
        }), 400

    # Run debate immediately
    protocol = DIYSceneDebateProtocol(base_url=chatmock_url)

    try:
        final_scenes = protocol.run_full_debate(
            video_idea=video_idea,
            video_hook=video_hook,
            diy_category=diy_category
        )

        return jsonify({
            "final_scenes": final_scenes,
            "tutorial": protocol.tutorial_json,
            "stats": {
                "total_scenes": len(final_scenes),
                "total_versions": len(protocol.scene_versions),
                "debate_rounds": len(protocol.debate_rounds)
            }
        })

    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@app.route('/api/debate/status/<session_id>', methods=['GET'])
def get_status(session_id):
    """
    Get debate session status

    GET /api/debate/status/<session_id>

    Returns:
    {
      "session_id": "abc123",
      "status": "running/complete/error",
      "progress": {...}
    }
    """
    if session_id not in sessions:
        return jsonify({"error": "Session not found"}), 404

    session = sessions[session_id]
    protocol = session["protocol"]

    return jsonify({
        "session_id": session_id,
        "status": session["status"],
        "progress": {
            "versions_created": len(protocol.scene_versions),
            "debate_rounds_complete": len(protocol.debate_rounds),
            "current_scene_count": len(protocol.scene_versions[-1].scenes) if protocol.scene_versions else 0
        }
    })


if __name__ == '__main__':
    print("\n" + "="*60)
    print("DIY SCENE DEBATE SERVICE")
    print("="*60)
    print("\nEndpoints:")
    print("  POST /api/debate/quick     - One-shot debate (recommended)")
    print("  POST /api/debate/start     - Start session")
    print("  POST /api/debate/run       - Run debate")
    print("  GET  /api/debate/status    - Check status")
    print("  GET  /health               - Health check")
    print("\nStarting server on http://localhost:5001...")
    print("="*60 + "\n")

    app.run(host='0.0.0.0', port=5001, debug=True)
