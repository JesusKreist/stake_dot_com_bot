#!/usr/bin/env python3
"""
NHL Stats Analyzer - Get historical stats for points, goals, assists, shots
Focuses on 0.5 and 1.5 lines like the example hockey ticket
"""

import requests
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import time

NHL_API_BASE = "https://api-web.nhle.com/v1"
CURRENT_SEASON = "20252026"

class NHLStatsAnalyzer:
    def __init__(self):
        self.session = requests.Session()
        self.player_cache = {}
        
    def get_player_id_from_roster(self, player_name: str, team_abbrev: str) -> Optional[int]:
        """Get player ID from team roster"""
        try:
            # Get team roster
            roster_url = f"{NHL_API_BASE}/roster/{team_abbrev}/current"
            response = self.session.get(roster_url, timeout=10)
            
            if response.status_code != 200:
                return None
                
            roster_data = response.json()
            
            # Search in forwards, defensemen, and goalies
            for position_group in ['forwards', 'defensemen', 'goalies']:
                if position_group in roster_data:
                    for player in roster_data[position_group]:
                        first_name = player.get('firstName', {}).get('default', '')
                        last_name = player.get('lastName', {}).get('default', '')
                        full_name = f"{first_name} {last_name}".lower()
                        
                        if player_name.lower() in full_name or full_name in player_name.lower():
                            return player.get('id')
            
            return None
            
        except Exception as e:
            print(f"Error getting player ID for {player_name}: {e}")
            return None
    
    def get_player_game_log(self, player_id: int, season: str = CURRENT_SEASON) -> List[Dict]:
        """Get player's game log for the season"""
        try:
            stats_url = f"{NHL_API_BASE}/player/{player_id}/game-log/{season}/2"  # 2 = regular season
            response = self.session.get(stats_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                return data.get('gameLog', [])
            
            return []
            
        except Exception as e:
            print(f"Error getting game log for player {player_id}: {e}")
            return []
    
    def analyze_prop(self, stat_values: List[int], line: float, prop_type: str) -> Dict:
        """Analyze a prop (OVER or UNDER) based on historical data"""
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
        # For low lines (0.5, 1.5), recent form is VERY important
        historical_score = min(hit_rate * 0.35, 35)  # 35% weight
        recent_score = min(recent_hit_rate * 0.35, 35)  # 35% weight (more than NBA)
        
        # Line differential score
        if line_diff > 0:
            line_score = min(20, line_diff * 10)
        else:
            line_score = max(0, 20 + (line_diff * 10))
        
        # Consistency score (lower std_dev is better for low lines)
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
    
    def analyze_player_stats(self, player_name: str, team_abbrev: str) -> Dict:
        """Get comprehensive stats analysis for a player"""
        print(f"\nAnalyzing {player_name} ({team_abbrev})...")
        
        # Get player ID
        player_id = self.get_player_id_from_roster(player_name, team_abbrev)
        
        if not player_id:
            print(f"  ❌ Could not find player ID")
            return None
        
        print(f"  Found player ID: {player_id}")
        
        # Get game log
        game_log = self.get_player_game_log(player_id)
        
        if not game_log:
            print(f"  ❌ No game log data")
            return None
        
        print(f"  Found {len(game_log)} games")
        
        # Extract stats
        goals = [g.get('goals', 0) for g in game_log]
        assists = [g.get('assists', 0) for g in game_log]
        points = [g.get('points', 0) for g in game_log]
        shots = [g.get('shots', 0) for g in game_log]
        
        # Analyze common props (0.5 and 1.5 lines)
        analysis = {
            'player_name': player_name,
            'player_id': player_id,
            'team': team_abbrev,
            'games_played': len(game_log),
            'props': {
                'points': {
                    'over_0.5': self.analyze_prop(points, 0.5, 'OVER'),
                    'over_1.5': self.analyze_prop(points, 1.5, 'OVER'),
                },
                'goals': {
                    'over_0.5': self.analyze_prop(goals, 0.5, 'OVER'),
                    'over_1.5': self.analyze_prop(goals, 1.5, 'OVER'),
                },
                'assists': {
                    'over_0.5': self.analyze_prop(assists, 0.5, 'OVER'),
                    'over_1.5': self.analyze_prop(assists, 1.5, 'OVER'),
                },
                'shots': {
                    'over_0.5': self.analyze_prop(shots, 0.5, 'OVER'),
                    'over_1.5': self.analyze_prop(shots, 1.5, 'OVER'),
                    'over_2.5': self.analyze_prop(shots, 2.5, 'OVER'),
                    'over_3.5': self.analyze_prop(shots, 3.5, 'OVER'),
                }
            }
        }
        
        # Print summary
        print(f"\n  Recent Stats (Last 5 Games):")
        print(f"    Points:  {points[:5]}")
        print(f"    Goals:   {goals[:5]}")
        print(f"    Assists: {assists[:5]}")
        print(f"    Shots:   {shots[:5]}")
        
        return analysis


def test_with_example_players():
    """Test with some players from the example ticket"""
    analyzer = NHLStatsAnalyzer()
    
    # Players from the failed ticket
    test_players = [
        ("Connor McDavid", "EDM"),
        ("Leon Draisaitl", "EDM"),
        ("Nathan MacKinnon", "COL"),
        ("Kirill Kaprizov", "MIN"),
        ("David Pastrnak", "BOS"),
        ("Artemi Panarin", "NYR"),
        ("Sidney Crosby", "PIT"),
    ]
    
    results = []
    
    for player_name, team in test_players:
        result = analyzer.analyze_player_stats(player_name, team)
        if result:
            results.append(result)
        time.sleep(0.5)  # Be nice to the API
    
    # Save results
    output_file = "nhl_test_analysis.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n{'='*80}")
    print(f"✅ Analysis complete! Saved to {output_file}")
    print(f"{'='*80}")
    
    # Print some highlights
    print("\n🔥 STRONGEST PROPS (Score >= 80, Recent >= 4/5):")
    print(f"{'='*80}")
    
    for player in results:
        player_name = player['player_name']
        
        for stat_type, props in player['props'].items():
            for line_type, analysis in props.items():
                if analysis['score'] >= 80 and analysis['recent_hits'] >= 4:
                    print(f"\n{player_name} - {stat_type.upper()} {line_type.upper()}")
                    print(f"  Score: {analysis['score']} | Hit Rate: {analysis['hit_rate']}% | Recent: {analysis['recent_hits']}/5")
                    print(f"  Last 5: {analysis['last_5_values']}")


if __name__ == "__main__":
    test_with_example_players()
