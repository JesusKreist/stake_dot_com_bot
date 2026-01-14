import json
import httpx
from typing import List, Dict, Any


def load_cookies(cookie_file: str = "cloudflare_cookies.json") -> Dict[str, str]:
    """Load cookies from JSON file."""
    with open(cookie_file, "r") as f:
        data = json.load(f)
    return data["cookies"]


class StakeNBAClient:
    """Client for interacting with Stake.com NBA betting API."""

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
            "Referer": "https://stake.com/sports/basketball/usa/nba",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
        }

    def get_nba_games(self) -> List[Dict[str, Any]]:
        """Get all active NBA games."""
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

        variables = {"sport": "basketball", "category": "usa", "tournament": "nba"}

        with httpx.Client() as client:
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

        with httpx.Client() as client:
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

    def extract_all_props(
        self, sgm_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Extract ALL available player props from NBA game data."""
        results = []

        fixture_data = sgm_data.get("data", {}).get("slugFixture", {})
        teams = fixture_data.get("swishGameTeams", [])

        for team in teams:
            team_name = team.get("name")
            players = team.get("players", [])

            for player in players:
                player_name = player.get("name")
                position = player.get("position")
                markets = player.get("markets", [])

                # Track all stats for each player
                player_props = {}

                for market in markets:
                    stat = market.get("stat", {})
                    stat_name = stat.get("name", "").lower()
                    lines = market.get("lines", [])

                    if lines:
                        # Get all available lines
                        all_lines = sorted(lines, key=lambda x: x.get("line", 0))
                        
                        # Get the range
                        lowest_line = all_lines[0] if all_lines else None
                        highest_line = all_lines[-1] if all_lines else None

                        # Create a key for this stat type
                        stat_key = stat_name.replace(" ", "_").replace("+", "_")

                        # Store the prop with all lines
                        if stat_key not in player_props:
                            player_props[stat_key] = {
                                "marketId": market.get("id"),
                                "swishStatId": stat.get("swishStatId"),
                                "swishStatName": stat.get("name"),
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
                                "lowestLineId": lowest_line.get("id") if lowest_line else None,
                                "lowestLineOverOdds": lowest_line.get("over") if lowest_line else None,
                                "highestLine": highest_line.get("line") if highest_line else None,
                                "highestLineId": highest_line.get("id") if highest_line else None,
                                "highestLineUnderOdds": highest_line.get("under") if highest_line else None,
                            }

                # Only add players who have at least one prop type
                if player_props:
                    results.append({
                        "name": player_name,
                        "team": team_name,
                        "position": position,
                        "props": player_props
                    })

        return results

    def get_all_nba_props(self) -> Dict[str, Any]:
        """Get all NBA games and extract ALL available props for each game."""
        games = self.get_nba_games()
        all_props = {}

        print(f"Found {len(games)} NBA games")

        for idx, game in enumerate(games, 1):
            game_slug = game["slug"]
            game_name = game["name"]

            print(f"\n[{idx}/{len(games)}] Processing: {game_name}")

            sgm_data = self.get_game_sgm_props(game_slug)
            props = self.extract_all_props(sgm_data)

            # Count total stat types across all players
            stat_types = set()
            for player in props:
                stat_types.update(player.get("props", {}).keys())

            print(f"  Found {len(props)} players with {len(stat_types)} different stat types")

            all_props[game_slug] = {"game_name": game_name, "props": props}

        return all_props


def main():
    """Example usage."""
    client = StakeNBAClient()

    all_props = client.get_all_nba_props()

    with open("nba_all_props.json", "w") as f:
        json.dump(all_props, f, indent=2)

    print(f"\n{'='*60}")
    print("Summary")
    print(f"{'='*60}")

    # Collect all stat types across all games
    all_stat_types = set()
    total_players = 0
    
    for game_slug, game_data in all_props.items():
        print(f"\n{game_data['game_name']}:")
        props_list = game_data["props"]
        total_players += len(props_list)
        
        for prop in props_list[:3]:
            print(f"  {prop['name']} ({prop.get('team', 'Unknown')}):")
            for stat_key, stat_data in list(prop.get('props', {}).items())[:3]:
                all_stat_types.add(stat_data['swishStatName'])
                print(f"    {stat_data['swishStatName']}: Lines {stat_data['lowestLine']}-{stat_data['highestLine']}")

    print(f"\n{'='*60}")
    print(f"Total Games: {len(all_props)}")
    print(f"Total Players: {total_players}")
    print(f"Unique Stat Types Found: {len(all_stat_types)}")
    print(f"\nAll Stat Types:")
    for stat_type in sorted(all_stat_types):
        print(f"  - {stat_type}")
    print(f"\n✅ Full data saved to nba_all_props.json")


if __name__ == "__main__":
    main()
