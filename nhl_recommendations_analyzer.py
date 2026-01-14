#!/usr/bin/env python3
"""
NHL Recommendations Analyzer
Combines scraped props from Stake.com with historical NHL stats
Focuses on 0.5 and 1.5 lines for points, goals, assists, and shots
"""

import json
import requests
from typing import Dict, List, Optional
import time

NHL_API_BASE = "https://api-web.nhle.com/v1"
CURRENT_SEASON = "20252026"


class NHLRecommendationsAnalyzer:
    def __init__(self, props_file: str = "nhl_props.json"):
        self.props_data = self.load_props(props_file)
        self.session = requests.Session()
        self.player_cache = {}

    def load_props(self, props_file: str) -> Dict:
        """Load scraped props from JSON file."""
        with open(props_file, 'r') as f:
            return json.load(f)

    def get_player_id_from_roster(self, player_name: str, team_name: str) -> Optional[int]:
        """Get player ID from team roster."""
        # Map full team names to abbreviations
        team_mapping = {
            "New York Rangers": "NYR",
            "Boston Bruins": "BOS",
            "Calgary Flames": "CGY",
            "Pittsburgh Penguins": "PIT",
            "Columbus Blue Jackets": "CBJ",
            "Colorado Avalanche": "COL",
            "Dallas Stars": "DAL",
            "San Jose Sharks": "SJS",
            "Carolina Hurricanes": "CAR",
            "Seattle Kraken": "SEA",
            "Philadelphia Flyers": "PHI",
            "Tampa Bay Lightning": "TBL",
            "Montreal Canadiens": "MTL",
            "Detroit Red Wings": "DET",
            "Toronto Maple Leafs": "TOR",
            "Vancouver Canucks": "VAN",
            "Buffalo Sabres": "BUF",
            "Anaheim Ducks": "ANA",
            "Ottawa Senators": "OTT",
            "Florida Panthers": "FLA",
            "Minnesota Wild": "MIN",
            "New York Islanders": "NYI",
            "Nashville Predators": "NSH",
            "Chicago Blackhawks": "CHI",
            "Edmonton Oilers": "EDM",
            "Los Angeles Kings": "LAK",
            "Vegas Golden Knights": "VGK",
            "St. Louis Blues": "STL",
        }

        team_abbrev = team_mapping.get(team_name)
        if not team_abbrev:
            return None

        # Check cache first
        cache_key = f"{team_abbrev}:{player_name.lower()}"
        if cache_key in self.player_cache:
            return self.player_cache[cache_key]

        try:
            roster_url = f"{NHL_API_BASE}/roster/{team_abbrev}/current"
            response = self.session.get(roster_url, timeout=10)

            if response.status_code != 200:
                return None

            roster_data = response.json()

            # Normalize search name
            search_name = player_name.lower().strip()
            search_parts = search_name.split()
            
            for position_group in ['forwards', 'defensemen', 'goalies']:
                if position_group in roster_data:
                    for player in roster_data[position_group]:
                        first_name = player.get('firstName', {}).get('default', '').lower()
                        last_name = player.get('lastName', {}).get('default', '').lower()
                        full_name = f"{first_name} {last_name}"

                        # Multiple matching strategies
                        if (search_name == full_name or  # Exact match
                            search_name in full_name or  # Partial match
                            full_name in search_name or
                            all(part in full_name for part in search_parts) or  # All parts present
                            (len(search_parts) >= 2 and search_parts[0] == first_name and search_parts[-1] == last_name)):  # First and last name
                            
                            player_id = player.get('id')
                            self.player_cache[cache_key] = player_id
                            return player_id

            return None

        except Exception as e:
            return None

    def get_player_game_log(self, player_id: int, season: str = CURRENT_SEASON) -> List[Dict]:
        """Get player's game log for the season."""
        try:
            stats_url = f"{NHL_API_BASE}/player/{player_id}/game-log/{season}/2"
            response = self.session.get(stats_url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                return data.get('gameLog', [])

            return []

        except Exception as e:
            return []

    def analyze_prop(self, stat_values: List[int], line: float, prop_type: str) -> Dict:
        """Analyze a prop (OVER or UNDER) based on historical data."""
        if not stat_values:
            return {
                'score': 0,
                'hit_rate': 0,
                'recent_hit_rate': 0,
                'recent_hits': 0,
                'total_games': 0
            }

        total_games = len(stat_values)
        recent_5 = stat_values[:5] if len(stat_values) >= 5 else stat_values

        # Calculate hit rates
        if prop_type == "OVER":
            hits = sum(1 for val in stat_values if val > line)
            recent_hits = sum(1 for val in recent_5 if val > line)
        else:  # UNDER
            hits = sum(1 for val in stat_values if val < line)
            recent_hits = sum(1 for val in recent_5 if val < line)

        hit_rate = (hits / total_games * 100) if total_games > 0 else 0
        recent_hit_rate = (recent_hits / len(recent_5) * 100) if recent_5 else 0

        # Calculate average and consistency
        avg = sum(stat_values) / len(stat_values) if stat_values else 0
        recent_avg = sum(recent_5) / len(recent_5) if recent_5 else 0

        # Variance from line
        if prop_type == "OVER":
            line_diff = avg - line
        else:
            line_diff = line - avg

        # Standard deviation for consistency
        variance = sum((x - avg) ** 2 for x in stat_values) / len(stat_values) if stat_values else 0
        std_dev = variance ** 0.5

        # Scoring algorithm (0-100)
        # For low lines (0.5, 1.5), recent form is CRITICAL
        historical_score = min(hit_rate * 0.30, 30)  # 30% weight
        recent_score = min(recent_hit_rate * 0.40, 40)  # 40% weight (MOST important)

        # Line differential score
        if line_diff > 0:
            line_score = min(20, line_diff * 10)
        else:
            line_score = max(0, 20 + (line_diff * 10))

        # Consistency score
        consistency_score = max(0, 10 - (std_dev * 2))

        total_score = historical_score + recent_score + line_score + consistency_score

        return {
            'score': round(total_score, 1),
            'hit_rate': round(hit_rate, 1),
            'recent_hit_rate': round(recent_hit_rate, 1),
            'recent_hits': recent_hits,
            'total_games': total_games,
            'average': round(avg, 2),
            'recent_avg': round(recent_avg, 2),
            'std_dev': round(std_dev, 2),
            'last_5_values': recent_5
        }

    def analyze_all_props(self) -> Dict:
        """Analyze all props from the scraped data."""
        recommendations = {}
        total_players = 0
        processed_players = 0

        # Count total players
        for game_data in self.props_data.values():
            total_players += len(game_data['props'])

        print(f"\n{'='*80}")
        print(f"NHL PROPS ANALYSIS - Processing {total_players} players")
        print(f"{'='*80}\n")

        for game_slug, game_data in self.props_data.items():
            game_name = game_data['game_name']
            players = game_data['props']

            print(f"\n{'='*80}")
            print(f"Game: {game_name}")
            print(f"{'='*80}")

            game_recommendations = []

            for player in players:
                processed_players += 1
                player_name = player['name']
                team_name = player['team']

                print(f"  [{processed_players}/{total_players}] {player_name} ({team_name})...", end=' ', flush=True)

                # Get player ID and stats
                player_id = self.get_player_id_from_roster(player_name, team_name)

                if not player_id:
                    print(f"❌ Not found")
                    continue

                game_log = self.get_player_game_log(player_id)

                if not game_log:
                    print(f"❌ No stats")
                    continue

                print(f"✓ {len(game_log)} games")

                # Extract stats
                goals = [g.get('goals', 0) for g in game_log]
                assists = [g.get('assists', 0) for g in game_log]
                points = [g.get('points', 0) for g in game_log]
                shots = [g.get('shots', 0) for g in game_log]

                # Analyze each available prop
                player_rec = {
                    'player_name': player_name,
                    'team': team_name,
                    'player_id': player_id,
                    'games_played': len(game_log),
                    'props': []
                }

                # Check each stat type
                for stat_type in ['points', 'goals', 'assists', 'shots']:
                    if stat_type not in player:
                        continue

                    stat_data = player[stat_type]
                    stat_values = {
                        'points': points,
                        'goals': goals,
                        'assists': assists,
                        'shots': shots
                    }[stat_type]

                    # Check 0.5 line
                    if stat_data.get('line_0_5') and stat_data['line_0_5'].get('overOdds'):
                        line_data = stat_data['line_0_5']
                        analysis = self.analyze_prop(stat_values, 0.5, 'OVER')

                        player_rec['props'].append({
                            'stat_type': stat_type,
                            'line': 0.5,
                            'bet_type': 'OVER',
                            'odds': line_data['overOdds'],
                            'line_id': line_data['lineId'],
                            'market_id': stat_data['marketId'],
                            **analysis
                        })

                    # Check 1.5 line
                    if stat_data.get('line_1_5') and stat_data['line_1_5'].get('overOdds'):
                        line_data = stat_data['line_1_5']
                        analysis = self.analyze_prop(stat_values, 1.5, 'OVER')

                        player_rec['props'].append({
                            'stat_type': stat_type,
                            'line': 1.5,
                            'bet_type': 'OVER',
                            'odds': line_data['overOdds'],
                            'line_id': line_data['lineId'],
                            'market_id': stat_data['marketId'],
                            **analysis
                        })

                if player_rec['props']:
                    game_recommendations.append(player_rec)

                time.sleep(0.1)  # Be nice to the API

            recommendations[game_slug] = {
                'game_name': game_name,
                'start_time': game_data['start_time'],
                'players': game_recommendations
            }

        return recommendations

    def save_recommendations(self, recommendations: Dict, output_file: str = "nhl_recommendations.json"):
        """Save recommendations to JSON file."""
        with open(output_file, 'w') as f:
            json.dump(recommendations, f, indent=2)

        print(f"\n{'='*80}")
        print(f"✅ Recommendations saved to {output_file}")
        print(f"{'='*80}")


def main():
    analyzer = NHLRecommendationsAnalyzer()
    recommendations = analyzer.analyze_all_props()
    analyzer.save_recommendations(recommendations)

    # Print summary of strongest props
    print(f"\n{'='*80}")
    print("🔥 STRONGEST PROPS (Score >= 75, Recent >= 4/5)")
    print(f"{'='*80}")

    strong_count = 0
    for game_slug, game_data in recommendations.items():
        for player in game_data['players']:
            for prop in player['props']:
                if prop['score'] >= 75 and prop['recent_hits'] >= 4:
                    strong_count += 1
                    print(f"\n{player['player_name']} - {prop['stat_type'].upper()} OVER {prop['line']}")
                    print(f"  Score: {prop['score']} | Hit Rate: {prop['hit_rate']}% | Recent: {prop['recent_hits']}/5")
                    print(f"  Odds: {prop['odds']:.2f}x | Last 5: {prop['last_5_values']}")

    print(f"\n{'='*80}")
    print(f"Total strong props: {strong_count}")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
