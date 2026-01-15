#!/usr/bin/env python3
"""
Run NBA Analysis Pipeline
Quick script to run all NBA analysis steps
"""

import subprocess
import sys
import os


def run_command(cmd, description):
    """Run a command and show output."""
    print(f"\n{'='*60}")
    print(f"🏀 {description}")
    print(f"{'='*60}\n")

    result = subprocess.run(
        cmd, shell=True, cwd=os.path.dirname(os.path.abspath(__file__))
    )

    if result.returncode != 0:
        print(f"\n❌ Error running: {description}")
        return False
    return True


def main():
    # Get Python executable from venv
    venv_python = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "venv", "bin", "python"
    )

    if not os.path.exists(venv_python):
        print(
            "❌ Virtual environment not found. Run: python -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
        )
        sys.exit(1)

    print("🏀 NBA Props Analysis Pipeline")
    print("=" * 60)

    # Step 1: Scrape props
    if not run_command(
        f"{venv_python} stake_nba_scraper.py",
        "Scraping today's NBA props from Stake.com",
    ):
        sys.exit(1)

    # Step 2: Analyze
    if not run_command(
        f"{venv_python} nba_comprehensive_analyzer.py",
        "Analyzing props against historical data (7-game lookback)",
    ):
        sys.exit(1)

    # Step 3: Generate tickets
    if not run_command(
        f"{venv_python} nba_ticket_generator_4games.py", "Generating 5 diverse tickets"
    ):
        sys.exit(1)

    # Step 4: Positional analysis
    if not run_command(
        f"{venv_python} nba_positional_analyzer.py",
        "Filtering for positional plays",
    ):
        print("Warning: Positional analysis failed, skipping positional tickets")
    else:
        # Step 5: Generate positional tickets
        run_command(
            f"{venv_python} nba_positional_ticket_generator.py",
            "Generating positional plays tickets",
        )

    # Step 6: Generate unders-only tickets
    run_command(
        f"{venv_python} nba_unders_ticket_generator.py",
        "Generating unders-only tickets",
    )

    print("\n" + "=" * 60)
    print("✅ All done! Check tickets_dir/ for your tickets")
    print("=" * 60)


if __name__ == "__main__":
    main()
