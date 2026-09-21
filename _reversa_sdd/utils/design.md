# Unit: `utils` — Design Técnico

> Especificação de design das funções utilitárias de suporte.

## Interface

| Símbolo | Assinatura | Retorno | Observação |
|---------|-----------|---------|------------|
| `setup_logging` | `(level: str = "INFO")` | `None` | Previne duplicação verificando `root_logger.handlers`. |
| `handle_max_iter_reached` | `(symbol: str, max_iter: int)` | `str` | Retorna e grava mensagem de erro de salvaguarda. |

## Decisões de Design Identificadas

| Decisão | Evidência no código | Confiança |
|---------|---------------------|-----------|
| Formato de log ISO estandardizado `[date] [level] [name] msg` | `sisanalisefinanceira/utils/logging.py:13-16` | 🟢 |
| Idempotência na adição de handlers ao logger raiz | `sisanalisefinanceira/utils/logging.py:25-26` | 🟢 |
