# pyright: ignore [reportMissingImports]
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    APP_ENV: str = Field(default="dev", description="Application environment (dev/prod)")
    
    # Database Settings (Will attempt PostgreSQL first, then fallback to SQLite if connection fails)
    POSTGRES_USER: str = Field(default="postgres", description="PostgreSQL Username")
    POSTGRES_PASSWORD: str = Field(default="postgres", description="PostgreSQL Password")
    POSTGRES_HOST: str = Field(default="localhost", description="PostgreSQL Host")
    POSTGRES_PORT: int = Field(default=5432, description="PostgreSQL Port")
    POSTGRES_DB: str = Field(default="quantforge_db", description="PostgreSQL Database Name")
    
    # SQLite fallback path inside backend directory
    SQLITE_DATABASE_PATH: str = Field(default="sqlite:///quantforge.db", description="Fallback SQLite connection string")
    
    # Data collection mode
    # Attempt live NSE option-chain scraping by default; fall back to simulation only if scraping fails.
    NSE_SIMULATE: bool = Field(default=False, description="Use simulated option chain data instead of direct NSE scraping")
    COLLECTION_INTERVAL_SECONDS: int = Field(default=60, description="Option chain scrape interval in seconds")
    
    # Derivatives specifications
    LOT_SIZE_NIFTY: int = Field(default=25, description="NIFTY lot size")
    LOT_SIZE_BANKNIFTY: int = Field(default=15, description="BANKNIFTY lot size")
    
    # Volatility models settings
    RISK_FREE_RATE: float = Field(default=0.07, description="Risk-free interest rate (e.g. 0.07 for 7% p.a.)")

    class Config:
        env_file = Path(__file__).resolve().parent / ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()
