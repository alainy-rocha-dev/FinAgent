# Versões do Spike — AgentPulse
# Data: 2026-10-10
# Commit: versões fixadas após verificação de versões estáveis atuais
# Lockfile gerado em `.venv_lock` via `pip freeze`

| Dependência | Versão | Tipo | Fonte |
|-------------|--------|------|-------|
| Celery | 5.6.0 | Python | PyPI |
| Redis (cliente Python) | 7.4.1 | Python | PyPI |
| Redis (servidor) | 7.2.7 | Docker | Docker Hub (tag fixa: `redis:7.2.7-alpine`) |
| LangGraph | 1.2.10 | Python | PyPI |
| langgraph-checkpoint | 4.2.0 | Python | PyPI (dependência transitiva) |
| langgraph-checkpoint-postgres | 3.1.0 | Python | PyPI |
| psycopg | 3.3.2 | Python | PyPI |
| psycopg-pool | 3.3.3 | Python | PyPI (dependência transitiva) |
| asyncpg | 0.30.0 | Python | PyPI |
| SQLAlchemy | 2.0.35 | Python | PyPI |
| pydantic | 2.11.5 | Python | PyPI |
| pydantic-core | 2.33.2 | Python | PyPI (dependência transitiva) |
| pydantic-settings | 2.11.0 | Python | PyPI |
| Postgres | 16.4 | Docker | Docker Hub (tag fixa: `postgres:16.4`) |

---
**Critério de escolha:** versões estáveis com ≥2 semanas de lançamento (não as absolutamente mais recentes).

**Importante:** LangGraph 1.2.x inclui `interrupt()` e `Command(resume=...)` necessários para o spike de retomada. A versão 0.2.15 anterior **não** possui essas APIs.

**Verificação de funcionalidade:**
- `from langgraph.types import interrupt` ✅ disponível em 1.2.10
- `from langgraph.types import Command` ✅ disponível em 1.2.10
- `langgraph.checkpoint.postgres.PostgresSaver` ✅ disponível em 3.1.0 com `autocommit=True` e `dict_row=True`

*Este arquivo deve ser versionado e atualizado a cada execução do spike.*
*Registre a data e o commit Git correspondente.*