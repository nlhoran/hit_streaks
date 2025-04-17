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
    """Fetch data from Tank01 MLB API with caching"""
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
    
    # Prepare request with the CORRECT endpoint format (no /mlb/ prefix)
    url = f"https://{RAPIDAPI_HOST}/{endpoint}"
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": RAPIDAPI_HOST
    }
    
    try:
        if debug_mode:
            st.sidebar.markdown(f"Calling API: {url}")
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
        else:
            if debug_mode:
                st.error(f"API returned status code {response.status_code}: {response.text}")
            return None
    except Exception as e:
        if debug_mode:
            st.error(f"Error fetching data: {str(e)}")
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

def get_team_roster(team_code):
    """Get roster for a team"""
    endpoint = "getMLBTeamRoster"
    params = {
        "teamAbr": team_code,
        "season": str(datetime.now().year)
    }
    
    return fetch_from_rapidapi(endpoint, params)

# No longer needed - we get pitchers directly from game data

def get_batter_vs_pitcher(batter_id, pitcher_id):
    """Get batter vs pitcher matchup data"""
    endpoint = "getMLBBatterVsPitcher"
    params = {
        "batterID": str(batter_id),
        "pitcherID": str(pitcher_id)
    }
    
    return fetch_from_rapidapi(endpoint, params)

def process_matchups(game_date=None):
    """Process all matchups for the specified date"""
    if game_date is None:
        game_date = datetime.now()
        
    games_data = get_games_for_date(game_date)
    if not games_data or not games_data.get("body"):
        if debug_mode:
            st.warning(f"No games found for {game_date.strftime('%Y-%m-%d')} or API error")
        return []
    
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
            if home_roster_data and home_roster_data.get("body"):
                st.sidebar.markdown(f"Home roster players: {len(home_roster_data.get('body', []))}")
            else:
                st.sidebar.markdown(f"❌ No home roster data for {home_team_code}")
                
            if away_roster_data and away_roster_data.get("body"):
                st.sidebar.markdown(f"Away roster players: {len(away_roster_data.get('body', []))}")
            else:
                st.sidebar.markdown(f"❌ No away roster data for {away_team_code}")
        
        # Find home pitcher name from roster
        home_pitcher_name = "Unknown Pitcher"
        if home_roster_data and home_roster_data.get("body"):
            for player in home_roster_data.get("body", []):
                if player.get("playerID") == home_pitcher_id:
                    home_pitcher_name = player.get("longName", "Unknown Pitcher")
                    break
                    
            if debug_mode and home_pitcher_name == "Unknown Pitcher":
                st.sidebar.markdown(f"❌ Could not find home pitcher {home_pitcher_id} in roster")
                    
        # Find away pitcher name from roster
        away_pitcher_name = "Unknown Pitcher"
        if away_roster_data and away_roster_data.get("body"):
            for player in away_roster_data.get("body", []):
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
                
                # Find batter name from roster
                batter_name = "Unknown Batter"
                if away_roster_data and away_roster_data.get("body"):
                    for player in away_roster_data.get("body", []):
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
                
                # Find batter name from roster
                batter_name = "Unknown Batter"
                if home_roster_data and home_roster_data.get("body"):
                    for player in home_roster_data.get("body", []):
                        if player.get("playerID") == batter_id:
                            batter_name = player.get("longName", "Unknown Batter")
                            break
                
                process_matchup(batter_id, batter_name, away_pitcher_id, away_pitcher_name, 
                               home_team_name, home_team_code, away_team_name, away_team_code,
                               game.get("gameTime", ""), all_matchups, True)
        else:
            # Process all away team batters vs home pitcher
            if away_roster_data and away_roster_data.get("body"):
                # Filter out pitchers from the roster
                away_batters = [p for p in away_roster_data.get("body", []) 
                               if p.get("primaryPosition") != "P"]
                
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
            if home_roster_data and home_roster_data.get("body"):
                # Filter out pitchers from the roster
                home_batters = [p for p in home_roster_data.get("body", []) 
                               if p.get("primaryPosition") != "P"]
                
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
            ab = int(stats.get("atBats", 0))
            
            if debug_mode:
                st.sidebar.markdown(f"At bats: {ab}")
            
            # We'll collect ALL matchups and filter later with the slider
            hits = int(stats.get("hits", 0))
            avg = stats.get("avg", "0.000")
            hr = int(stats.get("homeruns", 0))
            
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
                if avg_str.startswith("."):
                    return float("0" + avg_str)
                return float(avg_str)
            except ValueError:
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
                
        filtered_matchups = [m for m in matchups if int(m.get("AB", 0)) >= min_ab and get_avg_float(m) >= min_avg]
        
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