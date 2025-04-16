import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from datetime import datetime, timedelta
import requests
import time
import json
import os

# Set page configuration
st.set_page_config(
    page_title="MLB Hit Streak Dashboard",
    page_icon="⚾",
    layout="wide",
    initial_sidebar_state="expanded"
)

# App title and description
st.title("⚾ MLB Hit Streak Dashboard")

# Initialize session state
if "data_loaded" not in st.session_state:
    st.session_state.data_loaded = False
if "streak_data" not in st.session_state:
    st.session_state.streak_data = None
if "is_refreshing" not in st.session_state:
    st.session_state.is_refreshing = False
if "refresh_timestamp" not in st.session_state:
    st.session_state.refresh_timestamp = None
if "using_cached" not in st.session_state:
    st.session_state.using_cached = False

# Cache directory for data
CACHE_DIR = "mlb_streak_cache"
os.makedirs(CACHE_DIR, exist_ok=True)
CACHE_FILE = os.path.join(CACHE_DIR, "current_streaks.json")

# Define teams with colors
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

# Function to generate demo data with current MLB players
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
        {"Name": "Corey Seager", "Team": "TEX", "playerid": 608369, "position": "SS"},
        {"Name": "Pete Alonso", "Team": "NYM", "playerid": 624413, "position": "1B"},
        {"Name": "Jose Ramirez", "Team": "CLE", "playerid": 542432, "position": "3B"},
        {"Name": "Cody Bellinger", "Team": "CHC", "playerid": 641355, "position": "CF"},
        {"Name": "Jazz Chisholm Jr.", "Team": "MIA", "playerid": 665862, "position": "CF"},
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
    
    # Calculate singles (1B)
    for idx, row in df.iterrows():
        extra_base_hits = row['2B'] + row['3B'] + row['HR']
        if extra_base_hits > row['H']:
            # Adjust if we have more extra-base hits than total hits
            df.at[idx, 'H'] = extra_base_hits
        df.at[idx, '1B'] = row['H'] - extra_base_hits
    
    # Generate hit streak data
    # Assign a random current streak (weighted to have a few longer streaks)
    streak_weights = [0.6, 0.25, 0.1, 0.04, 0.01]  # More weight to shorter streaks
    streak_values = [np.random.randint(0, 3), np.random.randint(3, 6), 
                    np.random.randint(6, 10), np.random.randint(10, 15), 
                    np.random.randint(15, 25)]
    
    # Generate streaks with weighted distribution
    current_streaks = [np.random.choice(streak_values, p=streak_weights) for _ in range(player_count)]
    df['Current_Streak'] = current_streaks
    
    # Max streak is at least the current streak, potentially higher
    df['Max_Hit_Streak'] = [max(streak, np.random.randint(streak, min(streak + 8, 30))) 
                           for streak in current_streaks]
    
    # Games with hits will be at least equal to max streak
    df['Games_With_Hit'] = [max(streak, np.random.randint(streak, min(streak + 25, 50))) 
                           for streak in df['Max_Hit_Streak']]
    
    # Sort by current streak
    df = df.sort_values('Current_Streak', ascending=False)
    
    return df

# Function to get famous hit streaks for comparison
def get_famous_hit_streaks():
    """Return list of famous MLB hit streaks for context"""
    return [
        {"Player": "Joe DiMaggio", "Team": "NYY", "Year": 1941, "Streak": 56},
        {"Player": "Pete Rose", "Team": "CIN", "Year": 1978, "Streak": 44},
        {"Player": "Willie Keeler", "Team": "BAL", "Year": 1897, "Streak": 44},
        {"Player": "Bill Dahlen", "Team": "CHC", "Year": 1894, "Streak": 42},
        {"Player": "George Sisler", "Team": "STL", "Year": 1922, "Streak": 41},
        {"Player": "Ty Cobb", "Team": "DET", "Year": 1911, "Streak": 40},
        {"Player": "Paul Molitor", "Team": "MIL", "Year": 1987, "Streak": 39},
        {"Player": "Jimmy Rollins", "Team": "PHI", "Year": 2005, "Streak": 38},
        {"Player": "Tommy Holmes", "Team": "BSN", "Year": 1945, "Streak": 37},
        {"Player": "Chase Utley", "Team": "PHI", "Year": 2006, "Streak": 35}
    ]

# Check for and load cached data at startup
def load_cached_data():
    """Load data from cache file if it exists"""
    if os.path.exists(CACHE_FILE):
        try:
            data = pd.read_json(CACHE_FILE)
            cache_time = datetime.fromtimestamp(os.path.getmtime(CACHE_FILE))
            st.session_state.refresh_timestamp = cache_time
            st.session_state.using_cached = True
            return data
        except Exception as e:
            st.error(f"Error loading cached data: {str(e)}")
            return None
    return None

# Function to refresh data in background
def start_refresh_data():
    """Trigger data refresh"""
    st.session_state.is_refreshing = True
    # This will cause a rerun with is_refreshing=True

# Function to actually fetch MLB data - only called during refresh
def fetch_mlb_data(top_player_limit=40):
    """Fetch MLB data and save to cache"""
    try:
        # Fetch from MLB Stats API
        url = "https://statsapi.mlb.com/api/v1/stats?stats=season&group=hitting&sportId=1&limit=1000"
        
        with st.spinner("Fetching MLB season stats..."):
            response = requests.get(url, timeout=10)
            
        if response.status_code != 200:
            st.warning(f"MLB API returned status code {response.status_code}")
            return None
            
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
                'HR': player.get('stat', {}).get('homeRuns', 0)
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
        merged_df.to_json(CACHE_FILE)
        st.session_state.refresh_timestamp = datetime.now()
        
        return merged_df
            
    except Exception as e:
        st.warning(f"Error fetching MLB data: {str(e)}")
        return None

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
                    
                    all_streak_data.append({
                        'playerid': player_id,
                        'Games_With_Hit': games_with_hit,
                        'Current_Streak': current_streak,
                        'Max_Hit_Streak': max_streak
                    })
            
        except Exception as e:
            # Skip this player and continue
            continue
    
    # Clear progress indicators
    progress_bar.empty()
    progress_text.empty()
    
    return pd.DataFrame(all_streak_data)

# Create tabs for the app
tab1, tab2 = st.tabs(["Current Hit Streaks", "About Hit Streaks"])

# Load data at startup
if not st.session_state.data_loaded:
    cached_data = load_cached_data()
    if cached_data is not None:
        st.session_state.streak_data = cached_data
        st.session_state.data_loaded = True
    else:
        # No cache exists, use demo data for now
        st.session_state.streak_data = generate_demo_data()
        st.session_state.data_loaded = True
        st.session_state.using_cached = False

# Data source selection in sidebar
st.sidebar.header("⚙️ Settings")
data_source = st.sidebar.radio(
    "Data Source",
    options=["MLB Data", "Demo Data"],
    index=0
)

min_streak = st.sidebar.slider(
    "Minimum Streak Length",
    min_value=1,
    max_value=15,
    value=3,
    step=1
)

# Add refresh button and status
if st.sidebar.button("🔄 Refresh MLB Data"):
    start_refresh_data()
    
# Show data source info
if st.session_state.using_cached and data_source == "MLB Data":
    st.sidebar.info(f"Using cached MLB data from: {st.session_state.refresh_timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
elif data_source == "Demo Data":
    st.sidebar.info("Using synthetic demo data")

# Handle data refresh if requested
if st.session_state.is_refreshing and data_source == "MLB Data":
    with st.spinner("Refreshing MLB data... this may take a minute"):
        new_data = fetch_mlb_data(top_player_limit=40)
        if new_data is not None:
            st.session_state.streak_data = new_data
            st.session_state.using_cached = True
            st.success("Data refreshed successfully!")
        else:
            st.error("Failed to refresh data. Using previous data.")
    
    # Reset refresh flag
    st.session_state.is_refreshing = False
    st.experimental_rerun()

# Use demo data if selected
if data_source == "Demo Data":
    st.session_state.streak_data = generate_demo_data()
    st.session_state.using_cached = False
    
# Tab 1: Current Hit Streaks
with tab1:
    st.markdown("### Current MLB Hit Streaks")
    
    streak_data = st.session_state.streak_data
    
    if streak_data is not None and not streak_data.empty:
        # Filter by minimum streak
        filtered_data = streak_data[streak_data['Current_Streak'] >= min_streak]
        
        if not filtered_data.empty:
            # Create active streaks section
            st.subheader(f"🔥 Active Hit Streaks ({len(filtered_data)} players)")
            
            # Format dataframe for display
            display_columns = ['Name', 'Team', 'position', 'Current_Streak', 'Max_Hit_Streak', 'Games_With_Hit', 'AB', 'H']
            
            # Ensure all columns exist
            for col in display_columns:
                if col not in filtered_data.columns:
                    filtered_data[col] = 0
            
            display_df = filtered_data[display_columns].copy()
            
            # Add rank column
            display_df.insert(0, 'Rank', range(1, len(display_df) + 1))
            
            # Rename columns for display
            column_rename = {
                'Current_Streak': 'Current Streak',
                'Max_Hit_Streak': 'Season Best',
                'Games_With_Hit': 'Games w/ Hit',
                'position': 'Pos',
                'AB': 'At Bats',
                'H': 'Hits'
            }
            display_df = display_df.rename(columns=column_rename)
            
            # Display the dataframe
            st.dataframe(display_df, use_container_width=True)
            
            # Visualize top 10 current streaks
            st.subheader("📊 Top Active Hit Streaks")
            
            # Get top 10 by current streak
            top_10 = filtered_data.head(10)
            
            # Get player colors based on team
            team_colors = [TEAMS.get(team, {}).get('color', '#CCCCCC') for team in top_10['Team']]
            
            # Create bar chart of current streaks
            fig = px.bar(
                top_10,
                x='Name',
                y='Current_Streak',
                color='Team',
                color_discrete_map=dict(zip(top_10['Team'], team_colors)),
                title="Top Active Hit Streaks in MLB",
                labels={'Current_Streak': 'Consecutive Games with Hit', 'Name': 'Player'}
            )
            
            # Add a horizontal line for the record
            fig.add_shape(
                type="line",
                x0=-0.5,
                x1=len(top_10) - 0.5,
                y0=56,
                y1=56,
                line=dict(color="red", width=2, dash="dash"),
            )
            
            # Add text for Joe DiMaggio's record
            fig.add_annotation(
                x=len(top_10) / 2,
                y=57,
                text="Joe DiMaggio's Record (56 games)",
                showarrow=False,
                font=dict(color="red", size=12)
            )
            
            # Update layout
            fig.update_layout(height=500)
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Historical comparison
            st.subheader("🏆 Historical Context")
            
            # Get famous streaks
            famous_streaks = pd.DataFrame(get_famous_hit_streaks())
            
            # Create a comparison plot
            fig = px.bar(
                famous_streaks.head(5),
                x='Player',
                y='Streak',
                color='Team',
                text='Streak',
                title="Top 5 Hit Streaks in MLB History",
                labels={'Streak': 'Consecutive Games with Hit', 'Player': 'Player'},
                color_discrete_map={
                    'NYY': TEAMS['NYY']['color'],
                    'CIN': TEAMS['CIN']['color'],
                    'BAL': TEAMS['BAL']['color'], 
                    'CHC': TEAMS['CHC']['color'],
                    'STL': TEAMS['STL']['color'],
                    'DET': TEAMS['DET']['color']
                }
            )
            
            # Add current best streak for comparison
            if len(filtered_data) > 0:
                current_best = filtered_data.iloc[0]
                fig.add_trace(
                    px.bar(
                        pd.DataFrame([{
                            'Player': current_best['Name'] + " (Current)",
                            'Streak': current_best['Current_Streak'],
                            'Team': current_best['Team']
                        }]),
                        x='Player',
                        y='Streak',
                        text='Streak',
                        color='Team',
                        color_discrete_map={current_best['Team']: TEAMS.get(current_best['Team'], {}).get('color', '#CCCCCC')}
                    ).data[0]
                )
            
            # Update layout
            fig.update_layout(height=500)
            
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info(f"No active hit streaks of {min_streak} games or more. Try lowering the minimum streak length.")
    else:
        st.error("No data available. Please try a different data source or check connectivity.")

# Tab 2: About Hit Streaks
with tab2:
    st.markdown("### About MLB Hit Streaks")
    
    # Educational content
    st.subheader("What is a Hit Streak?")
    st.markdown("""
    A **hit streak** in baseball is when a player gets at least one hit in consecutive games. The streak continues 
    as long as the player records at least one hit in each game they play. The streak ends when the player plays 
    a complete game without recording a hit.
    
    **Rules for hit streaks:**
    - A player must have at least one official at-bat in a game for it to count toward the streak
    - Walks, hit-by-pitches, and sacrifices do not count as hits
    - If a player enters as a pinch-hitter or substitute and doesn't get a hit, the streak ends
    - Games where a player only walks or is hit by pitches (with no official at-bats) do not affect the streak
    """)
    
    st.subheader("Historical Significance")
    st.markdown("""
    Joe DiMaggio's 56-game hitting streak in 1941 is one of baseball's most revered records. It's considered 
    by many to be one of the most difficult records to break in all of sports.
    
    Statistical analyses have shown the improbability of DiMaggio's streak. Even for a player with a .350 batting 
    average, the odds of hitting safely in 56 consecutive games are less than 1 in 20,000.
    """)
    
    # Show famous streaks table
    st.subheader("Famous Hit Streaks")
    famous_df = pd.DataFrame(get_famous_hit_streaks())
    st.dataframe(famous_df, use_container_width=True)
    
    # Create visualization of famous streaks
    fig = px.bar(
        famous_df,
        x='Player',
        y='Streak',
        color='Team',
        text='Streak',
        hover_data=['Year'],
        title="All-Time Greatest MLB Hit Streaks",
        labels={'Streak': 'Consecutive Games with Hit', 'Player': 'Player'},
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Add interesting facts
    st.subheader("Interesting Facts")
    st.markdown("""
    - The longest active MLB hit streak at any given time rarely exceeds 20 games
    - In the modern era (since 2000), the longest hit streak is 38 games by Jimmy Rollins (2005-2006)
    - A 30+ game hitting streak typically occurs only about once every 5 years
    - The record for most consecutive games reaching base safely (hits, walks, hit-by-pitch) is 84 by Ted Williams in 1949
    - The odds of breaking DiMaggio's record have been estimated at 1 in 10,000 seasons by some statisticians
    """)

# Footer
st.markdown("---")
last_updated = "Never" if not st.session_state.refresh_timestamp else st.session_state.refresh_timestamp.strftime('%Y-%m-%d %H:%M:%S')
st.markdown(f"Data source: {'Demo' if data_source == 'Demo Data' else 'MLB API'}. Last update: {last_updated}")