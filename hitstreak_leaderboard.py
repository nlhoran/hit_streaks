import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import requests
import time
import os
import random

# Set page configuration
st.set_page_config(
    page_title="MLB Hit Streak Leaderboard",
    page_icon="⚾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# App title 
st.title("⚾ MLB Games with Hit Leaderboard")
st.markdown("Players with the most games with at least one hit (last 15 games)")

# Initialize session state for caching
if "streak_data" not in st.session_state:
    st.session_state.streak_data = None

# Cache directory for data
CACHE_DIR = "mlb_streak_cache"
os.makedirs(CACHE_DIR, exist_ok=True)

# Function to fetch MLB hit streak data with caching
def fetch_mlb_hit_streaks(top_player_limit=50):
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
            merged_df = merged_df.fillna({'Games_With_Hit': 0, 'Current_Streak': 0, 'Max_Hit_Streak': 0, 'Last_15': 0})
            merged_df = merged_df.sort_values('Last_15', ascending=False)
            
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
                    
                    # Get last 15 games with hit
                    last_15_hits = sum([g['had_hit'] for g in games[-15:]]) if len(games) >= 15 else sum([g['had_hit'] for g in games])
                    
                    all_streak_data.append({
                        'playerid': player_id,
                        'Games_With_Hit': games_with_hit,
                        'Current_Streak': current_streak,
                        'Max_Hit_Streak': max_streak,
                        'Last_15': last_15_hits
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
    
    # Generate realistic stats - ensure all columns have valid values
    player_count = len(df)
    df['AB'] = np.random.randint(60, 120, player_count)
    df['H'] = (np.random.uniform(0.250, 0.350, player_count) * df['AB']).astype(int)
    df['BB'] = np.random.randint(5, 20, player_count)
    df['2B'] = np.random.randint(3, 12, player_count)
    df['3B'] = np.random.randint(0, 3, player_count)
    df['HR'] = np.random.randint(1, 10, player_count)
    df['AVG'] = [f".{random.randint(240, 330)}" for _ in range(player_count)]
    
    # Fill any potential NaN values with reasonable defaults
    default_values = {
        'AB': 0, 'H': 0, 'BB': 0, '2B': 0, '3B': 0, 'HR': 0, 
        'AVG': '.000', '1B': 0
    }
    df = df.fillna(default_values)
    
    # Calculate singles (1B)
    for idx, row in df.iterrows():
        extra_base_hits = row['2B'] + row['3B'] + row['HR']
        if extra_base_hits > row['H']:
            df.at[idx, 'H'] = extra_base_hits
        df.at[idx, '1B'] = row['H'] - extra_base_hits
    
    # Generate streaks
    streak_weights = [0.6, 0.25, 0.1, 0.04, 0.01]  # More weight to shorter streaks
    streak_values = [random.randint(0, 3), random.randint(3, 6), 
                    random.randint(6, 10), random.randint(10, 15), 
                    random.randint(15, 25)]
    
    # Generate streaks with weighted distribution - ensure no NaN values
    current_streaks = [np.random.choice(streak_values, p=streak_weights) for _ in range(player_count)]
    df['Current_Streak'] = current_streaks
    df['Max_Hit_Streak'] = [max(streak, random.randint(streak, min(streak + 8, 30))) for streak in current_streaks]
    df['Games_With_Hit'] = [max(streak, random.randint(streak, min(streak + 25, 50))) for streak in df['Max_Hit_Streak']]
    
    # For Last_15, ensure all values are integers between 0-15
    df['Last_15'] = [min(15, max(0, random.randint(max(5, streak), min(15, streak + 10)))) for streak in current_streaks]
    
    # Fill any potential NaN values with zeros
    streak_columns = ['Current_Streak', 'Max_Hit_Streak', 'Games_With_Hit', 'Last_15']
    for col in streak_columns:
        df[col] = df[col].fillna(0).astype(int)
    
    # Sort by games with hit in last 15 games
    df = df.sort_values('Last_15', ascending=False)
    
    return df

# Sidebar filters
st.sidebar.header("⚙️ Settings")
data_source = st.sidebar.radio(
    "Data Source",
    options=["MLB Data", "Demo Data"],
    index=0
)

min_games_with_hit = st.sidebar.slider(
    "Minimum Games with Hit (out of 15)",
    min_value=1,
    max_value=15,
    value=5,
    step=1
)

# Add a refresh button
if st.sidebar.button("🔄 Refresh Data"):
    st.session_state.streak_data = None
    st.rerun()

# Main content - Load data
if data_source == "MLB Data":
    # Use cached session data if available 
    if st.session_state.streak_data is not None:
        streak_data = st.session_state.streak_data
    else:
        # Fetch new data
        streak_data = fetch_mlb_hit_streaks(top_player_limit=50)
        st.session_state.streak_data = streak_data
else:
    # Use demo data
    streak_data = generate_demo_data()

# Process and display data
if streak_data is not None and not streak_data.empty:
    # Check if we have Last_15 data, if not try to add it
    if 'Last_15' not in streak_data.columns:
        # Add a safe Last_15 column
        streak_data['Last_15'] = 0  # Initialize with zeros
        
        if 'Last_10' in streak_data.columns:
            # Safely convert Last_10 to Last_15 with a boost
            streak_data['Last_15'] = streak_data['Last_10'].fillna(0).apply(
                lambda x: min(int(x * 1.5), 15)
            )
        elif 'Games_With_Hit' in streak_data.columns:
            # Generate a reasonable estimate based on Games_With_Hit
            streak_data['Last_15'] = streak_data['Games_With_Hit'].fillna(0).apply(
                lambda x: min(int(x * 0.3), 15)
            )
        
        # Ensure the column is integer type with no NaN values
        streak_data['Last_15'] = streak_data['Last_15'].fillna(0).astype(int)
    
    # Filter by minimum games with hit in last 15 games
    filtered_data = streak_data[streak_data['Last_15'] >= min_games_with_hit]
    
    # Sort by games with hit in last 15 games (descending)
    filtered_data = filtered_data.sort_values('Last_15', ascending=False)
    
    if not filtered_data.empty:
        # Show games with hit section
        st.subheader(f"🔥 Top Players by Games with Hit ({len(filtered_data)} players)")
        
        # Create two columns for main display and sidebar
        col1, col2 = st.columns([7, 3])
        
        with col1:
            # Format dataframe for display
            display_df = filtered_data.copy()
            
            # Select and rename columns for the main table
            table_df = display_df[['Name', 'Team', 'position', 'Last_15', 'Current_Streak', 'Max_Hit_Streak', 'AVG']]
            
            # Add rank column
            table_df.insert(0, 'Rank', range(1, len(table_df) + 1))
            
            # Rename columns for display
            column_rename = {
                'Last_15': 'Games with Hit (Last 15)',
                'Current_Streak': 'Current Streak',
                'Max_Hit_Streak': 'Season Best Streak',
                'position': 'Pos',
                'AVG': 'Avg'
            }
            
            # Rename columns
            table_df = table_df.rename(columns=column_rename)
            
            # Display the table
            st.dataframe(table_df, use_container_width=True, hide_index=True)
        
        with col2:
            st.subheader("Player Links")
            
            # Top 5 players get highlighted
            top_n = min(5, len(filtered_data))
            top_players = filtered_data.head(top_n)
            
            for _, row in top_players.iterrows():
                st.markdown(f"**[{row['Name']}](https://www.mlb.com/player/{row['playerid']})** - {row['Last_15']}/15 games with hit")
            
            # Rest of the players
            if len(filtered_data) > top_n:
                st.markdown("---")
                for _, row in filtered_data.iloc[top_n:].iterrows():
                    st.markdown(f"[{row['Name']}](https://www.mlb.com/player/{row['playerid']}) - {row['Last_15']}/15 games with hit")
                
        # Add DiMaggio reference
        st.markdown("---")
        st.markdown("#### Joe DiMaggio's MLB record is 56 consecutive games with a hit (1941)")
    else:
        st.info(f"No players with {min_games_with_hit} or more games with a hit in the last 15 games. Try lowering the minimum value.")
else:
    st.error("No data available. Please try a different data source or check connectivity.")

# Footer
st.markdown("---")
st.markdown(f"Last update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")