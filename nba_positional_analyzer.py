#!/usr/bin/env python3
"""
NBA Positional Props Analyzer
Filters props that match positional tendencies and detects outliers.
"""

import json
from typing import Dict, List, Any, Optional, Tuple

# Positional Rules Configuration
# Maps position -> stat -> expected bet direction
POSITIONAL_RULES = {
    "C": {  # Centers - clearest patterns
        "assists": "UNDER",
        "rebounds": "OVER",
        "blocks": "OVER",
        "three attempted": "UNDER",
        "steals": "UNDER",
        "turnovers": "UNDER",
    },
    "PG": {  # Point Guards
        "assists": "OVER",
        "steals": "OVER",
        "rebounds": "UNDER",
        "blocks": "UNDER",
    },
    "SG": {  # Shooting Guards
        "fg attempted": "OVER",
        "three attempted": "OVER",
        "assists": "UNDER",
        "rebounds": "UNDER",
    },
    "PF": {  # Power Forwards
        "rebounds": "OVER",
        "assists": "UNDER",
        "blocks": "OVER",
    },
    "SF": None,  # Skip - too versatile
}

# Positional Norms for Outlier Detection (NBA league averages)
# Mean and standard deviation for each stat by position
POSITIONAL_NORMS = {
    "C": {
        "assists": {"mean": 2.5, "std": 1.5},
        "rebounds": {"mean": 10.0, "std": 2.5},
        "blocks": {"mean": 1.5, "std": 0.8},
        "three attempted": {"mean": 1.5, "std": 1.0},
        "steals": {"mean": 0.8, "std": 0.4},
        "turnovers": {"mean": 1.5, "std": 0.5},
    },
    "PG": {
        "assists": {"mean": 6.5, "std": 2.0},
        "steals": {"mean": 1.2, "std": 0.5},
        "rebounds": {"mean": 3.5, "std": 1.0},
        "blocks": {"mean": 0.3, "std": 0.2},
    },
    "SG": {
        "fg attempted": {"mean": 14.0, "std": 3.0},
        "three attempted": {"mean": 6.0, "std": 2.0},
        "assists": {"mean": 3.5, "std": 1.5},
        "rebounds": {"mean": 3.5, "std": 1.0},
    },
    "PF": {
        "rebounds": {"mean": 7.5, "std": 2.0},
        "assists": {"mean": 2.5, "std": 1.2},
        "blocks": {"mean": 0.8, "std": 0.5},
    },
}

# Outlier threshold (z-score)
OUTLIER_THRESHOLD = 2.0  # 2 standard deviations from positional mean

# Position priority for ticket generation (clearest patterns first)
POSITION_PRIORITY = {"C": 1, "PG": 2, "PF": 3, "SG": 4, "SF": 5}


def load_recommendations() -> List[Dict]:
    """Load pre-analyzed recommendations from nba_comprehensive_recommendations.json."""
    with open("nba_comprehensive_recommendations.json", "r") as f:
        return json.load(f)


def load_props_data() -> Dict[str, Any]:
    """Load nba_all_props.json with position data."""
    with open("nba_all_props.json", "r") as f:
        return json.load(f)


def build_player_position_map(props_data: Dict) -> Dict[str, str]:
    """Build a mapping of (player_name, team) -> position."""
    position_map = {}
    for game_slug, game_data in props_data.items():
        for player_data in game_data.get("props", []):
            player_name = player_data.get("name", "")
            team = player_data.get("team", "")
            position = player_data.get("position", "")
            if player_name and position:
                # Key by player name and team to handle players with same name
                key = f"{player_name}|{team}"
                position_map[key] = position
    return position_map


def get_player_position(player_name: str, team: str, position_map: Dict[str, str]) -> Optional[str]:
    """Look up player position from the position map."""
    key = f"{player_name}|{team}"
    return position_map.get(key)


def is_positional_match(position: str, stat: str, bet_type: str) -> bool:
    """Check if a prop matches the positional rule."""
    rules = POSITIONAL_RULES.get(position)
    if rules is None:  # SF or unknown position
        return False

    # Normalize stat name (handle variations)
    stat_lower = stat.lower()

    # Check if this stat has a rule for this position
    if stat_lower not in rules:
        return False

    # Check if the bet direction matches
    return rules[stat_lower] == bet_type


def detect_outlier(position: str, stat: str, avg_value: float) -> Dict:
    """
    Detect if a player's average deviates significantly from positional norms.
    Returns outlier info dict with z_score, is_outlier flag, and description.
    """
    stat_lower = stat.lower()
    norms = POSITIONAL_NORMS.get(position, {})
    stat_norms = norms.get(stat_lower)

    if stat_norms is None:
        return {"is_outlier": False, "z_score": 0, "reason": None}

    mean = stat_norms["mean"]
    std = stat_norms["std"]

    if std == 0:
        return {"is_outlier": False, "z_score": 0, "reason": None}

    z_score = (avg_value - mean) / std
    is_outlier = abs(z_score) > OUTLIER_THRESHOLD

    reason = None
    if is_outlier:
        direction = "above" if z_score > 0 else "below"
        reason = f"Player avg ({avg_value:.1f}) is {abs(z_score):.1f} std devs {direction} {position} norm ({mean})"

    return {
        "is_outlier": is_outlier,
        "z_score": round(z_score, 2),
        "positional_mean": mean,
        "positional_std": std,
        "reason": reason,
    }


def get_positional_rule_description(position: str, stat: str, bet_type: str) -> str:
    """Get a human-readable description of why this is a positional play."""
    descriptions = {
        ("C", "assists", "UNDER"): "Centers rarely handle the ball - low assists expected",
        ("C", "rebounds", "OVER"): "Centers are primary rebounders",
        ("C", "blocks", "OVER"): "Centers provide rim protection",
        ("C", "three attempted", "UNDER"): "Most centers don't shoot from deep",
        ("C", "steals", "UNDER"): "Centers positioned in paint, not perimeter",
        ("C", "turnovers", "UNDER"): "Fewer touches means fewer turnovers",
        ("PG", "assists", "OVER"): "Point guards are primary ball handlers",
        ("PG", "steals", "OVER"): "PGs guard opposing ball handlers",
        ("PG", "rebounds", "UNDER"): "Smallest players on court",
        ("PG", "blocks", "UNDER"): "Too short for rim protection",
        ("SG", "fg attempted", "OVER"): "Shooting guards are volume scorers",
        ("SG", "three attempted", "OVER"): "Spot-up shooting role",
        ("SG", "assists", "UNDER"): "Off-ball movement, not playmaking",
        ("SG", "rebounds", "UNDER"): "Perimeter players don't crash boards",
        ("PF", "rebounds", "OVER"): "Power forwards are secondary rebounders",
        ("PF", "assists", "UNDER"): "Limited playmaking role",
        ("PF", "blocks", "OVER"): "Help-side rim protection",
    }
    return descriptions.get((position, stat.lower(), bet_type), "Positional tendency")


def filter_positional_props(
    recommendations: List[Dict], position_map: Dict[str, str]
) -> Tuple[List[Dict], List[Dict]]:
    """
    Filter recommendations to only include position-matching props.
    Returns (positional_props, outlier_flagged_props)
    """
    positional_props = []
    outlier_flagged = []

    for rec in recommendations:
        player = rec.get("player", "")
        team = rec.get("team", "")
        stat = rec.get("stat", "")
        bet_type = rec.get("bet_type", "")
        avg_value = rec.get("avg_value", 0)

        # Get position
        position = get_player_position(player, team, position_map)

        if position is None or position == "SF":
            continue

        # Check if this prop matches positional rules
        if not is_positional_match(position, stat, bet_type):
            continue

        # Check for outlier
        outlier_info = detect_outlier(position, stat, avg_value)

        # Get rule description
        rule_description = get_positional_rule_description(position, stat, bet_type)

        prop_entry = {
            **rec,
            "position": position,
            "position_priority": POSITION_PRIORITY.get(position, 5),
            "is_positional_play": True,
            "positional_rule": rule_description,
            "outlier_info": outlier_info,
        }

        if outlier_info["is_outlier"]:
            outlier_flagged.append(prop_entry)
        else:
            positional_props.append(prop_entry)

    return positional_props, outlier_flagged


def calculate_positional_score(prop: Dict) -> float:
    """
    Apply positional bonus to scoring.
    Base score from comprehensive analyzer + positional alignment bonus.
    """
    base_score = prop.get("score", 0)

    # Positional confidence bonus by position clarity
    position_confidence = {
        "C": 1.05,  # 5% bonus - clearest patterns
        "PG": 1.04,  # 4% bonus - clear patterns
        "PF": 1.03,  # 3% bonus - good patterns
        "SG": 1.02,  # 2% bonus - moderate patterns
        "SF": 1.00,  # No bonus - too versatile
    }

    position = prop.get("position", "SF")
    multiplier = position_confidence.get(position, 1.0)

    return round(base_score * multiplier, 1)


def main():
    """Run positional analysis pipeline."""
    print("=" * 80)
    print("NBA POSITIONAL PROPS ANALYZER")
    print("=" * 80)
    print("Strategy: Filter props matching positional tendencies")
    print()
    print("Positional Rules:")
    print("  C  (Center):        Rebounds/Blocks OVER | Assists/3PA/Steals/TO UNDER")
    print("  PG (Point Guard):   Assists/Steals OVER | Rebounds/Blocks UNDER")
    print("  SG (Shooting Guard): FGA/3PA OVER | Assists/Rebounds UNDER")
    print("  PF (Power Forward): Rebounds/Blocks OVER | Assists UNDER")
    print("  SF (Small Forward): Skipped - too versatile")
    print()

    # Load data
    print("Loading data...")
    recommendations = load_recommendations()
    props_data = load_props_data()

    print(f"  Loaded {len(recommendations)} recommendations")

    # Build position map
    position_map = build_player_position_map(props_data)
    print(f"  Mapped positions for {len(position_map)} players")

    # Filter for positional matches
    print("\nFiltering for positional plays...")
    positional_props, outliers = filter_positional_props(recommendations, position_map)

    # Apply positional scoring
    for prop in positional_props:
        prop["positional_score"] = calculate_positional_score(prop)

    # Sort by positional score
    positional_props.sort(key=lambda x: x.get("positional_score", 0), reverse=True)

    # Count by position
    position_counts = {}
    for prop in positional_props:
        pos = prop.get("position", "Unknown")
        position_counts[pos] = position_counts.get(pos, 0) + 1

    print(f"\nFound {len(positional_props)} positional props:")
    for pos in ["C", "PG", "PF", "SG"]:
        count = position_counts.get(pos, 0)
        print(f"  {pos}: {count} props")

    print(f"\nFlagged {len(outliers)} outliers:")
    for outlier in outliers[:5]:  # Show first 5 outliers
        player = outlier.get("player", "")
        position = outlier.get("position", "")
        stat = outlier.get("stat", "")
        avg = outlier.get("avg_value", 0)
        z_score = outlier.get("outlier_info", {}).get("z_score", 0)
        print(f"  {player} ({position}): {stat} avg={avg:.1f} (z={z_score:.2f})")

    # Show top positional props
    print("\nTop 10 Positional Props:")
    print("-" * 80)
    for i, prop in enumerate(positional_props[:10], 1):
        player = prop.get("player", "")
        position = prop.get("position", "")
        stat = prop.get("stat", "")
        bet_type = prop.get("bet_type", "")
        line = prop.get("line", 0)
        score = prop.get("positional_score", 0)
        recent = prop.get("recent_hits", 0)
        historical = prop.get("historical_hit_rate", 0)
        rule = prop.get("positional_rule", "")

        print(f"{i:2}. [{position}] {player}")
        print(f"    {stat} {bet_type} {line}")
        print(f"    Score: {score} | Recent: {recent}/7 | Historical: {historical}%")
        print(f"    Rule: {rule}")
        print()

    # Prepare output
    output = {
        "positional_props": positional_props,
        "outliers_flagged": outliers,
        "summary": {
            "total_positional_props": len(positional_props),
            "total_outliers": len(outliers),
            "by_position": position_counts,
        },
    }

    # Save results
    with open("nba_positional_recommendations.json", "w") as f:
        json.dump(output, f, indent=2)

    print("=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)
    print(f"Total Positional Props: {len(positional_props)}")
    print(f"Outliers Flagged: {len(outliers)}")
    print(f"\nSaved to nba_positional_recommendations.json")


if __name__ == "__main__":
    main()
