#!/usr/bin/env -S uv run
# /// script
# dependencies = ["textual>=3.3,<4.0.0", "rich>=13.0.0,<14.0.0"]
# requires-python = ">=3.12"
# ///

import asyncio
import secrets
import sys
import random
import os
import shutil
import uuid
from typing import Any, Dict, List, Optional, Tuple

try:
    from textual.app import App, ComposeResult
    from textual.containers import Container, Horizontal, Vertical, Grid
    from textual.widgets import Header, Button, Label  # Footer removed
    from textual.binding import Binding
    # DOMQuery, events, Message removed as they appear unused
    from textual.reactive import reactive

    from rich.text import Text
    # Align, ConsoleOptions, Console, RenderResult, Measurement, Segments removed
    # Assuming Textual handles Rich integration sufficiently with just Text for this app's needs.

except ImportError:
    print("Run: uv cache clean && uv run multi_dice_roller.py", file=sys.stderr)
    sys.exit(1)

# --- Enums and Data Classes ---
# Unused DiceState, GridDimensions, StatisticsInfo, ValidationResult removed.
# --- End Enums and Data Classes ---

# --- Large ASCII die faces ---

# Dice face representations using simple ASCII pips. Each value is a
# multiline string that fits within the default 7x5 cell used by the CSS
# style. These are wider than the original emoji faces so they appear
# more prominent in terminals where the emoji were rendered very small.
DICE_ART: Dict[int, str] = {
    1: (
        "       \n"
        "       \n"
        "   ●   \n"
        "       \n"
        "       "
    ),
    2: (
        "       \n"
        " ●    \n"
        "       \n"
        "     ● \n"
        "       "
    ),
    3: (
        "       \n"
        " ●    \n"
        "   ●   \n"
        "     ● \n"
        "       "
    ),
    4: (
        "       \n"
        " ●   ● \n"
        "       \n"
        " ●   ● \n"
        "       "
    ),
    5: (
        "       \n"
        " ●   ● \n"
        "   ●   \n"
        " ●   ● \n"
        "       "
    ),
    6: (
        "       \n"
        " ●   ● \n"
        " ●   ● \n"
        " ●   ● \n"
        "       "
    ),
}

# --- Utility Functions ---

def get_grid_layout_dimensions(dice_count: int) -> Tuple[int, int]:
    """Calculate optimal grid layout dimensions (columns, rows) for a given number of dice."""
    layout_map = {
        1: (1, 1), 2: (2, 1), 3: (3, 1), 4: (2, 2),
        5: (3, 2), 6: (3, 2), 7: (4, 2), 8: (4, 2)
    }
    if not (1 <= dice_count <= 8):
        # Fallback for invalid counts. App logic should prevent 0 or <0.
        # For dice_count = 0, an empty grid is usually handled separately.
        # Returning (0,0) for 0 dice, and a default for >8 or other unexpected.
        if dice_count == 0:
            return (0, 0)
        # Default for > 8 dice or other unexpected values (e.g. negative, though MIN_DICE=1)
        # A small grid or error might be appropriate. For now, let's use a 4-column grid.
        # This case should ideally not be reached if MIN_DICE/MAX_DICE are enforced.
        # The spec's map only covers 1-8.
        # Returning a default like (4, (dice_count + 3) // 4) as in old func for >8
        if dice_count > 8 :
            return (4, (dice_count + 3) // 4)
        return (1,1) # Default for any other unexpected values (e.g. negative if checks fail)
    return layout_map.get(dice_count, (1, 1)) # .get with default for safety, though keys 1-8 are covered.

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
    """Detect terminal dimensions and basic feature support."""
    try:
        columns, rows = shutil.get_terminal_size()
    except Exception:
        columns, rows = 80, 24

    emoji_support = (
        sys.platform != "win32"
        and ("UTF-8" in os.environ.get("LC_CTYPE", "")
             or "UTF-8" in os.environ.get("LANG", ""))
    )
    truecolor = os.environ.get("COLORTERM", "") in {"truecolor", "24bit"}

# --- End Utility Functions ---
    return {
        "width": columns,
        "height": rows,
        "truecolor": truecolor,
        "emoji": emoji_support,
    }

# --- End Utility Functions ---

# --- Random Float Utility (as per spec) ---
def random_float(min_val: float, max_val: float) -> float:
    """
    Generates a cryptographically secure random float within a given range [min_val, max_val).
    Uses secrets.token_bytes for randomness and normalizes it to the specified range.
    """
    if not (isinstance(min_val, (int, float)) and isinstance(max_val, (int, float))):
        raise TypeError("min_val and max_val must be numbers")
    if min_val >= max_val:
        # Or handle as an error, e.g., raise ValueError
        # For now, allowing min_val == max_val, which will just return min_val
        if min_val > max_val: # If strictly greater, maybe raise error or swap
             raise ValueError("min_val cannot be greater than max_val")
        return min_val


    byte_count = 4 # 32 bits for precision
    try:
        raw_bytes = secrets.token_bytes(byte_count)
    except Exception:
        # Fallback to standard random if secrets.token_bytes fails (highly unlikely in normal environments).
        # This ensures the function still returns a value, albeit less secure.
        normalized_float = random.random()
    else:
        normalized_int = int.from_bytes(raw_bytes, 'big')
        # (2**(byte_count*8) - 1) is the max possible integer value for that many bytes
        max_int_val = (1 << (byte_count * 8)) -1 # More efficient calculation for 2**N - 1
        if max_int_val == 0: # Avoid division by zero if byte_count was 0 (not the case here)
            normalized_float = 0.0
        else:
            normalized_float = normalized_int / max_int_val

    return min_val + normalized_float * (max_val - min_val)

# --- Animation Controller Class ---
class DiceAnimationController:
    """Handles die animations independently from the main app."""

    def __init__(self, dice_widgets: List[Label], emojis: List[str]):
        self.dice_widgets = dice_widgets
        self.emojis = emojis

    @staticmethod
    def generate_random_duration() -> float:
        """Return a secure random duration between 0.3 and 0.6 seconds."""
        return random_float(0.3, 0.6)

    async def animate_single_die(self, index: int, duration: float) -> int:
        if not (0 <= index < len(self.dice_widgets)):
            return 1
        die_widget = self.dice_widgets[index]
        frames = int(duration / 0.05) or 1
        die_widget.add_class("rolling")
        for _ in range(frames):
            die_widget.update(Text(secrets.choice(self.emojis), justify="center"))
            await asyncio.sleep(0.05)
        result = secrets.randbelow(6) + 1
        die_widget.update(Text(self.emojis[result - 1], justify="center"))
        die_widget.remove_class("rolling")
        return result

    async def animate_all_dice(self, indices: List[int]) -> List[int]:
        tasks = [asyncio.create_task(self.animate_single_die(i, self.generate_random_duration())) for i in indices]
        return await asyncio.gather(*tasks)

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
        min-width: 50;
        width: 100%; /* Expand to available width */
        height: auto;
        max-width: 100%; /* Allow container to expand to full width */
        background: $panel;
        border: heavy $primary;
        margin: 1; /* Simplified from 1 2 */
        padding: 1 1; /* Reduced padding slightly */
    }

    /* Dice count controls were removed from the interface, so related styles
       have been deleted. */

    #dice-grid-container { /* Renamed from #dice-grid from spec */
        width: 100%;
        align: center middle;
        margin: 1 0; /* From spec */
        padding: 1;
    }

    .die-emoji-label {
        width: 7;
        min-width: 7;
        max-width: 7;
        height: 5;
        min-height: 5;
        max-height: 5;
        content-align: center middle;
        text-align: center;
        text-style: bold;
        background: $surface;
        border: solid $accent;
        margin: 0;
    }

    .die-emoji-label:hover { /* From spec */
        background: $surface-lighten-1;
        border: heavy $accent;
    }

    .die-emoji-label.rolling {
        border: round $warning;
        opacity: 0.75;
    }

    .die-emoji-label.selected {
        border: heavy $primary-darken-2;
        background: $primary-background-lighten-2;
        /* Ensure high contrast for selection */
    }

    .die-emoji-label.locked {
        background: $warning-darken-1; /* Darker warning for background */
        color: $text; /* Ensure text (emoji) is visible */
        border: thick $error-darken-2; /* Distinct border for locked state */
        /* Consider adding a textual lock indicator if emoji modification is too complex:
           e.g., prefixing the Label's renderable with "🔒 " in update_dice_visual_states
           For now, relying on background and border. */
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
    }

    Header {
        dock: top; /* Ensured */
        background: $primary;
        color: $text; /* From spec */
        text-style: bold; /* Ensured */
        padding: 0 1; /* Ensured */
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
        Binding("r", "roll_unlocked_dice", "Roll Unlocked Dice", show=True), # Changed action
        Binding("enter", "roll_unlocked_dice", "Roll Unlocked Dice", show=False), # Changed action
        Binding("space", "toggle_lock", "Lock/Unlock Die", show=True), # Changed

        Binding("up", "navigate_dice('up')", "Navigate Up", show=False),
        Binding("down", "navigate_dice('down')", "Navigate Down", show=False),
        Binding("left", "navigate_dice('left')", "Navigate Left", show=False),
        Binding("right", "navigate_dice('right')", "Navigate Right", show=False),

        Binding("ctrl+l", "lock_all", "Lock All", show=True),
        Binding("ctrl+u", "unlock_all", "Unlock All", show=True),

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
    current_results: reactive[List[int]] = reactive([]) # Default to empty list
    current_sum: reactive[int] = reactive(0) # Adjusted due to empty results
    current_frequencies_str: reactive[str] = reactive("No results yet") # Adjusted
    selected_die_index: reactive[int] = reactive(0) # Added from spec
    locked_dice: reactive[set[int]] = reactive(set) # Added from spec
    app_roll_count: reactive[int] = reactive(0) # Total rolls in thesession

    # Maximum number of dice
    MAX_DICE = 8
    MIN_DICE = 1

    # Placeholder for dice widgets. We will populate this in on_mount or when dice_count changes.
    # Using a list to store references to the Label widgets for the dice.
    dice_widgets: List[Label] = []
    # Use larger ASCII representations instead of small emoji faces
    dice_emojis: List[str] = [DICE_ART[i] for i in range(1, 7)]
    terminal_caps: Dict[str, Any] = {}
    animation_controller: Optional[DiceAnimationController] = None

    # --- Visual State Update Method ---
    def update_dice_visual_states(self) -> None:
        """
        Updates the visual state (CSS classes for .selected and .locked) of all dice widgets
        based on the current `self.selected_die_index` and `self.locked_dice` set.
        """
        if not self.dice_widgets: # No widgets to update
            return

        for i, die_widget in enumerate(self.dice_widgets):
            die_widget.remove_class("selected", "locked") # Clear existing states

            is_selected = (i == self.selected_die_index)
            is_locked = (i in self.locked_dice)

            if is_selected:
                die_widget.add_class("selected")

            if is_locked:
                die_widget.add_class("locked")

            # If a die is both selected and locked, it will have both classes.
            # CSS specificity or class order might matter if styles conflict.
            # Current CSS for .selected and .locked should compose reasonably.

    def on_mount(self) -> None:
        """Called when the app is first mounted. Initializes subtitle and UI elements."""
        self.terminal_caps = detect_terminal_capabilities()

        min_width = 60
        min_height = 20
        actual_width = int(self.terminal_caps.get("width", 80))
        actual_height = int(self.terminal_caps.get("height", 24))
        if actual_width < min_width or actual_height < min_height:
            self.notify(
                (
                    f"Terminal may be too small ({actual_width}x{actual_height}). "
                    f"Recommended minimum: {min_width}x{min_height}."
                ),
                severity="warning",
                timeout=5,
            )

        if not self.terminal_caps.get("emoji", True):
            self.notify(
                "Emoji support not detected. Dice summary may not render properly.",
                severity="warning",
                timeout=4,
            )

        self.sub_title = f"{self.dice_count} die | Sum: {self.current_sum} | Roll #{self.app_roll_count}"
        self.update_dice_grid_display()  # Initial setup of dice widgets
        self.animation_controller = DiceAnimationController(self.dice_widgets, self.dice_emojis)
        self.update_stats_display()
        self.update_button_states() # Ensure button states are correct on mount
        self.call_later(self.update_dice_visual_states) # Ensure it runs after initial dice are created

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header(self.TITLE)

        with Container(id="main-container"):


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


        self.update_dice_grid_display() # This recreates dice_widgets
        # Reset results when dice count changes
        if self.dice_count > 0:
             self.current_results = [1] * new_value # Default to 1s if dice exist
        else:
             self.current_results = []

        # Clamp selected_die_index if it's out of bounds
        if self.selected_die_index >= self.dice_count and self.dice_count > 0:
            self.selected_die_index = self.dice_count - 1
        elif self.dice_count == 0:
            self.selected_die_index = 0

        self.update_stats_display() # Update sum/freq for new default dice
        self.call_later(self.update_dice_visual_states) # Update visuals for new grid

        # Adapt main container layout to dice count (from spec's pseudocode)
        # Ensure main_container and roll_button also exist before querying them.
        # A more robust solution might involve checking self.is_mounted for these elements
        # if errors occur during very early/rapid dice_count changes.
        try:
            main_container = self.query_one("#main-container")
            roll_button = self.query_one("#roll-button", Button)

            main_container.styles.width = "100%"  # Fill available width
            main_container.styles.height = "auto"

            if self.dice_count == 1:
                roll_button.label = Text("🎲 Roll Die")
            else:
                roll_button.label = Text(f"🎲 Roll {self.dice_count} Dice")
        except Exception:  # Catch potential NoMatches if these are also queried too early
            pass  # If they don't exist yet, their properties will be set by compose or later calls

        self.update_button_states()

    def watch_is_rolling(self, old_value: bool, new_value: bool) -> None:
        """Called when is_rolling changes."""
        self.update_button_states()
        # Could also change status message here

    def watch_current_results(self, old_results: List[int], new_results: List[int]) -> None:
        """Update dice faces when results change."""
        dice_emojis = [""] + self.dice_emojis
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

    async def watch_selected_die_index(self, old_index: int, new_index: int) -> None:
        """Called when selected_die_index changes."""
        self.update_dice_visual_states()

    async def watch_locked_dice(self, old_set: set[int], new_set: set[int]) -> None:
        """Called when locked_dice changes."""
        # Ensure this is triggered correctly. For sets, direct mutation might not trigger.
        # If issues, assign a new set: self.locked_dice = new_set_instance
        self.update_dice_visual_states()


    # --- UI Update Methods ---

    def update_header_subtitle(self) -> None:
        """Updates the header's subtitle with current game status."""
        die_label = "die" if self.dice_count == 1 else "dice"
        self.sub_title = (
            f"{self.dice_count} {die_label} | Sum: {self.current_sum} | Roll #{self.app_roll_count}"
        )

    def update_dice_grid_display(self) -> None:
        """Update the dice grid based on the current dice_count."""
        grid_query = self.query("#dice-grid-container")
        if not grid_query:
            return # If the grid container doesn't exist yet, do nothing

        grid = grid_query.first(Grid)

        # Clear existing dice widgets from the list and grid
        # Call grid.remove_children() first to ensure all children are detached from the grid.
        grid.remove_children()

        # Then, iterate through the known dice_widgets to ensure they are fully removed
        # from the app's perspective (e.g., ID unregistration, other cleanup).
        # At this point, their parent should be None.
        for widget in self.dice_widgets:
            widget.remove() # This should handle Textual's internal cleanup for the widget.
        self.dice_widgets.clear() # Clear our Python list of references.

        # Calculate optimal grid dimensions using the new function
        cols, rows = get_grid_layout_dimensions(self.dice_count)

        if cols == 0 or rows == 0: # Handles dice_count == 0
            # Ensure grid is effectively empty or hidden, no specific classes needed.
            # Textual might handle grid-size 0,0 by making it disappear.
            # Or, set a very small size / display: none if required.
            # For now, assuming removing children and not adding classes is enough.
            # We can also explicitly set grid.styles.grid_size_columns = 0 etc.
            # Let's clear any existing grid-NXM classes if any were set.
            current_classes = list(grid.classes)
            for css_class in current_classes:
                if css_class.startswith("grid-") and 'x' in css_class:
                    grid.remove_class(css_class)
            # Optionally set grid.styles.display = "none" or grid.styles.width/height = 0
            return # No dice to display

        # Remove existing grid classes
        # A more robust way to remove only our specific grid classes
        current_classes = list(grid.classes) # Get a copy
        for css_class in current_classes:
            if css_class.startswith("grid-") and 'x' in css_class: # e.g. "grid-2x2"
                # Basic check, assumes our classes are well-formed like "grid-1x1"
                grid.remove_class(css_class)

        # Apply new grid class based on cols and rows from get_grid_layout_dimensions
        # The CSS classes .grid-XxY are responsible for setting grid-size-columns and grid-size-rows
        if cols > 0 and rows > 0:
            grid.add_class(f"grid-{cols}x{rows}")
        # else: If cols/rows are 0 (e.g. dice_count is 0), no class is added, grid remains empty.

        # Create and add new dice labels
        dice_emojis = [""] + self.dice_emojis
        for i in range(self.dice_count):
            initial_face = dice_emojis[self.current_results[i] if i < len(self.current_results) else 1]
            unique_id = f"die-{i}-{uuid.uuid4().hex}"
            die_label = Label(Text(initial_face, justify="center"), classes="die-emoji-label", id=unique_id)
            self.dice_widgets.append(die_label)
            grid.mount(die_label)

        self.animation_controller = DiceAnimationController(self.dice_widgets, self.dice_emojis)

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
        """Enable or disable buttons based on the application state."""
        try:
            roll_button = self.query_one("#roll-button", Button)
            reset_button = self.query_one("#reset-button", Button)

            roll_button.disabled = self.is_rolling
            reset_button.disabled = self.is_rolling
        except Exception:  # Covers NoMatches if buttons aren't there yet
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
            self.call_later(self.action_roll_unlocked_dice) # Use call_later for async actions from sync handlers


    def action_add_die(self) -> None:
        """Increments the number of dice."""
        if self.is_rolling:
            return
        if self.dice_count < self.MAX_DICE:
            self.dice_count += 1
            # current_results are updated by the watcher, which then calls update_stats_display
            self.notify(f"Added die. Now {self.dice_count}.", timeout=1.5)
        else:
            self.notify(f"Maximum {self.MAX_DICE} dice allowed.", severity="warning", timeout=2)
        self.update_button_states() # Ensure buttons reflect new state immediately

    def action_remove_die(self) -> None:
        """Decrements the number of dice."""
        if self.is_rolling:
            return
        if self.dice_count > self.MIN_DICE:
            self.dice_count -= 1
            # current_results are updated by the watcher, which then calls update_stats_display
            self.notify(f"Removed die. Now {self.dice_count}.", timeout=1.5)
        else:
            self.notify(f"Minimum {self.MIN_DICE} die required.", severity="warning", timeout=2)
        self.update_button_states() # Ensure buttons reflect new state immediately

    def action_set_dice_count(self, count: int) -> None:
        """Sets the number of dice directly."""
        if self.is_rolling:
            return
        if self.MIN_DICE <= count <= self.MAX_DICE:
            if self.dice_count != count:
                self.dice_count = count
                self.notify(f"Set dice count to {self.dice_count}.", timeout=1.5)
        else:
            self.notify(f"Dice count must be between {self.MIN_DICE} and {self.MAX_DICE}.", severity="error", timeout=2)
        self.update_button_states()

    def action_reset_dice(self) -> None:
        """
        Resets all dice to face '1', clears the session roll count, and unlocks all dice.
        """
        if self.is_rolling:
            return
        if self.dice_count > 0:
            self.current_results = [1] * self.dice_count
        else:
            self.current_results = []
        self.app_roll_count = 0
        self.locked_dice = set()
        # Optionally, self.selected_die_index could be reset to 0.
        self.notify("Dice and session stats reset.", timeout=2)
        self.update_button_states()
        self.call_later(self.update_dice_visual_states)

    # --- Action Methods for Navigation and Locking ---

    def action_navigate_dice(self, direction: str) -> None:
        """
        Navigates the selection focus (`self.selected_die_index`) up, down, left, or right
        among the dice in the grid, based on the `direction` string.
        """
        if self.is_rolling or self.dice_count == 0:
            return

        current = self.selected_die_index
        dice_count = self.dice_count

        # Grid columns mapping from spec
        cols_map = {1:1, 2:2, 3:3, 4:2, 5:3, 6:3, 7:4, 8:4}
        cols = cols_map.get(dice_count, 1) # Default to 1 col if dice_count not in map (e.g. 0)
        if dice_count == 0: # avoid division by zero or unexpected behavior with cols=0
            cols = 1


        new_index = current
        if direction == "up":
            new_index = max(0, current - cols)
        elif direction == "down":
            new_index = min(dice_count - 1, current + cols)
        elif direction == "left":
            new_index = max(0, current - 1)
        elif direction == "right":
            new_index = min(dice_count - 1, current + 1)

        if new_index != current:
            self.selected_die_index = new_index
            # Watcher for selected_die_index will call update_dice_visual_states

    def action_toggle_lock(self) -> None:
        """
        Toggles the lock state of the currently selected die (`self.selected_die_index`).
        If the die is locked, it becomes unlocked, and vice-versa.
        Updates `self.locked_dice` reactively.
        """
        if self.is_rolling or self.dice_count == 0:
            return

        idx = self.selected_die_index
        new_locked_set = self.locked_dice.copy() # Important: work with a copy for reactive update
        if idx in new_locked_set:
            new_locked_set.remove(idx)
            self.notify(f"Die {idx+1} unlocked.", timeout=1)
        else:
            new_locked_set.add(idx)
            self.notify(f"Die {idx+1} locked.", timeout=1)
        self.locked_dice = new_locked_set

    def action_lock_all(self) -> None:
        """Locks all currently displayed dice."""
        if self.is_rolling or self.dice_count == 0:
            return
        new_locked_set = set(range(self.dice_count))
        if new_locked_set != self.locked_dice:
            self.locked_dice = new_locked_set
            self.notify("All dice locked.", timeout=1)
        else:
            self.notify("All dice already locked.", timeout=1)

    def action_unlock_all(self) -> None:
        """Unlocks all currently displayed dice."""
        if self.is_rolling or self.dice_count == 0:
            return
        if self.locked_dice:
            self.locked_dice = set()
            self.notify("All dice unlocked.", timeout=1)
        else:
            self.notify("All dice already unlocked.", timeout=1)

    # --- Core Dice Rolling Logic ---

    async def action_roll_unlocked_dice(self) -> None:
        """
        Handles the core logic for rolling dice:
        1. Identifies unlocked dice.
        2. If no dice are unlocked, notifies the user.
        3. Otherwise, animate each unlocked die in parallel using
           ``DiceAnimationController``.
        4. Gathers results from the controller.
        5. Updates `self.current_results` with the new values for rolled dice.
        6. Increments `self.app_roll_count`.
        7. Sets `self.is_rolling` to False and updates UI states.
        """
        if self.is_rolling:
            return

        if self.dice_count == 0:
            self.notify("No dice to roll.", severity="warning", timeout=2)
            return

        unlocked_indices = [i for i in range(self.dice_count) if i not in self.locked_dice]

        if not unlocked_indices:
            self.notify("All dice are locked. Nothing to roll.", severity="info", timeout=2)
            roll_button = self.query_one("#roll-button", Button)
            if self.dice_count == 1 :
                 roll_button.label = Text("🎲 Roll Die")
            else:
                 roll_button.label = Text(f"🎲 Roll {self.dice_count} Dice")
            return

        self.is_rolling = True
        self.notify("Rolling unlocked dice...", timeout=0.2)

        if not self.animation_controller:
            self.animation_controller = DiceAnimationController(self.dice_widgets, self.dice_emojis)

        try:
            results_for_unlocked_dice = await self.animation_controller.animate_all_dice(unlocked_indices)
        except Exception as e:
            self.notify(f"Animation error: {e}", severity="error", timeout=3)
            self.is_rolling = False
            self.call_later(self.update_dice_visual_states)
            return
        # No 'else' needed here, if tasks is empty, results_for_unlocked_dice remains empty.
        # This case is already handled by 'if not unlocked_indices' check.

        # --- Results Phase ---
        new_results_list = list(self.current_results)

        if len(new_results_list) != self.dice_count:
             new_results_list = [1] * self.dice_count # Safeguard

        rolled_at_least_one = False
        # Ensure results from gather match the number of tasks/unlocked_indices
        if len(unlocked_indices) == len(results_for_unlocked_dice):
            for i, actual_die_index in enumerate(unlocked_indices):
                # actual_die_index is the true index in self.dice_widgets / self.current_results
                # results_for_unlocked_dice[i] is the result for that die
                if 0 <= actual_die_index < self.dice_count: # Bounds check
                    new_results_list[actual_die_index] = results_for_unlocked_dice[i]
                    rolled_at_least_one = True
        else:
            # This indicates a mismatch, should not happen if asyncio.gather worked as expected.
            self.notify("Error processing roll results (result/index mismatch).", severity="error", timeout=3)
            self.is_rolling = False
            self.call_later(self.update_dice_visual_states)
            return

        if rolled_at_least_one:
            self.current_results = new_results_list
            self.app_roll_count += 1
        else:
            # This might happen if unlocked_indices was empty but the initial check failed,
            # or if all animations returned errors (though gather would likely raise one).
            self.notify("No dice were effectively rolled.", severity="warning", timeout=2)

        self.is_rolling = False
        self.call_later(self.update_dice_visual_states)

# --- End Main Application Class ---

if __name__ == "__main__":
    app = DiceRollerApp()
    try:
        app.run()
    except KeyboardInterrupt:
        # Textual apps handle terminal restoration. A simple message is sufficient.
        print("\nApplication terminated by user (Ctrl+C).")
        # sys.exit(0) is often implicit or handled by Textual's graceful exit.
    except Exception as e:
        # Basic error logging to stderr for unexpected errors.
        import traceback
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        print("Traceback (most recent call last):", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        # Attempt to ensure terminal is restored if app crashed badly.
        # Textual aims to do this, but this is a fallback message.
        # Consider if more specific cleanup is needed for non-Textual resources.
        sys.exit(1) # Exit with error code 1 for unexpected exceptions
