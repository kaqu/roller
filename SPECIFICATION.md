# macOS Multi-Dice Terminal App Specification

## 1. System Overview & Scope

**Implementation Boundaries:** Single-file Python 3.12+ script using Textual framework for rich terminal UI with 1-8 dice support, dice locking, sum calculation, and frequency counting. Distributed via uv dependency management.

**Platform Requirements:**
- macOS 12.0+, terminal 80×30 minimum, Unicode emoji support
- Python 3.12+ via uv, Textual 3.3+, Rich 13.0+
- No external dependencies, offline operation, single executable file

**Technical Scope:** Independent die animations (0.3-0.6s random duration), arrow key navigation, space bar locking, cryptographic randomness, responsive grid layouts (1×1 to 4×2), real-time statistics.

**Excluded:** Network features, persistence, sound, multiple die types, themes.

## 2. Functional Implementation Requirements

### 2.1 Multi-Dice Rolling with Locking

```pseudocode
ASYNC FUNCTION rollUnlockedDice():
    DISABLE controls
    SET unlockedIndices = [i for i in range(diceCount) if i not in lockedDice]
    
    IF len(unlockedIndices) == 0:
        NOTIFY "All dice locked"
        RETURN
    
    SET tasks = [asyncio.create_task(animateSingleDie(i, randomFloat(0.3, 0.6))) 
                 for i in unlockedIndices]
    SET results = AWAIT asyncio.gather(*tasks)
    
    UPDATE currentResults[unlockedIndices] = results
    UPDATE statistics and display
    ENABLE controls
END

ASYNC FUNCTION animateSingleDie(index, duration):
    SET frames = int(duration / 0.05)  // 20fps
    FOR frame in range(frames):
        UPDATE die display with random emoji
        AWAIT sleep(0.05)
    SET final = secrets.randbelow(6) + 1
    UPDATE die display with final emoji
    RETURN final
END
```

### 2.2 Dice Selection and Locking

```pseudocode
PROPERTY selectedDieIndex = 0
PROPERTY lockedDice = set()

ASYNC FUNCTION navigateDiceSelection(direction):
    SET cols = getGridColumns()
    SWITCH direction:
        CASE "up": selectedDieIndex = max(0, selectedDieIndex - cols)
        CASE "down": selectedDieIndex = min(diceCount-1, selectedDieIndex + cols)
        CASE "left": selectedDieIndex = max(0, selectedDieIndex - 1)
        CASE "right": selectedDieIndex = min(diceCount-1, selectedDieIndex + 1)
    UPDATE visual selection
END

ASYNC FUNCTION toggleDieLock():
    IF selectedDieIndex in lockedDice:
        lockedDice.remove(selectedDieIndex)
    ELSE:
        lockedDice.add(selectedDieIndex)
    UPDATE visual lock state
END
```

### 2.3 Statistics and Display

```pseudocode
FUNCTION calculateStats(results):
    SET sum = sum(results)
    SET freq = {i: results.count(i) for i in range(1,7) if i in results}
    SET display = " | ".join([f"{count}×{emoji[val-1]}" for val, count in freq.items()])
    RETURN sum, display

FUNCTION formatGrid(diceCount):
    RETURN {1:(1,1), 2:(2,1), 3:(3,1), 4:(2,2), 5:(3,2), 6:(3,2), 7:(4,2), 8:(4,2)}[diceCount]
```

## 3. System Interface Specifications

### 3.1 UI Layout and Controls

**Key Bindings:**
- `r/enter`: Roll unlocked dice
- `↑↓←→`: Navigate dice selection  
- `space`: Lock/unlock selected die
- `+/-`: Add/remove dice
- `1-8`: Set dice count
- `ctrl+l/u`: Lock/unlock all
- `q`: Quit

**Widget Structure:**
```
Header (status) → DiceControls (±/count) → DiceGrid (emoji+states) → 
Stats (sum/freq) → ActionButtons (roll/reset) → Footer (help)
```

**CSS Classes:**
- `.die-emoji.selected`: Heavy border + highlight
- `.die-emoji.locked`: Warning colors + 🔒 overlay
- `.rolling`: Pulse animation (not applied to locked dice)

### 3.2 uv Script Integration

```python
#!/usr/bin/env -S uv run
# /// script
# dependencies = ["textual>=3.3,<4.0.0", "rich>=13.0.0,<14.0.0"]
# requires-python = ">=3.12"
# ///
```

**File Structure:** Single 40-55KB Python file with embedded CSS, complete error handling, terminal capability detection, fallback strategies.

## 4. Performance & Quality Requirements

**Performance Targets:**
- Independent die animations: 20fps per die, 0.3-0.6s random duration
- 8-dice concurrent animation: <20% CPU, <50MB memory
- Input response: <100ms, startup: <3s
- Statistics calculation: <25ms for any dice count

**Reliability:**
- Cryptographic randomness (secrets module) per die
- Statistical independence validation (p-value >0.05)
- Graceful error recovery, proper async cleanup
- Terminal resize handling, emoji fallback support

**Quality Standards:**
- 80%+ test coverage, type hints, docstrings
- Zero linting errors, comprehensive acceptance criteria
- Cross-dice correlation testing, performance profiling

## 5. Technical Implementation Guide

### 5.1 Core Architecture

```pseudocode
CLASS DiceRollerApp(App):
    PROPERTY diceCount=1, selectedDieIndex=0, lockedDice=set(), currentResults=[]
    
    BINDINGS = [("r", "roll"), ("space", "toggle_lock"), ("up/down/left/right", "navigate"), ...]
    
    FUNCTION compose(): RETURN header + controls + grid + stats + buttons + footer
    
    ASYNC FUNCTION rollUnlockedDice(), navigateDiceSelection(), toggleDieLock()
    ASYNC FUNCTION addDie(), removeDie(), resetDice()

CLASS DiceAnimationController:
    ASYNC FUNCTION animate_all_dice(unlocked_indices) -> results
    ASYNC FUNCTION animate_single_die(index, duration) -> result
    FUNCTION generate_random_duration() -> float  // 0.3-0.6s
```

### 5.2 Key Algorithms

**Random Duration Generation:**
```pseudocode
FUNCTION randomFloat(min, max):
    bytes = secrets.token_bytes(4)
    normalized = int.from_bytes(bytes, 'big') / (2**32 - 1)
    RETURN min + normalized * (max - min)
```

**Grid Navigation:**
```pseudocode
FUNCTION calculateGridNavigation(current, direction, diceCount):
    cols = {1:1, 2:2, 3:3, 4:2, 5:3, 6:3, 7:4, 8:4}[diceCount]
    SWITCH direction:
        up: RETURN max(0, current - cols)
        down: RETURN min(diceCount-1, current + cols)
        left: RETURN max(0, current - 1)  
        right: RETURN min(diceCount-1, current + 1)
```

## 6. Integration Contracts & Protocols

### 6.1 Error Handling

```pseudocode
TRY:
    MAIN application logic
EXCEPT KeyboardInterrupt:
    CLEANUP animations, RESTORE terminal, EXIT 0
EXCEPT ImportError:
    DISPLAY "Run: uv cache clean && uv run multi_dice_roller.py", EXIT 1
EXCEPT Exception:
    LOG error, CLEANUP state, EXIT 1
```

### 6.2 Testing Protocols

**Unit Tests:** Random distribution, animation timing, lock state management, grid calculations, statistics accuracy

**Integration Tests:** Complete roll cycles, dice count changes, lock/unlock operations, keyboard navigation, terminal compatibility

**Performance Tests:** 8-dice animation, memory leak detection, input response timing, statistical independence validation

---

## Implementation Readiness: ✅ COMPLETE

**Ready-to-Code Specification** providing:
- Complete algorithms in pseudocode translatable to any language
- Detailed class structures with method signatures
- Comprehensive UI specifications with CSS styling
- Independent animation system with proper async handling
- Statistical validation and error recovery procedures
- Terminal compatibility with graceful fallbacks

**Estimated Implementation:** 2-3 days for experienced Python/Textual developer

**File Output:** Single executable Python script (40-55KB) with embedded dependencies via uv, comprehensive error handling, and professional UX including dice locking, navigation, statistics, and smooth independent animations.
