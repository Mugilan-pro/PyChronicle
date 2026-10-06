"""PyChronicle — Complete 4-Week Terminal UI Demo.

Launches the interactive time-travel debugging dashboard with:
- Week 1: SQLite trace storage backend
- Week 2: Dual-pane layout, code viewer, and timeline scrubber
- Week 3: Time-scrubbing with real-time MOD / NEW variable deltas
- Week 4: Watch Variables panel with click-to-jump historical time-travel

Usage:
    python demo_all_weeks.py
"""

from pychronicle.ui.app import PyChronicleApp


def main() -> None:
    print("=" * 64)
    print("  PyChronicle — AST-Powered Time-Travel Debugger (All 4 Weeks)")
    print("=" * 64)
    print("Controls:")
    print("  [Left / h]   Step backward 1 event")
    print("  [Right / l]  Step forward 1 event")
    print("  [Home / g]   Jump to start (Step 1)")
    print("  [End / G]    Jump to end")
    print("  [Space / p]  Toggle Autoplay")
    print("  [w]          Add Watch Variable")
    print("  [f]          Focus variable search filter")
    print("  [?]          Help modal")
    print("  [q]          Quit")
    print("-" * 64)
    print("Launching dashboard (press 'q' inside TUI to quit)...")

    app = PyChronicleApp()
    app.run()


if __name__ == "__main__":
    main()
