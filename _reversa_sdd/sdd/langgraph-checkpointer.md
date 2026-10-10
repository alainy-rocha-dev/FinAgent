# Spec: langgraph-checkpointer

> Selo 🟡 PLANEJADO. Componente gerado pelo reversa-spec-sdd a partir do PRD FinAgent + AgentPulse.

---

## 1. Resumo

🟡 Checkpointer Postgres do LangGraph com `thread_id = task_id`, persistência de estado a cada nó, `graph_version` para compatibilidade, política de retenção, serializador sem pickle e conexão de lock dedicada para advisory lock.

---

## 2. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|------------|---------------------|
| 🟡 RF-01 | Configurar `PostgresSaver` (LangGraph) com `thread_id = task_id` | Must | Checkpoints salvos a cada nó do grafo; retomada carrega estado exato |
| 🟡 RF-02 | Usar pool `checkpoint_pool` dedicado: autocommit + `row_factory=dict_row` | Must | Conexão atende exigência do checkpointer; conexão comum falha no teste |
| 🟡 RF-03 | Gravar `graph_version` no checkpoint e na tabela `tasks` | Must | `GRAPH_VERSION` constante no código; `COMPATIBLE_VERSIONS` para mudanças aditivas |
| 🟡 RF-04 | Validar `graph_version` na retomada: igual ou em `COMPATIBLE_VERSIONS` → segue; caso contrário → FAILED | Must | Erro legível: "versão do fluxo incompatível, reenvie"; teste de retomada N → N+1 obrigatório |
| 🟡 RF-05 | Política de retenção: checkpoints de tarefas terminais removidos após N dias (padrão 7, configurável) | Must | Tarefas ativas e em AWAITING_APPROVAL nunca podadas; job diário com `retention_role` |
| 🟡 RF-06 | Serializador: formato nativo do LangGraph (confirmar versão fixada), sem pickle; estado restrito a tipos simples + Pydantic → dict | Must | Pickle desabilitado; dados grandes em tabela própria referenciados por id |
| 🟡 RF-07 | Conexão de lock dedicada (advisory lock) separada do `checkpoint_pool` e `domain_pool` | Must | Worker abre conexão de lock no início, mantém durante execução inteira |
| 🟡 RF-08 | Setup do checkpointer (tabelas, índices) roda com role `migrator` no deploy | Must | Não usa `app_user`; migração versionada (Alembic) |

---

## 3. Comportamentos

🟡 **Versionamento do grafo:**
- `GRAPH_VERSION = "1.0.0"` (constante no código, incrementada em mudanças breaking)
- `COMPATIBLE_VERSIONS = {"1.0.0", "1.1.0"}` (mudanças aditivas: novos nós opcionais, campos opcionais no estado)
- Na criação do checkpoint: grava `graph_version` no metadata do checkpoint e em `tasks.graph_version`
- Na retomada: `if checkpoint.graph_version not in COMPATIBLE_VERSIONS: raise GraphVersionMismatch`

🟡 **Retenção:**
- Job diário (Celery beat, instância única, `retention_role`): `DELETE FROM checkpoints WHERE task_id IN (SELECT task_id FROM tasks WHERE status IN ('PUBLISHED','REJECTED','EXPIRED','FAILED','BUDGET_EXCEEDED','DATA_QUALITY_BLOCKED') AND updated_at < now() - interval '7 days')`
- `retention_days` configurável (padrão 7, arbitrário)
- Checkpoints de tarefas não terminais **nunca** removidos

🟡 **Serializador:**
- Estado do grafo: apenas tipos JSON-serializáveis (dict, list, str, int, float, bool, None)
- Modelos Pydantic: `model_dump(mode='json')` antes de persistir
- Objetos grandes (payloads de mercado, relatórios): tabelas `market_payloads`, `quant_metrics`, `reports` com FK para `task_id`; checkpoint guarda apenas referências (ids)

🟡 **Pools (conforme decisão de arquitetura):**
- `checkpoint_pool`: `psycopg` pool, `autocommit=True`, `row_factory=dict_row`, tamanho ≥ 2
- `domain_pool`: `psycopg` pool, transacional, tamanho ≥ 2
- Lock connection: 1 conexão dedicada por worker filho, fora dos pools
- Fórmula: `pool_size ≥ 1 (lock) + domain_pool_size + checkpoint_pool_size`

---

## 4. Edge Cases

| Cenário | Comportamento |
|---------|---------------|
| 🟡 Retomada com `graph_version` incompatível | `FAILED` com motivo legível; tarefa não executa; requer reenvio |
| 🟡 Checkpoint corrompido / serialização falha | Erro no salvamento → nó falha → `task-state-machine` transiciona para FAILED |
| 🟡 Dados grandes no estado (ex: DataFrame) | Proibido no estado; deve ir em tabela própria com referência |
| 🟡 Postgres reinicia durante checkpoint | Pool descarta conexão ruim; `TransientError` → retry; checkpoint reescrito |
| 🟡 Worker morre com conexão de lock aberta | Lock liberado (fim de sessão); retomada adquire novo lock |

---

## 5. Não-Gols

🟡 Não definir estrutura do estado do grafo (pertence ao `analysis-graph`)
🟡 Não implementar migrações Alembic (infra, role `migrator`)
🟡 Não implementar job de retenção (Celery beat — componente `worker-queue` / `ci-quality`)
🟡 Não definir `GRAPH_VERSION` inicial (definida no código do grafo)

---

## 6. Interface de Integração

🟡 **Entrada:** `thread_id` (= `task_id`), estado do grafo (dict), metadata com `graph_version`
🟡 **Saída:** Checkpoint persistido; estado carregado na retomada
🟡 **Dependências:** `checkpoint_pool` (psycopg, autocommit, dict_row), conexão de lock dedicada, `task-state-machine` (para transição FAILED em versão incompatível), `worker-queue` (para criar pools no `worker_process_init`)

---

## 7. Critérios de Aceite (Gherkin)

```gherkin
Cenário: Retomada com graph_version compatível
  Dado checkpoint salvo com graph_version="1.0.0"
  E código atual tem GRAPH_VERSION="1.1.0" e COMPATIBLE_VERSIONS inclui "1.0.0"
  Quando worker retoma a tarefa
  Então checkpoint carrega com sucesso
  E tarefa continua do último nó

Cenário: Retomada com graph_version incompatível
  Dado checkpoint salvo com graph_version="1.0.0"
  E código atual tem GRAPH_VERSION="2.0.0" e COMPATIBLE_VERSIONS não inclui "1.0.0"
  Quando worker retoma a tarefa
  Então GraphVersionMismatch lançada
  E task-state-machine transiciona para FAILED com motivo "versão do fluxo incompatível, reenvie"

Cenário: Retenção remove apenas terminais antigos
  Dado tarefa PUBLISHED há 8 dias e tarefa RUNNING há 2 dias
  Quando job de retenção roda (padrão 7 dias)
  Então checkpoints da tarefa PUBLISHED são removidos
  E checkpoints da tarefa RUNNING permanecem
```

---

## 8. Perguntas Abertas

⚠️ **ABERTO:** Formato exato do serializador padrão do LangGraph na versão fixada e se exige `autocommit` + `row_factory=dict_row` para o checkpointer Postgres
⚠️ **ABERTO:** Tolerância do LangGraph a remoção/renomeação de nós com checkpoints existentes (define política de `graph_version`)
⚠️ **ABERTO:** Comportamento de `task_reject_on_worker_lost` + tempo de recuperação após SIGKILL com `visibility_timeout` do Redis

---

## 9. Valores Iniciais (a medir)

| Parâmetro | Valor Inicial | Fonte |
|-----------|---------------|-------|
| 🟡 `retention_days` (checkpoints terminais) | 7 dias | Arbitrário |
| 🟡 `checkpoint_pool` size | 2 | Mínimo |
| 🟡 `domain_pool` size | 2 | Mínimo |
| 🟡 Lock connection | 1 por worker filho | Decisão arquitetura |
| 🟡 `GRAPH_VERSION` inicial | "1.0.0" | Código |

---

## 10. Relatório de Avaliação (Scoring)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCORE TOTAL: 88/100
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Breakdown:
  Completude:    90/100 (peso 30%)
  Testabilidade: 85/100 (peso 25%)
  Clareza:       90/100 (peso 20%)
  Escopo:        85/100 (peso 15%)
  Edge Cases:    90/100 (peso 10%)

Gaps críticos:
  - Serializador nativo do LangGraph e configuração checkpointer Postgres dependem de versão fixada
  - Política de graph_version para mudanças aditivas vs breaking precisa de convenção clara

Sugestões:
  1. Fixar versão do LangGraph no spike e documentar serializador/checkpointer config
  2. Adicionar teste de retomada N → N+1 com nó aditivo no CI
  3. Validar fórmula de pool_size com lock connection no spike (deadlock se pool menor)
```