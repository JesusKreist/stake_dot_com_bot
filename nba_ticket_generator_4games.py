#!/usr/bin/env python3
"""
NBA Ticket Generator - 5 Tickets (4 Random Games Each)
Generates 5 tickets with 4 random games per ticket, 6-7 props per game
"""

import json
import random
from typing import List, Dict, Any
from collections import defaultdict


def load_recommendations() -> List[Dict]:
    """Load strong recommendations from analysis."""
    with open("nba_comprehensive_recommendations.json", "r") as f:
        return json.load(f)


def load_props_data() -> Dict:
    """Load original props data to get game information."""
    with open("nba_all_props.json", "r") as f:
        return json.load(f)


def organize_by_game(recommendations: List[Dict], props_data: Dict) -> Dict[str, List[Dict]]:
    """Organize recommendations by game."""
    # Create mapping of team to game
    team_to_game = {}
    for game_slug, game_data in props_data.items():
        game_name = game_data["game_name"]
        for player_data in game_data["props"]:
            team = player_data.get("team", "")
            team_to_game[team] = {
                "slug": game_slug,
                "name": game_name
            }
    
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


def select_picks_for_game(game_recs: List[Dict], num_picks: int, ticket_player_stats: set, global_used_props: set) -> List[Dict]:
    """
    Select diverse picks for a single game.
    Within a ticket, only ONE line per player+stat+bet_type combination is allowed.
    Across all tickets, avoid repeating the same exact prop unless necessary.
    """
    # Sort by score descending
    sorted_recs = sorted(game_recs, key=lambda x: x["score"], reverse=True)
    
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


def generate_tickets(num_tickets: int = 5, games_per_ticket: int = 4, picks_per_game: int = 6) -> List[Dict]:
    """
    Generate diverse tickets.
    Each ticket has 4 random games with 6-7 picks each.
    """
    recommendations = load_recommendations()
    props_data = load_props_data()
    
    print(f"Loaded {len(recommendations)} strong recommendations")
    
    # Organize by game
    game_recs = organize_by_game(recommendations, props_data)
    
    print(f"Found recommendations for {len(game_recs)} games")
    
    if len(game_recs) < games_per_ticket:
        print(f"⚠️  Only {len(game_recs)} games available, need {games_per_ticket}")
        games_per_ticket = len(game_recs)
    
    # Get list of all games
    all_games = list(game_recs.items())
    
    print(f"\nAvailable games:")
    for game_slug, recs in all_games:
        game_name = recs[0]["game_name"]
        print(f"  {game_name}: {len(recs)} strong props")
    
    tickets = []
    global_used_props = set()  # Track props used across ALL tickets
    
    for ticket_num in range(1, num_tickets + 1):
        # Randomly select 4 games for this ticket
        selected_games = random.sample(all_games, games_per_ticket)
        
        ticket_picks = []
        ticket_player_stats = set()
        
        # For each game, select 6-7 picks (randomly choose between 6 and 7)
        for game_slug, recs in selected_games:
            num_picks = random.choice([6, 7])
            game_picks = select_picks_for_game(recs, num_picks, ticket_player_stats, global_used_props)
            
            if len(game_picks) < num_picks:
                print(f"  ⚠️  Ticket {ticket_num}: Only {len(game_picks)} picks available for {recs[0]['game_name']}")
            
            ticket_picks.extend(game_picks)
        
        # Calculate total odds
        total_odds = 1.0
        for pick in ticket_picks:
            total_odds *= pick["odds"]
        
        tickets.append({
            "ticket_num": ticket_num,
            "picks": ticket_picks,
            "total_picks": len(ticket_picks),
            "total_odds": round(total_odds, 2),
            "num_games": len(selected_games),
            "selected_games": [recs[0]["game_name"] for _, recs in selected_games]
        })
        
        print(f"\n✅ Ticket {ticket_num}: {len(ticket_picks)} picks, {round(total_odds, 2)}x odds")
        print(f"   Games: {', '.join([recs[0]['game_name'] for _, recs in selected_games])}")
    
    return tickets


def save_tickets(tickets: List[Dict]):
    """Save tickets to files."""
    for ticket_data in tickets:
        ticket_num = ticket_data["ticket_num"]
        picks = ticket_data["picks"]
        total_odds = ticket_data["total_odds"]
        
        # Create directory
        import os
        ticket_dir = f"tickets_dir/nba_ticket_{ticket_num}"
        os.makedirs(ticket_dir, exist_ok=True)
        
        # Save human-readable ticket
        with open(f"{ticket_dir}/ticket.txt", "w") as f:
            f.write(f"NBA TICKET #{ticket_num}\n")
            f.write(f"{'='*80}\n")
            f.write(f"Total Picks: {len(picks)}\n")
            f.write(f"Total Odds: {total_odds}x\n")
            f.write(f"Games: {', '.join(ticket_data['selected_games'])}\n")
            f.write(f"{'='*80}\n\n")
            
            # Group by game
            current_game = None
            for pick in picks:
                if pick["game_name"] != current_game:
                    current_game = pick["game_name"]
                    f.write(f"\n{current_game}\n")
                    f.write(f"{'-'*80}\n")
                
                f.write(f"{pick['player']} ({pick['team']})\n")
                f.write(f"  {pick['stat']} {pick['bet_type']} {pick['line']}\n")
                f.write(f"  Odds: {pick['odds']}x | Score: {pick['score']}\n")
                f.write(f"  Recent: {pick['recent_hits']}/7 | Historical: {pick['historical_hit_rate']}%\n")
                f.write(f"  Last 7: {pick['last_7_values']}\n")
                f.write(f"\n")
        
        # Save betPrePlacementStore.json format
        outcomes = []
        for pick in picks:
            outcomes.append({
                "odds": pick["odds"],
                "isActive": True,
                "marketId": pick["marketId"],
                "lineId": pick["lineId"],
                "swishStatId": pick["swishStatId"],
                "player": pick["player"],
                "stat": pick["stat"],
                "line": pick["line"],
                "bet_type": pick["bet_type"]
            })
        
        bet_data = {
            "type": "sports-multi",
            "outcomes": outcomes,
            "totalOdds": total_odds,
            "stake": 0
        }
        
        with open(f"{ticket_dir}/betPrePlacementStore.json", "w") as f:
            json.dump(bet_data, f, indent=2)
        
        print(f"  Saved to {ticket_dir}/")


def main():
    """Generate 5 tickets."""
    print("="*80)
    print("NBA TICKET GENERATOR - 5 TICKETS (4 RANDOM GAMES EACH)")
    print("="*80)
    print("Generating 5 tickets with 4 random games per ticket")
    print("6-7 props per game\n")
    
    tickets = generate_tickets(num_tickets=5, games_per_ticket=4, picks_per_game=6)
    
    print("\n" + "="*80)
    print("TICKET SUMMARY")
    print("="*80)
    
    for ticket_data in tickets:
        print(f"\nTicket {ticket_data['ticket_num']}:")
        print(f"  Picks: {ticket_data['total_picks']}")
        print(f"  Games: {ticket_data['num_games']}")
        print(f"  Total Odds: {ticket_data['total_odds']}x")
        
        # Show game breakdown
        game_counts = {}
        for pick in ticket_data['picks']:
            game = pick['game_name']
            game_counts[game] = game_counts.get(game, 0) + 1
        
        for game, count in game_counts.items():
            print(f"    {game}: {count} picks")
    
    # Save tickets
    print("\n" + "="*80)
    print("SAVING TICKETS")
    print("="*80)
    save_tickets(tickets)
    
    print("\n✅ All tickets generated successfully!")


if __name__ == "__main__":
    main()
