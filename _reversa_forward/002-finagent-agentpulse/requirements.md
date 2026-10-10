# Requirements: Migração FinAgent para Infraestrutura AgentPulse

> Identificador: `002-finagent-agentpulse`
> Data: `2026-09-29`
> Pasta da extração reversa: `_reversa_sdd/`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA / DÚVIDA

## 1. Resumo executivo

Esta feature migra os três agentes do FinAgent (`DataCollectorAgent`, `QuantAnalystAgent`, `ReportWriterAgent`) para executarem como serviços independentes sobre a infraestrutura do AgentPulse. A migração introduz persistência de checkpoints em PostgreSQL, retry idempotente com chaves de idempotência, aprovação humana via interrupt/resume, e um teste de caos que comprova retomada sem duplicação após falha catastrófica do worker. A comunicação entre agentes via protocolo A2A é escopo futuro (próximo passo).

## 2. Contexto a partir do legado

| Fonte | Trecho relevante | Confidência |
|-------|------------------|-------------|
| `_reversa_sdd/architecture.md#3-modelo-de-entidades-e-schemas-pydantic-erd-resumido` | Schemas Pydantic imutáveis: `MarketDataPayload`, `QuantAnalysisMetrics`, `AgentState` | 🟢 |
| `_reversa_sdd/architecture.md#4-estilos-arquiteturais-e-padroes-de-projeto` | Adapter Pattern para orquestração intercambiável (LangGraph/CrewAI); Strategy Pattern para tools determinísticas; Anti-Hallucination Guardrail | 🟢 |
| `_reversa_sdd/domain.md#2-regras-de-negocio-implicitas-business-rules` | RN-01 a RN-06: sanitização de símbolos, mock fallback, tamanho mínimo de série, cálculo determinístico, validação anti-alucinação, teto de iterações | 🟢 |
| `_reversa_sdd/inventory.md#estrutura-de-diretorios` | Estrutura atual: `agents/`, `orchestrators/`, `utils/`, `models.py`, `cli.py` | 🟢 |
| `_reversa_sdd/code-analysis.md#2-analise-detalhada-dos-modulos` | Detalhamento dos 3 agentes e 2 orquestradores; fluxos de controle e algoritmos | 🟢 |
| `_reversa_sdd/architecture.md#5-dividas-tecnicas-e-oportunidades-identificadas` | Ausência de `requirements.txt`/`pyproject.toml`; testes parciais; rate limit sem retry exponencial | 🟡 |

## 3. Personas e cenários de uso

| Persona | Objetivo | Cenário-chave |
|---------|----------|---------------|
| Engenheiro de Plataforma | Executar pipeline FinAgent com resiliência operacional | Dispara execução via AgentPulse CLI; acompanha checkpoints no Postgres; aprova/interrompe via interrupt; mata worker no meio e valida retomada sem duplicar |
| Analista Financeiro | Obter relatórios determinísticos com rastreabilidade total | Mesma experiência CLI atual, mas com visibilidade de estado, retry automático e auditoria de execução |
| SRE / Operações | Observar e depurar falhas em produção | Acessa checkpoints no Postgres; replay de execução falha; métricas de retry e duração |

## 4. Regras de negócio novas ou alteradas

1. **RN-01: Checkpoint Obrigatório por Etapa** 🟢
   - Cada agente (coletor, analista, relator) deve persistir seu estado de saída (`MarketDataPayload`, `QuantAnalysisMetrics`, relatório final) em Postgres ao concluir sua etapa, associado a `execution_id` e `step_name`.
   - Origem no legado: `_reversa_sdd/domain.md#rn-06-teto-estrito-de-iteracoes-max-iter` (estende controle de estado)
   - Tipo: nova

2. **RN-02: Retry Idempotente com Chave de Idempotência** 🟢
   - Toda chamada externa (Yahoo Finance API, scraping) e todo passo de agente deve aceitar `idempotency_key = f"{execution_id}:{step_name}:{attempt}"` e ser segura para re-execução.
   - Tipo: nova

3. **RN-03: Aprovação Humana (Interrupt/Resume)** 🟡
   - Após a etapa de análise quantitativa, o pipeline deve pausar e aguardar aprovação humana explícita antes de prosseguir para geração do relatório.
   - O estado de "aguardando aprovação" deve ser persistido em Postgres com timestamp e `execution_id`.
   - Tipo: nova

4. **RN-04: Teste de Caos — Retomada Sem Duplicação** 🟢
   - Deve existir um teste automatizado que: (a) inicia execução, (b) mata o processo worker após checkpoint da análise quantitativa, (c) reinicia worker, (d) valida que o pipeline retoma da etapa de relatório sem re-executar coleta/análise e sem duplicar registros no Postgres.
   - Tipo: nova

5. **RN-05: Preservação de Contratos Pydantic Existentes** 🟢
   - `MarketDataPayload`, `QuantAnalysisMetrics`, `AgentState` permanecem inalterados. A migração não altera schemas de dados, apenas adiciona persistência e orquestração.
   - Origem no legado: `_reversa_sdd/architecture.md#3-modelo-de-entidades-e-schemas-pydantic-erd-resumido`
   - Tipo: nova (restrição)

6. **RN-06: Compatibilidade CLI Atual** 🟢
   - O comando `python -m sisanalisefinanceira.cli --symbol AAPL --engine langgraph` deve continuar funcionando, agora delegando execução ao AgentPulse (modo transparente) ou mantendo execução local (modo legado via flag `--legacy`).
   - Tipo: alterada

## 5. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de aceite | Confidência |
|----|-----------|------------|--------------------|-------------|
| RF-01 | Serviço AgentPulse para DataCollectorAgent | Must | Agente roda como worker AgentPulse; persiste `MarketDataPayload` em Postgres ao final; expõe health check | 🟢 |
| RF-02 | Serviço AgentPulse para QuantAnalystAgent | Must | Agente roda como worker; lê `MarketDataPayload` do checkpoint anterior; persiste `QuantAnalysisMetrics`; pausa para aprovação humana | 🟢 |
| RF-03 | Serviço AgentPulse para ReportWriterAgent | Must | Agente roda como worker; lê `QuantAnalysisMetrics` do checkpoint; persiste relatório final; valida anti-alucinação | 🟢 |
| RF-04 | Schema Postgres para Checkpoints | Must | Tabela `agent_checkpoints(execution_id, step_name, payload_jsonb, status, created_at, approved_at, idempotency_key)` com índices apropriados | 🟢 |
| RF-05 | Retry Idempotente em Coleta de Dados | Must | Falha na Yahoo Finance API → retry exponencial (max 3) com `idempotency_key`; mesmo `execution_id` não gera duplicatas no Postgres | 🟢 |
| RF-06 | Interrupt/Resume Humano Após Análise | Must | Pipeline pausa em `status = 'AWAITING_APPROVAL'`; CLI `agentpulse approve <execution_id>` retoma; `agentpulse reject <execution_id>` aborta; TTL 7 dias → `EXPIRED` | 🟡 |
| RF-07 | Teste de Caos Automatizado | Must | Script `test_chaos_resume.py`: inicia execução, mata worker (SIGKILL) após checkpoint de análise, reinicia, valida retomada no relatório sem duplicar checkpoints; **0 duplicadas e 0 perdidas em 100 execuções** | 🟢 |
| RF-08 | CLI AgentPulse para Operações | Should | Comandos: `agentpulse run <symbol>`, `agentpulse status <execution_id>`, `agentpulse approve <execution_id>`, `agentpulse reject <execution_id>`, `agentpulse replay <execution_id>` | 🟡 |
| RF-09 | Modo Legado (--legacy) no CLI FinAgent | Should | Flag `--legacy` executa pipeline original local sem AgentPulse; mantém compatibilidade total; **AVISO: sem durabilidade, retomada nem aprovação** | 🟢 |
| RF-10 | API Keys com Papéis (analyst/approver) | Must | Dois papéis: `analyst` (POST/GET tasks) e `approver` (POST approve/reject, GET); 403 cruzado; escopo idempotência por `api_key_id`; limite tarefas ativas por chave | 🟡 |

## 6. Requisitos Não Funcionais

| Tipo | Requisito | Evidência ou justificativa | Confidência |
|------|-----------|----------------------------|-------------|
| Desempenho | Latência adicional < 500ms por checkpoint (escrita Postgres) | Overhead de persistência deve ser negligenciável vs execução atual < 60s | 🟢 |
| Confiabilidade | 0 perda de execução: todo estado recuperável via Postgres | Checkpoint a cada etapa garante retomada exata | 🟢 |
| Segurança | `idempotency_key` impede duplicação financeira/operacional | Crítico para auditoria e compliance | 🟢 |
| Observabilidade | Logs estruturados JSON com `execution_id`, `step_name`, `attempt` | Correlação de traces distribuídos | 🟡 |
| Arquitetura | Migração não quebra testes existentes (`test_data_collector.py`, `test_quant_analyst.py`) | Regressão zero no comportamento determinístico | 🟢 |
| Operacional | Teste de caos: **0 duplicadas e 0 perdidas em 100 execuções** passa em CI/CD | Validação contínua da propriedade de retomada | 🟡 |
| Confiabilidade | Retomada sem condição de corrida (premissa nº 1) | Spike + caos 100 execuções validam | 🟢 |
| Confiabilidade | Auditoria numérica sobre texto livre (premissa nº 2) | 100% mutações efetivas detectadas nas classes cobertas | 🟢 |

## 7. Critérios de Aceitação

```gherkin
Cenário: Execução completa com aprovação humana
  Dado um símbolo válido "PETR4"
  Quando executo `agentpulse run PETR4`
  Então o DataCollectorAgent persiste checkpoint em Postgres com status 'COMPLETED'
  E o QuantAnalystAgent persiste checkpoint com status 'AWAITING_APPROVAL'
  Quando executo `agentpulse approve <execution_id>`
  Então o ReportWriterAgent executa e persiste relatório final
  E o status final da execução é 'PUBLISHED'

Cenário: Retomada após falha catastrófica (teste de caos)
  Dado uma execução iniciada com `agentpulse run AAPL`
  Quando o worker é morto (SIGKILL) após checkpoint de análise quantitativa
  E reinicio o worker AgentPulse
  Então o pipeline retoma automaticamente na etapa de relatório
  E nenhum checkpoint é duplicado no Postgres (contagem de linhas por execution_id permanece 3)
  E o relatório final é idêntico ao que seria gerado sem interrupção
  E **0 duplicadas e 0 perdidas em 100 execuções de caos**

Cenário: Retry idempotente em falha de API
  Dado que a Yahoo Finance API retorna HTTP 500 nas 2 primeiras tentativas
  Quando o DataCollectorAgent executa com retry exponencial
  Então a 3ª tentativa sucede e persiste exatamente 1 checkpoint de coleta
  E o `idempotency_key` garante que não há linhas duplicadas para mesma execução/etapa

Cenário: Rejeição humana aborta pipeline
  Dado execução pausada em `AWAITING_APPROVAL`
  Quando executo `agentpulse reject <execution_id>`
  Então o status final é 'REJECTED'
  E nenhum relatório é gerado
  E checkpoints anteriores permanecem íntegros para auditoria

Cenário: Expiração por TTL (7 dias)
  Dado execução em `AWAITING_APPROVAL` há mais de 168 horas
  Quando o reaper roda
  Então o status transiciona para `EXPIRED`
  E nenhum relatório é gerado
  E checkpoints anteriores permanecem íntegros para auditoria

Cenário: Dados STALE (desatualizados) prosseguem com aviso
  Dado coletor retorna cotação com `fetched_at` > `stale_max_age_days` por classe de ativo
  Quando pipeline processa
  Então `data_quality = STALE` no snapshot
  E `stale_warning = true` exibido na aprovação
  E pipeline prossegue para análise quantitativa

Cenário: Dados SIMULADOS bloqueados em produção
  Dado `APP_ENV=prod`
  Quando coletor tenta usar MockProvider
  Então `DATA_QUALITY_BLOCKED` imediato
  E aplicação recusa iniciar se `ALLOW_SIMULATED_PUBLICATION=true`

Cenário: Modo legado preserva comportamento original
  Dado `python -m sisanalisefinanceira.cli --symbol PETR4 --legacy`
  Então a execução roda local sem AgentPulse/Postgres
  E o relatório gerado é bit-a-bit idêntico ao comportamento pré-migração
  E **AVISO**: modo legacy NÃO tem durabilidade, retomada nem aprovação humana
```

## 8. Prioridade MoSCoW

| Item | MoSCoW | Justificativa |
|------|--------|---------------|
| RF-01, RF-02, RF-03 (Serviços AgentPulse) | Must | Core da migração — agentes devem rodar na nova infra |
| RF-04 (Schema Postgres) | Must | Fundação para todos os checkpoints |
| RF-05 (Retry Idempotente) | Must | Resiliência operacional obrigatória |
| RF-06 (Interrupt/Resume) | Must | Diferencial arquitetural pedido; aprovação humana |
| RF-07 (Teste de Caos) | Must | Prova de correção da retomada; requisito explícito |
| RF-08 (CLI AgentPulse) | Should | Experiência de operador; pode vir em iteração seguinte |
| RF-09 (Modo Legado) | Should | Compatibilidade e rollback seguro |
| RNF Observabilidade | Should | Importante para produção; não bloqueia MVP |
| Comunicação A2A entre agentes | Won't | Escopo explícito: "próximo passo" |

## 9. Esclarecimentos

> Sessão de dúvidas registrada: decisão de arquitetura de conexão Postgres incorporada abaixo.

## 10. Decisões de Arquitetura (resolvem lacunas)

### 10.1 Esquema de Conexão Postgres (resolve 🔴 Esquema de conexão Postgres)

**Decisão**: O código de domínio (coletor, analista, auditoria) **não cria pool nenhum**. Recebe repositórios por injeção. A infraestrutura (AgentPulse) é dona dos pools, um conjunto por papel de processo:

**API (processo assíncrono)**
- Engine SQLAlchemy async com `asyncpg`, como já está no AgentPulse
- Usada em `POST /tasks`, nas decisões de aprovação e nas leituras

**Worker (processo prefork, grafo síncrono)**: dois pools `psycopg`, porque as necessidades são incompatíveis:
- `domain_pool`: conexões transacionais, usadas pela máquina de estados, `market_payloads`, `published` e eventos (o `UPDATE` condicional e o `INSERT` do evento precisam estar na mesma transação)
- `checkpoint_pool`: conexões em **autocommit** e com `row_factory=dict_row`, que é a configuração que o checkpointer do Postgres exige (confirmar na versão fixada do LangGraph). Passar uma conexão comum a ele é um erro clássico

**Criação depois do fork**: os pools nascem no sinal `worker_process_init` do Celery e fecham em `worker_process_shutdown`. **Nunca no import do módulo**, porque o filho herdaria sockets do pai.

**Lock por `task_id`**: advisory lock de sessão vale enquanto a conexão que o adquiriu estiver aberta. Então o worker pega uma conexão dedicada para o lock durante a execução inteira, separada das do `domain_pool` e do `checkpoint_pool`. Duas consequências:
- **Dimensionamento**: cada filho precisa de pelo menos uma conexão de lock mais as dos pools. Se o pool for menor que isso, o worker trava esperando uma conexão que ele mesmo segura. Fórmula: `pool_size >= 1 (lock) + domain_pool_size + checkpoint_pool_size`. Testar com pool mínimo.
- **Compatibilidade**: advisory lock de sessão **não funciona atrás de pooler em modo transaction** (como PgBouncer nesse modo). Declarar que o MVP conecta direto ao Postgres. Alternativa se necessário: lease na tabela `tasks` (`locked_by`, `lease_until`) renovado pelo heartbeat que o `worker-queue` já prevê.

**Orçamento de conexões**: `conexões_API + (filhos_por_worker × conexões_por_filho × nº_workers) + margem ≤ max_connections` do Postgres. O Compose local costuma estourar isso em silêncio, então validar na subida.

**Papéis do banco**: 
- Pools usam `app_user` (só `INSERT`/`SELECT` em `task_events`)
- Migrações (Alembic) e o `setup()` do checkpointer rodam com `migrator`, como passo de deploy
- Retenção usa `retention_role`

**Perda de conexão**: reinício do Postgres ou `pg_terminate_backend` gera erro de conexão, que o adaptador converte em `TransientError`. O pool descarta a conexão ruim e reconecta.

**Testes que esta decisão exige**:
1. Matar conexões com `pg_terminate_backend` no meio de uma tarefa: retry e retomada sem duplicar
2. Reiniciar o container do Postgres com tarefas em voo: os workers se recuperam sem reinício
3. Pool de tamanho mínimo com a conexão de lock: nenhum deadlock
4. Número de conexões abertas com N workers e a API ligados: dentro do orçamento
5. O checkpointer rodando com uma conexão sem autocommit falha de forma clara no teste (confirma que a configuração é necessária)

### 10.2 Formato de `idempotency_key` (resolve 🔴 Formato de idempotency_key)

**Decisão**: Adotar `f"{execution_id}:{step_name}:{attempt}"` como proposto. Determinístico, rastreável, compatível com retry exponencial. Se o AgentPulse definir convenção posterior, migrar via alias.

### 10.3 Mecanismo de Interrupt/Resume (resolve 🔴 Mecanismo de interrupt/resume)

**Decisão**: Implementar via tabela de estado + polling no worker (simples, sem dependência de primitivas não confirmadas no AgentPulse). Estado `awaiting_approval` persistido em Postgres com `execution_id`, `step_name`, `created_at`, `approved_at` (nullable). CLI `agentpulse approve <execution_id>` faz `UPDATE` atômico; worker faz polling a cada 5s. Webhook/fila nativa fica para iteração futura se o AgentPulse expôr.

## 11. Lacunas Restantes

- Nenhuma — todas as lacunas originais foram resolvidas pelas decisões acima.

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-09-29 | Versão inicial gerada por `/reversa-requirements` | reversa |