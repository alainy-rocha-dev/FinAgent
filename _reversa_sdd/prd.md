# PRD: FinAgent + AgentPulse (Projeto 4)

> Selo 🟡 PLANEJADO. Documento gerado a partir de ideation + personas.

**Versão:** 1.0
**Data:** 2026-09-29T20:30:00Z
**Autor:** reversa-drafter
**Status:** rascunho

---

## 1. Problema

🟡 O FinAgent hoje roda como CLI standalone sem infraestrutura de produção (sem fila, sem retomada, sem idempotência, sem observabilidade, sem aprovação humana); o AgentPulse tem a infraestrutura (FastAPI + Celery + Redis + PostgreSQL) mas não possui agentes financeiros. A fusão resolve a lacuna: análises financeiras confiáveis, auditáveis, com retry/idempotência/observabilidade nativas, aprovação humana e garantias de retomada sem duplicação.

### Quem sente
🟡 Analistas de dados/tesouraria em fintechs que disparam análises no fechamento do dia ou antes de reuniões com prazo, e enfrentam falhas no meio do processo, dúvida se os dados são reais ou simulados, e incapacidade de explicar a origem de um número quando questionados pelo gestor.
🟡 Gestores de tesouraria/risco que aprovam relatórios sob pressão de tempo (minutos), sem evidência de que os números foram conferidos, se os dados são reais e atuais, e sem registro imutável do que foi verificado e por quem.

---

## 2. Personas-alvo

🟡 Referência completa em [`personas.md`](./personas.md). Resumo:

- **analista-dados**: 🟡 Analista de dados/tesouraria em fintech — dor principal: falta de confiança no processo (falha no meio sem retomada, dado simulado passando como real, impossibilidade de rastrear a origem de um número).
- **aprovador**: 🟡 Gestor de tesouraria/risco em fintech — dor principal: decidir sem evidência sob pressão de tempo, medo de publicar dado simulado/desatualizado, ausência de registro de quem aprovou o quê.

---

## 3. Métricas de sucesso

🟡 Derivadas do ideation.md, com unidade e alvo explícitos.

| Métrica | Unidade | Alvo | Prazo |
|---|---|---|---|
| 🟡 Publicações duplicadas ou perdidas em execuções de caos | contagem / 100 execuções | 0 | 3 meses |
| 🟡 Taxa de detecção da auditoria numérica sobre classes de mutação cobertas | % | 100% nas classes cobertas | 3 meses |
| 🟡 p95 tempo até AWAITING_APPROVAL (LLM stub) | segundos | a definir após primeira medição | 3 meses |
| 🟡 p95 tempo até AWAITING_APPROVAL (LLM real, carga baixa) | segundos | a definir após primeira medição | 3 meses |
| 🟡 Cobertura de testes (pytest + Locust) | % | ≥ 90% | 3 meses |

---

## 4. Escopo (in)

🟡 Derivado de ideation.md + personas.md + jornadas.

- 🟡 API assíncrona FastAPI com POST /tasks (Idempotency-Key obrigatória, constraint única no banco) e GET /tasks/{id}
- 🟡 Fila Celery + Redis com acks_late, worker executando grafo LangGraph
- 🟡 Checkpointer Postgres do LangGraph (thread_id = task_id) com persistência de estado a cada nó
- 🟡 Interrupt no grafo para aprovação humana → status AWAITING_APPROVAL
- 🟡 Endpoints POST /tasks/{id}/approve|reject com justificativa; retomada via reenfileiramento com mesmo thread_id
- 🟡 Publicação única garantida por registro `published(task_id)` com constraint única
- 🟡 Grafo LangGraph: Planner → Coletor → Analista Quant → Redator → Auditoria numérica → Revisor → (interrupt) → Publicar
- 🟡 Auditoria numérica: Redator produz saída estruturada referenciando valores calculados por chave; validador compara relatório vs. métricas determinísticas
- 🟡 Coletor com data_quality: LIVE | SIMULATED; SIMULATED bloqueia publicação ou exige aprovação explícita
- 🟡 Retry com backoff exponencial + jitter apenas para erros transitórios (API de mercado, LLM); erros de validação não retentam
- 🟡 Autenticação (API key), rate limiting, timeout por etapa, orçamento de tokens/custo por tarefa (estado BUDGET_EXCEEDED)
- 🟡 Observabilidade: OpenTelemetry traces API→Celery→nós; métricas (duração, retries, falhas, tokens, custo); dashboard
- 🟡 Tabela de eventos imutável (trilha de auditoria) com snapshot do que o aprovador viu no momento da decisão
- 🟡 Página HTML mínima de aprovação (servida pelo FastAPI, template Jinja2) com resumo de decisão e botões Aprovar/Rejeitar
- 🟡 Testes de caos: docker kill do worker no meio, repetição N vezes, contagem de publicações duplicadas/perdidas
- 🟡 Teste de carga Locust: 50 POSTs concorrentes com mesma Idempotency-Key → uma tarefa; 10 req/s sustentado
- 🟡 ADR docs/adr/001-celery-vs-temporal.md
- 🟡 Correções do FinAgent: typo "Altura Escala" → "Alta Escala", diagrama de arquitetura renderizado

---

## 5. Não-objetivos (out)

🟡 Lista explícita do que NÃO está incluso.

- 🟡 Recomendação de investimento, execução de ordens, gestão de portfólio
- 🟡 Multiusuário com permissões finas (RBAC), login social, SSO
- 🟡 Front-end completo para o Analista (a interação do analista permanece via API)
- 🟡 Coletor exposto como serviço MCP/A2A (Fase 6 opcional, só se houver ganho real após fases 1-5)
- 🟡 CrewAI como motor de produção (mantido apenas como adaptador para benchmark Projeto 5)
- 🟡 Temporal/Inngest/Restate na versão inicial (documentado em ADR como caminho de evolução)

---

## 6. Restrições

🟡 Derivadas das fontes e perguntas de cobertura.

| Tipo | Descrição |
|---|---|
| 🟡 Técnica | 🟡 Python 3.11+, FastAPI, Celery, Redis, PostgreSQL, LangGraph, SQLAlchemy, Pydantic, OpenTelemetry, pytest, Locust |
| 🟡 Prazo | 🟡 ~4 semanas para fases 1-5 (conforme plano do ideation.md) |
| 🟡 Compliance | 🟡 Projeto é implementação de referência, não declara conformidade regulatória. Usa apenas dados públicos de mercado; não processa dados pessoais de clientes. Único dado pessoal: identificador do aprovador + horário da decisão. Trilha de auditoria append-only (sem UPDATE/DELETE), retenção configurável, segregação de ambientes por configuração, segredos fora do código, provedores com termos de uso compatíveis, zero dados pessoais enviados ao LLM. Fora de escopo: recomendação de investimento, execução de ordens, envio a CVM/Banco Central. |
| 🟡 Orçamento | 🟡 Limite por tarefa: teto de tokens e custo estimado (BUDGET_EXCEEDED ao estourar, valor = ~3x média medida em 20 execuções). Limite mensal global configurável (recusa novas tarefas ao atingir, valor inicial a definir). Modelos: pequeno/barato para Planner e Redator; maior só se auditoria mostrar ganho; suporte opcional Ollama. Testes (caos, Locust, CI) usam stub LLM sem custo. Infra: Docker Compose referência, deploy opcional em VM pequena, sem serviços gerenciados no MVP. |
| 🟡 Dados de mercado | 🟡 Dependência de provedores gratuitos (Yahoo Finance/yfinance) sem SLA; confirmar termos de uso antes de manter como padrão. Provedor alternativo: Banco Central do Brasil para câmbio (API pública). |

---

## 7. Dependências externas

🟡 Serviços, APIs, dados externos.

- 🟡 Yahoo Finance (ou yfinance) para cotações de ações/ETFs — sem API oficial, sem SLA
- 🟡 Banco Central do Brasil (opcional) para câmbio oficial — API pública
- 🟡 OpenAI / Anthropic API para LLM (Planner, Redator, Revisor) — custo por token, rate limits
- 🟡 PostgreSQL 15+, Redis 7+ — infraestrutura própria ou gerenciada

---

## 8. Riscos

🟡 Derivados de: (a) Premissas a validar do ideation.md, (b) gaps nas jornadas das personas, (c) restrições.

| Risco | Impacto | Probabilidade | Mitigação proposta |
|---|---|---|---|
| 🟡 Condição de corrida na retomada (Celery acks_late + checkpointer + interrupt) | 🟡 alto | 🟡 média | Spike inicial 2-3 dias com grafo mínimo, lock por task_id (advisory lock Postgres), transições de estado atômicas (UPDATE ... WHERE status = 'AWAITING_APPROVAL') |
| 🟡 Auditoria numérica frágil: extração de números do texto livre do LLM falha | 🟡 alto | 🟡 média | Redator emite saída estruturada (valores por chave calculada), auditoria compara chaves, suíte de mutações com classes documentadas (dígito trocado, unidade trocada, arredondamento, inventado, valor de outro ativo) |
| 🟡 Provedor de dados de mercado (Yahoo Finance) instável ou muda endpoint | 🟡 médio | 🟡 alta | Coletor atrás de interface plugável, segundo provedor (BCB para câmbio), data_quality = SIMULATED bloqueia publicação, fallback mock controlado |
| 🟡 Latência/custo do LLM inviabiliza volume ou p95 | 🟡 médio | 🟡 média | Modelo pequeno/local (Ollama) para Redator; orçamento por tarefa (BUDGET_EXCEEDED); stub LLM para testes de desempenho |
| 🟡 Aprovador não consegue usar API (nível técnico básico) | 🟡 alto | 🟡 baixa (já endereçado) | Página HTML mínima de aprovação no MVP, servida pelo FastAPI |
| 🟡 Teste de caos (docker kill) não roda em CI padrão | 🟡 médio | 🟡 média | Job noturno/manual separado; CI de PR roda subconjunto rápido (unit + integração sem kill) |

---

## 9. Critérios de aceite (alto nível)

🟡 Um critério por persona principal, formato Dado/Quando/Então.

- 🟡 **Dado** analista submete análise via POST /tasks com Idempotency-Key, **Quando** worker processa e grafo chega ao interrupt, **Então** tarefa fica AWAITING_APPROVAL com data_quality, auditoria e relatório visíveis.
- 🟡 **Dado** tarefa em AWAITING_APPROVAL, **Quando** aprovador acessa página de aprovação e clica Aprovar, **Então** tarefa transiciona para PUBLISHED exatamente uma vez, evento de aprovação gravado com snapshot imutável.
- 🟡 **Dado** worker é morto (docker kill) durante execução do grafo, **Quando** worker reinicia e retoma a tarefa, **Então** tarefa conclui sem publicação duplicada nem perda, mantendo idempotência.
- 🟡 **Dado** 50 requisições POST concorrentes com mesma Idempotency-Key, **Quando** processadas, **Então** exatamente uma tarefa é criada no banco.
- 🟡 **Dado** relatório com números adulterados (classes de mutação cobertas), **Quando** auditoria numérica roda, **Então** 100% das adulterações nas classes cobertas são detectadas.
- 🟡 **Dado** provedor de mercado cai e coletor usa mock, **Quando** data_quality = SIMULATED, **Então** publicação é bloqueada ou exige aprovação explícita, e relatório exibe aviso destacado.

---

## Pendências de cobertura

🟡 Todas as seções anteriormente marcadas [INDEFINIDO] foram resolvidas com as respostas do usuário:

1. **Compliance:** Resolvido — projeto é implementação de referência, não declara conformidade regulatória; trilha append-only, retenção configurável, zero dados pessoais ao LLM.
2. **Orçamento:** Resolvido — teto por tarefa (~3x média medida), limite mensal configurável, modelos pequenos/baratos + Ollama opcional, stub LLM em testes, Docker Compose referência.

---

Gerado por reversa-drafter em 2026-09-29T20:30:00Z
Fontes: ideation.md, personas.md