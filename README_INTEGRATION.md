# AgentOS <-> Hermes integration: feedback + governor

Two pieces wire your brain and Hermes's body into one coherent, safe system.

## 1. Board write-back (hermes_feedback.py)
Keeps ground_state.json live when Hermes acts. Have Hermes call these after it
does anything that changes your situation.

CLI (use these in Hermes cron scripts / skill post-steps):
    python hermes_feedback.py shipped "what" --url https://...
    python hermes_feedback.py outcome "the move" --pulled --moved --notes "..."
    python hermes_feedback.py pending "what needs a hand" --trigger "the move"
    python hermes_feedback.py done 0
    python hermes_feedback.py note "scanned X, nothing actionable"

Everything is also journaled to state/hermes_activity.md - your morning read of
what the body did overnight.

## 2. The governor (governor.py)
Every AUTO action must pass the Questioner before it runs. GREENLIGHT executes;
DOWNGRADE/REFUSE/no-verdict are held for you (queued via the action gate).
Already wired into action_gate.py's AUTO path - structural, not optional.

Standalone check:
    python governor.py "the action you're considering"

FAIL-SAFE: with no model wired, the governor HOLDS (never auto-executes). To let
autonomous actions actually fire, wire the Questioner's model:
    export AGENTOS_PROVIDER=gemini        # or anthropic
    export AGENTOS_MODEL=<current model id>
    export GEMINI_API_KEY=...             # or ANTHROPIC_API_KEY
Principle: no judge, no autonomous action.

## 3. Add both to the MCP bridge (so Hermes can call them)
In agentos_mcp.py, register two more tools alongside your existing four:

    @server.tool()
    def agentos_report(blob: str) -> str:
        "Report an outcome/shipped/pending/done/note back to the AgentOS board."
        import hermes_feedback, json
        return json.dumps(hermes_feedback.report(blob))

    @server.tool()
    def agentos_governor_check(action: str) -> str:
        "Ask the AgentOS governor whether an autonomous action may proceed."
        import governor, json
        return json.dumps(governor.decide(action))

Then in Hermes, instruct it (system prompt / AGENTS.md): before any autonomous
action, call agentos_governor_check; after any action that changes the
situation, call agentos_report.
