from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "BioDataset Scout API"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    ncbi_api_base: str = "https://api.ncbi.nlm.nih.gov/datasets/v2"
    ncbi_api_key: str = ""
    allow_live_preview: bool = True
    max_preview_seconds: int = 20

    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore', env_prefix='BIODATASET_')

settings = Settings()
