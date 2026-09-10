from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://indra:indra@localhost:5432/indra"
    redis_url: str = "redis://localhost:6379/0"
    cors_origins: str = "http://localhost:5173"
    bmc_gis_base_url: str = "https://prsrvgisapp.mcgm.gov.in/server/rest/services/mcgm/MCGMGIS_Departments_Master_All_Layers_WGS/MapServer"
    imd_current_api_url: str = ""
    imd_station_ids: str = ""
    gpm_api_url: str = ""
    gpm_api_token: str = ""
    sentinel_catalog_url: str = ""
    sentinel_client_id: str = ""
    sentinel_client_secret: str = ""
    flood_model_path: str = "backend/data/models/flood_risk.joblib"
    model_confidence_floor: float = 0.50
    model_confidence_ceiling: float = 0.99
    model_untrained_baseline_confidence: float = 0.55
    spatial_grid_step_deg: float = 0.0005
    request_timeout_seconds: float = 45.0
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
