#!/usr/bin/env -S uv run
# /// script
# dependencies = [
#     "textual>=0.70.0,<1.0.0",
#     "rich>=13.0.0,<14.0.0", # rich is a dependency of textual, but specifying it for clarity
# ]
# requires-python = ">=3.12"
# description = "A multi-dice rolling application for the terminal."
# authors = [{name = "Jules", email = "no-reply@example.com"}]
# ///

import asyncio
import secrets
import sys
import random
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional, Callable

try:
    from textual.app import App, ComposeResult
    from textual.containers import Container, Horizontal, Vertical, Grid
    from textual.widgets import Header, Footer, Button, Label, Static
    from textual.binding import Binding
    from textual.css.query import DOMQuery
    from textual import events
    from textual.reactive import reactive
    from textual.message import Message

    from rich.text import Text
    from rich.align import Align
    from rich.console import ConsoleOptions, Console, RenderResult
    from rich.measure import Measurement
    from rich.segment import Segments

except ImportError:
    print("Error: Missing required dependencies (textual, rich).", file=sys.stderr)
    print("Please ensure 'textual' and 'rich' are installed.", file=sys.stderr)
    print("You can typically install them using: pip install textual rich", file=sys.stderr)
    print("If using uv, ensure the script header is correct and run with: uv run multi_dice_roller.py", file=sys.stderr)
    sys.exit(1)

# --- Enums and Data Classes ---

class DiceState(Enum):
    """Represents the state of a die or the dice rolling process."""
    IDLE = auto()
    ROLLING = auto()
    COMPLETED = auto() # Animation finished, result shown

@dataclass
class GridDimensions:
    """Represents the dimensions of the dice grid."""
    columns: int
    rows: int

@dataclass
class StatisticsInfo:
    """Holds calculated statistics for a set of dice rolls."""
    total_sum: int
    frequencies: Dict[int, int] # Face value -> count
    roll_count: int = 0

@dataclass
class ValidationResult:
    """Holds the result of a validation check."""
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

# --- End Enums and Data Classes ---

# --- Utility Functions ---

def calculateOptimalGrid(dice_count: int) -> GridDimensions:
    """Calculate optimal grid layout for given number of dice."""
    if dice_count <= 0:
        return GridDimensions(columns=0, rows=0)
    if dice_count == 1:
        return GridDimensions(columns=1, rows=1)
    elif dice_count == 2:
        return GridDimensions(columns=2, rows=1)
    elif dice_count == 3:
        return GridDimensions(columns=3, rows=1)
    elif dice_count == 4:
        return GridDimensions(columns=2, rows=2)
    elif dice_count in (5, 6):
        return GridDimensions(columns=3, rows=2)
    elif dice_count in (7, 8):
        return GridDimensions(columns=4, rows=2)
    else: # Should not happen with max 8 dice, but as a fallback
        return GridDimensions(columns=4, rows=(dice_count + 3) // 4)

def calculate_frequencies(results: List[int]) -> Dict[int, int]:
    """Calculates the frequency of each die face in the results."""
    frequencies: Dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}
    for result in results:
        if 1 <= result <= 6:
            frequencies[result] += 1
    return frequencies

def format_frequencies(frequencies: Dict[int, int]) -> str:
    """Formats the frequency data into a display string.
    Example: "1x⚀ | 2x⚁ | 1x⚅"
    """
    # Standard dice emojis
    dice_emojis = ["", "⚀", "⚁", "⚂", "⚃", "⚄", "⚅"] # Index 0 is unused

    parts = []
    for face_value in sorted(frequencies.keys()):
        count = frequencies[face_value]
        if count > 0:
            parts.append(f"{count}x{dice_emojis[face_value]}")
    return " | ".join(parts) if parts else "No results yet"

def detect_terminal_capabilities() -> dict:
    """Basic terminal capability detection.
    For now, just gets size. Could be expanded.
    """
    # In a Textual app, self.app.size is preferred once the app is running.
    # This is a more general placeholder.
    try:
        import shutil
        columns, rows = shutil.get_terminal_size()
        return {
            "width": columns,
            "height": rows,
            "truecolor": True, # Assuming modern terminal for now
            "emoji": True      # Assuming modern terminal for now
        }
    except Exception:
        return {
            "width": 80, # Default
            "height": 24, # Default
            "truecolor": False,
            "emoji": False
        }

def validate_multi_dice_randomness(roll_history: List[List[int]]) -> ValidationResult:
    """Placeholder for multi-dice randomness validation.
    True statistical validation is complex and beyond scope for initial setup.
    """
    # This is a simplified placeholder.
    # A real implementation would involve statistical tests (e.g., Chi-squared).
    if not roll_history:
        return ValidationResult(is_valid=True, warnings=["No history to validate."])

    # Basic checks:
    num_dice = 0
    if roll_history[0]:
        num_dice = len(roll_history[0])

    for roll in roll_history:
        if len(roll) != num_dice:
            return ValidationResult(is_valid=False, errors=["Inconsistent number of dice in history."])
        for value in roll:
            if not (1 <= value <= 6):
                return ValidationResult(is_valid=False, errors=[f"Invalid die value '{value}' in history."])

    return ValidationResult(is_valid=True, warnings=["Simplified validation passed."])

# --- End Utility Functions ---

# --- Main Application Class ---

class DiceRollerApp(App[None]):
    """A multi-dice rolling application for the terminal."""

    CSS = """
    App {
        background: $surface; /* Changed from Screen for consistency */
    }

    Screen { /* Ensure screen itself also aligns if needed */
        align: center middle;
    }

    #main-container {
        align: center middle; /* Added from spec */
        width: auto; /* Start with auto, will be adjusted by dice count */
        height: auto; /* Start with auto, will be adjusted by dice count */
        max-width: 90; /* As per spec */
        background: $panel;
        border: heavy $primary;
        margin: 1; /* Simplified from 1 2 */
        padding: 1 1; /* Reduced padding slightly */
    }

    .dice-controls-container { /* Renamed from .dice-controls from spec */
        align: center middle;
        width: 100%;
        height: 5; /* From spec */
        margin-bottom: 1; /* From spec */
    }

    #dice-count-label { /* Renamed from #dice-count from spec */
        width: 1fr; /* Changed from fixed width to be more flexible */
        max-width: 14; /* Max width for the label */
        height: 3; /* Explicit height */
        text-align: center;
        margin: 0 1; /* Reduced margin */
        content-align: center middle;
        background: $accent;
        color: $text;
        border: solid $primary;
    }

    #add-die, #remove-die {
        width: 6; /* From spec */
        height: 3; /* From spec */
        min-height: 3; /* From spec */
    }

    #dice-grid-container { /* Renamed from #dice-grid from spec */
        width: 100%;
        /* min-height: 8; From spec - this might be too large, let grid content define it */
        /* max-height: 16; From spec - let grid content define it */
        align: center middle;
        margin: 1 0; /* From spec */
        /* grid-gutter: 1 2; From spec - can be added if desired */
        /* border: round $accent lightly-transparent; Kept from previous */
        padding: 1;
    }

    .die-emoji-label {
        width: 8; /* From spec */
        height: 4; /* From spec */
        content-align: center middle;
        text-align: center; /* Ensured */
        text-style: bold; /* From spec */
        background: $surface;
        border: solid $accent; /* From spec */
        margin: 0; /* From spec */
        /* font-size: 150%; Replaced by text-size from spec if available, or keep if text-size not in spec */
        /* Using Textual's text-size property if available, otherwise this is Rich specific.
           The spec's CSS has 'text-size: 2;' for .die-emoji, assuming this means 2 cells or similar.
           Textual Label doesn't have direct text-size CSS. Font-size is better for web.
           For terminal, the size of the label itself dictates content space.
           The spec's `createDieEmoji` uses `with_font_size(large)`.
           Let's ensure the label is big enough and text is centered.
        */
    }

    .die-emoji-label:hover { /* From spec */
        background: $surface-lighten-1;
        border: heavy $accent;
    }

    .die-emoji-label.rolling {
        border: round $warning;
        opacity: 0.75;
    }

    .stats-container {
        width: 100%;
        height: auto; /* Changed from fixed 6 to auto */
        align: center middle;
        background: $surface-lighten-1; /* From spec */
        border: solid $secondary; /* From spec */
        margin: 1 0; /* From spec */
        padding: 1; /* From spec */
    }

    #sum-display {
        width: 100%;
        text-align: center;
        text-style: bold; /* From spec */
        color: $primary; /* From spec */
        margin-bottom: 0; /* Reduced from 1 */
    }

    #frequency-display {
        width: 100%;
        text-align: center;
        color: $text; /* From spec */
        /* text-size: 0.9em; From spec - Textual Label doesn't have direct text-size. */
        /* We can make the label itself smaller or use Rich Text styling if needed. */
        margin-top: 0; /* Added */
    }

    .action-buttons-container { /* Renamed from .action-buttons from spec */
        width: 100%;
        height: 5; /* From spec */
        align: center middle;
        margin: 1 0; /* From spec */
    }

    #roll-button { /* Combined with #reset-button styling from spec */
        width: 60%; /* From spec */
        min-width: 20; /* From spec */
        margin: 0 1; /* From spec */
        min-height: 3; /* From spec */
    }

    #reset-button {
        width: 30%; /* From spec */
        min-width: 12; /* From spec */
        margin: 0 1; /* From spec */
        min-height: 3; /* From spec */
    }

    #instructions { /* Renamed from #help-text from spec */
        width: 100%;
        text-align: center;
        color: $text-muted; /* From spec */
        margin-top: 1; /* From spec */
        /* text-size: 0.8em; From spec - not directly applicable to Textual Label CSS */
    }

    Header {
        dock: top; /* Ensured */
        background: $primary;
        color: $text; /* From spec */
        text-style: bold; /* Ensured */
        padding: 0 1; /* Ensured */
    }

    Footer {
        dock: bottom; /* Ensured */
        background: $secondary; /* From spec */
        height: 1; /* Ensured */
    }

    /* Responsive grid layouts from spec */
    .grid-1x1 { grid-size-columns: 1; grid-size-rows: 1; grid-gutter: 1; }
    .grid-2x1 { grid-size-columns: 2; grid-size-rows: 1; grid-gutter: 1; }
    .grid-3x1 { grid-size-columns: 3; grid-size-rows: 1; grid-gutter: 1; }
    .grid-2x2 { grid-size-columns: 2; grid-size-rows: 2; grid-gutter: 1; }
    .grid-3x2 { grid-size-columns: 3; grid-size-rows: 2; grid-gutter: 1; }
    .grid-4x2 { grid-size-columns: 4; grid-size-rows: 2; grid-gutter: 1; }
    """

    TITLE = "🎲 Multi-Dice Roller"

    BINDINGS = [
        Binding("r", "roll_all_dice", "Roll Dice", show=True),
        Binding("space", "roll_all_dice", "Roll Dice", show=False), # Show=False for alternative keys
        Binding("enter", "roll_all_dice", "Roll Dice", show=False),

        Binding("+", "add_die", "Add Die", show=True),
        Binding("=", "add_die", "Add Die", show=False), # Alias for +

        Binding("-", "remove_die", "Remove Die", show=True),

        Binding("1", "set_dice_count(1)", "1 Die", show=True, key_display="1"),
        Binding("2", "set_dice_count(2)", "2 Dice", show=True, key_display="2"),
        Binding("3", "set_dice_count(3)", "3 Dice", show=True, key_display="3"),
        Binding("4", "set_dice_count(4)", "4 Dice", show=True, key_display="4"),
        Binding("5", "set_dice_count(5)", "5 Dice", show=True, key_display="5"),
        Binding("6", "set_dice_count(6)", "6 Dice", show=True, key_display="6"),
        Binding("7", "set_dice_count(7)", "7 Dice", show=True, key_display="7"),
        Binding("8", "set_dice_count(8)", "8 Dice", show=True, key_display="8"),

        Binding("q", "request_quit", "Quit", show=True), # Using request_quit for graceful exit
        Binding("escape", "request_quit", "Quit", show=False)
        # Ctrl+C is usually handled by Textual by default to quit
    ]

    # Reactive properties
    dice_count: reactive[int] = reactive(1)
    is_rolling: reactive[bool] = reactive(False)
    current_results: reactive[List[int]] = reactive(lambda: [1]) # Default to one die showing 1
    current_sum: reactive[int] = reactive(1)
    current_frequencies_str: reactive[str] = reactive("1x⚀")
    app_roll_count: reactive[int] = reactive(0) # Total rolls in the session

    # Maximum number of dice
    MAX_DICE = 8
    MIN_DICE = 1

    # Placeholder for dice widgets. We will populate this in on_mount or when dice_count changes.
    # Using a list to store references to the Label widgets for the dice.
    dice_widgets: List[Label] = []


    def on_mount(self) -> None:
        """Called when the app is first mounted."""
        # Terminal capability check (basic size check)
        # capabilities = detect_terminal_capabilities() # self.size is preferred in on_mount
        min_width = 60  # Adjusted minimum width for warning
        min_height = 20 # Adjusted minimum height for warning

        # Use self.size for current terminal dimensions available from Textual App
        actual_width, actual_height = self.size

        if actual_width < min_width or actual_height < min_height:
            self.notify(
                f"Terminal may be too small ({actual_width}x{actual_height}). Recommended minimum: {min_width}x{min_height}.",
                severity="warning",
                timeout=5 # Show warning for a bit longer
            )

        self.sub_title = f"{self.dice_count} die | Sum: {self.current_sum} | Roll #{self.app_roll_count}"
        self.update_dice_grid_display() # Initial setup of dice widgets
        self.update_stats_display()
        self.update_button_states() # Ensure button states are correct on mount

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header(self.TITLE)
        yield Footer()

        with Container(id="main-container"):
            # Dice Controls
            with Horizontal(classes="dice-controls-container"):
                yield Button("➖", id="remove-die", variant="error")
                yield Label(f"Dice: {self.dice_count}", id="dice-count-label") # Will be updated by watch_dice_count
                yield Button("➕", id="add-die", variant="success")

            # Dice Grid
            # The actual dice Label widgets will be added/removed dynamically in update_dice_grid_display
            yield Grid(id="dice-grid-container")

            # Statistics Display
            with Vertical(classes="stats-container"):
                yield Label(f"Sum: {self.current_sum}", id="sum-display")
                yield Label(self.current_frequencies_str, id="frequency-display")

            # Action Buttons
            with Horizontal(classes="action-buttons-container"):
                yield Button("🎲 Roll All Dice", id="roll-button", variant="primary")
                yield Button("🔄 Reset", id="reset-button")

            yield Label("Press 'r' to roll, '+'/'-' for dice, '1-8' for count, 'q' to quit", id="instructions")

    # --- Watchers for reactive properties ---

    def watch_dice_count(self, old_value: int, new_value: int) -> None:
        """Called when dice_count changes."""
        # Only update the label if it exists (i.e., compose() has run for this widget)
        dice_count_labels = self.query("#dice-count-label")
        if dice_count_labels:
            dice_count_labels.first(Label).update(f"Dice: {new_value}")

        self.update_dice_grid_display()
        # Reset results when dice count changes, or adjust as per spec
        self.current_results = [1] * new_value
        self.update_stats_display() # Update sum/freq for new default dice

        # Adapt main container layout to dice count (from spec's pseudocode)
        # Ensure main_container and roll_button also exist before querying them if there's a similar risk
        # For now, assuming they are less problematic or handled if errors arise.
        # A more robust solution might involve checking self.is_mounted or a similar flag.
        try:
            main_container = self.query_one("#main-container")
            roll_button = self.query_one("#roll-button", Button)

            if self.dice_count >= 7: # 7 to 8 dice
                main_container.styles.width = "70"
                main_container.styles.height = "28"
            elif self.dice_count >= 4: # 4 to 6 dice
                main_container.styles.width = "60"
                main_container.styles.height = "28"
            else: # 1 to 3 dice
                main_container.styles.width = "50"
                main_container.styles.height = "22"

            if self.dice_count == 1:
                roll_button.label = Text("🎲 Roll Die")
            else:
                roll_button.label = Text(f"🎲 Roll {self.dice_count} Dice")
        except Exception: # Catch potential NoMatches if these are also queried too early
            pass # If they don't exist yet, their properties will be set by compose or later calls

        self.update_button_states()

    def watch_is_rolling(self, old_value: bool, new_value: bool) -> None:
        """Called when is_rolling changes."""
        self.update_button_states()
        # Could also change status message here

    def watch_current_results(self, old_results: List[int], new_results: List[int]) -> None:
        """Update dice faces when results change."""
        dice_emojis = ["", "⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]
        for i, widget in enumerate(self.dice_widgets):
            if i < len(new_results):
                widget.update(Text(dice_emojis[new_results[i]], justify="center"))
            else: # Should not happen if dice_widgets is synced with dice_count
                widget.update("")
        self.update_stats_display()

    def watch_app_roll_count(self, old_count: int, new_count: int) -> None:
        """Update header subtitle when roll count or other stats change."""
        self.update_header_subtitle()

    def watch_current_sum(self, old_sum: int, new_sum: int) -> None:
        """Update header subtitle when sum changes."""
        self.update_header_subtitle()

    # --- UI Update Methods ---

    def update_header_subtitle(self) -> None:
        """Updates the header's subtitle with current game status."""
        self.sub_title = f"{self.dice_count} {'die' if self.dice_count == 1 else 'dice'} | Sum: {self.current_sum} | Roll #{self.app_roll_count}"

    def update_dice_grid_display(self) -> None:
        """Update the dice grid based on the current dice_count."""
        grid_query = self.query("#dice-grid-container")
        if not grid_query:
            return # If the grid container doesn't exist yet, do nothing

        grid = grid_query.first(Grid)

        # Clear existing dice widgets from the list and grid
        for widget in self.dice_widgets:
            widget.remove()
        self.dice_widgets.clear()
        grid.remove_children()

        if self.dice_count == 0: # Should not happen based on MIN_DICE
            grid.styles.grid_size_columns = 1
            grid.styles.grid_size_rows = 1
            return

        # Calculate optimal grid dimensions
        dims = calculateOptimalGrid(self.dice_count)

        # Remove existing grid classes
        # A more robust way to remove only our specific grid classes
        current_classes = list(grid.classes) # Get a copy
        for css_class in current_classes:
            if css_class.startswith("grid-") and 'x' in css_class: # e.g. "grid-2x2"
                try:
                    # Validate it's one of our defined grid classes before removing
                    parts = css_class.replace("grid-", "").split('x')
                    if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                         grid.remove_class(css_class)
                except ValueError: # or other parsing error
                    pass # Not one of our grid classes

        # Apply new grid class
        if dims.columns > 0 and dims.rows > 0:
            grid.add_class(f"grid-{dims.columns}x{dims.rows}")
        # If no dice, grid will be empty and no specific class needed, or a default.

        # Create and add new dice labels
        dice_emojis = ["", "⚀", "⚁", "⚂", "⚃", "⚄", "⚅"] # Index 0 unused
        for i in range(self.dice_count):
            # Default to face '1' (⚀)
            initial_face = dice_emojis[self.current_results[i] if i < len(self.current_results) else 1]
            die_label = Label(Text(initial_face, justify="center"), classes="die-emoji-label", id=f"die-{i}")
            self.dice_widgets.append(die_label)
            grid.mount(die_label)

    def update_stats_display(self) -> None:
        """Updates the sum and frequency labels from current_results."""
        if not self.current_results:
            self.current_sum = 0
            self.current_frequencies_str = "No results yet"
        else:
            self.current_sum = sum(self.current_results)
            frequencies = calculate_frequencies(self.current_results)
            self.current_frequencies_str = format_frequencies(frequencies)

        sum_display_query = self.query("#sum-display")
        if sum_display_query:
            sum_display_query.first(Label).update(f"Sum: {self.current_sum}")

        frequency_display_query = self.query("#frequency-display")
        if frequency_display_query:
            frequency_display_query.first(Label).update(self.current_frequencies_str)

        self.update_header_subtitle() # Also update header as stats change

    def update_button_states(self) -> None:
        """Enable/disable buttons based on app state."""
        try:
            roll_button = self.query_one("#roll-button", Button)
            add_button = self.query_one("#add-die", Button)
            remove_button = self.query_one("#remove-die", Button)
            reset_button = self.query_one("#reset-button", Button)

            roll_button.disabled = self.is_rolling
            reset_button.disabled = self.is_rolling
            add_button.disabled = self.is_rolling or self.dice_count >= self.MAX_DICE
            remove_button.disabled = self.is_rolling or self.dice_count <= self.MIN_DICE

            # Disable number keys for dice count if rolling (will be handled in key bindings)
        except Exception: # Covers NoMatches if buttons aren't there yet
            pass

    # --- Action Methods for Dice Management ---

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if self.is_rolling: # Prevent actions while rolling
            return

        button_id = event.button.id
        if button_id == "add-die":
            self.action_add_die()
        elif button_id == "remove-die":
            self.action_remove_die()
        elif button_id == "reset-button":
            self.action_reset_dice()
        elif button_id == "roll-button":
            self.call_later(self.action_roll_all_dice) # Use call_later for async actions from sync handlers


    def action_add_die(self) -> None:
        """Increments the number of dice."""
        if self.is_rolling: return
        if self.dice_count < self.MAX_DICE:
            self.dice_count += 1
            # current_results are updated by the watcher, which then calls update_stats_display
            self.notify(f"Added die. Now {self.dice_count}.", timeout=1.5)
        else:
            self.notify(f"Maximum {self.MAX_DICE} dice allowed.", severity="warning", timeout=2)
        self.update_button_states() # Ensure buttons reflect new state immediately

    def action_remove_die(self) -> None:
        """Decrements the number of dice."""
        if self.is_rolling: return
        if self.dice_count > self.MIN_DICE:
            self.dice_count -= 1
            # current_results are updated by the watcher, which then calls update_stats_display
            self.notify(f"Removed die. Now {self.dice_count}.", timeout=1.5)
        else:
            self.notify(f"Minimum {self.MIN_DICE} die required.", severity="warning", timeout=2)
        self.update_button_states() # Ensure buttons reflect new state immediately

    def action_set_dice_count(self, count: int) -> None:
        """Sets the number of dice directly."""
        if self.is_rolling: return
        if self.MIN_DICE <= count <= self.MAX_DICE:
            if self.dice_count != count:
                self.dice_count = count
                self.notify(f"Set dice count to {self.dice_count}.", timeout=1.5)
            # else:
                # self.notify(f"Dice count is already {self.dice_count}.", timeout=1.5)
        else:
            self.notify(f"Dice count must be between {self.MIN_DICE} and {self.MAX_DICE}.", severity="error", timeout=2)
        self.update_button_states()

    def action_reset_dice(self) -> None:
        """Resets all dice to their default state (face 1) and clears stats for current dice count."""
        if self.is_rolling: return
        self.current_results = [1] * self.dice_count
        self.app_roll_count = 0 # Reset session roll count as per spec interpretation
        # self.current_sum and self.current_frequencies_str are updated by watch_current_results -> update_stats_display
        # self.sub_title is updated by watch_app_roll_count & watch_current_sum -> update_header_subtitle
        self.notify("Dice and session stats reset.", timeout=2)
        # Individual die widgets are updated by watch_current_results
        self.update_button_states()

    # --- Animation Logic ---
    async def animate_die(self, die_widget: Label, duration: float) -> None:
        """Animates a single die widget for a given duration."""
        if not die_widget:
            return

        num_frames = int(duration * 20) # Aim for 20fps
        delay_per_frame = duration / num_frames
        dice_emojis = ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"]

        original_classes = die_widget.classes
        die_widget.add_class("rolling") # Add a class for potential styling during roll

        for _ in range(num_frames):
            random_face = secrets.choice(dice_emojis)
            die_widget.update(Text(random_face, justify="center"))
            await asyncio.sleep(delay_per_frame)

        # Restore original classes, remove 'rolling'
        # This is a simple way; Textual 0.50+ offers set_classes
        current_classes = [c for c in die_widget.classes if c != "rolling"]
        die_widget.classes = " ".join(current_classes)
        # For older Textual versions, you might need to remove and re-add specific classes
        # or ensure "rolling" is removed if you added other animation-specific classes.

        # The final face will be set by watch_current_results after all animations complete.
        # Here, we can reset it to a neutral or the last random face.
        # die_widget.update(Text(secrets.choice(dice_emojis), justify="center")) # Optional: leave on last random face

    # --- Core Dice Rolling Logic ---

    async def action_roll_all_dice(self) -> None:
        """Handles the logic for rolling all active dice."""
        if self.is_rolling:
            return

        self.is_rolling = True # This will trigger button state updates via its watcher

        # --- Animation Phase ---
        self.notify("Rolling dice...", timeout=0.2) # Brief notification

        animation_tasks = []
        if self.dice_count > 0 and self.dice_widgets:
            for i in range(self.dice_count):
                if i < len(self.dice_widgets):
                    die_widget = self.dice_widgets[i]
                    # Duration for each die's animation is random (0.3s to 0.6s)
                    anim_duration = secrets.uniform(0.3, 0.6)
                    animation_tasks.append(self.animate_die(die_widget, anim_duration))

            if animation_tasks:
                await asyncio.gather(*animation_tasks)
            else: # Fallback if somehow no tasks were created despite dice_count > 0
                await asyncio.sleep(0.5) # Default wait
        else:
            # No dice to animate, but still ensure a small delay if needed for flow
            await asyncio.sleep(0.1)

        # --- Results Phase ---
        new_results = []
        if self.dice_count > 0:
            for _ in range(self.dice_count):
                new_results.append(secrets.randbelow(6) + 1) # Generate 1-6
            self.current_results = new_results # This will trigger watchers to update faces and stats
            self.app_roll_count += 1
            self.notify(f"Roll #{self.app_roll_count} results: {self.current_sum}", timeout=2)
        else:
            self.notify("No dice to roll.", severity="warning", timeout=2)
            self.current_results = [] # Clear results if no dice

        self.is_rolling = False # This will re-enable buttons via its watcher

# --- End Main Application Class ---

if __name__ == "__main__":
    app = DiceRollerApp()
    app.run()
