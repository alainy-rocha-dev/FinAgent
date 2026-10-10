# Ideation, FinAgent + AgentPulse (Projeto 4)

> Selo 🟡 PLANEJADO em todos os itens, sujeito a validação.

## Brief original
Projeto 4: FinAgent + AgentPulse — Mover os agentes do FinAgent (DataCollector, QuantAnalyst, ReportWriter) para serviços que rodam sobre a infraestrutura do AgentPulse (FastAPI + Celery + Redis + PostgreSQL). Adicionar: checkpoints em Postgres, retry idempotente, aprovação humana (interrupt/resume), teste de caos (matar worker no meio e provar retomada sem duplicar). Caso de uso concreto: Análise Financeira de Ativos (o fluxo original do FinAgent). Requisitos de produção: autenticação, rate limiting, idempotência (chave no POST), timeouts, limite de custo por tarefa, observabilidade (traces/métricas). Cobertura total de testes (%) + teste de carga (Locust). Correções: typo "Altura Escala" → "Alta Escala", diagrama de arquitetura renderizado.

## Problema
🟡 O FinAgent hoje roda como CLI standalone sem infra de produção; o AgentPulse tem a infra (FastAPI + Celery + Redis + Postgres) mas não os agentes financeiros. Quem sente: engenheiros/teams que querem análises financeiras confiáveis, auditáveis, com retry/idempotência/observabilidade nativas — no momento de colocar em produção.

## Valor entregue
🟡 O usuário consegue submeter uma análise de mercado e receber um relatório em que cada número foi conferido contra o cálculo original, que só é publicado após aprovação humana, que sobrevive à queda de um worker sem duplicar nem perder trabalho, e que deixa um registro auditável de cada etapa.

## Alternativas existentes
🟡 LangGraph oferece checkpoint e interrupção para aprovação humana, mas não fornece a API assíncrona, a idempotência de entrada e a trilha de auditoria; este projeto os constrói em volta dele.
Temporal, Inngest e Restate oferecem execução durável robusta, mas não trazem semântica de agentes nem verificação numérica, e exigem mais infraestrutura. O projeto usa Celery + Postgres por simplicidade e documenta a troca como decisão de arquitetura (ADR), com Temporal como caminho de evolução.
Airflow, Prefect e Dagster orquestram pipelines previsíveis; não são desenhados para laços de agentes com estado retomável por interrupção humana.
CrewAI, OpenAI Agents SDK e Claude Agent SDK definem agentes, mas a durabilidade e a auditoria ficam por conta do usuário.
Plataformas gerenciadas (Bedrock, Vertex) resolvem infraestrutura com lock-in de nuvem, e a validação numérica específica do domínio continua sendo responsabilidade do usuário.
Lacuna que o projeto preenche: nenhuma dessas opções combina, de forma verificável, execução retomável, publicação sem duplicidade, aprovação humana e conferência determinística de cada número do relatório.

## Público-alvo (bruto)
🟡 Analista de dados ou tesouraria em uma fintech, que precisa entregar relatórios de mercado que um gestor possa aprovar e auditar, e não apenas relatórios bem escritos.
Papéis de apoio: o aprovador (gestor ou risco), que libera a publicação, e o engenheiro de plataforma, que opera o serviço e acompanha os SLOs.

## Métricas de sucesso
🟡 Métrica principal: 0 publicações duplicadas e 0 perdidas em 100 execuções de caos (kill aleatório do worker durante a execução), medido em job noturno de CI e publicado no README.
Métricas de apoio:
- Taxa de detecção da auditoria numérica sobre uma suíte de mutações com classes documentadas (meta: 100% nas classes cobertas, com as classes não cobertas listadas).
- p95 do tempo até AWAITING_APPROVAL, medido com o LLM simulado (stub) para isolar o sistema, e separadamente com o LLM real em carga baixa; as metas serão fixadas após a primeira medição.

## Premissas a validar
🟡 Retomada sem condição de corrida: Celery (com acks_late), o checkpointer do LangGraph e interrupt compõem de forma segura sob falha e concorrência. Se não, a garantia de "sem duplicar nem perder" não se sustenta. Mitigação: spike inicial com testes de concorrência, lock por tarefa e transições de estado atômicas.
🟡 Auditoria numérica confiável: é possível extrair e conferir os números do relatório de forma robusta. Se o texto livre do LLM escapar da verificação, a auditoria dá falsa segurança. Mitigação: o Redator produz saída estruturada que referencia valores calculados por chave, e a auditoria é medida por uma suíte de mutações.
🟡 Dados de mercado estáveis o bastante: os provedores gratuitos permanecem utilizáveis e com termos de uso compatíveis. Se não, o coletor degrada. Mitigação: coletor atrás de uma interface com mais de um provedor, e dados simulados sempre marcados e bloqueando a publicação.

## Notas
🟡 ADR obrigatório: docs/adr/001-celery-vs-temporal.md comparando custo operacional, semântica de retomada, curva de aprendizado e maturidade para agentes.
🟡 Spike inicial (2-3 dias) para validar a premissa de retomada sem condições de corrida antes de construir o resto.
🟡 Correções do FinAgent original: typo "Altura Escala" → "Alta Escala", diagrama de arquitetura renderizado, dados simulados nunca passam em silêncio (data_quality: LIVE | SIMULATED).
🟡 LangGraph como motor de produção; CrewAI mantido apenas como adaptador para benchmark do Projeto 5.
🟡 Planner e Revisor adicionados ao grafo para torná-lo um sistema de agentes (não apenas pipeline).
🟡 Fase 6 (Coletor como serviço MCP/A2A) opcional, só se houver ganho real de arquitetura após fases 1-5.

---
Gerado por reversa-ideator em 2026-09-29T19:45:00Z
Fonte: newproject-brief.md
Sessão de ideação reaproveitada: none