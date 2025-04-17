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
st.markdown("Best batter vs. pitcher matchups for today's MLB games")

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
    
    # Show API endpoint info for debugging
    st.sidebar.markdown("### API Endpoint Information")
    st.sidebar.info("""
    This app uses the following Tank01 API endpoints:
    - /mlb/getBatterVsPitcher (for matchup data)
    - /mlb/getGamesByDate (for today's games)
    - /mlb/getTeamRoster (for team rosters)
    """)

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
                st.warning(f"Error reading cache: {str(e)}")
    
    # Prepare request - Fix: Make sure endpoint includes /mlb/ prefix per API docs
    if not endpoint.startswith('/'):
        endpoint = '/' + endpoint
    if not endpoint.startswith('/mlb/'):
        endpoint = '/mlb' + endpoint
        
    url = f"https://{RAPIDAPI_HOST}{endpoint}"
    headers = {
        "X-RapidAPI-Key": RAPIDAPI_KEY,
        "X-RapidAPI-Host": RAPIDAPI_HOST
    }
    
    try:
        # Debug info
        st.sidebar.markdown(f"Calling API: {url}")
        st.sidebar.markdown(f"Params: {params}")
        
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        # Debug info
        st.sidebar.markdown(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            
            # Save to cache
            with open(cache_file, 'w') as f:
                json.dump(data, f)
                
            return data
        else:
            st.error(f"API returned status code {response.status_code}: {response.text}")
            return None
    except Exception as e:
        st.error(f"Error fetching data: {str(e)}")
        return None

def get_todays_games():
    """Get today's scheduled MLB games"""
    date_str = datetime.now().strftime('%Y%m%d')
    
    # Using Tank01 API's game endpoint - corrected based on API docs
    endpoint = "/mlb/getGamesByDate"
    params = {
        "gameDate": date_str
    }
    
    games_data = fetch_from_rapidapi(endpoint, params)
    
    # Debug info
    if games_data:
        st.sidebar.markdown(f"Found {len(games_data.get('body', []))} games")
    else:
        st.sidebar.markdown("No games data returned")
    
    return games_data

def get_team_roster(team_code):
    """Get roster for a team"""
    endpoint = "/mlb/getTeamRoster"
    params = {
        "teamAbr": team_code,
        "season": str(datetime.now().year)
    }
    
    return fetch_from_rapidapi(endpoint, params)

def get_batter_vs_pitcher(batter_id, pitcher_id):
    """Get batter vs pitcher matchup data"""
    endpoint = "/mlb/getBatterVsPitcher"
    params = {
        "batterID": str(batter_id),
        "pitcherID": str(pitcher_id)
    }
    
    return fetch_from_rapidapi(endpoint, params)

def process_matchups():
    """Process all matchups for today's games"""
    games_data = get_todays_games()
    if not games_data or not games_data.get("body"):
        st.warning("No games found for today or API error")
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
        
        home_team = game.get("homeTeam", {})
        away_team = game.get("awayTeam", {})
        
        home_team_code = home_team.get("abbreviation")
        away_team_code = away_team.get("abbreviation")
        
        home_team_name = home_team.get("name")
        away_team_name = away_team.get("name")
        
        progress_text.text(f"Processing game {i+1} of {total_games}: {away_team_name} @ {home_team_name}")
        
        # Get the probable pitchers
        # Note: Tank01 API might not provide this directly, we might need to fetch them separately
        home_pitcher_data = fetch_from_rapidapi("/mlb/getProbablePitcher", {"team": home_team_code})
        away_pitcher_data = fetch_from_rapidapi("/mlb/getProbablePitcher", {"team": away_team_code})
        
        # Extract pitcher information
        home_pitcher = None
        away_pitcher = None
        
        if home_pitcher_data and home_pitcher_data.get("body"):
            home_pitcher = home_pitcher_data.get("body")
        
        if away_pitcher_data and away_pitcher_data.get("body"):
            away_pitcher = away_pitcher_data.get("body")
        
        # If we don't have probable pitchers, skip this game
        if not home_pitcher or not away_pitcher:
            progress_text.text(f"Skipping game (no probable pitchers): {away_team_name} @ {home_team_name}")
            continue
            
        home_pitcher_id = home_pitcher.get("playerID")
        away_pitcher_id = away_pitcher.get("playerID")
        
        home_pitcher_name = home_pitcher.get("longName", "Unknown Pitcher")
        away_pitcher_name = away_pitcher.get("longName", "Unknown Pitcher")
        
        # Get team rosters
        home_roster_data = get_team_roster(home_team_code)
        away_roster_data = get_team_roster(away_team_code)
        
        # Process away team batters vs home pitcher
        if away_roster_data and away_roster_data.get("body"):
            away_batters = [p for p in away_roster_data.get("body", []) 
                           if p.get("primaryPosition") != "P"]
            
            for batter in away_batters:
                batter_id = batter.get("playerID")
                batter_name = batter.get("longName", "")
                
                if not batter_id:
                    continue
                    
                # Get batter vs pitcher matchup
                matchup_data = get_batter_vs_pitcher(batter_id, home_pitcher_id)
                
                if matchup_data and matchup_data.get("body"):
                    stats = matchup_data.get("body", {}).get("stats", {})
                    
                    try:
                        ab = int(stats.get("atBats", 0))
                        
                        if ab >= 6:  # Apply minimum AB filter
                            hits = int(stats.get("hits", 0))
                            avg = stats.get("avg", "0.000")
                            hr = int(stats.get("homeruns", 0))
                            
                            # Add to matchups list
                            all_matchups.append({
                                "Batter": batter_name,
                                "Batter ID": batter_id,
                                "Pitcher": home_pitcher_name,
                                "Pitcher ID": home_pitcher_id,
                                "Team": away_team_name,
                                "Opponent": home_team_name,
                                "AB": ab,
                                "H": hits,
                                "HR": hr,
                                "AVG": avg,
                                "Game Time": game.get("gameTime", "")
                            })
                    except (ValueError, TypeError):
                        continue
        
        # Process home team batters vs away pitcher
        if home_roster_data and home_roster_data.get("body"):
            home_batters = [p for p in home_roster_data.get("body", []) 
                           if p.get("primaryPosition") != "P"]
            
            for batter in home_batters:
                batter_id = batter.get("playerID")
                batter_name = batter.get("longName", "")
                
                if not batter_id:
                    continue
                    
                # Get batter vs pitcher matchup
                matchup_data = get_batter_vs_pitcher(batter_id, away_pitcher_id)
                
                if matchup_data and matchup_data.get("body"):
                    stats = matchup_data.get("body", {}).get("stats", {})
                    
                    try:
                        ab = int(stats.get("atBats", 0))
                        
                        if ab >= 6:  # Apply minimum AB filter
                            hits = int(stats.get("hits", 0))
                            avg = stats.get("avg", "0.000")
                            hr = int(stats.get("homeruns", 0))
                            
                            # Add to matchups list
                            all_matchups.append({
                                "Batter": batter_name,
                                "Batter ID": batter_id,
                                "Pitcher": away_pitcher_name,
                                "Pitcher ID": away_pitcher_id,
                                "Team": home_team_name,
                                "Opponent": away_team_name,
                                "AB": ab,
                                "H": hits,
                                "HR": hr,
                                "AVG": avg,
                                "Game Time": game.get("gameTime", "")
                            })
                    except (ValueError, TypeError):
                        continue
    
    # Clear progress indicators
    progress_bar.empty()
    progress_text.empty()
    
    # Sort by batting average (descending)
    def get_avg(m):
        try:
            return float(str(m.get("AVG", "0.000")).replace('.', '0.'))
        except ValueError:
            return 0.0
            
    sorted_matchups = sorted(all_matchups, key=get_avg, reverse=True)
    
    return sorted_matchups

# Sidebar controls
st.sidebar.header("⚙️ Settings")

min_ab = st.sidebar.slider(
    "Minimum At Bats",
    min_value=5,
    max_value=30,
    value=6,
    step=1
)

min_avg = st.sidebar.slider(
    "Minimum Batting Average",
    min_value=0.200,
    max_value=0.500,
    value=0.300,
    step=0.025,
    format="%.3f"
)

# Add a refresh button
if st.sidebar.button("🔄 Refresh Data"):
    st.session_state.matchup_data = None
    st.session_state.last_update = datetime.now()
    st.experimental_rerun()

# Add debug mode toggle
debug_mode = st.sidebar.checkbox("Debug Mode")

# Main content
if RAPIDAPI_KEY:
    # Use cached data if available, otherwise fetch new data
    if st.session_state.matchup_data is None:
        with st.spinner("Fetching today's matchups... (this may take a few minutes)"):
            matchups = process_matchups()
            st.session_state.matchup_data = matchups
            st.session_state.last_update = datetime.now()
    else:
        matchups = st.session_state.matchup_data
    
    # Display matchups
    if matchups:
        # Filter by user selections
        def get_avg_float(m):
            try:
                return float(str(m.get("AVG", "0.000")).replace('.', '0.'))
            except ValueError:
                return 0.0
                
        filtered_matchups = [m for m in matchups if int(m.get("AB", 0)) >= min_ab and get_avg_float(m) >= min_avg]
        
        st.subheader(f"🔥 Top Batter vs. Pitcher Matchups Today ({len(filtered_matchups)})")
        
        if filtered_matchups:
            # Convert to DataFrame for display
            df = pd.DataFrame(filtered_matchups)
            
            # Add rank column
            df.insert(0, "Rank", range(1, len(df) + 1))
            
            # Display columns
            display_cols = ["Rank", "Batter", "Team", "Pitcher", "Opponent", "AB", "H", "HR", "AVG"]
            
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
                test_endpoint = "/mlb/help"
                test_result = fetch_from_rapidapi(test_endpoint)
                
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