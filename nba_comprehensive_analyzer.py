#!/usr/bin/env python3
"""
NBA Comprehensive Stats Analyzer
Analyzes all available NBA props with 7-game lookback
"""

import json
from nba_api.stats.endpoints import playergamelog
from nba_api.stats.static import players
import time
from typing import Dict, List, Any, Optional


def find_player_id(player_name: str) -> Optional[int]:
    """Find NBA player ID from name."""
    all_players = players.get_players()
    
    # Try exact match first
    for player in all_players:
        if player['full_name'].lower() == player_name.lower():
            return player['id']
    
    # Try partial match
    for player in all_players:
        if player_name.lower() in player['full_name'].lower():
            return player['id']
    
    return None


def get_player_game_logs(player_id: int, season: str = "2025-26") -> List[Dict]:
    """Get player's game logs for the current season."""
    try:
        time.sleep(0.6)  # Rate limiting
        gamelog = playergamelog.PlayerGameLog(
            player_id=player_id,
            season=season,
            season_type_all_star='Regular Season'
        )
        df = gamelog.get_data_frames()[0]
        
        if df.empty:
            return []
        
        # Convert to list of dicts
        games = df.to_dict('records')
        return games
    except Exception as e:
        print(f"    Error getting game log: {e}")
        return []


def calculate_stat_value(game: Dict, stat_type: str) -> Optional[float]:
    """Calculate stat value from game log based on stat type."""
    try:
        if stat_type == "points":
            return float(game.get('PTS', 0))
        elif stat_type == "assists":
            return float(game.get('AST', 0))
        elif stat_type == "rebounds":
            return float(game.get('REB', 0))
        elif stat_type == "steals":
            return float(game.get('STL', 0))
        elif stat_type == "blocks":
            return float(game.get('BLK', 0))
        elif stat_type == "turnovers":
            return float(game.get('TOV', 0))
        elif stat_type == "fg_made":
            return float(game.get('FGM', 0))
        elif stat_type == "fg_attempted":
            return float(game.get('FGA', 0))
        elif stat_type == "three_attempted":
            return float(game.get('FG3A', 0))
        elif stat_type == "threesmade":
            return float(game.get('FG3M', 0))
        elif stat_type == "ft_made":
            return float(game.get('FTM', 0))
        elif stat_type == "ft_attempted":
            return float(game.get('FTA', 0))
        elif stat_type == "points+assists":
            return float(game.get('PTS', 0)) + float(game.get('AST', 0))
        elif stat_type == "points+rebounds":
            return float(game.get('PTS', 0)) + float(game.get('REB', 0))
        elif stat_type == "points+rebounds+assists":
            return float(game.get('PTS', 0)) + float(game.get('REB', 0)) + float(game.get('AST', 0))
        elif stat_type == "steals+blocks":
            return float(game.get('STL', 0)) + float(game.get('BLK', 0))
        elif stat_type == "first_quarter_points":
            # Not available in standard game logs
            return None
        elif stat_type == "first_quarter_assists":
            # Not available in standard game logs
            return None
        elif stat_type == "first_quarter_rebounds":
            # Not available in standard game logs
            return None
        else:
            return None
    except (KeyError, ValueError, TypeError):
        return None


def analyze_prop(games: List[Dict], stat_type: str, line: float, bet_type: str, lookback: int = 7) -> Dict:
    """Analyze a specific prop bet against historical data."""
    if not games:
        return {
            "error": "No games data",
            "score": 0,
            "historical_hit_rate": 0,
            "recent_hit_rate": 0,
            "recent_hits": 0,
            "total_games": 0
        }
    
    # Use only the most recent games (up to lookback)
    recent_games = games[:lookback]
    
    hits = []
    recent_hits_count = 0
    stat_values = []
    
    for i, game in enumerate(games):
        stat_value = calculate_stat_value(game, stat_type)
        
        if stat_value is None:
            continue
            
        stat_values.append(stat_value)
        
        # Determine if bet would have hit
        if bet_type == "over":
            hit = stat_value > line
        else:  # under
            hit = stat_value < line
        
        hits.append(hit)
        
        # Count recent hits (first lookback games)
        if i < lookback and hit:
            recent_hits_count += 1
    
    if not stat_values:
        return {
            "error": "No valid stat values",
            "score": 0,
            "historical_hit_rate": 0,
            "recent_hit_rate": 0,
            "recent_hits": 0,
            "total_games": 0
        }
    
    # Calculate metrics
    total_games = len(hits)
    historical_hits = sum(hits)
    historical_hit_rate = (historical_hits / total_games * 100) if total_games > 0 else 0
    recent_hit_rate = (recent_hits_count / min(lookback, total_games) * 100) if total_games > 0 else 0
    
    avg_value = sum(stat_values) / len(stat_values)
    
    # Calculate line difference (positive means favorable)
    if bet_type == "over":
        line_diff = avg_value - line
    else:
        line_diff = line - avg_value
    
    line_diff_pct = (line_diff / line * 100) if line != 0 else 0
    
    # Calculate consistency (inverse of coefficient of variation)
    if len(stat_values) > 1:
        import statistics
        std_dev = statistics.stdev(stat_values)
        cv = (std_dev / avg_value) if avg_value != 0 else 0
        consistency = max(0, 100 - (cv * 100))
    else:
        consistency = 50
    
    # Scoring algorithm (0-100)
    score = (
        historical_hit_rate * 0.35 +  # 35% weight on historical hit rate
        recent_hit_rate * 0.25 +       # 25% weight on recent hit rate
        min(line_diff_pct * 2, 20) +   # Up to 20 points for favorable line
        consistency * 0.15 +            # 15% weight on consistency
        (total_games / 20 * 5)          # Up to 5 points for sample size
    )
    
    return {
        "score": round(score, 1),
        "historical_hit_rate": round(historical_hit_rate, 1),
        "recent_hit_rate": round(recent_hit_rate, 1),
        "recent_hits": recent_hits_count,
        "total_games": total_games,
        "avg_value": round(avg_value, 1),
        "line": line,
        "line_diff": round(line_diff, 1),
        "consistency": round(consistency, 1),
        "last_7_values": [round(calculate_stat_value(g, stat_type), 1) for g in recent_games if calculate_stat_value(g, stat_type) is not None][:7]
    }


def main():
    """Main analyzer function."""
    # Load props data
    with open("nba_all_props.json", "r") as f:
        props_data = json.load(f)
    
    all_recommendations = []
    total_players = 0
    players_found = 0
    players_not_found = 0
    total_props = 0
    strong_props = 0
    
    print("=" * 80)
    print("NBA COMPREHENSIVE PROPS ANALYZER")
    print("=" * 80)
    print(f"Analyzing {len(props_data)} games with 7-game lookback")
    print()
    
    for game_slug, game_data in props_data.items():
        game_name = game_data["game_name"]
        players = game_data["props"]
        
        print(f"\n{game_name}")
        print("-" * 80)
        
        for player_data in players:
            player_name = player_data["name"]
            team = player_data.get("team", "Unknown")
            props = player_data.get("props", {})
            
            total_players += 1
            
            print(f"\n  {player_name} ({team})")
            
            # Find player ID
            player_id = find_player_id(player_name)
            
            if not player_id:
                print(f"    ❌ Player not found in NBA API")
                players_not_found += 1
                continue
            
            players_found += 1
            
            # Get game logs
            games = get_player_game_logs(player_id)
            
            if not games:
                print(f"    ❌ No game logs found")
                continue
            
            print(f"    ✅ Found {len(games)} games")
            
            # Analyze each prop
            player_recommendations = []
            
            for stat_key, prop_data in props.items():
                stat_name = prop_data["swishStatName"]
                
                # Analyze both OVER and UNDER for each line
                for line_data in prop_data.get("allLines", []):
                    line = line_data["line"]
                    over_odds = line_data["overOdds"]
                    under_odds = line_data["underOdds"]
                    
                    total_props += 2  # Both over and under
                    
                    # Analyze OVER
                    over_analysis = analyze_prop(games, stat_key, line, "over", lookback=7)
                    if over_analysis.get("score", 0) >= 70 and over_analysis.get("recent_hits", 0) >= 5:
                        strong_props += 1
                        player_recommendations.append({
                            "player": player_name,
                            "team": team,
                            "stat": stat_name,
                            "bet_type": "OVER",
                            "line": line,
                            "odds": over_odds,
                            "lineId": line_data["lineId"],
                            "marketId": prop_data["marketId"],
                            "swishStatId": prop_data["swishStatId"],
                            **over_analysis
                        })
                    
                    # Analyze UNDER
                    under_analysis = analyze_prop(games, stat_key, line, "under", lookback=7)
                    if under_analysis.get("score", 0) >= 70 and under_analysis.get("recent_hits", 0) >= 5:
                        strong_props += 1
                        player_recommendations.append({
                            "player": player_name,
                            "team": team,
                            "stat": stat_name,
                            "bet_type": "UNDER",
                            "line": line,
                            "odds": under_odds,
                            "lineId": line_data["lineId"],
                            "marketId": prop_data["marketId"],
                            "swishStatId": prop_data["swishStatId"],
                            **under_analysis
                        })
            
            # Show top props for this player
            if player_recommendations:
                player_recommendations.sort(key=lambda x: x["score"], reverse=True)
                for rec in player_recommendations[:3]:
                    print(f"    {rec['stat']} {rec['bet_type']} {rec['line']}: "
                          f"Score {rec['score']} | Recent {rec['recent_hits']}/7 | "
                          f"Hist {rec['historical_hit_rate']}%")
            
            all_recommendations.extend(player_recommendations)
    
    # Save recommendations
    with open("nba_comprehensive_recommendations.json", "w") as f:
        json.dump(all_recommendations, f, indent=2)
    
    print("\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    print(f"Total Players: {total_players}")
    print(f"Players Found: {players_found}")
    print(f"Players Not Found: {players_not_found}")
    print(f"Total Props Analyzed: {total_props}")
    print(f"Strong Props (Score ≥70, Recent ≥5/7): {strong_props}")
    print(f"\n✅ Recommendations saved to nba_comprehensive_recommendations.json")


if __name__ == "__main__":
    main()
