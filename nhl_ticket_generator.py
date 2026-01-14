#!/usr/bin/env python3
"""
NHL Ticket Generator
Generates optimal parlay tickets from NHL recommendations
Max 9 games per ticket, max 3 players per game
"""

import json
import random
from typing import Dict, List
from collections import defaultdict


class NHLTicketGenerator:
    def __init__(self, recommendations_file: str = "nhl_recommendations.json"):
        with open(recommendations_file, 'r') as f:
            self.recommendations = json.load(f)

    def get_all_strong_picks(self, min_score: float = 70, min_hit_rate: float = 65, min_recent_hits: int = 4) -> List[Dict]:
        """Get all strong picks that meet the criteria."""
        strong_picks = []

        for game_slug, game_data in self.recommendations.items():
            for player in game_data['players']:
                for prop in player['props']:
                    if (prop['score'] >= min_score and 
                        prop['hit_rate'] >= min_hit_rate and 
                        prop['recent_hits'] >= min_recent_hits):
                        
                        strong_picks.append({
                            'game_slug': game_slug,
                            'game_name': game_data['game_name'],
                            'player_name': player['player_name'],
                            'team': player['team'],
                            'stat_type': prop['stat_type'],
                            'line': prop['line'],
                            'bet_type': prop['bet_type'],
                            'odds': prop['odds'],
                            'score': prop['score'],
                            'hit_rate': prop['hit_rate'],
                            'recent_hits': prop['recent_hits'],
                            'last_5': prop['last_5_values'],
                            'line_id': prop['line_id'],
                            'market_id': prop['market_id']
                        })

        return strong_picks

    def group_picks_by_game(self, picks: List[Dict]) -> Dict[str, List[Dict]]:
        """Group picks by game."""
        grouped = defaultdict(list)
        for pick in picks:
            grouped[pick['game_slug']].append(pick)
        
        # Sort each game's picks by score
        for game_slug in grouped:
            grouped[game_slug].sort(key=lambda x: x['score'], reverse=True)
        
        return dict(grouped)

    def generate_ticket(self, picks_by_game: Dict[str, List[Dict]], 
                       num_games: int, max_players_per_game: int = 3) -> Dict:
        """Generate a single ticket."""
        # Select games with most strong picks
        game_pick_counts = [(slug, len(picks)) for slug, picks in picks_by_game.items()]
        game_pick_counts.sort(key=lambda x: x[1], reverse=True)
        
        # Select top N games
        selected_games = [slug for slug, _ in game_pick_counts[:num_games]]
        
        ticket_picks = []
        total_odds = 1.0

        for game_slug in selected_games:
            game_picks = picks_by_game[game_slug][:max_players_per_game]
            
            for pick in game_picks:
                ticket_picks.append(pick)
                total_odds *= pick['odds']

        return {
            'picks': ticket_picks,
            'num_picks': len(ticket_picks),
            'num_games': num_games,
            'combined_odds': round(total_odds, 2)
        }

    def save_ticket(self, ticket_num: int, ticket: Dict):
        """Save ticket to files."""
        import os

        ticket_dir = f"tickets_dir/nhl_ticket_{ticket_num}"
        os.makedirs(ticket_dir, exist_ok=True)

        # Save human-readable ticket
        ticket_file = f"{ticket_dir}/ticket.txt"
        with open(ticket_file, 'w') as f:
            f.write("="*80 + "\n")
            f.write(f"  NHL TICKET {ticket_num} - {ticket['num_games']} Games\n")
            f.write("="*80 + "\n")
            f.write(f"  Total Picks: {ticket['num_picks']} | Combined Odds: {ticket['combined_odds']}x\n")
            f.write("="*80 + "\n\n")

            # Group by game
            picks_by_game = defaultdict(list)
            for pick in ticket['picks']:
                picks_by_game[pick['game_name']].append(pick)

            for idx, (game_name, picks) in enumerate(picks_by_game.items(), 1):
                f.write(f"Game {idx}: {game_name}\n")
                f.write("-"*80 + "\n")
                
                for pick_idx, pick in enumerate(picks, 1):
                    f.write(f"  {pick_idx}. {pick['player_name']} ({pick['team']})\n")
                    f.write(f"     {pick['stat_type'].upper()} {pick['bet_type']} {pick['line']}\n")
                    f.write(f"     Score: {pick['score']} | Odds: {pick['odds']:.2f}x | Hit Rate: {pick['hit_rate']}% (Recent: {pick['recent_hits']}/5)\n")
                    f.write(f"     Last 5 games: {pick['last_5']}\n\n")

        # Save betPrePlacementStore.json format
        bet_store = {
            "outcomes": []
        }

        for pick in ticket['picks']:
            bet_store["outcomes"].append({
                "lineId": pick['line_id'],
                "marketId": pick['market_id'],
                "odds": pick['odds']
            })

        bet_store_file = f"{ticket_dir}/betPrePlacementStore.json"
        with open(bet_store_file, 'w') as f:
            json.dump(bet_store, f, indent=2)

        print(f"  ✓ Saved to {ticket_dir}/")

    def generate_multiple_tickets(self, num_tickets: int = 3):
        """Generate multiple tickets with different game combinations."""
        print(f"\n{'='*80}")
        print("NHL TICKET GENERATOR")
        print(f"{'='*80}\n")

        # Get strong picks
        strong_picks = self.get_all_strong_picks()
        print(f"Found {len(strong_picks)} STRONG picks (score >= 70, hit rate >= 65%, recent >= 4/5)\n")

        if not strong_picks:
            print("❌ No picks meet the criteria!")
            return

        picks_by_game = self.group_picks_by_game(strong_picks)
        available_games = len(picks_by_game)

        print(f"Games with strong picks: {available_games}\n")

        if available_games == 0:
            print("❌ No games have strong picks!")
            return

        print(f"{'='*80}")
        print(f"Generating {num_tickets} Tickets (Max 9 games, Max 3 players/game)")
        print(f"{'='*80}\n")

        for i in range(1, num_tickets + 1):
            # Use different game counts for variety
            if available_games >= 9:
                num_games = min(9, available_games)
            elif available_games >= 6:
                num_games = min(7 + (i % 2), available_games)  # Alternate 7-8
            else:
                num_games = available_games

            ticket = self.generate_ticket(picks_by_game, num_games, max_players_per_game=3)
            
            # Get unique games
            unique_games = set(pick['game_name'] for pick in ticket['picks'])
            
            print(f"Ticket {i}:")
            print(f"  Games: {len(unique_games)} ({', '.join(sorted(unique_games)[:3])}...)")
            print(f"  Total picks: {ticket['num_picks']}")
            print(f"  Combined odds: {ticket['combined_odds']}x\n")

            self.save_ticket(i, ticket)

            # Shuffle picks for next ticket to create variety
            for game_picks in picks_by_game.values():
                random.shuffle(game_picks)

        print(f"\n{'='*80}")
        print(f"✅ All {num_tickets} tickets generated successfully!")
        print(f"{'='*80}")


def main():
    generator = NHLTicketGenerator()
    generator.generate_multiple_tickets(num_tickets=3)


if __name__ == "__main__":
    main()
