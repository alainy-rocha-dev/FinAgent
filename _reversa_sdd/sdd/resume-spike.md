# Spec: resume-spike

> Selo 🟡 PLANEJADO. Componente gerado pelo reversa-spec-sdd a partir do PRD FinAgent + AgentPulse.

---

## 1. Resumo

🟡 Spike de validação da premissa central: Celery (acks_late, task_reject_on_worker_lost, visibility_timeout do Redis) + checkpointer Postgres (LangGraph) + interrupt compõem sem duplicar nem perder trabalho sob kill do worker, reentrega do broker, aprovação duplicada/concorrente e dois workers no mesmo thread_id.

Critério de saída: 0 duplicadas e 0 perdidas nos 5 cenários definidos; 100% das retomadas continuam do último checkpoint; cenário 5 com comportamento definido.

---

## 2. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|------------|---------------------|
| 🟡 RF-01 | Executar grafo LangGraph mínimo (2-3 nós) sob Celery worker com acks_late | Must | Worker processa tarefa e persiste checkpoints no Postgres a cada nó |
| 🟡 RF-02 | Simular kill do worker (SIGKILL) após checkpoint do nó analista quant (antes do interrupt) | Must | Ao reiniciar worker, tarefa retoma do interrupt sem reexecutar nós anteriores; 0 duplicadas |
| 🟡 RF-03 | Simular kill entre checkpoint do interrupt e transição RUNNING → AWAITING_APPROVAL | Must | Retomada correta; sem duplicação de evento REVIEW_READY |
| 🟡 RF-04 | Simular kill durante retomada, entre efeito no destino (INSERT published) e ack | Must | Transação atômica garante que ou ambos persistem ou nenhum; retomada idempotente |
| 🟡 RF-05 | Simular kill entre commit da decisão (approve/reject) e enfileiramento do resume | Must | Decisão persistida; resume enfileirado na retomada; sem perda |
| 🟡 RF-06 | Forçar reentrega real do broker (visibility_timeout reduzido, tarefa > timeout) | Must | task_reject_on_worker_lost + reentrega → retomada sem duplicar; 0 perdidas |
| 🟡 RF-07 | Duas requisições approve simultâneas no mesmo task_id | Must | Apenas uma transição APPROVED → PUBLISHED; segunda recebe 409 ou idempotente |
| 🟡 RF-08 | Dois workers processando mesmo thread_id (race de lock) | Must | Advisory lock garante execução exclusiva; segundo worker aguarda ou falha limpo |
| 🟡 RF-09 | Coletar métricas por execução: duplicadas, perdidas, tempo recuperação, tentativas, distribuição kills, estado final | Must | Relatório JSON + Markdown com 100 execuções (20 por cenário C1, 21 C2, 20 C3, 20 C4, 19 C5) |
| 🟡 RF-10 | Failpoints ativáveis só com APP_ENV=test (SIGKILL no próprio processo em pontos nomeados) | Must | Failpoints recusados no startup se APP_ENV=prod; docker kill real em parte das execuções |

---

## 3. Comportamentos

🟡 **Cenários de caos (100 execuções, semente fixa para escolha de cenário e jitter):**
- **C1 (20):** Kill após checkpoint do analista quant, antes do interrupt
- **C2 (21, 3 variantes × 7):** Kill entre checkpoint interrupt e RUNNING→AWAITING_APPROVAL; kill durante retomada entre efeito no destino e ack; kill entre commit decisão e enfileiramento resume
- **C3 (20):** Reentrega real do broker (visibility_timeout reduzido no ambiente de caos, tarefa mais longa que ele; valor registrado no relatório)
- **C4 (20):** Decisões concorrentes (approve × approve, approve × reject, approve × expiração) no mesmo task_id
- **C5 (19):** Dois workers sobre mesmo thread_id (mensagens resume duplicadas)

🟡 **Métricas medidas:**
- Duplicadas = entregas > 1 por tarefa aprovada no destino de teste do Publisher + efeitos colaterais ou eventos de transição repetidos (tabela `published` tem UNIQUE e não serve de medida)
- Perdidas = tarefa aprovada não terminal após `visibility_timeout` + reaper + margem
- Retomadas que reexecutaram nó já concluído (meta 0)
- Publicações sem aprovação ou com hash diferente do aprovado (meta 0)
- Tempo de recuperação; tentativas; distribuição dos pontos de kill; estado final

🟡 **Ambiente:** Docker Compose efêmero (GitHub Actions), Postgres + Redis reais, LLM stub (sem custo, latência fixa 50ms)

---

## 4. Edge Cases

| Cenário | Comportamento Esperado |
|---------|------------------------|
| 🟡 Worker morre durante escrita do checkpoint | Checkpoint parcial descartado; retomada reexecuta nó |
| 🟡 Redis indisponível no momento do ack | Tarefa reentregue após visibility_timeout; idempotência garante correção |
| 🟡 Postgres reinicia durante execução | Conexão descartada pelo pool; TransientError → retry; retomada do último checkpoint válido |
| 🟡 Dois approve com hash de snapshot diferentes | Primeira vence; segunda 409 com detalhe de mismatch |
| 🟡 Failpoint ativado em prod | Startup falha com erro claro; não executa |

---

## 5. Não-Gols

🟡 Não implementar política de retenção de checkpoints (componente `langgraph-checkpointer`)
🟡 Não implementar reaper (componente `worker-queue`)
🟡 Não implementar UI de aprovação (componente `approval-ui`)
🟡 Não testar Temporal ou outros orquestradores (ADR separado)
🟡 Não medir performance de vazão (componente `chaos-load-tests`)

---

## 6. Interface de Integração

🟡 **Entrada:** Grafo LangGraph mínimo (Planner → Coletor → Analista Quant → Interrupt), configuração Celery/Redis/Postgres de teste
🟡 **Saída:** Relatório `spike-report.json` + `spike-report.md` com métricas dos 100 execuções
🟡 **Dependências:** `langgraph-checkpointer` (checkpointer Postgres), `task-state-machine` (estados e lock), `worker-queue` (config Celery)

---

## 7. Critérios de Aceite (Gherkin)

```gherkin
Cenário: Spike valida premissa central
  Dado um grafo mínimo rodando sob Celery com acks_late e checkpointer Postgres
  Quando executo 100 cenários de caos com failpoints e docker kill real
  Então 0 duplicadas e 0 perdidas em todas as execuções
  E 100% das retomadas continuam do último checkpoint persistido
  E o relatório registra distribuição de kills, tempo de recuperação e tentativas por tarefa
  E falhas de lock, retomadas bloqueadas indevidamente e locks órfãos são contabilizadas
```

---

## 8. Perguntas Abertas

⚠️ **ABERTO:** Formato exato do serializador padrão do LangGraph na versão fixada e se exige `autocommit` + `row_factory=dict_row` para o checkpointer Postgres
⚠️ **ABERTO:** Se o nó que contém `interrupt()` reexecuta desde o início na retomada, ou retoma do ponto de interrupção
⚠️ **ABERTO:** Assinatura de `Command(resume=...)` na versão fixada do LangGraph
⚠️ **ABERTO:** Tolerância do LangGraph a remoção/renomeação de nós com checkpoints existentes (define política de `graph_version`)
⚠️ **ABERTO:** Comportamento de `task_reject_on_worker_lost` + tempo de recuperação após SIGKILL com `visibility_timeout` do Redis
⚠️ **ABERTO:** Rascunho IETF vigente para `Idempotency-Key` (header, semântica de replay, escopo, status atual)
⚠️ **ABERTO:** Termos de uso Yahoo Finance / BCB / demais provedores (permitem produção? rate limits, atribuição, cache)
⚠️ **ABERTO:** Cada característica atribuída ao Temporal no ADR verificável na documentação da versão avaliada

---

## 9. Valores Iniciais (a medir)

| Parâmetro | Valor Inicial | Fonte |
|-----------|---------------|-------|
| 🟡 `visibility_timeout` (produção) | 900s | Arbitrário |
| 🟡 `visibility_timeout` (caos) | Reduzido (registrar valor) | Medido no caos |
| 🟡 `task_time_limit` | TBD | Definir com `retry_backoff_max` + margem |
| 🟡 `retry_backoff_max` | TBD | Celery config |
| 🟡 `max_retries` | TBD | Celery config |
| 🟡 Intervalo heartbeat | 15s | Arbitrário |

---

## 10. Relatório de Avaliação (Scoring)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCORE TOTAL: 87/100
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Breakdown:
  Completude:    90/100 (peso 30%)
  Testabilidade: 95/100 (peso 25%)
  Clareza:       85/100 (peso 20%)
  Escopo:        85/100 (peso 15%)
  Edge Cases:    80/100 (peso 10%)

Gaps críticos:
  - Perguntas abertas sobre versão fixada do LangGraph e comportamentos de interrupt/recovery
  - Valores de timeout/retries do Celery ainda não definidos

Sugestões (por impacto):
  1. Fixar versões exatas no spike (LangGraph, Celery, Redis, Postgres) antes de executar
  2. Implementar failpoints no grafo mínimo antes de rodar 100 execuções
  3. Definir `task_time_limit`, `retry_backoff_max`, `max_retries` baseados em p99 medido no spike
```