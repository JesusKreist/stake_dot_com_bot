#!/usr/bin/env python3
"""
NBA Unders-Only Ticket Generator
Generates tickets focused exclusively on UNDER bets with high confidence.
"""

import json
import os
import random
from collections import defaultdict
from typing import Dict, List, Any


def load_recommendations() -> List[Dict]:
    """Load recommendations from nba_comprehensive_recommendations.json."""
    with open("nba_comprehensive_recommendations.json", "r") as f:
        return json.load(f)


def load_props_data() -> Dict:
    """Load original props data to get game information."""
    with open("nba_all_props.json", "r") as f:
        return json.load(f)


def filter_unders_props(recommendations: List[Dict]) -> List[Dict]:
    """
    Filter for high-confidence UNDER props.

    Criteria:
    - bet_type == "UNDER"
    - score >= 75
    - recent_hits >= 4 (4+/7 recent games)
    """
    unders = []
    for rec in recommendations:
        bet_type = rec.get("bet_type", "")
        score = rec.get("score", 0)
        recent_hits = rec.get("recent_hits", 0)

        if bet_type == "UNDER" and score >= 75 and recent_hits >= 4:
            unders.append(rec)

    return unders


def organize_by_game(
    recommendations: List[Dict], props_data: Dict
) -> Dict[str, List[Dict]]:
    """Organize recommendations by game."""
    # Create mapping of team to game
    team_to_game = {}
    for game_slug, game_data in props_data.items():
        game_name = game_data["game_name"]
        for player_data in game_data["props"]:
            team = player_data.get("team", "")
            team_to_game[team] = {"slug": game_slug, "name": game_name}

    # Organize recommendations by game
    game_recommendations = defaultdict(list)
    for rec in recommendations:
        team = rec.get("team", "")
        if team in team_to_game:
            game_info = team_to_game[team]
            rec["game_slug"] = game_info["slug"]
            rec["game_name"] = game_info["name"]
            game_recommendations[game_info["slug"]].append(rec)

    return dict(game_recommendations)


def select_picks_for_game(
    game_recs: List[Dict],
    num_picks: int,
    ticket_player_stats: set,
    global_used_props: set,
) -> List[Dict]:
    """
    Select diverse picks for a single game.
    Within a ticket, only ONE line per player+stat+bet_type combination is allowed.
    Across all tickets, avoid repeating the same exact prop unless necessary.
    """
    # Sort by score descending
    sorted_recs = sorted(game_recs, key=lambda x: x.get("score", 0), reverse=True)

    selected = []

    # First pass: Try to find unique props not used in any ticket
    for rec in sorted_recs:
        if len(selected) >= num_picks:
            break

        player = rec["player"]
        stat = rec["stat"]
        bet_type = rec["bet_type"]
        line = rec["line"]

        # Create combination keys
        player_stat_bet_key = f"{player}|{stat}|{bet_type}"
        full_prop_key = f"{player}|{stat}|{bet_type}|{line}"

        # Within a single ticket, we can't use the same player+stat+bet_type
        if player_stat_bet_key in ticket_player_stats:
            continue

        # Try to avoid props already used in other tickets
        if full_prop_key in global_used_props:
            continue

        # Add this pick
        selected.append(rec)
        ticket_player_stats.add(player_stat_bet_key)
        global_used_props.add(full_prop_key)

    # Second pass: If we don't have enough picks, allow repeats from other tickets
    if len(selected) < num_picks:
        for rec in sorted_recs:
            if len(selected) >= num_picks:
                break

            player = rec["player"]
            stat = rec["stat"]
            bet_type = rec["bet_type"]
            line = rec["line"]

            player_stat_bet_key = f"{player}|{stat}|{bet_type}"
            full_prop_key = f"{player}|{stat}|{bet_type}|{line}"

            # Skip if already in this ticket
            if player_stat_bet_key in ticket_player_stats:
                continue

            # Allow repeats now
            selected.append(rec)
            ticket_player_stats.add(player_stat_bet_key)
            global_used_props.add(full_prop_key)

    return selected


def generate_unders_tickets(
    num_tickets: int = 3, games_per_ticket: int = 5, picks_per_game: int = 6
) -> List[Dict]:
    """
    Generate unders-only tickets.

    Strategy:
    - Filter for UNDER bets with score >= 75 and recent_hits >= 4
    - 5 games per ticket
    - 6-7 picks per game
    - ~30-35 picks per ticket
    """
    recommendations = load_recommendations()
    props_data = load_props_data()

    # Filter for unders only
    unders_recs = filter_unders_props(recommendations)

    print(f"Found {len(unders_recs)} UNDER props (score >= 75, recent >= 4/7)")

    if not unders_recs:
        print("No UNDER props meet the criteria!")
        return []

    # Organize by game
    game_recs = organize_by_game(unders_recs, props_data)

    print(f"UNDER props spread across {len(game_recs)} games")

    if len(game_recs) < games_per_ticket:
        print(f"Only {len(game_recs)} games available, adjusting...")
        games_per_ticket = len(game_recs)

    # Get list of all games with enough props
    all_games = [(slug, recs) for slug, recs in game_recs.items() if len(recs) >= 3]

    print(f"\nGames with 3+ UNDER props:")
    for game_slug, recs in all_games:
        game_name = recs[0]["game_name"]
        avg_score = sum(r.get("score", 0) for r in recs) / len(recs)
        print(f"  {game_name}: {len(recs)} props (avg score: {avg_score:.1f})")

    if len(all_games) < games_per_ticket:
        print(f"Only {len(all_games)} games with 3+ props, using all available")
        all_games = list(game_recs.items())
        all_games.sort(key=lambda x: len(x[1]), reverse=True)

    tickets = []
    global_used_props = set()

    for ticket_num in range(1, num_tickets + 1):
        if len(all_games) < games_per_ticket:
            print(f"Not enough games for ticket {ticket_num}")
            break

        # Randomly select games for this ticket
        selected_games = random.sample(all_games, min(games_per_ticket, len(all_games)))

        ticket_picks = []
        ticket_player_stats = set()

        # For each game, select 6-7 picks
        for game_slug, recs in selected_games:
            num_picks = random.choice([6, 7])
            game_picks = select_picks_for_game(
                recs, num_picks, ticket_player_stats, global_used_props
            )

            if len(game_picks) < 3:
                print(
                    f"  Ticket {ticket_num}: Only {len(game_picks)} picks for {recs[0]['game_name']}"
                )

            ticket_picks.extend(game_picks)

        # Calculate total odds
        total_odds = 1.0
        for pick in ticket_picks:
            total_odds *= pick["odds"]

        # Calculate average confidence metrics
        avg_score = sum(p.get("score", 0) for p in ticket_picks) / len(ticket_picks) if ticket_picks else 0
        avg_historical = sum(p.get("historical_hit_rate", 0) for p in ticket_picks) / len(ticket_picks) if ticket_picks else 0

        tickets.append(
            {
                "ticket_num": ticket_num,
                "picks": ticket_picks,
                "total_picks": len(ticket_picks),
                "total_odds": round(total_odds, 2),
                "num_games": len(selected_games),
                "selected_games": [recs[0]["game_name"] for _, recs in selected_games],
                "avg_score": round(avg_score, 1),
                "avg_historical": round(avg_historical, 1),
                "ticket_type": "unders",
            }
        )

        print(
            f"\nUnders Ticket {ticket_num}: {len(ticket_picks)} picks, {round(total_odds, 2)}x odds"
        )
        print(f"   Avg Score: {avg_score:.1f} | Avg Historical: {avg_historical:.1f}%")
        print(
            f"   Games: {', '.join([recs[0]['game_name'] for _, recs in selected_games])}"
        )

    return tickets


def save_unders_tickets(tickets: List[Dict]):
    """
    Save tickets to tickets_dir/nba_unders_*/
    """
    for ticket_data in tickets:
        ticket_num = ticket_data["ticket_num"]
        picks = ticket_data["picks"]
        total_odds = ticket_data["total_odds"]

        # Create directory
        ticket_dir = f"tickets_dir/nba_unders_{ticket_num}"
        os.makedirs(ticket_dir, exist_ok=True)

        # Save human-readable ticket
        with open(f"{ticket_dir}/ticket.txt", "w") as f:
            f.write(f"NBA UNDERS-ONLY TICKET #{ticket_num}\n")
            f.write(f"{'='*80}\n")
            f.write(f"Strategy: High-Confidence UNDER Bets Only\n")
            f.write(f"Criteria: Score >= 75 AND Recent >= 4/7\n")
            f.write(f"{'='*80}\n")
            f.write(f"Total Picks: {len(picks)}\n")
            f.write(f"Total Odds: {total_odds}x\n")
            f.write(f"Avg Score: {ticket_data['avg_score']}\n")
            f.write(f"Avg Historical Hit Rate: {ticket_data['avg_historical']}%\n")
            f.write(f"Games: {', '.join(ticket_data['selected_games'])}\n")
            f.write(f"{'='*80}\n")

            # Group by game
            current_game = None
            for pick in picks:
                game = pick.get("game_name", "Unknown")
                if game != current_game:
                    current_game = game
                    f.write(f"\n{current_game}\n")
                    f.write(f"{'-'*80}\n")

                player = pick.get("player", "")
                team = pick.get("team", "")
                stat = pick.get("stat", "")
                bet_type = pick.get("bet_type", "")
                line = pick.get("line", 0)
                odds = pick.get("odds", 0)
                score = pick.get("score", 0)
                base_score = pick.get("base_score", score)
                recent = pick.get("recent_hits", 0)
                historical = pick.get("historical_hit_rate", 0)
                last_7 = pick.get("last_7_values", [])

                # Contextual factors
                home_away = pick.get("home_away", "unknown")
                is_b2b = pick.get("is_b2b", False)
                minutes_trend = pick.get("minutes_trend", "unknown")

                f.write(f"{player} ({team})\n")
                f.write(f"  {stat} {bet_type} {line}\n")
                f.write(f"  Odds: {odds}x | Score: {score} (base: {base_score})\n")
                f.write(f"  Recent: {recent}/7 | Historical: {historical}%\n")

                # Show contextual factors if they affected the score
                context_parts = []
                if home_away != "unknown":
                    context_parts.append(f"{'Home' if home_away == 'home' else 'Away'}")
                if is_b2b:
                    context_parts.append("B2B")
                if minutes_trend in ["up", "down"]:
                    context_parts.append(f"Min {minutes_trend}")
                if context_parts:
                    f.write(f"  Context: {' | '.join(context_parts)}\n")

                f.write(f"  Last 7: {last_7}\n")
                f.write("\n")

        # Save betPrePlacementStore.json format
        outcomes = []
        for pick in picks:
            outcomes.append(
                {
                    "odds": pick["odds"],
                    "isActive": True,
                    "marketId": pick["marketId"],
                    "lineId": pick["lineId"],
                    "swishStatId": pick["swishStatId"],
                    "player": pick["player"],
                    "stat": pick["stat"],
                    "line": pick["line"],
                    "bet_type": pick["bet_type"],
                }
            )

        bet_data = {
            "type": "sports-multi",
            "outcomes": outcomes,
            "totalOdds": total_odds,
            "stake": 0,
            "ticket_type": "unders",
        }

        with open(f"{ticket_dir}/betPrePlacementStore.json", "w") as f:
            json.dump(bet_data, f, indent=2)

        print(f"  Saved to {ticket_dir}/")


def main():
    """Generate unders-only tickets."""
    print("=" * 80)
    print("NBA UNDERS-ONLY TICKET GENERATOR")
    print("=" * 80)
    print("Strategy: Focus on high-confidence UNDER bets")
    print("Criteria: Score >= 75 AND Recent >= 4/7 games")
    print()
    print("Why UNDERS?")
    print("  - Player fatigue on back-to-backs")
    print("  - Tough defensive matchups")
    print("  - Blowouts reducing minutes")
    print("  - Regression to mean")
    print()

    tickets = generate_unders_tickets(num_tickets=3, games_per_ticket=5, picks_per_game=6)

    if tickets:
        print("\n" + "=" * 80)
        print("UNDERS TICKET SUMMARY")
        print("=" * 80)

        for ticket_data in tickets:
            print(f"\nUnders Ticket {ticket_data['ticket_num']}:")
            print(f"  Picks: {ticket_data['total_picks']}")
            print(f"  Games: {ticket_data['num_games']}")
            print(f"  Total Odds: {ticket_data['total_odds']}x")
            print(f"  Avg Score: {ticket_data['avg_score']}")
            print(f"  Avg Historical: {ticket_data['avg_historical']}%")

            # Show game breakdown
            game_counts = {}
            for pick in ticket_data["picks"]:
                game = pick.get("game_name", "Unknown")
                game_counts[game] = game_counts.get(game, 0) + 1

            for game, count in game_counts.items():
                print(f"    {game}: {count} picks")

        # Save tickets
        print("\n" + "=" * 80)
        print("SAVING UNDERS TICKETS")
        print("=" * 80)
        save_unders_tickets(tickets)

        print(f"\nGenerated {len(tickets)} unders-only tickets")
    else:
        print("\nNo unders tickets generated - not enough qualifying props")


if __name__ == "__main__":
    main()
