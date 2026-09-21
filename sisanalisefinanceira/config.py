"""
Configurações de ambiente e parâmetros globais do sistema.
"""

import os
from typing import Optional
from pydantic import BaseModel, Field


class Settings(BaseModel):
    """Configurações globais do sistema multiagentes."""
    
    # Provider keys
    openai_api_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("OPENAI_API_KEY", "")
    )
    anthropic_api_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", "")
    )
    
    # Settings
    max_iter: int = Field(default=3, description="Limite máximo de iterações do orquestrador")
    use_mock_fallback: bool = Field(default=True, description="Usar dados mock se scraping/API falhar")
    default_moving_average_window: int = Field(default=2, description="Janela padrão de média móvel")
    output_reports_dir: str = Field(default="reports", description="Diretório para salvar relatórios")
    log_level: str = Field(default="INFO", description="Nível de log")
    default_model: str = Field(default="gpt-4o-mini", description="Modelo LLM padrão")


# Instância global
settings = Settings()
