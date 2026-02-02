"""Main Textual application for Amplifier TUI."""

import sys
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.theme import Theme
from textual.widgets import Footer, Static

from .widgets import ReasoningPanel, ConversationPanel, InputPanel

# Custom Amplifier theme
AMPLIFIER_THEME = Theme(
    name="amplifier",
    primary="#00c300",  # header bg (RGB 0,195,0)
    secondary="#008080",  # dark cyan
    accent="#199cf4",  # reasoning border (RGB 25,156,244)
    success="#00c300",  # conversation border
    warning="#ffffff",  # input border (white)
    error="#ff0000",  # red
    background="#000000",  # black
    surface="#1a1a1a",  # dark gray
    dark=True,
)


class AmplifierTUI(App):
    """Full-screen TUI for Amplifier with 3-panel layout."""

    TITLE = "Amplifier"
    SUB_TITLE = "AI Assistant"

    CSS = """
    Screen {
        background: $background;
        layout: vertical;
    }

    #header {
        dock: top;
        height: 1;
        background: $primary;
        color: $background;
        padding: 0 1;
    }

    Vertical {
        height: 100%;
    }

    ReasoningPanel {
        height: 3fr;
        border: solid $accent;
        border-title-color: $accent;
        border-title-style: bold;
        background: $surface;
        padding: 0 1;
    }

    ConversationPanel {
        height: 7fr;
        border: solid $success;
        border-title-color: $success;
        border-title-style: bold;
        background: $surface;
        padding: 0 1;
    }

    InputPanel {
        height: auto;
        min-height: 5;
        max-height: 10;
        border: solid $warning;
        border-title-color: $warning;
        border-title-style: bold;
        background: $surface;
        padding: 0 1;
    }

    InputPanel:focus-within {
        border: double $warning;
    }

    InputPanel TextArea {
        border: none;
        background: transparent;
        width: 100%;
    }

    Footer {
        dock: bottom;
    }
    """

    BINDINGS = [
        Binding("ctrl+enter", "submit_input", "Send", show=True),
        Binding("cmd+enter", "submit_input", "Send", show=False),  # Mac equivalent
        Binding("ctrl+l", "clear", "Clear", show=True),
        Binding("pageup", "scroll_reasoning_up", "PageUp", show=True),
        Binding("pagedown", "scroll_reasoning_down", "PageDown", show=True),
        Binding("ctrl+c", "quit", "Quit", show=True),
        Binding("ctrl+d", "quit", "Exit", show=False),  # Alternative exit
    ]

    def __init__(
        self,
        session=None,
        config_data: dict | None = None,
        prepared_bundle=None,
        bundle_name: str = "default",
        model_name: str = "unknown",
        session_id: str = "",
        initial_transcript: list[dict] | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.session = session
        self.config_data = config_data or {}
        self.prepared_bundle = prepared_bundle
        self.bundle_name = bundle_name
        self.model_name = model_name
        self.session_id = session_id
        self.initial_transcript = initial_transcript or []
        self._is_processing = False

        # Register custom theme
        self.register_theme(AMPLIFIER_THEME)

    def compose(self) -> ComposeResult:
        session_short = self.session_id[:8] if self.session_id else "new"
        header_text = (
            f"[bold]Amplifier[/] │ Session: {session_short} │ "
            f"Bundle: {self.bundle_name} │ Model: {self.model_name}"
        )
        yield Vertical(
            Static(header_text, id="header"),
            ReasoningPanel(id="reasoning"),
            ConversationPanel(id="conversation"),
            InputPanel(id="input"),
            Footer(),
        )

    def on_mount(self) -> None:
        # Set amplifier theme as default
        self.theme = "amplifier"
        self.query_one("#input", InputPanel).focus_input()
        # Initialize session in background if we have a prepared bundle
        if self.prepared_bundle and not self.session:
            self.run_worker(self._init_session(), exclusive=True)

    def action_submit_input(self) -> None:
        """Action handler for submitting input (Ctrl-J)."""
        input_panel = self.query_one("#input", InputPanel)
        input_panel.action_submit_input()

    def _restore_transcript_to_panels(self, transcript: list[dict]) -> None:
        """Restore conversation history and reasoning from transcript.

        Separates messages into conversation (text) and reasoning (thinking blocks,
        tool calls) panels to match live chat display.

        Args:
            transcript: List of message dicts with 'role', 'content' fields
        """
        from ..ui.message_renderer import _extract_content_blocks

        conversation = self.query_one("#conversation", ConversationPanel)
        reasoning = self.query_one("#reasoning", ReasoningPanel)

        for message in transcript:
            role = message.get("role")

            if role == "user":
                content = message.get("content", "")
                if isinstance(content, str):
                    conversation.append_user_message(content)

            elif role == "assistant":
                # Extract text and thinking blocks separately
                text_blocks, thinking_blocks = _extract_content_blocks(
                    message, show_thinking=True
                )

                # Display thinking blocks in reasoning panel
                for thinking in thinking_blocks:
                    reasoning.append_thinking(thinking)

                # Display text in conversation panel
                if text_blocks:
                    content = "\n".join(text_blocks)
                    conversation.append_assistant_message(content)

    def _update_model_from_session(self) -> None:
        """Update header with actual model from the session's provider."""
        if not self.session:
            return
        try:
            providers = self.session.coordinator.get("providers")
            if providers and len(providers) > 0:
                provider = providers[0]
                # Try to get model from provider's attributes
                model = (
                    getattr(provider, "default_model", None)
                    or getattr(provider, "model", None)
                    or getattr(provider, "model_name", None)
                )
                if model and model != "unknown":
                    self.model_name = model
                    # Update header
                    header = self.query_one("#header", Static)
                    header.update(
                        f" Amplifier TUI │ Bundle: {self.bundle_name} │ Model: {self.model_name}"
                    )
        except Exception:
            pass  # Keep existing model name on error

    async def _init_session(self) -> None:
        """Initialize the AI session."""
        reasoning = self.query_one("#reasoning", ReasoningPanel)
        reasoning.append_status("Initializing session...")

        try:
            # Create session from prepared bundle
            try:
                self.session = await self.prepared_bundle.create_session(
                    session_id=self.session_id
                )
            except TypeError:
                self.session = await self.prepared_bundle.create_session()

            await self.session.initialize()

            # Register TUI hooks to capture events
            self._register_tui_hooks()

            # Update header with actual model from provider
            self._update_model_from_session()

            # Restore initial transcript if resuming a session
            if self.initial_transcript:
                reasoning.append_status("Restoring conversation history...")
                self._restore_transcript_to_panels(self.initial_transcript)

            reasoning.append_status("Session ready!")
        except Exception as e:
            reasoning.append_error(f"Failed to initialize: {e}")

    def on_input_panel_submitted(self, event: InputPanel.Submitted) -> None:
        """Handle user input submission."""
        prompt = event.value.strip()
        if not prompt or self._is_processing:
            return

        # Clear input
        input_panel = self.query_one("#input", InputPanel)
        input_panel.clear()

        # Show user message in CONVERSATION panel
        conversation = self.query_one("#conversation", ConversationPanel)
        conversation.append_user_message(prompt)

        # Process in background
        self.run_worker(self._process_prompt(prompt), exclusive=True)

    async def _process_prompt(self, prompt: str) -> None:
        """Process a prompt and stream the response."""
        self._is_processing = True
        reasoning = self.query_one("#reasoning", ReasoningPanel)
        conversation = self.query_one("#conversation", ConversationPanel)

        if not self.session:
            reasoning.append_error(
                "No session available. Please wait for initialization."
            )
            self._is_processing = False
            return

        try:
            reasoning.append_status("Processing...")

            # Use session.execute() to properly trigger all hooks
            result = await self.session.execute(prompt)

            # Show the result in conversation
            if result:
                conversation.append_assistant_message(str(result))

            reasoning.append_status("Done")
            reasoning.append_separator()

        except Exception as e:
            reasoning.append_error(str(e))
            conversation.finish_streaming()
        finally:
            self._is_processing = False

    def action_clear(self) -> None:
        self.query_one("#reasoning", ReasoningPanel).clear()
        self.query_one("#conversation", ConversationPanel).clear()

    def action_scroll_reasoning_up(self) -> None:
        """Scroll reasoning panel up (PageUp)."""
        reasoning = self.query_one("#reasoning", ReasoningPanel)
        reasoning.scroll_up(5)

    def action_scroll_reasoning_down(self) -> None:
        """Scroll reasoning panel down (PageDown)."""
        reasoning = self.query_one("#reasoning", ReasoningPanel)
        reasoning.scroll_down(5)

    def _register_tui_hooks(self) -> None:
        """Register hooks to capture tool calls and reasoning for the TUI."""
        if not self.session:
            print("DEBUG: No session for hooks", file=sys.stderr)
            return

        hooks = self.session.coordinator.get("hooks")
        if not hooks:
            print("DEBUG: No hooks registry", file=sys.stderr)
            return

        print(f"DEBUG: Registering TUI hooks on {hooks}", file=sys.stderr)

        from amplifier_core.models import HookResult

        # Store reference to app for use in closures
        app = self
        app._thinking_blocks = {}
        app._last_usage_key = None  # Track last usage to avoid duplicates

        async def on_content_block_start(event: str, data: dict) -> HookResult:
            """Called when a content block starts (e.g., thinking)."""
            print(
                f"DEBUG: content_block:start -> {data.get('block_type')}",
                file=sys.stderr,
            )
            block_type = data.get("block_type")
            block_index = data.get("block_index")
            if block_type in {"thinking", "reasoning"} and block_index is not None:
                app._thinking_blocks[block_index] = True
                reasoning = app.query_one("#reasoning", ReasoningPanel)
                reasoning.append_status("💭 Thinking...")
            return HookResult()

        async def on_content_block_end(event: str, data: dict) -> HookResult:
            """Called when a content block ends (contains full content)."""
            print(f"DEBUG: content_block:end -> {data}", file=sys.stderr)
            block = data.get("block", {})
            block_type = (
                block.get("type")
                if isinstance(block, dict)
                else getattr(block, "type", None)
            )
            usage = data.get("usage")

            reasoning = app.query_one("#reasoning", ReasoningPanel)

            # Display thinking block content
            if block_type in {"thinking", "reasoning", "thinking_block"} or (
                hasattr(block_type, "value")
                and block_type.value in {"thinking", "reasoning"}
            ):
                thinking_text = ""
                if isinstance(block, dict):
                    thinking_text = (
                        block.get("thinking", "")
                        or block.get("text", "")
                        or block.get("summary", "")
                    )
                else:
                    thinking_text = (
                        getattr(block, "thinking", "")
                        or getattr(block, "text", "")
                        or getattr(block, "summary", "")
                    )
                if thinking_text:
                    reasoning.append_thinking(thinking_text)

            # Display token usage
            if usage:
                input_tokens = (
                    getattr(usage, "input_tokens", 0)
                    if hasattr(usage, "input_tokens")
                    else usage.get("input_tokens", 0)
                )
                output_tokens = (
                    getattr(usage, "output_tokens", 0)
                    if hasattr(usage, "output_tokens")
                    else usage.get("output_tokens", 0)
                )
                cache_read = (
                    getattr(usage, "cache_read_input_tokens", 0)
                    if hasattr(usage, "cache_read_input_tokens")
                    else usage.get("cache_read_input_tokens", 0)
                )
                cache_create = (
                    getattr(usage, "cache_creation_input_tokens", 0)
                    if hasattr(usage, "cache_creation_input_tokens")
                    else usage.get("cache_creation_input_tokens", 0)
                )
                # Create a key to detect duplicate usage reports
                usage_key = (input_tokens, output_tokens, cache_read, cache_create)
                if usage_key != app._last_usage_key:
                    app._last_usage_key = usage_key
                    total_input = input_tokens + cache_read + cache_create
                    total = total_input + output_tokens
                    usage_text = f"📊 Tokens: {total_input:,} in / {output_tokens:,} out = {total:,}"
                    if cache_read > 0:
                        cache_pct = (
                            int((cache_read / total_input) * 100)
                            if total_input > 0
                            else 0
                        )
                        usage_text += f" ({cache_pct}% cached)"
                    reasoning.append_status(usage_text)

            return HookResult()

        async def on_tool_pre(event: str, data: dict) -> HookResult:
            """Called before a tool is executed."""
            print(f"DEBUG: tool:pre -> {data.get('tool_name')}", file=sys.stderr)
            tool_name = data.get("tool_name", "unknown")
            tool_input = data.get("tool_input", data.get("arguments", {}))
            reasoning = app.query_one("#reasoning", ReasoningPanel)
            reasoning.append_tool_call(tool_name, tool_input)
            return HookResult()

        async def on_tool_post(event: str, data: dict) -> HookResult:
            """Called after a tool is executed."""
            print(f"DEBUG: tool:post -> {data.get('tool_name')}", file=sys.stderr)
            tool_name = data.get("tool_name", "unknown")
            result = data.get("tool_response", data.get("result", ""))
            if isinstance(result, dict):
                result = result.get("output", result)
            result_str = str(result)[:500]
            reasoning = app.query_one("#reasoning", ReasoningPanel)
            reasoning.append_tool_result(tool_name, result_str)
            return HookResult()

        async def on_content_block_delta(event: str, data: dict) -> HookResult:
            """Called when a text delta arrives (streaming)."""
            delta = data.get("delta", {})
            delta_type = (
                delta.get("type")
                if isinstance(delta, dict)
                else getattr(delta, "type", None)
            )

            # Handle text delta - stream to conversation panel
            if delta_type == "text_delta" or delta_type == "text":
                text = (
                    delta.get("text", "")
                    if isinstance(delta, dict)
                    else getattr(delta, "text", "")
                )
                if text:
                    conversation = app.query_one("#conversation", ConversationPanel)
                    conversation.append_streaming(text)

            return HookResult()

        async def on_thinking_delta(event: str, data: dict) -> HookResult:
            """Called when a thinking delta arrives (streaming)."""
            delta = data.get("delta", "")
            if isinstance(delta, dict):
                delta = delta.get("thinking", "") or delta.get("text", "")
            if delta:
                reasoning = app.query_one("#reasoning", ReasoningPanel)
                reasoning.append_thinking_delta(delta)
            return HookResult()

        # Register the hooks for streaming UI events
        hooks.register(
            "content_block:start", on_content_block_start, name="tui-block-start"
        )
        hooks.register("content_block:end", on_content_block_end, name="tui-block-end")
        hooks.register(
            "content_block:delta", on_content_block_delta, name="tui-block-delta"
        )
        hooks.register("thinking:delta", on_thinking_delta, name="tui-thinking-delta")
        hooks.register("tool:pre", on_tool_pre, name="tui-tool-pre")
        hooks.register("tool:post", on_tool_post, name="tui-tool-post")
        print("DEBUG: TUI hooks registered successfully", file=sys.stderr)
