# MLB Hit Streak Dashboard

A Streamlit dashboard for tracking and visualizing current MLB hit streaks.

## Features

- Real-time MLB hit streak data from MLB Stats API
- Interactive visualizations of current hit streaks
- Historical hit streak context and comparison
- Educational content about hit streaks and their significance
- Cached data to ensure fast loading and reliability

## Versions

The repository contains several versions of the dashboard:

- `hit_streaks.py`: Original version with basic functionality
- `simple_streaks.py`: Improved version with direct MLB API access and better error handling
- `simple_streaks_optimized.py`: Performance-optimized version with reduced API calls
- `simple_streaks_cached.py`: Fully-cached version that loads instantly and refreshes on demand

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/hit_streaks.git
cd hit_streaks

# Install required packages
pip install streamlit pandas numpy plotly requests
```

## Usage

```bash
# Run the latest version
streamlit run simple_streaks_cached.py
```

## Data Sources

- MLB Stats API for current player statistics
- Historical records for context and comparison

## License

MIT