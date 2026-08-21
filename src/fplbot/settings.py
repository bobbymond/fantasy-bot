"""Load optional `config.yaml` and resolve paths from the process cwd."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_NAME = "config.yaml"


@dataclass(frozen=True)
class Paths:
    """Resolved filesystem locations (absolute)."""

    root: Path
    fpl_cache: Path
    silver: Path
    my_team: Path


@dataclass(frozen=True)
class ModelParams:
    """Projection / strength hyperparameters (``config.yaml`` → ``model``)."""

    # Last N FPL gameweek ids with results in silver (0 = all finished GWs in silver).
    strength_window_gw: int = 0
    
    # Prior season configuration
    prior_season_weight: float = 0.7  # Initial weight for prior season data
    prior_transition_gw: int = 6      # GW where prior influence drops to zero
    promoted_club_degradation: float = 0.15  # Performance degradation for promoted clubs


@dataclass(frozen=True)
class ApiConfig:
    """External API configuration."""
    
    football_data_api_key: str | None = None


@dataclass(frozen=True)
class AppConfig:
    """Paths plus FPL Classic options from ``config.yaml``."""

    paths: Paths
    fpl_entry_id: int | None
    model: ModelParams
    apis: ApiConfig


def _read_config_dict(config_path: Path | None) -> dict[str, Any]:
    root = Path.cwd().resolve()
    cfg_file = (config_path or (root / DEFAULT_CONFIG_NAME)).resolve()
    if not cfg_file.is_file():
        return {}
    with cfg_file.open(encoding="utf-8") as fh:
        loaded = yaml.safe_load(fh)
    return loaded if isinstance(loaded, dict) else {}


def _load_model_params(data: dict[str, Any]) -> ModelParams:
    raw = data.get("model") or {}
    if not isinstance(raw, dict):
        raw = {}
    sw_raw = raw.get("strength_window_gw", 0)
    if sw_raw is None:
        strength_window_gw = 0
    else:
        strength_window_gw = int(sw_raw)
    
    # Prior season parameters
    prior_season_weight = float(raw.get("prior_season_weight", 0.7))
    prior_transition_gw = int(raw.get("prior_transition_gw", 6))
    promoted_club_degradation = float(raw.get("promoted_club_degradation", 0.15))
    
    return ModelParams(
        strength_window_gw=strength_window_gw,
        prior_season_weight=prior_season_weight,
        prior_transition_gw=prior_transition_gw,
        promoted_club_degradation=promoted_club_degradation,
    )


def _load_api_config(data: dict[str, Any]) -> ApiConfig:
    """Load API configuration."""
    apis_raw = data.get("apis") or {}
    if not isinstance(apis_raw, dict):
        apis_raw = {}
    
    football_data_raw = apis_raw.get("football_data") or {}
    if not isinstance(football_data_raw, dict):
        football_data_raw = {}
    
    football_data_api_key = football_data_raw.get("api_key")
    
    return ApiConfig(
        football_data_api_key=football_data_api_key
    )


def load_app_config(*, config_path: Path | None = None) -> AppConfig:
    """Paths + ``fpl.entry_id`` (may be ``None``) + ``model`` params."""
    data = _read_config_dict(config_path)
    paths_raw = data.get("paths") or {}
    if not isinstance(paths_raw, dict):
        paths_raw = {}
    root = Path.cwd().resolve()
    fpl_cache = (root / Path(paths_raw.get("fpl_cache", "cache/fpl"))).resolve()
    silver = (root / Path(paths_raw.get("silver", "data/silver"))).resolve()
    my_team = (root / Path(paths_raw.get("my_team", "cache/my_team.json"))).resolve()
    paths = Paths(root=root, fpl_cache=fpl_cache, silver=silver, my_team=my_team)

    fpl_raw = data.get("fpl") or {}
    if not isinstance(fpl_raw, dict):
        fpl_raw = {}
    raw_eid = fpl_raw.get("entry_id")
    fpl_entry_id: int | None
    if raw_eid is None:
        fpl_entry_id = None
    else:
        fpl_entry_id = int(raw_eid)

    return AppConfig(
        paths=paths,
        fpl_entry_id=fpl_entry_id,
        model=_load_model_params(data),
        apis=_load_api_config(data)
    )


def load_paths(*, config_path: Path | None = None) -> Paths:
    """Read `config.yaml` from cwd when present; otherwise use defaults."""
    return load_app_config(config_path=config_path).paths


def load_model_params(*, config_path: Path | None = None) -> ModelParams:
    """Model hyperparameters only (defaults if no config)."""
    return load_app_config(config_path=config_path).model
