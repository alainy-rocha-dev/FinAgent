"""
Utilitário de configuração de logs e tratamento de erros do sistema multiagentes.
"""

import logging
import sys


def setup_logging(level: str = "INFO"):
    """Configura o sistema de log padrão para o pacote."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Evitar manipuladores duplicados
    if not root_logger.handlers:
        root_logger.addHandler(console_handler)


def handle_max_iter_reached(symbol: str, max_iter: int) -> str:
    """Gera mensagem formatada de salvaguarda quando MAX_ITER_REACHED for disparado."""
    logger = logging.getLogger("sisanalisefinanceira.guard")
    msg = f"SALVAGUARDA ATIVADA: Limite de {max_iter} iterações atingido para o símbolo '{symbol}' sem convergência."
    logger.error(msg)
    return msg
