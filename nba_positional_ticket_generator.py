#!/usr/bin/env python3
"""
NBA Positional Plays Ticket Generator
Generates tickets based on position-aligned prop bets.
"""

import json
import os
import random
from collections import defaultdict
from typing import Dict, List, Any


def load_positional_recommendations() -> Dict:
    """Load nba_positional_recommendations.json."""
    with open("nba_positional_recommendations.json", "r") as f:
        return json.load(f)


def load_props_data() -> Dict:
    """Load original props data to get game information."""
    with open("nba_all_props.json", "r") as f:
        return json.load(f)


def organize_by_game(
    positional_props: List[Dict], props_data: Dict
) -> Dict[str, List[Dict]]:
    """Organize positional props by game."""
    # Create mapping of team to game
    team_to_game = {}
    for game_slug, game_data in props_data.items():
        game_name = game_data["game_name"]
        for player_data in game_data["props"]:
            team = player_data.get("team", "")
            team_to_game[team] = {"slug": game_slug, "name": game_name}

    # Organize props by game
    game_props = defaultdict(list)
    for prop in positional_props:
        team = prop.get("team", "")
        if team in team_to_game:
            game_info = team_to_game[team]
            prop["game_slug"] = game_info["slug"]
            prop["game_name"] = game_info["name"]
            game_props[game_info["slug"]].append(prop)

    return dict(game_props)


def select_positional_picks(
    game_recs: List[Dict],
    num_picks: int,
    ticket_player_stats: set,
    global_used_props: set,
) -> List[Dict]:
    """
    Select picks with positional diversity.
    Prioritizes props from positions with clearer patterns (C > PG > PF > SG).
    """
    # Sort by position priority first, then by positional score
    sorted_recs = sorted(
        game_recs,
        key=lambda x: (x.get("position_priority", 5), -x.get("positional_score", 0)),
    )

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


def generate_positional_tickets(
    num_tickets: int = 3, games_per_ticket: int = 4, picks_per_game: int = 5
) -> List[Dict]:
    """
    Generate positional plays tickets.

    Strategy:
    - Prioritize C and PG props (clearest patterns)
    - Include SG and PF to fill out tickets
    - 4 games per ticket, 5-6 picks per game
    - ~20-24 picks per ticket
    """
    data = load_positional_recommendations()
    props_data = load_props_data()

    positional_props = data.get("positional_props", [])

    if not positional_props:
        print("No positional props available!")
        return []

    print(f"Loaded {len(positional_props)} positional props")

    # Organize by game
    game_props = organize_by_game(positional_props, props_data)

    print(f"Found props for {len(game_props)} games")

    if len(game_props) < games_per_ticket:
        print(f"Only {len(game_props)} games available, adjusting...")
        games_per_ticket = len(game_props)

    # Get list of all games with enough props
    all_games = [(slug, props) for slug, props in game_props.items() if len(props) >= 3]

    print(f"\nGames with 3+ positional props:")
    for game_slug, props in all_games:
        game_name = props[0]["game_name"]
        # Count by position
        pos_counts = {}
        for p in props:
            pos = p.get("position", "?")
            pos_counts[pos] = pos_counts.get(pos, 0) + 1
        pos_str = ", ".join(f"{k}:{v}" for k, v in sorted(pos_counts.items()))
        print(f"  {game_name}: {len(props)} props ({pos_str})")

    if len(all_games) < games_per_ticket:
        print(f"Only {len(all_games)} games with 3+ props, using all available")
        all_games = list(game_props.items())
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

        # For each game, select 5-6 picks (randomly choose)
        for game_slug, props in selected_games:
            num_picks = random.choice([5, 6])
            game_picks = select_positional_picks(
                props, num_picks, ticket_player_stats, global_used_props
            )

            if len(game_picks) < 3:
                print(
                    f"  Ticket {ticket_num}: Only {len(game_picks)} picks for {props[0]['game_name']}"
                )

            ticket_picks.extend(game_picks)

        # Calculate total odds
        total_odds = 1.0
        for pick in ticket_picks:
            total_odds *= pick["odds"]

        # Count by position
        position_breakdown = {}
        for pick in ticket_picks:
            pos = pick.get("position", "?")
            position_breakdown[pos] = position_breakdown.get(pos, 0) + 1

        tickets.append(
            {
                "ticket_num": ticket_num,
                "picks": ticket_picks,
                "total_picks": len(ticket_picks),
                "total_odds": round(total_odds, 2),
                "num_games": len(selected_games),
                "selected_games": [props[0]["game_name"] for _, props in selected_games],
                "position_breakdown": position_breakdown,
                "ticket_type": "positional",
            }
        )

        print(
            f"\nPositional Ticket {ticket_num}: {len(ticket_picks)} picks, {round(total_odds, 2)}x odds"
        )
        print(f"   Positions: {position_breakdown}")
        print(
            f"   Games: {', '.join([props[0]['game_name'] for _, props in selected_games])}"
        )

    return tickets


def save_positional_tickets(tickets: List[Dict]):
    """
    Save tickets to tickets_dir/nba_positional_*/
    Format matches existing ticket structure with position annotations.
    """
    for ticket_data in tickets:
        ticket_num = ticket_data["ticket_num"]
        picks = ticket_data["picks"]
        total_odds = ticket_data["total_odds"]
        position_breakdown = ticket_data["position_breakdown"]

        # Create directory
        ticket_dir = f"tickets_dir/nba_positional_{ticket_num}"
        os.makedirs(ticket_dir, exist_ok=True)

        # Save human-readable ticket
        with open(f"{ticket_dir}/ticket.txt", "w") as f:
            f.write(f"NBA POSITIONAL PLAYS TICKET #{ticket_num}\n")
            f.write(f"{'='*80}\n")
            f.write(f"Strategy: Position-Based Prop Selection\n")
            f.write(f"{'='*80}\n")
            f.write(f"Total Picks: {len(picks)}\n")
            f.write(f"Total Odds: {total_odds}x\n")
            f.write(f"Games: {', '.join(ticket_data['selected_games'])}\n")
            f.write(f"{'='*80}\n\n")

            # Position breakdown
            f.write("POSITIONAL BREAKDOWN:\n")
            for pos in ["C", "PG", "PF", "SG"]:
                count = position_breakdown.get(pos, 0)
                if count > 0:
                    f.write(f"  {pos}: {count} picks\n")
            f.write("\n")
            f.write(f"{'='*80}\n")

            # Group by game
            current_game = None
            for pick in picks:
                game = pick.get("game_name", "Unknown")
                if game != current_game:
                    current_game = game
                    f.write(f"\n{current_game}\n")
                    f.write(f"{'-'*80}\n")

                position = pick.get("position", "?")
                player = pick.get("player", "")
                team = pick.get("team", "")
                stat = pick.get("stat", "")
                bet_type = pick.get("bet_type", "")
                line = pick.get("line", 0)
                odds = pick.get("odds", 0)
                score = pick.get("positional_score", pick.get("score", 0))
                recent = pick.get("recent_hits", 0)
                historical = pick.get("historical_hit_rate", 0)
                rule = pick.get("positional_rule", "")
                last_7 = pick.get("last_7_values", [])

                f.write(f"[{position}] {player} ({team})\n")
                f.write(f"  {stat} {bet_type} {line}\n")
                f.write(f"  Odds: {odds}x | Score: {score}\n")
                f.write(f"  Recent: {recent}/7 | Historical: {historical}%\n")
                f.write(f"  Rule: {rule}\n")
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
                    "position": pick.get("position", ""),
                    "positional_score": pick.get("positional_score", 0),
                }
            )

        bet_data = {
            "type": "sports-multi",
            "outcomes": outcomes,
            "totalOdds": total_odds,
            "stake": 0,
            "ticket_type": "positional",
        }

        with open(f"{ticket_dir}/betPrePlacementStore.json", "w") as f:
            json.dump(bet_data, f, indent=2)

        print(f"  Saved to {ticket_dir}/")


def main():
    """Generate positional tickets."""
    print("=" * 80)
    print("NBA POSITIONAL PLAYS TICKET GENERATOR")
    print("=" * 80)
    print("Strategy: Position-based prop selection")
    print("  - Centers: Rebounds OVER, Assists/3PA/Steals UNDER, Blocks OVER")
    print("  - Point Guards: Assists/Steals OVER, Rebounds/Blocks UNDER")
    print("  - Shooting Guards: FGA/3PA OVER, Assists/Rebounds UNDER")
    print("  - Power Forwards: Rebounds/Blocks OVER, Assists UNDER")
    print()

    tickets = generate_positional_tickets(num_tickets=3, games_per_ticket=4, picks_per_game=5)

    if tickets:
        print("\n" + "=" * 80)
        print("POSITIONAL TICKET SUMMARY")
        print("=" * 80)

        for ticket_data in tickets:
            print(f"\nPositional Ticket {ticket_data['ticket_num']}:")
            print(f"  Picks: {ticket_data['total_picks']}")
            print(f"  Games: {ticket_data['num_games']}")
            print(f"  Total Odds: {ticket_data['total_odds']}x")
            print(f"  Position Breakdown: {ticket_data['position_breakdown']}")

            # Show game breakdown
            game_counts = {}
            for pick in ticket_data["picks"]:
                game = pick.get("game_name", "Unknown")
                game_counts[game] = game_counts.get(game, 0) + 1

            for game, count in game_counts.items():
                print(f"    {game}: {count} picks")

        # Save tickets
        print("\n" + "=" * 80)
        print("SAVING POSITIONAL TICKETS")
        print("=" * 80)
        save_positional_tickets(tickets)

        print(f"\nGenerated {len(tickets)} positional tickets")
    else:
        print("\nNo positional tickets generated - check if positional props are available")


if __name__ == "__main__":
    main()
