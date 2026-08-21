"""Historical season data ingestion for team priors."""

from __future__ import annotations

import datetime
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

from fplbot.ingest.client import FplClient
from fplbot.ingest.errors import FplIngestError
from fplbot.ingest.fpl import Bootstrap, Team

# Historical FPL API endpoints (may require research)
HISTORICAL_BOOTSTRAP_URL = "https://fantasy.premierleague.com/api/bootstrap-static/{season}/"
HISTORICAL_FIXTURES_URL = "https://fantasy.premierleague.com/api/fixtures/?season={season}"

# External API fallback
FOOTBALL_DATA_URL = "https://api.football-data.org/v4/competitions/PL/teams?season={season}"

__all__ = ["PriorSeasonClient", "SeasonPrior", "fetch_previous_season_data"]


@dataclass(frozen=True)
class SeasonPrior:
    """Team strength priors from previous season."""
    
    season: int
    team_id: int
    team_name: str
    home_attack: float
    away_attack: float
    home_defence: float
    away_defence: float
    matches_played: int
    
    @classmethod
    def from_team_stats(cls, season: int, team: Team, matches_played: int) -> SeasonPrior:
        """Create prior from team statistics."""
        return cls(
            season=season,
            team_id=team.id,
            team_name=team.name,
            home_attack=team.strength_attack_home / 100.0,
            away_attack=team.strength_attack_away / 100.0,
            home_defence=team.strength_defence_home / 100.0,
            away_defence=team.strength_defence_away / 100.0,
            matches_played=matches_played
        )


class PriorSeasonClient:
    """Client for fetching historical season data."""
    
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(
            headers={"User-Agent": "fplbot-prior-season/0.1.0"},
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
        )
        self._own_client = client is None
    
    def close(self) -> None:
        if self._own_client:
            self._client.close()
    
    def __enter__(self) -> PriorSeasonClient:
        return self
    
    def __exit__(self, *_exc: object) -> None:
        self.close()
    
    def fetch_season_bootstrap(self, season: int) -> Optional[Bootstrap]:
        """Fetch bootstrap data for a specific season."""
        try:
            url = HISTORICAL_BOOTSTRAP_URL.format(season=season)
            resp = self._client.get(url)
            resp.raise_for_status()
            data = resp.json()
            
            if not isinstance(data, dict):
                raise FplIngestError(f"Season {season}: bootstrap JSON must be an object")
            
            return Bootstrap.from_dict(data)
        except httpx.HTTPError as e:
            print(f"Warning: Could not fetch historical season {season}: {e}")
            return None
    
    def fetch_season_fixtures(self, season: int) -> Optional[List[Dict[str, Any]]]:
        """Fetch fixtures for a specific season."""
        try:
            url = HISTORICAL_FIXTURES_URL.format(season=season)
            resp = self._client.get(url)
            resp.raise_for_status()
            data = resp.json()
            
            if not isinstance(data, list):
                raise FplIngestError(f"Season {season}: fixtures JSON must be an array")
            
            return data
        except httpx.HTTPError as e:
            print(f"Warning: Could not fetch fixtures for season {season}: {e}")
            return None
    
    def calculate_team_priors(self, season: int) -> List[SeasonPrior]:
        """Calculate team strength priors for a season."""
        bootstrap = self.fetch_season_bootstrap(season)
        fixtures = self.fetch_season_fixtures(season)
        
        if not bootstrap or not fixtures:
            return []
        
        # Count matches played per team
        matches_played = {team.id: 0 for team in bootstrap.teams}
        for fixture in fixtures:
            if fixture.get("finished", False):
                matches_played[fixture["team_h"]] += 1
                matches_played[fixture["team_a"]] += 1
        
        priors = []
        for team in bootstrap.teams:
            prior = SeasonPrior.from_team_stats(
                season=season,
                team=team,
                matches_played=matches_played.get(team.id, 0)
            )
            priors.append(prior)
        
        return priors


def fetch_previous_season_data(current_season: int) -> List[SeasonPrior]:
    """Fetch team priors from the previous season."""
    previous_season = current_season - 1
    
    with PriorSeasonClient() as client:
        priors = client.calculate_team_priors(previous_season)
        
        if not priors:
            print(f"Warning: No priors found for season {previous_season}")
            print("Falling back to external data source...")
            # TODO: Implement external API fallback
            
        return priors


def save_end_of_season_snapshot(season: int, output_path: str) -> None:
    """Save end-of-season snapshot for future use as priors."""
    with PriorSeasonClient() as client:
        priors = client.calculate_team_priors(season)
        
        if priors:
            snapshot = {
                "season": season,
                "created_at": datetime.datetime.now().isoformat(),
                "priors": [prior.__dict__ for prior in priors]
            }
            
            with open(output_path, 'w') as f:
                json.dump(snapshot, f, indent=2)
            
            print(f"Saved {len(priors)} team priors for season {season} to {output_path}")
        else:
            print(f"Warning: No priors calculated for season {season}")