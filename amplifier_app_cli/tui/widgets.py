"""Custom widgets for Amplifier TUI."""

from datetime import datetime
from textual.app import ComposeResult
from textual.containers import VerticalScroll
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Static, Markdown, TextArea

# Import Rich's Markdown for better rendering in conversation panel
from amplifier_app_cli.console import Markdown as RichMarkdown

# Text colors
CONVERSATION_COLOR = "#C7C7C7"  # RGB 199,199,199
REASONING_COLOR = "#A6A6A6"  # RGB 166,166,166


def _timestamp() -> str:
    """Return current timestamp in HH:MM:SS format."""
    return datetime.now().strftime("%H:%M:%S")


def _clean_text(text: str, max_len: int = 500) -> str:
    """Clean text for single-line display: normalize whitespace, truncate."""
    # Replace newlines and multiple spaces with single space
    cleaned = " ".join(text.split())
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len] + "..."
    return cleaned


def _normalize_newlines(text: str) -> str:
    """Normalize different newline formats to single \\n."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


class ReasoningPanel(VerticalScroll):
    """Panel showing AI reasoning, thinking, and tool calls (30% height)."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.border_title = "Reasoning & Tool Calls"
        self._streaming_thinking: Markdown | None = None
        self._streaming_thinking_text: str = ""
        self._thinking_ts: str = ""

    def start_thinking_stream(self) -> None:
        """Start a new streaming thinking block."""
        self._thinking_ts = _timestamp()
        self._streaming_thinking_text = ""
        # Use Markdown widget to preserve newlines
        self._streaming_thinking = Markdown(f"**[{self._thinking_ts}]** 🧠")
        self.mount(self._streaming_thinking)
        self.scroll_end(animate=False)

    def append_thinking_delta(self, delta: str) -> None:
        """Append a delta to the current streaming thinking block."""
        if self._streaming_thinking is None:
            self.start_thinking_stream()
        self._streaming_thinking_text += delta
        # Format with Markdown to preserve newlines, indent continuation lines
        normalized = _normalize_newlines(self._streaming_thinking_text)
        lines = normalized.split("\n")
        # Keep first 15 lines to avoid huge blocks
        if len(lines) > 15:
            lines = lines[:15] + ["... (truncated)"]
        
        md_text = f"**[{self._thinking_ts}]** 🧠\n"
        for line in lines:
            md_text += f"    {line}\n"
        
        if self._streaming_thinking is not None:
            self._streaming_thinking.update(md_text)
        self.scroll_end(animate=False)

    def finish_thinking_stream(self) -> None:
        """Finish the current streaming thinking block."""
        self._streaming_thinking = None
        self._streaming_thinking_text = ""

    def append_thinking(self, content: str) -> None:
        ts = _timestamp()
        # Format with Markdown to preserve newlines, indent continuation lines
        normalized = _normalize_newlines(content)
        lines = normalized.split("\n")
        # Keep first 15 lines to avoid huge blocks
        if len(lines) > 15:
            lines = lines[:15] + ["... (truncated)"]
        
        md_text = f"**[{ts}]** 🧠\n"
        for line in lines:
            md_text += f"    {line}\n"
        
        self.mount(Markdown(md_text))
        self.scroll_end(animate=False)

    def append_tool_call(self, tool_name: str, arguments: dict) -> None:
        ts = _timestamp()
        args_preview = ", ".join(
            f"{k}={_clean_text(str(v), 30)}" for k, v in list(arguments.items())[:3]
        )
        self.mount(
            Static(f"[dim]{ts}[/] [{REASONING_COLOR}]▶ {tool_name}({args_preview})[/]")
        )
        self.scroll_end(animate=False)

    def append_tool_result(self, tool_name: str, result: str) -> None:
        ts = _timestamp()
        display = _clean_text(result, 200)
        self.mount(Static(f"[dim]{ts}[/] [{REASONING_COLOR}]  └─ {display}[/]"))
        self.scroll_end(animate=False)

    def append_status(self, message: str) -> None:
        ts = _timestamp()
        self.mount(Static(f"[dim]{ts}[/] [{REASONING_COLOR}]● {message}[/]"))
        self.scroll_end(animate=False)

    def append_error(self, message: str) -> None:
        ts = _timestamp()
        self.mount(Static(f"[dim]{ts}[/] [red]✗ Error: {message}[/]"))
        self.scroll_end(animate=False)

    def append_separator(self) -> None:
        """Add a separator line to mark the end of a reasoning block."""
        self.mount(Static(f"[dim]{'─' * 60}[/]"))
        self.scroll_end(animate=False)

    def clear(self) -> None:
        for child in list(self.children):
            child.remove()


class ConversationPanel(VerticalScroll):
    """Panel showing the conversation - user messages and AI replies (70% height)."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.border_title = "Conversation"
        self._streaming_widget: Static | None = None
        self._streaming_text: str = ""
        self._streaming_ts: str = ""

    def append_user_message(self, message: str) -> None:
        """Add a user message to the conversation."""
        ts = _timestamp()
        self.mount(Static(f"[dim]{ts}[/] [bold cyan]You:[/] [{CONVERSATION_COLOR}]{message}[/]"))
        self.scroll_end(animate=False)

    def append_assistant_message(self, content: str) -> None:
        """Add a complete assistant message with markdown support using Rich."""
        ts = _timestamp()
        self._streaming_widget = None
        self._streaming_text = ""
        # Label with timestamp
        self.mount(Static(f"[dim]{ts}[/] [bold yellow]Assistant:[/]"))
        # Use Rich Markdown wrapped in Static widget for proper rendering
        rich_md = RichMarkdown(content)
        self.mount(Static(rich_md))
        # Add separator
        self.mount(Static(f"[dim]{'─' * 60}[/]"))
        self.scroll_end(animate=False)

    def start_assistant_response(self) -> None:
        """Start a new streaming assistant response."""
        self._streaming_ts = _timestamp()
        self._streaming_text = ""
        self._streaming_widget = Static(
            f"[dim]{self._streaming_ts}[/] [bold yellow]Assistant:[/] "
        )
        self.mount(self._streaming_widget)
        self.scroll_end(animate=False)

    def append_streaming(self, text: str) -> None:
        """Append text to the current streaming response."""
        self._streaming_text += text
        if self._streaming_widget is None:
            self.start_assistant_response()
        if self._streaming_widget is not None:
            self._streaming_widget.update(
                f"[dim]{self._streaming_ts}[/] [bold yellow]Assistant:[/] [{CONVERSATION_COLOR}]{self._streaming_text}[/]"
            )
        self.scroll_end(animate=False)

    def finish_streaming(self) -> None:
        """Finish the current streaming response and add separator."""
        if self._streaming_text:
            # Add separator after streaming completes (no empty Static to avoid double newlines)
            self.mount(Static(f"[dim]{chr(0x2500) * 60}[/]"))
            self.scroll_end(animate=False)
        self._streaming_widget = None
        self._streaming_text = ""

    def clear(self) -> None:
        self._streaming_widget = None
        self._streaming_text = ""
        for child in list(self.children):
            child.remove()


class InputPanel(Widget):
    """Input panel for user messages - supports multi-line paste (Ctrl-J to send)."""

    class Submitted(Message):
        def __init__(self, value: str) -> None:
            self.value = value
            super().__init__()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.border_title = "Input (Ctrl+Enter to send, Cmd+Enter on Mac)"

    def compose(self) -> ComposeResult:
        yield TextArea(id="user-input", show_line_numbers=False)

    def on_mount(self) -> None:
        """Configure TextArea after mounting."""
        text_area = self.query_one("#user-input", TextArea)
        text_area.text = ""

    def _submit_input(self) -> None:
        """Submit the current input."""
        text_area = self.query_one("#user-input", TextArea)
        value = text_area.text.strip()
        
        # Skip if this is the placeholder text
        if value == "Type your message... (paste multi-line, Ctrl-J to send)":
            return
        
        if value:
            self.post_message(self.Submitted(value))

    def action_submit_input(self) -> None:
        """Action bound to Ctrl-J for submitting input."""
        self._submit_input()

    def action_exit(self) -> None:
        """Action bound to Ctrl-D for exiting."""
        self.app.exit()

    def clear(self) -> None:
        try:
            text_area = self.query_one("#user-input", TextArea)
            text_area.text = ""
        except Exception:
            pass

    def focus_input(self) -> None:
        """Focus the input field."""
        try:
            self.query_one("#user-input", TextArea).focus()
        except Exception:
            pass


# Keep old name for backwards compatibility
ResponsePanel = ConversationPanel
