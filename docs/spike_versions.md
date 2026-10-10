# Versões do Spike — AgentPulse
# Data: 2026-10-10
# Commit: versão corrigida após verificação de versões estáveis atuais

| Dependência | Versão | Tipo | Fonte |
|-------------|--------|------|-------|
| Celery | 5.6.0 | Python | PyPI |
| Redis (cliente Python) | 7.4.1 | Python | PyPI |
| Redis (servidor) | 7.2.7 | Docker | Docker Hub (tag fixa: `redis:7.2.7-alpine`) |
| LangGraph | 1.2.10 | Python | PyPI |
| langgraph-checkpoint-postgres | 3.1.0 | Python | PyPI |
| psycopg | 3.3.2 | Python | PyPI |
| asyncpg | 0.30.0 | Python | PyPI |
| SQLAlchemy | 2.0.35 | Python | PyPI |
| pydantic | 2.11.5 | Python | PyPI |
| pydantic-settings | 2.11.0 | Python | PyPI |
| Postgres | 16.4 | Docker | Docker Hub (tag fixa: `postgres:16.4`) |

---
**Critério de escolha:** versões estáveis com ≥2 semanas de lançamento (não as absolutamente mais recentes).

**Importante:** LangGraph 1.2.x inclui `interrupt()` e `Command(resume=...)` necessários para o spike de retomada. A versão 0.2.15 anterior **não** possui essas APIs.

*Este arquivo deve ser versionado e atualizado a cada execução do spike.*
*Registre a data e o commit Git correspondente.*