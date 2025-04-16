import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import requests
import time
import os

# Set page configuration
st.set_page_config(
    page_title="MLB Hit Streak Leaderboard",
    page_icon="⚾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# App title 
st.title("⚾ MLB Hit Streak Leaderboard")
st.markdown("Current active hit streaks in Major League Baseball")

# Initialize session state for caching
if "streak_data" not in st.session_state:
    st.session_state.streak_data = None

# Cache directory for data
CACHE_DIR = "mlb_streak_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

# Team abbreviations and colors
TEAMS = {
    "ARI": {"name": "Arizona Diamondbacks", "color": "#A71930"},
    "ATL": {"name": "Atlanta Braves", "color": "#CE1141"},
    "BAL": {"name": "Baltimore Orioles", "color": "#DF4601"},
    "BOS": {"name": "Boston Red Sox", "color": "#BD3039"},
    "CHC": {"name": "Chicago Cubs", "color": "#0E3386"},
    "CWS": {"name": "Chicago White Sox", "color": "#27251F"},
    "CIN": {"name": "Cincinnati Reds", "color": "#C6011F"},
    "CLE": {"name": "Cleveland Guardians", "color": "#00385D"},
    "COL": {"name": "Colorado Rockies", "color": "#333366"},
    "DET": {"name": "Detroit Tigers", "color": "#0C2340"},
    "HOU": {"name": "Houston Astros", "color": "#EB6E1F"},
    "KC": {"name": "Kansas City Royals", "color": "#004687"},
    "LAA": {"name": "Los Angeles Angels", "color": "#BA0021"},
    "LAD": {"name": "Los Angeles Dodgers", "color": "#005A9C"},
    "MIA": {"name": "Miami Marlins", "color": "#00A3E0"},
    "MIL": {"name": "Milwaukee Brewers", "color": "#0A2351"},
    "MIN": {"name": "Minnesota Twins", "color": "#002B5C"},
    "NYM": {"name": "New York Mets", "color": "#FF5910"},
    "NYY": {"name": "New York Yankees", "color": "#0C2340"},
    "OAK": {"name": "Oakland Athletics", "color": "#003831"},
    "PHI": {"name": "Philadelphia Phillies", "color": "#E81828"},
    "PIT": {"name": "Pittsburgh Pirates", "color": "#27251F"},
    "SD": {"name": "San Diego Padres", "color": "#2F241D"},
    "SF": {"name": "San Francisco Giants", "color": "#FD5A1E"},
    "SEA": {"name": "Seattle Mariners", "color": "#0C2C56"},
    "STL": {"name": "St. Louis Cardinals", "color": "#C41E3A"},
    "TB": {"name": "Tampa Bay Rays", "color": "#092C5C"},
    "TEX": {"name": "Texas Rangers", "color": "#003278"},
    "TOR": {"name": "Toronto Blue Jays", "color": "#134A8E"},
    "WSH": {"name": "Washington Nationals", "color": "#AB0003"}
}

def create_player_link(player_name, player_id):
    """Create a clickable link to the player's MLB game log"""
    # Create URL-friendly name (lowercase, replace spaces with hyphens)
    url_name = player_name.lower().replace(' ', '-')
    url = f"https://www.mlb.com/player/{url_name}/{player_id}"
    
    # Return markdown link
    return f"[{player_name}]({url})"

# Function to fetch MLB hit streak data with caching
def fetch_mlb_hit_streaks(top_player_limit=40):
    """Fetch current hit streak data from MLB Stats API with fallback to cached data"""
    cache_file = os.path.join(CACHE_DIR, "current_streaks.json")
    cache_time = 3600  # 1 hour cache
    
    # Check if cache file exists and is recent
    if os.path.exists(cache_file):
        file_modified_time = os.path.getmtime(cache_file)
        if (time.time() - file_modified_time) < cache_time:
            try:
                return pd.read_json(cache_file)
            except Exception as e:
                st.warning(f"Error reading cache file: {str(e)}")
    
    try:
        # First try to fetch from MLB Stats API
        url = "https://statsapi.mlb.com/api/v1/stats?stats=season&group=hitting&sportId=1&limit=1000"
        
        with st.spinner("Fetching MLB season stats..."):
            response = requests.get(url, timeout=10)
            
        if response.status_code == 200:
            player_stats = response.json()
            
            # Process player stats
            players = []
            for player in player_stats.get('stats', [{}])[0].get('splits', []):
                player_data = {
                    'Name': player.get('player', {}).get('fullName'),
                    'Team': player.get('team', {}).get('abbreviation'),
                    'playerid': player.get('player', {}).get('id'),
                    'position': player.get('position', {}).get('abbreviation'),
                    'AB': player.get('stat', {}).get('atBats', 0),
                    'H': player.get('stat', {}).get('hits', 0),
                    'BB': player.get('stat', {}).get('baseOnBalls', 0),
                    '1B': 0,  # Will calculate these later
                    '2B': player.get('stat', {}).get('doubles', 0),
                    '3B': player.get('stat', {}).get('triples', 0),
                    'HR': player.get('stat', {}).get('homeRuns', 0),
                    'AVG': player.get('stat', {}).get('avg', '.000')
                }
                
                # Calculate singles (1B)
                player_data['1B'] = player_data['H'] - (player_data['2B'] + player_data['3B'] + player_data['HR'])
                
                players.append(player_data)
            
            # Create DataFrame
            df = pd.DataFrame(players)
            
            # Fetch hit streak information for top hitters by hits (limited to improve performance)
            top_hitters = df.sort_values('H', ascending=False).head(top_player_limit)
            
            # Get today's date for streak calculation
            today = datetime.now()
            season_start = datetime(today.year, 3, 30)  # Approximate MLB season start
            
            # Show progress for streak calculation
            with st.spinner(f"Fetching hit streaks for top {top_player_limit} hitters... (this may take a minute)"):
                streaks = fetch_hit_streaks(top_hitters['playerid'].tolist(), season_start.strftime('%Y-%m-%d'), today.strftime('%Y-%m-%d'))
            
            # Merge streak data with player stats
            merged_df = pd.merge(df, streaks, on='playerid', how='left')
            merged_df = merged_df.fillna({'Games_With_Hit': 0, 'Current_Streak': 0, 'Max_Hit_Streak': 0})
            merged_df = merged_df.sort_values('Current_Streak', ascending=False)
            
            # Save to cache
            merged_df.to_json(cache_file)
            return merged_df
            
        else:
            st.warning(f"MLB API returned status code {response.status_code}. Using cached or demo data.")
            # Try to load from cache
            if os.path.exists(cache_file):
                return pd.read_json(cache_file)
            else:
                return generate_demo_data()
                
    except Exception as e:
        st.warning(f"Error fetching MLB data: {str(e)}. Using cached or demo data.")
        # Try to load from cache
        if os.path.exists(cache_file):
            return pd.read_json(cache_file)
        else:
            return generate_demo_data()

# Function to fetch hit streaks for players
def fetch_hit_streaks(player_ids, start_date, end_date):
    """Fetch hit streak data for a list of player IDs"""
    all_streak_data = []
    
    # Add progress tracking
    progress_text = st.empty()
    progress_bar = st.progress(0)
    
    for i, player_id in enumerate(player_ids):
        # Update progress
        progress = i / len(player_ids)
        progress_bar.progress(progress)
        progress_text.text(f"Processing player {i+1} of {len(player_ids)}")
        
        try:
            # Get player game logs with shorter timeout
            url = f"https://statsapi.mlb.com/api/v1/people/{player_id}/stats?stats=gameLog&group=hitting&season={datetime.now().year}&gameType=R"
            
            response = requests.get(url, timeout=3)
            if response.status_code == 200:
                game_data = response.json()
                
                # Extract game-by-game hitting data
                games = []
                for game in game_data.get('stats', [{}])[0].get('splits', []):
                    game_date = game.get('date')
                    hits = game.get('stat', {}).get('hits', 0)
                    games.append({'date': game_date, 'had_hit': 1 if hits > 0 else 0})
                
                if games:
                    # Sort games by date
                    games = sorted(games, key=lambda x: x['date'])
                    
                    # Calculate current streak and max streak
                    current_streak = 0
                    max_streak = 0
                    streak = 0
                    games_with_hit = 0
                    
                    for game in games:
                        if game['had_hit'] == 1:
                            streak += 1
                            games_with_hit += 1
                            max_streak = max(max_streak, streak)
                        else:
                            streak = 0
                    
                    # Current streak is the current value of streak if last games had hits
                    current_streak = streak
                    
                    # Get last ten games streak
                    last_10_hits = sum([g['had_hit'] for g in games[-10:]]) if len(games) >= 10 else sum([g['had_hit'] for g in games])
                    
                    all_streak_data.append({
                        'playerid': player_id,
                        'Games_With_Hit': games_with_hit,
                        'Current_Streak': current_streak,
                        'Max_Hit_Streak': max_streak,
                        'Last_10': last_10_hits
                    })
            
        except Exception as e:
            # Skip this player and continue
            continue
    
    # Clear progress indicators
    progress_bar.empty()
    progress_text.empty()
    
    return pd.DataFrame(all_streak_data)

# Function to generate demo data
def generate_demo_data():
    """Generate realistic demo data with current MLB players"""
    st.info("Using demo data with realistic current MLB player information")
    
    # Current top MLB players (2024 season)
    players = [
        {"Name": "Gunnar Henderson", "Team": "BAL", "playerid": 683002, "position": "SS"},
        {"Name": "Shohei Ohtani", "Team": "LAD", "playerid": 660271, "position": "DH"},
        {"Name": "Aaron Judge", "Team": "NYY", "playerid": 592450, "position": "RF"},
        {"Name": "Juan Soto", "Team": "NYY", "playerid": 665742, "position": "RF"},
        {"Name": "Freddie Freeman", "Team": "LAD", "playerid": 518692, "position": "1B"},
        {"Name": "Steven Kwan", "Team": "CLE", "playerid": 680757, "position": "LF"},
        {"Name": "Bobby Witt Jr.", "Team": "KC", "playerid": 677951, "position": "SS"},
        {"Name": "Bryce Harper", "Team": "PHI", "playerid": 547180, "position": "1B"},
        {"Name": "Mookie Betts", "Team": "LAD", "playerid": 605141, "position": "SS"},
        {"Name": "Yordan Alvarez", "Team": "HOU", "playerid": 670541, "position": "DH"},
        {"Name": "Adley Rutschman", "Team": "BAL", "playerid": 668939, "position": "C"},
        {"Name": "Francisco Lindor", "Team": "NYM", "playerid": 596019, "position": "SS"},
        {"Name": "Rafael Devers", "Team": "BOS", "playerid": 646240, "position": "3B"},
        {"Name": "Elly De La Cruz", "Team": "CIN", "playerid": 682829, "position": "SS"},
        {"Name": "Mike Trout", "Team": "LAA", "playerid": 545361, "position": "CF"},
        {"Name": "Matt Olson", "Team": "ATL", "playerid": 621566, "position": "1B"},
        {"Name": "Julio Rodriguez", "Team": "SEA", "playerid": 677594, "position": "CF"},
        {"Name": "Corbin Carroll", "Team": "ARI", "playerid": 682998, "position": "CF"},
        {"Name": "Luis Robert Jr.", "Team": "CWS", "playerid": 673357, "position": "CF"},
        {"Name": "Vladimir Guerrero Jr.", "Team": "TOR", "playerid": 665489, "position": "1B"},
    ]
    
    # Create DataFrame
    df = pd.DataFrame(players)
    
    # Generate realistic stats
    player_count = len(df)
    df['AB'] = np.random.randint(60, 120, player_count)
    df['H'] = (np.random.uniform(0.250, 0.350, player_count) * df['AB']).astype(int)
    df['BB'] = np.random.randint(5, 20, player_count)
    df['2B'] = np.random.randint(3, 12, player_count)
    df['3B'] = np.random.randint(0, 3, player_count)
    df['HR'] = np.random.randint(1, 10, player_count)
    df['AVG'] = [f".{random.randint(240, 330)}" for _ in range(player_count)]
    
    # Calculate singles (1B)
    for idx, row in df.iterrows():
        extra_base_hits = row['2B'] + row['3B'] + row['HR']
        if extra_base_hits > row['H']:
            df.at[idx, 'H'] = extra_base_hits
        df.at[idx, '1B'] = row['H'] - extra_base_hits
    
    # Generate streaks
    import random
    streak_weights = [0.6, 0.25, 0.1, 0.04, 0.01]  # More weight to shorter streaks
    streak_values = [random.randint(0, 3), random.randint(3, 6), 
                    random.randint(6, 10), random.randint(10, 15), 
                    random.randint(15, 25)]
    
    # Generate streaks with weighted distribution
    current_streaks = [np.random.choice(streak_values, p=streak_weights) for _ in range(player_count)]
    df['Current_Streak'] = current_streaks
    df['Max_Hit_Streak'] = [max(streak, random.randint(streak, min(streak + 8, 30))) for streak in current_streaks]
    df['Games_With_Hit'] = [max(streak, random.randint(streak, min(streak + 25, 50))) for streak in df['Max_Hit_Streak']]
    df['Last_10'] = [random.randint(max(3, streak - 4), min(10, streak + 5)) for streak in current_streaks]
    
    # Sort by current streak
    df = df.sort_values('Current_Streak', ascending=False)
    
    return df

# Sidebar filters
st.sidebar.header("⚙️ Settings")
data_source = st.sidebar.radio(
    "Data Source",
    options=["MLB Data", "Demo Data"],
    index=0
)

min_streak = st.sidebar.slider(
    "Minimum Streak Length",
    min_value=0,
    max_value=15,
    value=1,
    step=1
)

# Add a refresh button
if st.sidebar.button("🔄 Refresh Data"):
    st.session_state.streak_data = None
    st.experimental_rerun()

# Main content - Load data
if data_source == "MLB Data":
    # Use cached session data if available 
    if st.session_state.streak_data is not None:
        streak_data = st.session_state.streak_data
    else:
        # Fetch new data
        streak_data = fetch_mlb_hit_streaks(top_player_limit=40)
        st.session_state.streak_data = streak_data
else:
    # Use demo data
    streak_data = generate_demo_data()

# Process and display data
if streak_data is not None and not streak_data.empty:
    # Filter by minimum streak
    filtered_data = streak_data[streak_data['Current_Streak'] >= min_streak]
    
    if not filtered_data.empty:
        # Show active streaks section
        st.subheader(f"🔥 Active Hit Streaks ({len(filtered_data)} players)")
        
        # Format dataframe for display
        display_df = filtered_data.copy()
        
        # Create clickable player name links
        display_df['Name_Link'] = display_df.apply(
            lambda row: create_player_link(row['Name'], row['playerid']), axis=1
        )
        
        # Final display columns with important ones first
        final_columns = ['Name_Link', 'Team', 'position', 'Current_Streak', 'Last_10', 'Max_Hit_Streak', 'AVG', 'AB', 'H']
        
        # Ensure all columns exist
        for col in final_columns:
            if col not in display_df.columns and col != 'Name_Link':
                display_df[col] = 0
                
        # Add rank column
        display_df.insert(0, 'Rank', range(1, len(display_df) + 1))
        
        # Rename columns for display
        column_rename = {
            'Name_Link': 'Player',
            'Current_Streak': 'Current Streak',
            'Max_Hit_Streak': 'Season Best',
            'Last_10': 'Hits in Last 10',
            'position': 'Pos',
            'AB': 'At Bats',
            'H': 'Hits',
            'AVG': 'Batting Avg'
        }
        
        # Keep only needed columns in proper order
        display_columns = ['Rank'] + final_columns
        display_df = display_df[display_columns].rename(columns=column_rename)
        
        # Use HTML to create a table with clickable links
        st.write(display_df.to_html(escape=False, index=False), unsafe_allow_html=True)
        
        # Add DiMaggio reference
        st.markdown("---")
        st.markdown("#### Joe DiMaggio's MLB record is 56 consecutive games with a hit (1941)")
    else:
        st.info(f"No active hit streaks of {min_streak} games or more. Try lowering the minimum streak length.")
else:
    st.error("No data available. Please try a different data source or check connectivity.")

# Footer
st.markdown("---")
st.markdown(f"Last update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")