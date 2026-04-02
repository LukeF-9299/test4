"""
Configuration management for Lite LLM API Service
"""

from pydantic_settings import BaseSettings
from typing import List, Optional, Dict, Any
import os
import json


class Settings(BaseSettings):
    # Environment
    environment: str = "development"  # development, staging, production
    
    # Database Configuration
    database_url: str = "postgresql+asyncpg://username:password@localhost:5432/api_keys_db"
    usage_logs_db_url: str = "postgresql+asyncpg://username:password@localhost:5432/usage_logs_db"
    analytics_db_url: str = "postgresql+asyncpg://username:password@localhost:5432/analytics_db"
    
    # Local SQLite fallback (for development)
    use_local_db: bool = True
    local_db_path: str = "data/lite_llm_local.db"
    
    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_secret_key: str = "your-secret-key-here"
    
    # LiteLLM Configuration
    litellm_debug: bool = True
    litellm_load_balancing_strategy: str = "weighted"
    litellm_health_check_interval: int = 30
    
    # Server Configuration
    servers_config_file: str = "servers_config.json"
    
    # Data Retention
    data_retention_days: int = 180
    
    # CORS Configuration
    allowed_origins: str = "http://localhost:3000,http://localhost:8080"
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "json"
    
    class Config:
        env_file = ".env"
        case_sensitive = False
    
    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",")]
    
    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        return self.environment.lower() == "development"
    
    def get_database_urls(self) -> Dict[str, str]:
        """Get appropriate database URLs based on environment"""
        if self.is_development and self.use_local_db:
            # Use SQLite for local development
            sqlite_url = f"sqlite+aiosqlite:///{self.local_db_path}"
            return {
                "api_keys": sqlite_url,
                "usage_logs": sqlite_url,
                "analytics": sqlite_url
            }
        else:
            # Use PostgreSQL for production
            return {
                "api_keys": self.database_url,
                "usage_logs": self.usage_logs_db_url,
                "analytics": self.analytics_db_url
            }
    
    def load_servers_config(self) -> Dict[str, Any]:
        """Load server configuration from JSON file"""
        try:
            with open(self.servers_config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Servers config file not found: {self.servers_config_file}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in servers config file: {e}")
    
    def save_servers_config(self, config: Dict[str, Any]):
        """Save server configuration to JSON file"""
        with open(self.servers_config_file, 'w') as f:
            json.dump(config, f, indent=2)


# Global settings instance
settings = Settings()
