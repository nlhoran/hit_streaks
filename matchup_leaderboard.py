import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import requests
import time
import os
import json

# Set page configuration
st.set_page_config(
    page_title="MLB Matchup Leaderboard",
    page_icon="⚾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# App title 
st.title("⚾ MLB Batter vs. Pitcher Matchups")
st.markdown("Find the best batter vs. pitcher matchups for any MLB game day")

# RapidAPI settings - You'll need to fill these in
RAPIDAPI_KEY = st.secrets.get("RAPIDAPI_KEY", "")  # Store in Streamlit secrets
RAPIDAPI_HOST = "tank01-mlb-live-in-game-real-time-statistics.p.rapidapi.com"

# Cache directory for data
CACHE_DIR = "mlb_matchup_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

# Initialize session state for caching
if "matchup_data" not in st.session_state:
    st.session_state.matchup_data = None
if "last_update" not in st.session_state:
    st.session_state.last_update = None

# Display API key status
if not RAPIDAPI_KEY:
    st.warning("⚠️ RapidAPI key not configured. Please add your key to Streamlit secrets.")
    st.markdown("""
    To use this app:
    1. Sign up for [RapidAPI](https://rapidapi.com/)
    2. Subscribe to the [Tank01 MLB API](https://rapidapi.com/tank01/api/tank01-mlb-live-in-game-real-time-statistics/)
    3. Add your API key to the Streamlit secrets file (.streamlit/secrets.toml)
    """)

# Add debug mode toggle
debug_mode = st.sidebar.checkbox("Debug Mode")

def fetch_from_rapidapi(endpoint, params=None):
    """Fetch data from Tank01 MLB API with caching and rate limiting"""
    if not RAPIDAPI_KEY:
        st.error("RapidAPI key not configured")
        return None
        
    # Create cache key based on endpoint and params
    param_str = "_".join([f"{k}_{v}" for k, v in (params or {}).items()])
    cache_key = f"{endpoint}_{param_str}"
    cache_file = os.path.join(CACHE_DIR, f"{cache_key.replace('/', '_')}.json")
    
    # Check if cache exists and is recent (less than 6 hours old)
    if os.path.exists(cache_file):
        file_modified_time = os.path.getmtime(cache_file)
        if (time.time() - file_modified_time) < (6 * 3600):  # 6 hours
            try:
                with open(cache_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                if debug_mode:
                    st.warning(f"Error reading cache: {str(e)}")
    
    # Rate limiting: check if we're making too many API calls
    # Initialize API call counter in session state if needed
    if "api_call_count" not in st.session_state:
        st.session_state.api_call_count = 0
        st.session_state.api_call_reset_time = time.time() + 60  # Reset after 1 minute
    
    # Check if we should reset the counter
    current_time = time.time()
    if current_time > st.session_state.api_call_reset_time:
        st.session_state.api_call_count = 0
        st.session_state.api_call_reset_time = current_time + 60  # Reset after 1 minute
    
    # Check if we're over the limit (20 calls per minute for Basic plan)
    # Using 18 to be safe
    MAX_CALLS_PER_MINUTE = 18
    
    if st.session_state.api_call_count >= MAX_CALLS_PER_MINUTE:
        if debug_mode:
            st.sidebar.warning(f"⚠️ Rate limit reached ({st.session_state.api_call_count} calls in the last minute). Using cached data or waiting.")
        
        # If this is a critical endpoint, wait and retry
        critical_endpoints = ["getMLBTeams", "getMLBGamesForDate"]
        if endpoint in critical_endpoints:
            if debug_mode:
                st.sidebar.info("Critical endpoint, waiting for rate limit reset...")
            
            # Wait until reset
            sleep_time = st.session_state.api_call_reset_time - current_time
            if sleep_time > 0:
                time.sleep(sleep_time)
                
            # Reset counter
            st.session_state.api_call_count = 0
            st.session_state.api_call_reset_time = time.time() + 60
        else:
            # For non-critical endpoints, return cached data or None
            return None
    
    # Increment API call counter
    st.session_state.api_call_count += 1
    
    # Prepare request with the correct endpoint format
    url = f"https://{RAPIDAPI_HOST}/{endpoint}"
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": RAPIDAPI_HOST
    }
    
    try:
        if debug_mode:
            st.sidebar.markdown(f"Calling API ({st.session_state.api_call_count}/{MAX_CALLS_PER_MINUTE}): {url}")
            st.sidebar.markdown(f"Params: {params}")
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        if debug_mode:
            st.sidebar.markdown(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            # Save to cache
            with open(cache_file, 'w') as f:
                json.dump(data, f)
                
            return data
        elif response.status_code == 429:  # Too Many Requests
            if debug_mode:
                st.sidebar.error("📛 API Rate Limit Exceeded (429). Waiting...")
            
            # Wait for a minute
            time.sleep(60)
            
            # Reset counter
            st.session_state.api_call_count = 0
            st.session_state.api_call_reset_time = time.time() + 60
            
            # Try again (recursively)
            return fetch_from_rapidapi(endpoint, params)
        else:
            if debug_mode:
                st.sidebar.error(f"API returned status code {response.status_code}: {response.text}")
            return None
    except Exception as e:
        if debug_mode:
            st.sidebar.error(f"Error fetching data: {str(e)}")
        return None

def get_games_for_date(date=None):
    """Get scheduled MLB games for a specific date"""
    # Use provided date or default to today
    if date is None:
        date = datetime.now()
        
    date_str = date.strftime('%Y%m%d')
    
    # Using Tank01 API's game endpoint
    endpoint = "getMLBGamesForDate"
    params = {
        "gameDate": date_str
    }
    
    if debug_mode:
        st.sidebar.markdown(f"Fetching games for date: {date_str}")
        
    games_data = fetch_from_rapidapi(endpoint, params)
    
    if debug_mode:
        if games_data:
            st.sidebar.markdown(f"API Response Status: {games_data.get('statusCode')}")
            if games_data.get('body'):
                st.sidebar.markdown(f"Found {len(games_data.get('body', []))} games for {date.strftime('%Y-%m-%d')}")
                # Show first game details to verify structure
                if len(games_data.get('body', [])) > 0:
                    first_game = games_data.get('body')[0]
                    st.sidebar.markdown("First game data structure:")
                    st.sidebar.json(first_game)
            else:
                st.sidebar.markdown(f"No games found for {date.strftime('%Y-%m-%d')}")
        else:
            st.sidebar.markdown("No response from games API")
    
    return games_data

def get_teams_data():
    """Get all MLB teams data - might be needed to get team ID for roster queries"""
    # Cache this data since it won't change frequently
    if "teams_data" in st.session_state and st.session_state.teams_data:
        return st.session_state.teams_data
    
    endpoint = "getMLBTeams"
    params = {}  # No parameters needed
    
    if debug_mode:
        st.sidebar.markdown("Fetching all MLB teams data")
    
    teams_data = fetch_from_rapidapi(endpoint, params)
    
    if teams_data and teams_data.get("statusCode") == 200:
        if debug_mode:
            st.sidebar.markdown(f"Successfully fetched MLB teams data")
            if teams_data.get("body"):
                st.sidebar.markdown(f"Found {len(teams_data.get('body'))} teams")
                # Display first team as example
                if len(teams_data.get("body")) > 0:
                    first_team = teams_data.get("body")[0]
                    st.sidebar.markdown(f"Sample team: {first_team.get('city', '')} {first_team.get('nickname', '')} ({first_team.get('abbreviation', '')})")
            
        st.session_state.teams_data = teams_data
        return teams_data
    else:
        if debug_mode:
            st.sidebar.markdown("Failed to fetch MLB teams data")
            if teams_data:
                st.sidebar.markdown(f"Status code: {teams_data.get('statusCode')}")
                if teams_data.get('error'):
                    st.sidebar.markdown(f"Error: {teams_data.get('error')}")
        return None

def get_team_id_from_abbreviation(team_code):
    """Get team ID from team abbreviation"""
    teams_data = get_teams_data()
    
    if not teams_data or not teams_data.get("body"):
        if debug_mode:
            st.sidebar.markdown(f"No teams data available to lookup ID for {team_code}")
        return None
    
    # Look for the team with matching abbreviation
    for team in teams_data.get("body", []):
        if team.get("abbreviation") == team_code:
            team_id = team.get("teamID")
            if debug_mode:
                st.sidebar.markdown(f"Found team ID {team_id} for {team_code}")
            return team_id
    
    if debug_mode:
        st.sidebar.markdown(f"Could not find team ID for {team_code}")
    return None

def get_team_roster(team_code):
    """Get roster for a team using documented format"""
    # According to documentation, need either teamAbv or teamID
    endpoint = "getMLBTeamRoster"
    
    # First try with team abbreviation (exactly as documented)
    params = {
        "teamAbv": team_code,  # This is the documented parameter name
        "statsToGet": "true"   # Get stats for each player
    }
    
    if debug_mode:
        st.sidebar.markdown(f"Getting roster for {team_code} using documented params")
    
    roster_data = fetch_from_rapidapi(endpoint, params)
    
    # Check if the call was successful
    if roster_data and roster_data.get("statusCode") == 200:
        if debug_mode:
            if roster_data.get("body") and roster_data.get("body").get("roster"):
                roster = roster_data.get("body", {}).get("roster", [])
                st.sidebar.markdown(f"✅ Success! Found {len(roster)} players")
                
                # Show a sample player if available
                if len(roster) > 0:
                    st.sidebar.markdown(f"Sample player: {roster[0].get('longName', roster[0].get('playerID', 'Unknown'))}")
            elif roster_data.get("error"):
                st.sidebar.markdown(f"⚠️ API returned error: {roster_data.get('error')}")
            else:
                st.sidebar.markdown("⚠️ API returned empty roster")
        
        return roster_data
    elif debug_mode:
        st.sidebar.markdown(f"❌ Failed to get roster for {team_code}")
        if roster_data:
            if roster_data.get("error"):
                st.sidebar.markdown(f"Error: {roster_data.get('error')}")
    
    # If that failed, try with team ID if we can get it
    team_id = get_team_id_from_abbreviation(team_code)
    
    if team_id:
        if debug_mode:
            st.sidebar.markdown(f"Trying with teamID={team_id}")
            
        params = {
            "teamID": team_id,
            "statsToGet": "true"
        }
        
        roster_data = fetch_from_rapidapi(endpoint, params)
        
        if roster_data and roster_data.get("statusCode") == 200:
            if debug_mode:
                if roster_data.get("body") and roster_data.get("body").get("roster"):
                    roster = roster_data.get("body", {}).get("roster", [])
                    st.sidebar.markdown(f"✅ Success with teamID! Found {len(roster)} players")
                    
                    # Show a sample player if available
                    if len(roster) > 0:
                        st.sidebar.markdown(f"Sample player: {roster[0].get('longName', roster[0].get('playerID', 'Unknown'))}")
                elif roster_data.get("error"):
                    st.sidebar.markdown(f"⚠️ API returned error: {roster_data.get('error')}")
                else:
                    st.sidebar.markdown("⚠️ API returned empty roster")
            return roster_data
    
    # As a last resort, return minimal data
    if debug_mode:
        st.sidebar.markdown(f"All roster attempts failed for {team_code}, using fallback")
    
    return {
        "statusCode": 200,
        "body": {"roster": []}
    }

# No longer needed - we get pitchers directly from game data

def get_batter_vs_pitcher(batter_id, pitcher_id):
    """Get batter vs pitcher matchup data"""
    # Create a cache key for this matchup
    cache_key = f"{batter_id}_{pitcher_id}"
    
    # Check if we've already tried this matchup
    if "matchup_cache" not in st.session_state:
        st.session_state.matchup_cache = {}
    
    if cache_key in st.session_state.matchup_cache:
        return st.session_state.matchup_cache[cache_key]
    
    # Check if we've already fetched all matchup data for this batter
    batter_cache_key = f"batter_{batter_id}"
    if batter_cache_key not in st.session_state.matchup_cache:
        # Get all matchups for this batter against all pitchers
        if debug_mode:
            st.sidebar.markdown(f"Fetching all matchups for batter {batter_id}")
        
        endpoint = "getMLBBatterVsPitcher"
        params = {"playerID": str(batter_id)}
        
        all_matchups_data = fetch_from_rapidapi(endpoint, params)
        
        # Store in the cache
        st.session_state.matchup_cache[batter_cache_key] = all_matchups_data
    else:
        # Use cached data
        all_matchups_data = st.session_state.matchup_cache[batter_cache_key]
    
    # Now extract the specific matchup we want
    if all_matchups_data and all_matchups_data.get("statusCode") == 200 and all_matchups_data.get("body"):
        # The response might contain all matchups for this batter
        matchups = all_matchups_data.get("body")
        
        if debug_mode:
            st.sidebar.markdown(f"Looking for pitcher {pitcher_id} in batter {batter_id}'s matchups")
            if isinstance(matchups, dict) and "opponents" in matchups:
                st.sidebar.markdown(f"Found {len(matchups['opponents'])} opponent matchups for batter {batter_id}")
                # Display a sample opponent to see the structure
                if len(matchups['opponents']) > 0:
                    st.sidebar.markdown("Sample opponent data structure:")
                    st.sidebar.json(matchups['opponents'][0])
            elif isinstance(matchups, dict):
                st.sidebar.markdown(f"Matchup data structure: {list(matchups.keys())}")
        
        # Try to find the matchup with this pitcher
        # Based on the actual response structure
        pitcher_matchup = None
        
        # Structure: { playerID: "123", opponents: [{ playerID: "456", stats: {...} }] }
        if isinstance(matchups, dict) and "opponents" in matchups:
            opponents = matchups.get("opponents", [])
            for opponent in opponents:
                if str(opponent.get("playerID")) == str(pitcher_id):
                    pitcher_matchup = opponent
                    break
        
        # If we found the matchup
        if pitcher_matchup:
            stats = pitcher_matchup.get("stats", {})
            
            if debug_mode:
                # Using correct field names from the API response
                at_bats = stats.get("AB", 0)
                hits = stats.get("H", 0)
                avg = stats.get("AVG", "0.000")
                st.sidebar.markdown(f"✅ Found matchup: Batter {batter_id} vs Pitcher {pitcher_id}: AB={at_bats}, H={hits}, AVG={avg}")
            
            # No need to change the structure - just pass through the stats as is
            result = {
                "statusCode": 200,
                "body": {"stats": stats}
            }
            
            # Cache this result
            st.session_state.matchup_cache[cache_key] = result
            return result
        elif debug_mode:
            st.sidebar.markdown(f"❌ No matchup found between batter {batter_id} and pitcher {pitcher_id}")
    elif debug_mode:
        if all_matchups_data and all_matchups_data.get("error"):
            st.sidebar.markdown(f"⚠️ API error: {all_matchups_data.get('error')}")
            st.sidebar.json(all_matchups_data)
        else:
            st.sidebar.markdown("⚠️ No matchup data returned")
    
    # Create a fake result with minimal stats so the app can continue
    # Using the correct field names from the API
    empty_result = {
        "statusCode": 200,
        "body": {"stats": {"AB": "0", "H": "0", "AVG": "0.000", "HR": "0", "2B": "0", "3B": "0"}}
    }
    
    # Cache this empty result to avoid redundant API calls
    st.session_state.matchup_cache[cache_key] = empty_result
    return empty_result

def process_matchups(game_date=None):
    """Process all matchups for the specified date"""
    if game_date is None:
        game_date = datetime.now()
    
    # Progress status
    status_placeholder = st.empty()
    status_placeholder.info(f"Getting games for {game_date.strftime('%A, %B %d, %Y')}...")
    
    games_data = get_games_for_date(game_date)
    if not games_data or not games_data.get("body"):
        if debug_mode:
            st.warning(f"No games found for {game_date.strftime('%Y-%m-%d')} or API error")
        return []
    
    # Show progress on how many games were found    
    games = games_data.get("body", [])
    status_placeholder.info(f"Found {len(games)} games. Processing...")
        
    # If there are too many games, limit the search to keep within rate limits
    MAX_GAMES_TO_PROCESS = 6
    if len(games) > MAX_GAMES_TO_PROCESS:
        if debug_mode:
            st.warning(f"⚠️ Limiting to {MAX_GAMES_TO_PROCESS} games due to API rate limits")
        games = games[:MAX_GAMES_TO_PROCESS]
    
    all_matchups = []
    progress_bar = st.progress(0)
    progress_text = st.empty()
    
    # Extract games
    games = games_data.get("body", [])
    total_games = len(games)
    
    for i, game in enumerate(games):
        progress = (i / total_games)
        progress_bar.progress(progress)
        
        # The structure here depends on the actual API response
        home_team = game.get("homeTeam", {})
        away_team = game.get("awayTeam", {})
        
        # Extract and format team information
        home_team_code = home_team.get("abbreviation") or game.get("home")
        away_team_code = away_team.get("abbreviation") or game.get("away")
        
        home_team_name = home_team.get("name") or home_team_code
        away_team_name = away_team.get("name") or away_team_code
        
        progress_text.text(f"Processing game {i+1} of {total_games}: {away_team_name} @ {home_team_name}")
        
        # Extract probable pitchers directly from the game data
        probable_pitchers = game.get("probableStartingPitchers", {})
        
        if debug_mode:
            st.sidebar.markdown(f"Game ID: {game.get('gameID')}")
            st.sidebar.markdown(f"Probable pitchers field: {probable_pitchers}")
        
        # Extract home and away pitcher IDs
        home_pitcher_id = probable_pitchers.get("home")
        away_pitcher_id = probable_pitchers.get("away")
        
        if debug_mode:
            st.sidebar.markdown(f"Home pitcher ID: {home_pitcher_id}")
            st.sidebar.markdown(f"Away pitcher ID: {away_pitcher_id}")
        
        # If we don't have probable pitchers, skip this game
        if not home_pitcher_id or not away_pitcher_id:
            progress_text.text(f"Skipping game (no probable pitchers): {away_team_name} @ {home_team_name}")
            if debug_mode:
                st.sidebar.markdown(f"Skipping game due to missing pitcher(s): {away_team_name} @ {home_team_name}")
            continue
            
        # Get roster data
        if debug_mode:
            st.sidebar.markdown(f"Getting roster for home team: {home_team_code}")
        
        home_roster_data = get_team_roster(home_team_code)
        
        if debug_mode:
            st.sidebar.markdown(f"Getting roster for away team: {away_team_code}")
        
        away_roster_data = get_team_roster(away_team_code)
        
        # Debug roster information
        if debug_mode:
            # Check home roster
            if home_roster_data and home_roster_data.get("statusCode") == 200:
                if home_roster_data.get("body") and home_roster_data.get("body").get("roster"):
                    roster = home_roster_data.get("body").get("roster", [])
                    st.sidebar.markdown(f"Home roster players: {len(roster)}")
                    if len(roster) > 0:
                        st.sidebar.markdown(f"Sample home player: {roster[0].get('longName', roster[0].get('playerID', 'Unknown'))}")
                        # Show first player's structure for debugging
                        st.sidebar.markdown("Sample home player structure:")
                        st.sidebar.json(roster[0])
                elif home_roster_data.get("error"):
                    st.sidebar.markdown(f"⚠️ Home roster error: {home_roster_data.get('error')}")
                else:
                    st.sidebar.markdown(f"⚠️ Home roster empty for {home_team_code}")
            else:
                st.sidebar.markdown(f"❌ No valid home roster data for {home_team_code}")
                
            # Check away roster
            if away_roster_data and away_roster_data.get("statusCode") == 200:
                if away_roster_data.get("body") and away_roster_data.get("body").get("roster"):
                    roster = away_roster_data.get("body").get("roster", [])
                    st.sidebar.markdown(f"Away roster players: {len(roster)}")
                    if len(roster) > 0:
                        st.sidebar.markdown(f"Sample away player: {roster[0].get('longName', roster[0].get('playerID', 'Unknown'))}")
                elif away_roster_data.get("error"):
                    st.sidebar.markdown(f"⚠️ Away roster error: {away_roster_data.get('error')}")
                else:
                    st.sidebar.markdown(f"⚠️ Away roster empty for {away_team_code}")
            else:
                st.sidebar.markdown(f"❌ No valid away roster data for {away_team_code}")
        
        # Find home pitcher name from roster - using correct structure based on docs
        home_pitcher_name = "Unknown Pitcher"
        if (home_roster_data and home_roster_data.get("body") and 
            home_roster_data.get("body").get("roster")):
            
            roster = home_roster_data.get("body").get("roster", [])
            for player in roster:
                if player.get("playerID") == home_pitcher_id:
                    home_pitcher_name = player.get("longName", "Unknown Pitcher")
                    break
                    
            if debug_mode and home_pitcher_name == "Unknown Pitcher":
                st.sidebar.markdown(f"❌ Could not find home pitcher {home_pitcher_id} in roster")
                    
        # Find away pitcher name from roster
        away_pitcher_name = "Unknown Pitcher"
        if (away_roster_data and away_roster_data.get("body") and 
            away_roster_data.get("body").get("roster")):
            
            roster = away_roster_data.get("body").get("roster", [])
            for player in roster:
                if player.get("playerID") == away_pitcher_id:
                    away_pitcher_name = player.get("longName", "Unknown Pitcher")
                    break
                    
            if debug_mode and away_pitcher_name == "Unknown Pitcher":
                st.sidebar.markdown(f"❌ Could not find away pitcher {away_pitcher_id} in roster")
        
        # Check if lineup data is available
        has_lineup_data = False
        probable_lineups = game.get("probableStartingLineups", {})
        if probable_lineups and probable_lineups.get("away") and probable_lineups.get("home"):
            has_lineup_data = len(probable_lineups.get("away", [])) > 0 and len(probable_lineups.get("home", [])) > 0
        
        if debug_mode:
            st.sidebar.markdown(f"Lineup data available: {has_lineup_data}")
        
        # Process batters - either from lineup (if available) or from full roster
        # Create sets of lineup player IDs for easier lookup later
        lineup_player_ids = set()
        
        if has_lineup_data:
            # Add all lineup player IDs to the set
            for player in probable_lineups.get("away", []):
                if player.get("playerID"):
                    lineup_player_ids.add(player.get("playerID"))
            
            for player in probable_lineups.get("home", []):
                if player.get("playerID"):
                    lineup_player_ids.add(player.get("playerID"))
                    
            # Process away lineup batters vs home pitcher
            away_lineup = probable_lineups.get("away", [])
            for lineup_slot in away_lineup:
                batter_id = lineup_slot.get("playerID")
                
                if not batter_id:
                    continue
                
                # Find batter name from roster - using correct structure
                batter_name = "Unknown Batter"
                if (away_roster_data and away_roster_data.get("body") and 
                    away_roster_data.get("body").get("roster")):
                    
                    roster = away_roster_data.get("body").get("roster", [])
                    for player in roster:
                        if player.get("playerID") == batter_id:
                            batter_name = player.get("longName", "Unknown Batter")
                            break
                
                process_matchup(batter_id, batter_name, home_pitcher_id, home_pitcher_name, 
                               away_team_name, away_team_code, home_team_name, home_team_code,
                               game.get("gameTime", ""), all_matchups, True)
            
            # Process home lineup batters vs away pitcher
            home_lineup = probable_lineups.get("home", [])
            for lineup_slot in home_lineup:
                batter_id = lineup_slot.get("playerID")
                
                if not batter_id:
                    continue
                
                # Find batter name from roster - using correct structure
                batter_name = "Unknown Batter"
                if (home_roster_data and home_roster_data.get("body") and 
                    home_roster_data.get("body").get("roster")):
                    
                    roster = home_roster_data.get("body").get("roster", [])
                    for player in roster:
                        if player.get("playerID") == batter_id:
                            batter_name = player.get("longName", "Unknown Batter")
                            break
                
                process_matchup(batter_id, batter_name, away_pitcher_id, away_pitcher_name, 
                               home_team_name, home_team_code, away_team_name, away_team_code,
                               game.get("gameTime", ""), all_matchups, True)
        else:
            # Process all away team batters vs home pitcher
            if (away_roster_data and away_roster_data.get("body") and 
                away_roster_data.get("body").get("roster")):
                # Filter out pitchers from the roster
                roster = away_roster_data.get("body").get("roster", [])
                all_away_batters = [p for p in roster if p.get("primaryPosition") != "P"]
                
                # Limit batters per team to control API usage
                MAX_BATTERS_PER_TEAM = 10
                if len(all_away_batters) > MAX_BATTERS_PER_TEAM:
                    if debug_mode:
                        st.sidebar.warning(f"⚠️ Limiting to {MAX_BATTERS_PER_TEAM} batters due to API rate limits")
                    away_batters = all_away_batters[:MAX_BATTERS_PER_TEAM]
                else:
                    away_batters = all_away_batters
                
                for batter in away_batters:
                    batter_id = batter.get("playerID")
                    batter_name = batter.get("longName", "")
                    
                    if not batter_id:
                        continue
                    
                    in_lineup = batter_id in lineup_player_ids if has_lineup_data else False
                    
                    process_matchup(batter_id, batter_name, home_pitcher_id, home_pitcher_name, 
                                   away_team_name, away_team_code, home_team_name, home_team_code,
                                   game.get("gameTime", ""), all_matchups, in_lineup)
            
            # Process all home team batters vs away pitcher
            if (home_roster_data and home_roster_data.get("body") and 
                home_roster_data.get("body").get("roster")):
                # Filter out pitchers from the roster
                roster = home_roster_data.get("body").get("roster", [])
                all_home_batters = [p for p in roster if p.get("primaryPosition") != "P"]
                
                # Limit batters per team to control API usage
                MAX_BATTERS_PER_TEAM = 10
                if len(all_home_batters) > MAX_BATTERS_PER_TEAM:
                    if debug_mode:
                        st.sidebar.warning(f"⚠️ Limiting to {MAX_BATTERS_PER_TEAM} batters due to API rate limits")
                    home_batters = all_home_batters[:MAX_BATTERS_PER_TEAM]
                else:
                    home_batters = all_home_batters
                
                for batter in home_batters:
                    batter_id = batter.get("playerID")
                    batter_name = batter.get("longName", "")
                    
                    if not batter_id:
                        continue
                    
                    in_lineup = batter_id in lineup_player_ids if has_lineup_data else False
                    
                    process_matchup(batter_id, batter_name, away_pitcher_id, away_pitcher_name, 
                                   home_team_name, home_team_code, away_team_name, away_team_code,
                                   game.get("gameTime", ""), all_matchups, in_lineup)
    
    # Clear progress indicators
    progress_bar.empty()
    progress_text.empty()

def process_matchup(batter_id, batter_name, pitcher_id, pitcher_name, 
                   team_name, team_code, opponent_name, opponent_code, 
                   game_time, all_matchups, in_lineup=False):
    """Process a single batter vs pitcher matchup and add to results if relevant"""
    # Get batter vs pitcher matchup data
    matchup_data = get_batter_vs_pitcher(batter_id, pitcher_id)
    
    if debug_mode:
        st.sidebar.markdown(f"Processing matchup: {batter_name} vs {pitcher_name}")
    
    if matchup_data and matchup_data.get("body"):
        stats = matchup_data.get("body", {}).get("stats", {})
        
        if debug_mode:
            st.sidebar.markdown(f"Matchup stats found: {stats}")
        
        try:
            # Use the correct field names from the API response
            ab = int(stats.get("AB", 0))
            
            if debug_mode:
                st.sidebar.markdown(f"At bats: {ab}")
            
            # We'll collect ALL matchups and filter later with the slider
            hits = int(stats.get("H", 0))
            avg = stats.get("AVG", "0.000")
            hr = int(stats.get("HR", 0))
            
            if debug_mode:
                st.sidebar.markdown(f"✅ Adding matchup: {batter_name} ({hits}/{ab}, {avg})")
            
            # Add to matchups list
            all_matchups.append({
                "Batter": batter_name,
                "Batter ID": batter_id,
                "Pitcher": pitcher_name,
                "Pitcher ID": pitcher_id,
                "Team": team_name,
                "Team Code": team_code,
                "Opponent": opponent_name,
                "Opponent Code": opponent_code,
                "AB": ab,
                "H": hits,
                "HR": hr,
                "AVG": avg,
                "Game Time": game_time,
                "In Lineup": in_lineup
            })
        except (ValueError, TypeError) as e:
            if debug_mode:
                st.sidebar.markdown(f"❌ Error processing stats: {str(e)}")
    else:
        if debug_mode:
            if matchup_data:
                st.sidebar.markdown(f"❌ No matchup data body: {matchup_data.get('statusCode')}")
            else:
                st.sidebar.markdown(f"❌ No matchup data returned")
    
    # Sort by batting average (descending)
    def get_avg_float(m):
        try:
            # Convert string AVG to float
            avg_str = str(m.get("AVG", "0.000"))
            if avg_str.startswith("."):
                return float("0" + avg_str)
            return float(avg_str)
        except ValueError:
            return 0.0
            
    sorted_matchups = sorted(all_matchups, key=get_avg_float, reverse=True)
    
    return sorted_matchups

# Sidebar controls
st.sidebar.header("⚙️ Settings")

# Date selection options
st.sidebar.subheader("Game Date")
date_option = st.sidebar.radio(
    "Select Game Date",
    options=["Today", "Tomorrow", "Custom Date"],
    index=0
)

# Add a date input if custom date is selected
if date_option == "Custom Date":
    selected_date = st.sidebar.date_input(
        "Select a Date",
        value=datetime.now() + timedelta(days=2),
        min_value=datetime.now(),
        max_value=datetime.now() + timedelta(days=10)
    )
    game_date = selected_date
elif date_option == "Tomorrow":
    game_date = datetime.now() + timedelta(days=1)
else:  # Today
    game_date = datetime.now()

# Show the selected date
st.sidebar.info(f"Showing matchups for: {game_date.strftime('%A, %B %d, %Y')}")

# Store the selected date in session state to avoid refresh issues
if "selected_game_date" not in st.session_state or st.session_state.selected_game_date != game_date:
    st.session_state.selected_game_date = game_date
    # Clear existing data if date changes
    st.session_state.matchup_data = None

# Other filters
st.sidebar.subheader("Matchup Filters")
min_ab = st.sidebar.slider(
    "Minimum At Bats",
    min_value=1,
    max_value=30,
    value=6,
    step=1
)

min_avg = st.sidebar.slider(
    "Minimum Batting Average",
    min_value=0.000,
    max_value=0.500,
    value=0.300,
    step=0.025,
    format="%.3f"
)

# Add a refresh button
if st.sidebar.button("🔄 Refresh Data"):
    st.session_state.matchup_data = None
    st.session_state.last_update = datetime.now()
    st.rerun()

# Main content
if RAPIDAPI_KEY:
    # Use cached data if available, otherwise fetch new data
    if st.session_state.matchup_data is None:
        with st.spinner(f"Fetching matchups for {game_date.strftime('%A, %B %d')}... (this may take a few minutes)"):
            matchups = process_matchups(game_date)
            st.session_state.matchup_data = matchups
            st.session_state.last_update = datetime.now()
    else:
        matchups = st.session_state.matchup_data
    
    # Display matchups
    if matchups:
        # Filter by user selections
        def get_avg_float(m):
            try:
                avg_str = str(m.get("AVG", "0.000"))
                if debug_mode and m.get("Batter"):
                    st.sidebar.markdown(f"Converting AVG for {m.get('Batter')}: '{avg_str}'")
                
                # Handle different formats
                if avg_str.startswith("."):
                    return float("0" + avg_str)
                # Convert string values to float
                return float(avg_str)
            except ValueError as e:
                if debug_mode:
                    st.sidebar.markdown(f"❌ Error converting AVG: {str(e)} for value: '{avg_str}'")
                return 0.0
        
        if debug_mode:
            st.sidebar.markdown(f"Total matchups before filtering: {len(matchups)}")
            if len(matchups) > 0:
                # Display first matchup as example
                st.sidebar.markdown("Sample matchup data:")
                st.sidebar.json(matchups[0])
                
            # Show AB filter results
            ab_filtered = [m for m in matchups if int(m.get("AB", 0)) >= min_ab]
            st.sidebar.markdown(f"Matchups after AB filter ({min_ab}+): {len(ab_filtered)}")
            
            # Display some examples of matches that pass the AB filter
            if len(ab_filtered) > 0 and len(ab_filtered) < 10:
                for m in ab_filtered:
                    avg_value = get_avg_float(m)
                    passes_avg = avg_value >= min_avg
                    st.sidebar.markdown(f"- {m.get('Batter')}: {m.get('AB')} AB, {m.get('AVG')} ({avg_value:.3f}) - Passes AVG filter: {passes_avg}")
                
        # Combined filter for AB and AVG    
        filtered_matchups = []
        has_valid_matchups = False
        
        for m in matchups:
            try:
                # Explicit conversion with debug output
                try:
                    ab = int(m.get("AB", 0))
                except ValueError:
                    if debug_mode:
                        st.sidebar.markdown(f"❌ AB conversion failed for {m.get('Batter')}: '{m.get('AB')}'")
                    ab = 0
                
                avg_str = str(m.get("AVG", "0.000"))
                try:
                    # Try both possible formats
                    if avg_str.startswith("."):
                        avg = float("0" + avg_str)
                    else:
                        avg = float(avg_str)
                except ValueError:
                    if debug_mode:
                        st.sidebar.markdown(f"❌ AVG conversion failed for {m.get('Batter')}: '{avg_str}'")
                    avg = 0.0
                
                # Show detailed debugging for the problematic matchup
                if debug_mode and m.get("Batter") == "Salvador Perez":
                    st.sidebar.markdown(f"⚠️ DEBUG - Salvador Perez values: AB={ab}, AVG={avg}, Raw AVG='{avg_str}'")
                    st.sidebar.markdown(f"Filter checks: AB >= {min_ab} = {ab >= min_ab}, AVG >= {min_avg} = {avg >= min_avg}")
                
                if ab >= min_ab and avg >= min_avg:
                    filtered_matchups.append(m)
                    has_valid_matchups = True
                elif debug_mode and ab >= min_ab and m.get("Batter"):
                    # Show examples that pass AB but fail AVG filter
                    st.sidebar.markdown(f"❌ {m.get('Batter')} failed AVG filter: {avg:.3f} < {min_avg:.3f}")
            except Exception as e:
                if debug_mode:
                    st.sidebar.markdown(f"❌ Error filtering: {str(e)}")
                    
        # Force display of at least one matchup for debugging
        if debug_mode and not has_valid_matchups and len(matchups) > 0:
            st.sidebar.markdown("⚠️ Forcing display of first matchup for debugging")
            filtered_matchups = [matchups[0]]
        
        if debug_mode:
            st.sidebar.markdown(f"Matchups after AVG filter ({min_avg}+): {len(filtered_matchups)}")
            
            # Display minimum AB filter settings
            st.sidebar.markdown(f"Current filter settings: {min_ab}+ ABs, {min_avg}+ AVG")
            
            # Show how many hits each player had
            ab_counts = {}
            for m in matchups:
                ab = int(m.get("AB", 0))
                if ab not in ab_counts:
                    ab_counts[ab] = 0
                ab_counts[ab] += 1
            
            st.sidebar.markdown("AB distribution:")
            for ab, count in sorted(ab_counts.items()):
                st.sidebar.markdown(f"- {ab} ABs: {count} matchups")
        
        st.subheader(f"🔥 Top Batter vs. Pitcher Matchups Today ({len(filtered_matchups)})")
        
        if filtered_matchups:
            # Convert to DataFrame for display
            df = pd.DataFrame(filtered_matchups)
            
            # Add rank column
            df.insert(0, "Rank", range(1, len(df) + 1))
            
            # Display columns
            display_cols = ["Rank", "Batter", "Team", "Pitcher", "Opponent", "AB", "H", "HR", "AVG", "In Lineup"]
            
            # Add a filter for lineup status
            show_only_in_lineup = st.checkbox("Show only confirmed lineup batters", value=False)
            if show_only_in_lineup:
                df = df[df["In Lineup"] == True]
                if len(df) == 0:
                    st.info("No confirmed lineup batters found with the current filters. Try adjusting your filters or unchecking the 'Show only confirmed lineup batters' option.")
            
            # Format the In Lineup column
            df["In Lineup"] = df["In Lineup"].apply(lambda x: "✅" if x else "")
            
            # Two-column layout
            col1, col2 = st.columns([7, 3])
            
            with col1:
                # Display the table
                st.dataframe(
                    df[display_cols],
                    use_container_width=True,
                    hide_index=True
                )
                
                # Add link to view full matchup details
                if len(filtered_matchups) > 0:
                    st.markdown("#### View More Stats")
                    selected_matchup = st.selectbox(
                        "Select a matchup to view detailed stats:",
                        options=[f"{m['Batter']} vs {m['Pitcher']} ({m['AVG']})" for m in filtered_matchups],
                        index=0
                    )
                    
                    # Get the selected matchup
                    selected_index = [f"{m['Batter']} vs {m['Pitcher']} ({m['AVG']})" for m in filtered_matchups].index(selected_matchup)
                    matchup = filtered_matchups[selected_index]
                    
                    # Show detailed stats
                    st.markdown(f"### {matchup['Batter']} vs {matchup['Pitcher']}")
                    
                    stat_cols = st.columns(4)
                    with stat_cols[0]:
                        st.metric("At Bats", matchup['AB'])
                    with stat_cols[1]:
                        st.metric("Hits", matchup['H'])
                    with stat_cols[2]:
                        st.metric("Home Runs", matchup['HR'])
                    with stat_cols[3]:
                        st.metric("Batting Average", matchup['AVG'])
                    
                    # Calculate success probability
                    try:
                        success_prob = get_avg_float(matchup) * 100
                    except:
                        success_prob = 0
                    
                    # Show probability as progress bar
                    st.markdown("#### Success Probability")
                    st.progress(min(success_prob/100, 1.0))
                    st.write(f"{success_prob:.1f}% chance of getting a hit based on historical performance")
                    
                    # Links to player profiles
                    st.markdown(f"[View {matchup['Batter']}'s MLB Profile](https://www.mlb.com/player/{matchup['Batter ID']})")
                    st.markdown(f"[View {matchup['Pitcher']}'s MLB Profile](https://www.mlb.com/player/{matchup['Pitcher ID']})")
            
            with col2:
                st.subheader("Quick Links")
                
                # Show top 5 matchups
                st.markdown("#### Top 5 Matchups")
                top_n = min(5, len(filtered_matchups))
                for i in range(top_n):
                    m = filtered_matchups[i]
                    st.markdown(f"**{i+1}. [{m['Batter']}](https://www.mlb.com/player/{m['Batter ID']})** vs. [{m['Pitcher']}](https://www.mlb.com/player/{m['Pitcher ID']}) - {m['AVG']} ({m['H']}/{m['AB']})")
                
                # Show game times
                st.markdown("#### Today's Games")
                game_times = {}
                for m in filtered_matchups:
                    game_key = f"{m['Team']} vs {m['Opponent']}"
                    game_time = m.get('Game Time', '')
                    if game_key not in game_times and game_time:
                        try:
                            # Format game time for display
                            game_datetime = datetime.fromisoformat(game_time.replace('Z', '+00:00'))
                            local_time = game_datetime.strftime('%I:%M %p')
                            game_times[game_key] = local_time
                        except:
                            game_times[game_key] = game_time
                
                for game, time in game_times.items():
                    st.markdown(f"**{game}** - {time}")
        else:
            st.info(f"No matchups found with at least {min_ab} ABs and {min_avg:.3f} average. Try adjusting your filters.")
    else:
        st.info("No matchups found for today's games. This could be due to no games scheduled, no probable pitchers announced, or insufficient historical matchup data.")
        
        if debug_mode:
            # Test API connectivity
            st.subheader("API Connectivity Test")
            if st.button("Test API Connection"):
                # Try the games endpoint that we know works
                test_endpoint = "getMLBGamesForDate"
                test_params = {"gameDate": datetime.now().strftime('%Y%m%d')}
                test_result = fetch_from_rapidapi(test_endpoint, test_params)
                
                if test_result:
                    st.success("API connection successful!")
                    st.json(test_result)
                else:
                    st.error("API connection failed. Check your API key and try again.")
    
    # Display last update time
    if st.session_state.last_update:
        st.sidebar.info(f"Last updated: {st.session_state.last_update.strftime('%Y-%m-%d %H:%M:%S')}")
else:
    # Example data for demonstration when API key isn't configured
    st.subheader("Example Matchup Data (Demo)")
    
    example_data = [
        {"Batter": "Mike Trout", "Team": "LAA", "Pitcher": "Justin Verlander", "Opponent": "HOU", "AB": 42, "H": 19, "HR": 3, "AVG": ".452"},
        {"Batter": "Bryce Harper", "Team": "PHI", "Pitcher": "Max Scherzer", "Opponent": "NYM", "AB": 38, "H": 16, "HR": 4, "AVG": ".421"},
        {"Batter": "Aaron Judge", "Team": "NYY", "Pitcher": "Nathan Eovaldi", "Opponent": "BOS", "AB": 24, "H": 10, "HR": 2, "AVG": ".417"},
        {"Batter": "Freddie Freeman", "Team": "LAD", "Pitcher": "Yu Darvish", "Opponent": "SD", "AB": 28, "H": 11, "HR": 1, "AVG": ".393"},
        {"Batter": "Jose Altuve", "Team": "HOU", "Pitcher": "Gerrit Cole", "Opponent": "NYY", "AB": 26, "H": 10, "HR": 2, "AVG": ".385"},
    ]
    
    # Convert to DataFrame
    df = pd.DataFrame(example_data)
    
    # Add rank column
    df.insert(0, "Rank", range(1, len(df) + 1))
    
    # Display table
    st.dataframe(df, use_container_width=True, hide_index=True)
    
    # Add some example visuals
    st.markdown("### 🔍 Matchup Details")
    
    # Sample stats for Mike Trout vs Justin Verlander
    stat_cols = st.columns(4)
    with stat_cols[0]:
        st.metric("At Bats", "42")
    with stat_cols[1]:
        st.metric("Hits", "19")
    with stat_cols[2]:
        st.metric("Home Runs", "3")
    with stat_cols[3]:
        st.metric("Batting Average", ".452")
    
    # Sample success probability
    st.markdown("#### Success Probability")
    st.progress(0.452)
    st.write("45.2% chance of getting a hit based on historical performance")
    
    st.markdown("### ⚠️ This is example data")
    st.markdown("To see real matchup data, add your RapidAPI key in the Streamlit secrets configuration.")

# Footer
st.markdown("---")
st.markdown(f"Data is based on historical batter vs. pitcher matchups. Minimum {min_ab} at-bats required for statistical significance.")