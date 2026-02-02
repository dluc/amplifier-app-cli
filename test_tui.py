#!/usr/bin/env python3
"""Standalone test for the TUI."""
from amplifier_app_cli.tui.app import AmplifierTUI
from amplifier_app_cli.tui.widgets import ReasoningPanel, ResponsePanel, InputPanel

class DemoTUI(AmplifierTUI):
    async def on_input_panel_submitted(self, event: InputPanel.Submitted) -> None:
        prompt = event.value.strip()
        if not prompt:
            return
        input_panel = self.query_one("#input", InputPanel)
        input_panel.clear()
        reasoning = self.query_one("#reasoning", ReasoningPanel)
        response_panel = self.query_one("#response", ResponsePanel)
        reasoning.append_user_message(prompt)
        reasoning.append_thinking("Thinking...")
        reasoning.append_tool_call("grep", {"pattern": "*.py"})
        reasoning.append_tool_result("grep", "Found 15 files")
        response_panel.set_response(f"Response to: {prompt}")

if __name__ == "__main__":
    DemoTUI(bundle_name="demo", model_name="demo", session_id="test").run()
