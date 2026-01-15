#!/usr/bin/env python3
"""
NBA Comprehensive Stats Analyzer
Analyzes all available NBA props with 7-game lookback
Enhanced with contextual factors: Home/Away, Back-to-Back, Rest Days, Minutes Trend
"""

import json
from datetime import datetime, timedelta
from nba_api.stats.endpoints import playergamelog
from nba_api.stats.static import players
import statistics
import time
from typing import Dict, List, Any, Optional


# =============================================================================
# CONTEXTUAL FACTOR HELPERS
# =============================================================================

def detect_home_away(matchup: str) -> str:
    """
    Detect if game is home or away from MATCHUP field.
    Format: "LAL vs. ATL" (first team is home) or "LAL @ ATL" (first team is away)

    Returns: "home", "away", or "unknown"
    """
    if not matchup:
        return "unknown"

    if " vs. " in matchup:
        return "home"  # "vs." means the first team is home
    elif " @ " in matchup:
        return "away"  # "@" means the first team is away

    return "unknown"


def get_home_away_multiplier(home_away: str) -> float:
    """
    Calculate home court advantage bonus.
    Home games: +4% bonus
    """
    if home_away == "home":
        return 1.04
    return 1.0


def parse_game_date(date_str: str) -> Optional[datetime]:
    """
    Parse NBA API date format (e.g., "JAN 14, 2026").
    """
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%b %d, %Y")
    except ValueError:
        try:
            # Try alternate format
            return datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return None


def detect_rest_days(games: List[Dict]) -> Dict:
    """
    Detect rest days and back-to-back situations.

    Returns dict with:
    - is_b2b: bool (back-to-back game)
    - rest_days: int (days since last game, -1 if unknown)
    """
    if not games or len(games) < 2:
        return {"is_b2b": False, "rest_days": -1}

    # Get most recent two game dates to check for B2B pattern
    date1 = parse_game_date(games[0].get("GAME_DATE", ""))
    date2 = parse_game_date(games[1].get("GAME_DATE", ""))

    if not date1 or not date2:
        return {"is_b2b": False, "rest_days": -1}

    days_between = (date1 - date2).days

    return {
        "is_b2b": days_between <= 1,
        "rest_days": days_between
    }


def get_b2b_multiplier(is_b2b: bool, rest_days: int, bet_type: str) -> float:
    """
    Calculate B2B/rest adjustment for score.

    Back-to-back:
    - OVER bets: -5% (players tired, less production)
    - UNDER bets: +3% (tired players support unders)

    Well-rested (2+ days):
    - All bets: +3% bonus
    """
    if is_b2b:
        if bet_type.upper() == "OVER":
            return 0.95  # -5%
        else:
            return 1.03  # +3%
    elif rest_days >= 2:
        return 1.03  # +3% for well-rested

    return 1.0


def calculate_minutes_trend(games: List[Dict]) -> Dict:
    """
    Compare last 3 games minutes to season average.

    Returns dict with:
    - season_avg_min: float
    - recent_avg_min: float (last 3 games)
    - trend: "up", "down", or "stable"
    - trend_pct: percentage change
    """
    if not games or len(games) < 3:
        return {
            "season_avg_min": 0,
            "recent_avg_min": 0,
            "trend": "unknown",
            "trend_pct": 0
        }

    all_minutes = []
    for game in games:
        min_val = game.get("MIN", 0)
        try:
            if isinstance(min_val, str) and ":" in min_val:
                minutes = float(min_val.split(":")[0])
            else:
                minutes = float(min_val) if min_val else 0
            if minutes > 0:
                all_minutes.append(minutes)
        except (ValueError, TypeError):
            continue

    if len(all_minutes) < 3:
        return {
            "season_avg_min": 0,
            "recent_avg_min": 0,
            "trend": "unknown",
            "trend_pct": 0
        }

    season_avg = sum(all_minutes) / len(all_minutes)
    recent_avg = sum(all_minutes[:3]) / 3

    if season_avg == 0:
        return {
            "season_avg_min": 0,
            "recent_avg_min": round(recent_avg, 1),
            "trend": "stable",
            "trend_pct": 0
        }

    trend_pct = ((recent_avg - season_avg) / season_avg) * 100

    if trend_pct > 5:
        trend = "up"
    elif trend_pct < -5:
        trend = "down"
    else:
        trend = "stable"

    return {
        "season_avg_min": round(season_avg, 1),
        "recent_avg_min": round(recent_avg, 1),
        "trend": trend,
        "trend_pct": round(trend_pct, 1)
    }


def get_minutes_trend_multiplier(trend: str, bet_type: str) -> float:
    """
    Adjust score based on minutes trend.

    Minutes UP:
    - OVER: +3% (more time = more production)
    - UNDER: -2% (more time hurts unders)

    Minutes DOWN:
    - OVER: -2% (less time = less production)
    - UNDER: +3% (less time helps unders)
    """
    if trend == "up":
        return 1.03 if bet_type.upper() == "OVER" else 0.98
    elif trend == "down":
        return 0.98 if bet_type.upper() == "OVER" else 1.03
    return 1.0


# =============================================================================
# CORE FUNCTIONS
# =============================================================================


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
    """
    Analyze a specific prop bet against historical data.
    Enhanced with contextual factors: Home/Away, B2B, Rest Days, Minutes Trend.
    """
    if not games:
        return {
            "error": "No games data",
            "score": 0,
            "base_score": 0,
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
            "base_score": 0,
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
        std_dev = statistics.stdev(stat_values)
        cv = (std_dev / avg_value) if avg_value != 0 else 0
        consistency = max(0, 100 - (cv * 100))
    else:
        consistency = 50

    # Base scoring algorithm (0-100)
    base_score = (
        historical_hit_rate * 0.35 +  # 35% weight on historical hit rate
        recent_hit_rate * 0.25 +       # 25% weight on recent hit rate
        min(line_diff_pct * 2, 20) +   # Up to 20 points for favorable line
        consistency * 0.15 +            # 15% weight on consistency
        (total_games / 20 * 5)          # Up to 5 points for sample size
    )

    # ==========================================================================
    # CONTEXTUAL ADJUSTMENTS
    # ==========================================================================

    # 1. Home/Away detection (from most recent game's matchup pattern)
    most_recent_matchup = games[0].get("MATCHUP", "") if games else ""
    home_away = detect_home_away(most_recent_matchup)
    home_multiplier = get_home_away_multiplier(home_away)

    # 2. Back-to-back / Rest days detection
    rest_info = detect_rest_days(games)
    b2b_multiplier = get_b2b_multiplier(
        rest_info["is_b2b"],
        rest_info["rest_days"],
        bet_type
    )

    # 3. Minutes trend analysis
    minutes_info = calculate_minutes_trend(games)
    minutes_multiplier = get_minutes_trend_multiplier(minutes_info["trend"], bet_type)

    # Apply all contextual adjustments
    adjusted_score = base_score * home_multiplier * b2b_multiplier * minutes_multiplier

    return {
        "score": round(adjusted_score, 1),
        "base_score": round(base_score, 1),
        "historical_hit_rate": round(historical_hit_rate, 1),
        "recent_hit_rate": round(recent_hit_rate, 1),
        "recent_hits": recent_hits_count,
        "total_games": total_games,
        "avg_value": round(avg_value, 1),
        "line": line,
        "line_diff": round(line_diff, 1),
        "consistency": round(consistency, 1),
        "last_7_values": [round(calculate_stat_value(g, stat_type), 1) for g in recent_games if calculate_stat_value(g, stat_type) is not None][:7],
        # Contextual factors
        "home_away": home_away,
        "home_bonus": round((home_multiplier - 1) * 100, 1),
        "is_b2b": rest_info["is_b2b"],
        "rest_days": rest_info["rest_days"],
        "b2b_adjustment": round((b2b_multiplier - 1) * 100, 1),
        "minutes_trend": minutes_info["trend"],
        "minutes_trend_pct": minutes_info["trend_pct"],
        "season_avg_min": minutes_info["season_avg_min"],
        "recent_avg_min": minutes_info["recent_avg_min"],
        "minutes_adjustment": round((minutes_multiplier - 1) * 100, 1),
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
