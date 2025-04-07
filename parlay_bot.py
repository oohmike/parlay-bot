import discord
from discord.ext import commands, tasks
import requests
import sqlite3
from datetime import datetime
import itertools
import math

# Initialize Discord bot
bot = commands.Bot(command_prefix='!')

# Set up SQLite database
conn = sqlite3.connect('parlays.db')
cursor = conn.cursor()
cursor.execute('''
CREATE TABLE IF NOT EXISTS parlays (
    id INTEGER PRIMARY KEY,
    date TEXT,
    platform TEXT,
    bets TEXT,
    odds REAL,
    hit_rate REAL,
    outcome TEXT
)
''')
conn.commit()

# Odds conversion functions
def american_to_decimal(odds):
    """Convert American odds to decimal odds."""
    if odds > 0:
        return 1 + (odds / 100)
    else:
        return 1 - (100 / odds)

def decimal_to_american(decimal):
    """Convert decimal odds to American odds."""
    if decimal >= 2:
        return (decimal - 1) * 100
    else:
        return -100 / (decimal - 1)

# Fetch odds from OddsAPI
def fetch_odds(api_key, sport, bookmaker):
    """Retrieve odds for a given sport and bookmaker."""
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/?apiKey={api_key}&regions=us&markets=h2h&bookmakers={bookmaker}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching odds: {e}")
        return None

# Placeholder for probability estimation (replace with real models)
def estimate_probability(bet):
    """Estimate the true probability of a bet winning."""
    # TODO: Replace with machine learning/statistical model
    return 0.6  # Dummy value for now

# Select the best parlay for a platform
def select_parlay(odds_data, bookmaker):
    """Choose a parlay with up to 5 picks, odds >= +1000, maximizing hit rate."""
    bets = []
    for event in odds_data:
        for market in event['bookmakers']:
            if market['key'] == bookmaker:
                for outcome in market['markets'][0]['outcomes']:
                    p_i = estimate_probability(outcome)
                    d_i = american_to_decimal(outcome['price'])
                    bets.append({
                        'name': f"{event['home_team']} vs {event['away_team']} - {outcome['name']}",
                        'p_i': p_i,
                        'd_i': d_i,
                        'odds': outcome['price']
                    })
    
    max_hit_rate = 0
    best_combination = None
    for r in range(1, 6):  # 1 to 5 picks
        for combo in itertools.combinations(bets, r):
            p_product = math.prod(bet['p_i'] for bet in combo)
            d_product = math.prod(bet['d_i'] for bet in combo)
            if d_product >= 11.0 and p_product > max_hit_rate:
                max_hit_rate = p_product
                best_combination = combo
    
    if best_combination:
        parlay_odds = decimal_to_american(math.prod(bet['d_i'] for bet in best_combination))
        return {
            'bets': [bet['name'] for bet in best_combination],
            'odds': parlay_odds,
            'hit_rate': max_hit_rate
        }
    return None

# Command to generate parlays
@bot.command()
async def generate_parlay(ctx):
    """Generate and send daily parlays for DraftKings and FanDuel."""
    api_key = 'YOUR_ODDS_API_KEY'  # Replace with your OddsAPI key
    sports = ['basketball_nba', 'americanfootball_nfl', 'baseball_mlb', 'mma_mixed_martial_arts']
    parlays = {}
    
    for bookmaker in ['draftkings', 'fanduel']:
        all_odds = []
        for sport in sports:
            odds_data = fetch_odds(api_key, sport, bookmaker)
            if odds_data:
                all_odds.extend(odds_data)
        parlay = select_parlay(all_odds, bookmaker)
        if parlay:
            parlays[bookmaker] = parlay
            # Log to database
            cursor.execute('INSERT INTO parlays (date, platform, bets, odds, hit_rate, outcome) VALUES (?, ?, ?, ?, ?, ?)',
                           (datetime.now().strftime('%Y-%m-%d'), bookmaker, ','.join(parlay['bets']), parlay['odds'], parlay['hit_rate'], 'pending'))
            conn.commit()
    
    # Format and send message
    message = "Today's Parlays:\n\n"
    for platform, parlay in parlays.items():
        message += f"**{platform.capitalize()} Parlay:**\n"
        for i, bet in enumerate(parlay['bets'], 1):
            message += f"{i}. {bet}\n"
        message += f"Odds: {parlay['odds']}\nEstimated Hit Rate: {parlay['hit_rate']:.2%}\n\n"
        message += "Add these bets to your parlay slip manually on {platform.capitalize()}.\n\n"
    if not parlays:
        message = "No suitable parlays found today."
    await ctx.send(message)

# Command to view history
@bot.command()
async def history(ctx):
    """Display the 10 most recent parlays and their outcomes."""
    cursor.execute('SELECT * FROM parlays ORDER BY date DESC LIMIT 10')
    rows = cursor.fetchall()
    message = "Recent Parlays:\n\n"
    for row in rows:
        message += f"**Date**: {row[1]}, **Platform**: {row[2]}\n"
        message += f"**Odds**: {row[4]}, **Hit Rate**: {row[5]:.2%}, **Outcome**: {row[6]}\n"
        message += f"**Bets**: {row[3]}\n\n"
    if not rows:
        message = "No parlay history available yet."
    await ctx.send(message)

# Placeholder for updating outcomes
def update_outcomes():
    """Update parlay outcomes based on game results."""
    # TODO: Fetch game results via API, match with bets, update database
    pass

# Schedule daily outcome updates
@tasks.loop(hours=24)
async def daily_update():
    """Run daily task to update parlay outcomes."""
    update_outcomes()

@daily_update.before_loop
async def before_daily_update():
    await bot.wait_until_ready()

daily_update.start()

# Run the bot
import os

TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise ValueError("DISCORD_TOKEN environment variable not set.")

bot.run(TOKEN)
 # Replace with your Discord bot token
