#!/usr/bin/env python3
"""
Stake.com NHL Props Scraper
Fetches points, goals, assists, and shots props for NHL games
Focuses on 0.5 and 1.5 lines
"""

import json
import httpx
from typing import List, Dict, Any


def load_cookies(cookie_file: str = "cloudflare_cookies.json") -> Dict[str, str]:
    """Load cookies from JSON file."""
    with open(cookie_file, "r") as f:
        data = json.load(f)
    return data["cookies"]


class StakeNHLClient:
    """Client for interacting with Stake.com NHL betting API."""

    def __init__(self, cookie_file: str = "cloudflare_cookies.json"):
        self.base_url = "https://stake.com/_api/graphql"
        self.cookies = load_cookies(cookie_file)
        self.headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:144.0) Gecko/20100101 Firefox/144.0",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.5",
            "Content-Type": "application/json",
            "X-Language": "en",
            "Origin": "https://stake.com",
            "Referer": "https://stake.com/sports/ice-hockey/usa/nhl",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }

    def get_nhl_games(self) -> List[Dict[str, Any]]:
        """Get all active NHL games."""
        query = """query TournamentIndex($sport: String!, $category: String!, $tournament: String!) {
  slugTournament(sport: $sport, category: $category, tournament: $tournament) {
    id
    name
    slug
    fixtureList(type: active, limit: 20) {
      id
      status
      slug
      name
      data {
        __typename
        ... on SportFixtureDataMatch {
          startTime
          competitors {
            name
            abbreviation
          }
        }
      }
    }
  }
}"""

        variables = {"sport": "ice-hockey", "category": "usa", "tournament": "nhl"}

        with httpx.Client(http2=True) as client:
            response = client.post(
                self.base_url,
                headers=self.headers,
                cookies=self.cookies,
                json={"query": query, "variables": variables},
            )

            if response.status_code == 200:
                data = response.json()
                return data["data"]["slugTournament"]["fixtureList"]
            else:
                print(f"Error getting games: {response.status_code}")
                print(f"Response: {response.text}")
                return []

    def get_game_sgm_props(self, fixture_slug: str) -> Dict[str, Any]:
        """Get Same Game Multi props for a specific fixture."""
        query = """query SwishMarket_SlugFixture($fixture: String!, $inPlay: Boolean!) {
  slugFixture(fixture: $fixture) {
    id
    status
    tournament {
      slug
    }
    data {
      __typename
      ... on SportFixtureDataMatch {
        competitors {
          name
          abbreviation
          extId
        }
        startTime
      }
    }
    swishGame {
      id
      status
    }
    swishGameTeams {
      id
      name
      players {
        id
        name
        position
        markets(inPlay: $inPlay, statTypes: [match, player, match_props, team_props]) {
          id
          stat {
            swishStatId
            name
            value
          }
          lines {
            id
            line
            over
            under
          }
        }
      }
    }
  }
}"""

        variables = {"fixture": fixture_slug, "inPlay": False}

        with httpx.Client(http2=True) as client:
            response = client.post(
                self.base_url,
                headers=self.headers,
                cookies=self.cookies,
                json={"query": query, "variables": variables},
            )

            if response.status_code == 200:
                return response.json()
            else:
                print(
                    f"Error getting SGM props for {fixture_slug}: {response.status_code}"
                )
                return {}

    def extract_hockey_props(
        self, sgm_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extract points, goals, assists, and shots props (focusing on 0.5 and 1.5 lines)."""
        results = []

        fixture_data = sgm_data.get("data", {}).get("slugFixture", {})
        teams = fixture_data.get("swishGameTeams", [])

        for team in teams:
            team_name = team.get("name")
            players = team.get("players", [])

            for player in players:
                player_name = player.get("name")
                markets = player.get("markets", [])

                # Track all relevant stats for each player
                player_props = {}

                for market in markets:
                    stat = market.get("stat", {})
                    stat_name = stat.get("name", "").lower()

                    # Focus on the key hockey stats
                    stat_mapping = {
                        "points": "points",
                        "goals": "goals",
                        "assists": "assists",
                        "shots": "shots",
                        "shots on goal": "shots"  # Some might use this variant
                    }

                    if stat_name in stat_mapping:
                        lines = market.get("lines", [])

                        if lines:
                            # Get all available lines
                            all_lines = sorted(lines, key=lambda x: x.get("line", 0))
                            
                            # Extract 0.5 and 1.5 lines specifically
                            line_0_5 = next((l for l in all_lines if l.get("line") == 0.5), None)
                            line_1_5 = next((l for l in all_lines if l.get("line") == 1.5), None)
                            
                            # Also get the range for reference
                            lowest_line = all_lines[0] if all_lines else None
                            highest_line = all_lines[-1] if all_lines else None

                            prop_key = stat_mapping[stat_name]
                            player_props[prop_key] = {
                                "marketId": market.get("id"),
                                "swishStatId": stat.get("swishStatId"),
                                "swishStatName": stat.get("name"),
                                "line_0_5": {
                                    "line": 0.5,
                                    "lineId": line_0_5.get("id") if line_0_5 else None,
                                    "overOdds": line_0_5.get("over") if line_0_5 else None,
                                    "underOdds": line_0_5.get("under") if line_0_5 else None,
                                } if line_0_5 else None,
                                "line_1_5": {
                                    "line": 1.5,
                                    "lineId": line_1_5.get("id") if line_1_5 else None,
                                    "overOdds": line_1_5.get("over") if line_1_5 else None,
                                    "underOdds": line_1_5.get("under") if line_1_5 else None,
                                } if line_1_5 else None,
                                "allLines": [
                                    {
                                        "line": l.get("line"),
                                        "lineId": l.get("id"),
                                        "overOdds": l.get("over"),
                                        "underOdds": l.get("under"),
                                    }
                                    for l in all_lines
                                ],
                                "lowestLine": lowest_line.get("line") if lowest_line else None,
                                "highestLine": highest_line.get("line") if highest_line else None,
                            }

                # Only add players who have at least one prop type
                if player_props:
                    results.append({
                        "name": player_name,
                        "team": team_name,
                        **player_props
                    })

        return results

    def get_all_nhl_props(self) -> Dict[str, Any]:
        """Get all NHL games and extract player props for each game."""
        games = self.get_nhl_games()
        all_props = {}

        print(f"Found {len(games)} NHL games")

        for idx, game in enumerate(games, 1):
            game_slug = game["slug"]
            game_name = game["name"]
            game_data = game.get("data", {})
            start_time = game_data.get("startTime", "N/A")

            print(f"\n[{idx}/{len(games)}] Processing: {game_name}")
            print(f"  Start time: {start_time}")

            sgm_data = self.get_game_sgm_props(game_slug)
            props = self.extract_hockey_props(sgm_data)

            print(f"  Found {len(props)} players with props")

            all_props[game_slug] = {
                "game_name": game_name,
                "start_time": start_time,
                "props": props
            }

        return all_props


def main():
    """Example usage."""
    client = StakeNHLClient()

    all_props = client.get_all_nhl_props()

    output_file = "nhl_props.json"
    with open(output_file, "w") as f:
        json.dump(all_props, f, indent=2)

    print(f"\n{'='*80}")
    print("Summary")
    print(f"{'='*80}")

    total_players = 0
    for game_slug, game_data in all_props.items():
        props_list = game_data["props"]
        total_players += len(props_list)
        
        print(f"\n{game_data['game_name']}:")
        print(f"  Players with props: {len(props_list)}")
        
        # Show sample of available props
        sample_players = props_list[:2]
        for prop in sample_players:
            print(f"\n  {prop['name']} ({prop['team']}):")
            
            for stat_type in ["points", "goals", "assists", "shots"]:
                if stat_type in prop:
                    stat_data = prop[stat_type]
                    
                    # Show 0.5 line if available
                    if stat_data.get("line_0_5"):
                        line_data = stat_data["line_0_5"]
                        if line_data.get("overOdds"):
                            print(f"    {stat_type.upper()} OVER 0.5: {line_data['overOdds']}")
                    
                    # Show 1.5 line if available
                    if stat_data.get("line_1_5"):
                        line_data = stat_data["line_1_5"]
                        if line_data.get("overOdds"):
                            print(f"    {stat_type.upper()} OVER 1.5: {line_data['overOdds']}")

    print(f"\n{'='*80}")
    print(f"✅ Total games: {len(all_props)}")
    print(f"✅ Total players: {total_players}")
    print(f"✅ Full data saved to {output_file}")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
