"""Generate default prior season data for team strengths."""

import json
from pathlib import Path
from typing import Dict, List, Any

# Default team strength ratings based on typical Premier League performance
# These are educated guesses for the 2025 season
DEFAULT_TEAM_PRIORS = {
    # Top teams (attack: 1.8-2.2, defence: 0.6-0.9)
    1: {"name": "Arsenal", "home_attack": 2.0, "away_attack": 1.8, "home_defence": 0.7, "away_defence": 0.8},
    2: {"name": "Aston Villa", "home_attack": 1.7, "away_attack": 1.5, "home_defence": 0.8, "away_defence": 1.0},
    3: {"name": "Bournemouth", "home_attack": 1.4, "away_attack": 1.2, "home_defence": 1.1, "away_defence": 1.3},
    4: {"name": "Brentford", "home_attack": 1.5, "away_attack": 1.3, "home_defence": 1.0, "away_defence": 1.2},
    5: {"name": "Brighton", "home_attack": 1.8, "away_attack": 1.6, "home_defence": 0.9, "away_defence": 1.1},
    6: {"name": "Chelsea", "home_attack": 1.6, "away_attack": 1.4, "home_defence": 0.9, "away_defence": 1.1},
    7: {"name": "Crystal Palace", "home_attack": 1.3, "away_attack": 1.1, "home_defence": 1.0, "away_defence": 1.2},
    8: {"name": "Everton", "home_attack": 1.2, "away_attack": 1.0, "home_defence": 1.1, "away_defence": 1.3},
    9: {"name": "Fulham", "home_attack": 1.4, "away_attack": 1.2, "home_defence": 1.0, "away_defence": 1.2},
    10: {"name": "Hull", "home_attack": 1.1, "away_attack": 0.9, "home_defence": 1.3, "away_defence": 1.5},  # Promoted
    11: {"name": "Ipswich", "home_attack": 1.1, "away_attack": 0.9, "home_defence": 1.3, "away_defence": 1.5},  # Promoted
    12: {"name": "Leeds", "home_attack": 1.3, "away_attack": 1.1, "home_defence": 1.1, "away_defence": 1.3},
    13: {"name": "Leicester", "home_attack": 1.6, "away_attack": 1.4, "home_defence": 1.0, "away_defence": 1.2},
    14: {"name": "Liverpool", "home_attack": 2.2, "away_attack": 2.0, "home_defence": 0.6, "away_defence": 0.8},
    15: {"name": "Man City", "home_attack": 2.3, "away_attack": 2.1, "home_defence": 0.5, "away_defence": 0.7},
    16: {"name": "Man Utd", "home_attack": 1.9, "away_attack": 1.7, "home_defence": 0.8, "away_defence": 1.0},
    17: {"name": "Newcastle", "home_attack": 1.8, "away_attack": 1.6, "home_defence": 0.8, "away_defence": 1.0},
    18: {"name": "Nott'm Forest", "home_attack": 1.3, "away_attack": 1.1, "home_defence": 1.1, "away_defence": 1.3},
    19: {"name": "Southampton", "home_attack": 1.2, "away_attack": 1.0, "home_defence": 1.2, "away_defence": 1.4},
    20: {"name": "Tottenham", "home_attack": 1.9, "away_attack": 1.7, "home_defence": 0.8, "away_defence": 1.0},
    21: {"name": "West Ham", "home_attack": 1.5, "away_attack": 1.3, "home_defence": 1.0, "away_defence": 1.2},
    22: {"name": "Wolves", "home_attack": 1.4, "away_attack": 1.2, "home_defence": 1.0, "away_defence": 1.2},
    # New teams for 2026 season
    45: {"name": "Coventry", "home_attack": 1.0, "away_attack": 0.8, "home_defence": 1.4, "away_defence": 1.6},  # Promoted
    46: {"name": "Sunderland", "home_attack": 1.0, "away_attack": 0.8, "home_defence": 1.4, "away_defence": 1.6},  # Promoted
}

def generate_default_priors(season: int = 2025) -> List[Dict[str, Any]]:
    """Generate default prior season data."""
    priors = []
    
    for team_id, team_data in DEFAULT_TEAM_PRIORS.items():
        prior = {
            "season": season,
            "team_id": team_id,
            "team_name": team_data["name"],
            "home_attack": team_data["home_attack"],
            "away_attack": team_data["away_attack"],
            "home_defence": team_data["home_defence"],
            "away_defence": team_data["away_defence"],
            "matches_played": 38,  # Full season
        }
        priors.append(prior)
    
    return priors

def write_default_priors_to_silver(silver_dir: Path) -> None:
    """Write default priors to silver directory."""
    from fplbot.silver.writer import write_season_priors
    
    priors = generate_default_priors(season=2025)
    write_season_priors(
        silver_dir=silver_dir,
        priors=priors,
        season=2025
    )
    print(f"Written {len(priors)} default team priors for season 2025 to {silver_dir}/season_priors.parquet")

if __name__ == "__main__":
    import sys
    silver_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/silver")
    write_default_priors_to_silver(silver_dir)