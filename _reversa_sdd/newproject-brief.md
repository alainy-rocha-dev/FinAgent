# Brief inicial, /reversa-new

> Selo 🟡 PLANEJADO. Documento de entrada do time Code New Project Agents.

**Data:** 2026-09-29T19:30:00Z
**Usuário:** arocha

## Ideia original
Projeto 4: FinAgent + AgentPulse — Mover os agentes do FinAgent (DataCollector, QuantAnalyst, ReportWriter) para serviços que rodam sobre a infraestrutura do AgentPulse (FastAPI + Celery + Redis + PostgreSQL). Adicionar: checkpoints em Postgres, retry idempotente, aprovação humana (interrupt/resume), teste de caos (matar worker no meio e provar retomada sem duplicar). Caso de uso concreto: Análise Financeira de Ativos (o fluxo original do FinAgent). Requisitos de produção: autenticação, rate limiting, idempotência (chave no POST), timeouts, limite de custo por tarefa, observabilidade (traces/métricas). Cobertura total de testes (%) + teste de carga (Locust). Correções: typo "Altura Escala" → "Alta Escala", diagrama de arquitetura renderizado.

---

Gerado por /reversa-new em 2026-09-29T19:30:00Z