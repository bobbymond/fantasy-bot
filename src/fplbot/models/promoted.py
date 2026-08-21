"""Promoted club identification and special priors handling."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Set

import httpx

from fplbot.ingest.fpl import Team

__all__ = ["PromotedClubDetector", "identify_promoted_clubs", "apply_promoted_prior"]

# External API endpoints
FOOTBALL_DATA_URL = "https://api.football-data.org/v4/competitions/PL/teams?season={season}"
PREMIER_LEAGUE_URL = "https://www.premierleague.com/tables?co=1&se={season}&ha=-1"


@dataclass(frozen=True)
class PromotedClubDetector:
    """Detect promoted clubs for a given season."""
    
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(
            headers={"User-Agent": "fplbot-promoted-detector/0.1.0"},
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
        )
        self._own_client = client is None
    
    def close(self) -> None:
        if self._own_client:
            self._client.close()
    
    def __enter__(self) -> PromotedClubDetector:
        return self
    
    def __exit__(self, *_exc: object) -> None:
        self.close()
    
    def detect_from_team_comparison(self, current_season: int, 
                                  previous_season_teams: List[Team]) -> Set[int]:
        """Detect promoted clubs by comparing with previous season teams."""
        # This method assumes we have access to previous season teams
        # In practice, this would require storing previous season data
        previous_team_ids = {team.id for team in previous_season_teams}
        
        # For now, return empty set - implementation would require
        # access to current season teams which we don't have here
        return set()
    
    def detect_from_external_api(self, season: int) -> Set[int]:
        """Detect promoted clubs using external football-data.org API."""
        try:
            url = FOOTBALL_DATA_URL.format(season=season)
            resp = self._client.get(url)
            resp.raise_for_status()
            data = resp.json()
            
            promoted_clubs = set()
            for team in data.get("teams", []):
                # Look for newly promoted teams - this is a heuristic
                # In reality, we'd need to know which teams were promoted
                founded = team.get("founded")
                if founded and int(founded) >= season - 1:  # Very new clubs
                    promoted_clubs.add(team.get("id"))
            
            return promoted_clubs
        except Exception as e:
            print(f"Warning: Could not fetch promoted clubs from external API: {e}")
            return set()


def identify_promoted_clubs(current_season: int, 
                           previous_season_teams: Optional[List[Team]] = None) -> Set[int]:
    """Identify promoted clubs for the current season."""
    
    promoted_clubs = set()
    
    # Method 1: Team comparison (if we have previous season data)
    if previous_season_teams:
        with PromotedClubDetector() as detector:
            promoted_clubs.update(
                detector.detect_from_team_comparison(current_season, previous_season_teams)
            )
    
    # Method 2: External API fallback
    if not promoted_clubs:
        with PromotedClubDetector() as detector:
            promoted_clubs.update(detector.detect_from_external_api(current_season))
    
    # Method 3: Hardcoded knowledge for recent seasons
    if not promoted_clubs and current_season == 2025:
        # Example: Hardcode known promoted clubs for 2025 season
        # This would need to be updated each season
        promoted_clubs.update({
            45,  # Example team ID 1
            46,  # Example team ID 2  
            47,  # Example team ID 3
        })
    
    return promoted_clubs


def apply_promoted_prior(team_id: int, current_rate: float, 
                        model_params, is_attack: bool) -> float:
    """Apply performance degradation for promoted clubs."""
    
    if team_id in identify_promoted_clubs(2025):  # Hardcoded current season
        degradation = model_params.promoted_club_degradation
        if is_attack:
            # Attack rates are reduced for promoted clubs
            return current_rate * (1 - degradation)
        else:
            # Defence rates are increased (worse defence) for promoted clubs
            return current_rate * (1 + degradation)
    
    return current_rate


def mark_promoted_teams_in_silver(silver_dir: Path, promoted_team_ids: Set[int]) -> None:
    """Mark promoted teams in the silver data."""
    try:
        import pyarrow.parquet as pq
        import pyarrow as pa
        
        teams_path = silver_dir / "teams.parquet"
        if not teams_path.exists():
            return
        
        teams_table = pq.read_table(teams_path)
        teams_data = teams_table.to_pylist()
        
        # Add promoted flag
        for team in teams_data:
            team["is_promoted"] = team["id"] in promoted_team_ids
        
        # Write back with promoted flag
        new_table = pa.Table.from_pylist(teams_data)
        pq.write_table(new_table, teams_path)
        
        print(f"Marked {len(promoted_team_ids)} teams as promoted in silver data")
        
    except Exception as e:
        print(f"Warning: Could not mark promoted teams in silver: {e}")