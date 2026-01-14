# Stake.com Sports Betting Props Analyzer

A Python tool that scrapes player props from Stake.com, analyzes them against historical stats, and generates optimized parlay tickets with high-probability picks.

## 🎯 Features

- **Scrapes live props** from Stake.com's GraphQL API
- **Analyzes historical performance** using official NBA/NHL APIs
- **7-game lookback** for recent form analysis
- **Smart scoring algorithm** (0-100) based on:
  - Historical hit rate (35%)
  - Recent hit rate (25%)
  - Line vs average (20%)
  - Consistency (15%)
  - Sample size (5%)
- **Diverse ticket generation** - no duplicate props across tickets
- **Multiple sports support**: NBA (complete), NHL (complete), NFL (WIP)

## 📋 Requirements

- Python 3.10+
- Virtual environment with dependencies

## 🚀 Quick Start

### 1. Clone and Setup

```bash
git clone https://github.com/yourusername/stake_dot_com_bot.git
cd stake_dot_com_bot
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Get Cloudflare Cookies

You need to get cookies from a logged-in Stake.com session:

1. Open Stake.com in your browser and log in
2. Open Developer Tools (F12) → Network tab
3. Find any request to `stake.com/_api/graphql`
4. Copy the cookies and save to `cloudflare_cookies.json`:

```json
{
  "cookies": {
    "cf_clearance": "your_cf_clearance_value",
    "__cf_bm": "your_cf_bm_value",
    "session": "your_session_value"
  }
}
```

### 3. Run for NBA

```bash
# Step 1: Scrape today's props
python stake_nba_scraper.py

# Step 2: Analyze props against historical data
python nba_comprehensive_analyzer.py

# Step 3: Generate tickets
python nba_ticket_generator_4games.py

# To do all the steps
python ./run_nba.py
```

### 4. Run for NHL

```bash
# Step 1: Scrape today's props
python stake_nhl_scraper.py

# Step 2: Analyze props against historical data
python nhl_recommendations_analyzer.py

# Step 3: Generate tickets
python nhl_ticket_generator.py
```

## 📁 Project Structure

```
stake_dot_com_bot/
├── stake_nba_scraper.py          # Scrapes NBA props from Stake.com
├── stake_nhl_scraper.py          # Scrapes NHL props from Stake.com
├── nba_comprehensive_analyzer.py # Analyzes NBA props with 7-game lookback
├── nhl_recommendations_analyzer.py # Analyzes NHL props with historical stats
├── nba_ticket_generator_4games.py # Generates 5 NBA tickets (4 games each)
├── nhl_ticket_generator.py       # Generates 3 NHL tickets
├── cloudflare_cookies.json       # Your Stake.com session cookies
├── tickets_dir/                  # Generated tickets output
│   ├── nba_ticket_1/
│   │   ├── ticket.txt            # Human-readable ticket
│   │   └── betPrePlacementStore.json # Machine-readable format
│   └── ...
├── output/                       # Analysis logs and outputs
├── archive/                      # Old/deprecated files
├── wip/                          # Work in progress (NFL)
└── venv/                         # Python virtual environment
```

## ⚙️ Configuration

### Ticket Generator Settings

In `nba_ticket_generator_4games.py`:

```python
generate_tickets(
    num_tickets=5,        # Number of tickets to generate
    games_per_ticket=4,   # Games per ticket
    picks_per_game=6      # Base picks per game (6-7 randomly)
)
```

### Analysis Thresholds

Strong props require:

- **Score ≥ 70** (out of 100)
- **Recent hits ≥ 5/7** (hit in 5 of last 7 games)

## 📊 Output Files

After running the scraper and analyzer:

- `nba_all_props.json` - All scraped props with lines and odds
- `nba_comprehensive_recommendations.json` - Analyzed props with scores
- `tickets_dir/nba_ticket_X/ticket.txt` - Human-readable ticket
- `tickets_dir/nba_ticket_X/betPrePlacementStore.json` - For automated betting

## 🔧 Troubleshooting

### "Player not found in NBA API"

Some players (especially rookies) may not be in the NBA API database yet. These are skipped automatically.

### "No games found"

Check if your `cloudflare_cookies.json` is valid. Cookies expire and need to be refreshed.

### Rate Limiting

The analyzer includes 0.6s delays between API calls. If you get blocked, increase the delay in `nba_comprehensive_analyzer.py`.

## 📝 Notes

- Cookies expire periodically - refresh them if you get errors
- The system uses the **2025-26 season** data
- Props are analyzed against last 7 games for recency
- Tickets avoid duplicate props across all generated tickets

## ⚠️ Disclaimer

This tool is for educational purposes only. Sports betting involves risk. Always gamble responsibly.

## 🏗️ Work In Progress

- **NFL Support** - Scraper started but incomplete (see `wip/` folder)

## 📜 License

MIT License
