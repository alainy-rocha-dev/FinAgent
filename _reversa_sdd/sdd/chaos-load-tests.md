# Spec: chaos-load-tests

> Selo 🟡 PLANEJADO. Componente gerado pelo reversa-spec-sdd a partir do PRD FinAgent + AgentPulse.

---

## 1. Resumo

🟡 Testes de caos (100 execuções, 0 duplicadas e 0 perdidas) e carga (pytest assíncrono para idempotência + Locust para vazão fim-a-fim). Métricas reais: entregas > 1 no destino de teste do Publisher, retomadas reexecutando nó, publicações sem aprovação/hash divergente. CI em duas camadas: fumaça obrigatória em PR + noturno completo.

---

## 2. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|------------|---------------------|
| 🟡 RF-01 | Teste de caos: 100 execuções (C1=20, C2=21 em 3 variantes, C3=20, C4=20, C5=19) | Must | 0 duplicadas, 0 perdidas; taxa real < ~3% (regra dos três com 0 em 100) |
| 🟡 RF-02 | Cenário C1 (20): kill após checkpoint do analista quant, antes do interrupt | Must | Failpoint `KILL_AFTER_QUANT` (SIGKILL no próprio processo, só `APP_ENV=test`) + parte docker kill real |
| 🟡 RF-03 | Cenário C2 (21, 3 variantes × 7): kill entre checkpoint interrupt e RUNNING→AWAITING_APPROVAL; kill durante retomada entre efeito no destino e ack; kill entre commit decisão e enfileiramento resume | Must | Failpoints nomeados + docker kill real |
| 🟡 RF-04 | Cenário C3 (20): reentrega real do broker — `visibility_timeout` reduzido no ambiente de caos, tarefa mais longa que ele; valor registrado no relatório | Must | `task_reject_on_worker_lost` + reentrega real prova idempotência |
| 🟡 RF-05 | Cenário C4 (20): decisões concorrentes (approve × approve, approve × reject, approve × expiração) no mesmo task_id | Must | Transições atômicas garantem uma única aprovação |
| 🟡 RF-06 | Cenário C5 (19): dois workers sobre mesmo thread_id (mensagens resume duplicadas) | Must | Advisory lock garante execução exclusiva |
| 🟡 RF-07 | Métricas por execução: duplicadas (entregas > 1 no destino de teste do Publisher + efeitos colaterais/eventos repetidos), perdidas (aprovada não terminal após visibility_timeout + reaper + margem), retomadas reexecutando nó concluído (meta 0), publicações sem aprovação ou hash divergente (meta 0), tempo recuperação, tentativas, distribuição kills, estado final | Must | Relatório JSON + Markdown |
| 🟡 RF-08 | Correção de idempotência em pytest assíncrono: 50 POSTs concorrentes, mesma chave + mesmo api_key_id = exatamente 1 tarefa; uma resposta 202, demais 200 ou 409 | Must | Não usa Locust (pytest consegue afirmar contagem exata) |
| 🟡 RF-09 | Teste de carga Locust: 10 req/s por 60s com chaves únicas, LLM stub (50ms), API key de limites altos | Must | Mede latência POST + tempo até AWAITING_APPROVAL, vazão, erros 5xx (meta 0). Hardware e concorrência workers registrados. Metas p95 fixadas após 1ª medição |
| 🟡 RF-10 | CI: fumaça de caos (~5 execuções, pontos nomeados C2 e C1) obrigatória em PRs que tocam módulos críticos | Must | Workflow roda sempre; job detecta arquivos alterados e pula passos pesados se não crítico. Flaky: falha → 1 retry → falha de novo = falhou |
| 🟡 RF-11 | Job noturno: 100 execuções completas; vermelho → issue automática; política: corrigir antes de novo merge no caminho crítico | Must | Runner Actions com Docker Compose efêmero |
| 🟡 RF-12 | Módulos críticos para CI: `task-state-machine`, `langgraph-checkpointer`, `worker-queue`, `analysis-graph`, `approval-flow`, `publication`, `audit-trail`, `numeric-audit` | Must | Lista versionada no workflow |

---

## 3. Comportamentos

🟡 **Runner de caos (`tests/chaos_runner.py`):**
```python
async def run_chaos(executions: int = 100, seed: int = 42) -> ChaosReport:
    random.seed(seed)
    report = ChaosReport()
    for i in range(executions):
        scenario = choose_scenario(seed + i)  # distribuição C1-C5
        failpoint = choose_failpoint(scenario)
        env = {"APP_ENV": "test", f"FAILPOINT_{failpoint}": "1"}
        # Reduz visibility_timeout para C3
        if scenario == "C3":
            env["VISIBILITY_TIMEOUT"] = "30"  # valor reduzido, registrado
        result = await run_single_chaos(scenario, env)
        report.add(result)
    return report
```

🟡 **Métricas reais (não `published` count):**
- **Duplicadas:** Contador no destino de teste do Publisher (ex: `test_deliveries[task_id] += 1` no mock Publisher) > 1
- **Perdidas:** Tarefa com `status = APPROVED` não terminal após `visibility_timeout + reaper_interval + margem`
- **Retomadas reexecutando nó:** Compara `step_name` no checkpoint antes/depois da retomada; se recuou → conta
- **Hash divergente:** `snapshot_hash` no evento `APPROVAL_DECISION` vs `task_events` mais recente no momento da publicação

🟡 **Teste de idempotência (pytest assíncrono):**
```python
@pytest.mark.asyncio
async def test_idempotency_50_concurrent(api_client, api_key_analyst):
    tasks = [api_client.post("/tasks", headers={"Idempotency-Key": "same-key", "Authorization": f"Bearer {api_key_analyst}"}) for _ in range(50)]
    responses = await asyncio.gather(*tasks)
    statuses = [r.status_code for r in responses]
    task_ids = [r.json().get("task_id") for r in responses if r.status_code in (200, 202)]
    assert statuses.count(202) == 1  # exatamente uma criação
    assert all(s in (200, 409) for s in statuses if s != 202)  # demais replay ou conflito
    assert len(set(task_ids)) == 1  # exatamente 1 task_id
```

🟡 **Locust (vazão fim-a-fim):**
```python
class FinAgentUser(HttpUser):
    wait_time = constant(0.1)  # ~10 req/s
    def on_start(self):
        self.api_key = os.getenv("LOAD_TEST_API_KEY")  # limites altos
    
    @task
    def submit_task(self):
        with self.client.post("/tasks", headers={"Idempotency-Key": str(uuid4()), "Authorization": f"Bearer {self.api_key}"}, json={"symbol": "PETR4", "acknowledge_simulated": True}, catch_response=True) as response:
            if response.status_code == 202:
                task_id = response.json()["task_id"]
                # Poll até AWAITING_APPROVAL
                start = time.time()
                while time.time() - start < 30:
                    r = self.client.get(f"/tasks/{task_id}", headers={"Authorization": f"Bearer {self.api_key}"})
                    if r.json()["status"] == "AWAITING_APPROVAL":
                        response.success()
                        break
                    time.sleep(0.5)
                else:
                    response.failure("Timeout to AWAITING_APPROVAL")
```

---

## 4. Edge Cases

| Cenário | Comportamento |
|---------|---------------|
| 🟡 Tarefa `APPROVED` mas Publisher falha (hash mismatch) | Volta para `AWAITING_APPROVAL` com flag; caos conta como "hash divergente" |
| 🟡 Worker morre durante `await_approval` | Não há processo para matar (worker já terminou); cenário C2 cobre pontos perigosos reais |
| 🟡 `visibility_timeout` reduzido causa reentrega durante execução normal | Tarefa > timeout → reentregue; idempotência garante correção; métrica registra |
| 🟡 Flaky test no CI | 1 retry; se repete → falha; não mascara instabilidade |
| 🟡 Locust com LLM real | **Não permitido** — só stub (sem custo, latência controlada) |

---

## 5. Não-Gols

🟡 Não implementar grafo / worker / API (componentes respectivos)
🟡 Não implementar dashboard de caos (relatório JSON/Markdown + artifact + issue)
🟡 Não definir metas de p95 latência (fixar após 1ª medição; 2s é hipótese inicial)
🟡 Não testar Temporal ou outros orquestradores (ADR separado)
🟡 Não medir performance de componentes isolados (só fim-a-fim)

---

## 6. Interface de Integração

🟡 **Entrada:** Sistema completo rodando (API, worker, Postgres, Redis), config de caos (`APP_ENV=test`, failpoints, `visibility_timeout` reduzido)
🟡 **Saída:** Relatório `chaos-report.json` + `chaos-report.md`; artifact no CI; issue se noturno falha
🟡 **Dependências:** Todos os componentes (teste fim-a-fim), `ci-quality` (orquestra execução no CI), `observability` (métricas para validação)

---

## 7. Critérios de Aceite (Gherkin)

```gherkin
Cenário: Caos 100 execuções — 0 duplicadas, 0 perdidas
  Dado sistema rodando com APP_ENV=test e failpoints configurados
  Quando executo 100 cenários de caos (C1-C5 com distribuição fixa)
  Então relatório mostra: duplicadas = 0, perdidas = 0
  E retomadas reexecutando nó = 0
  E publicações sem aprovação/hash divergente = 0
  E taxa real de duplicação/perda < ~3% (regra dos três)

Cenário: Idempotência 50 POSTs concorrentes
  Dado 50 requisições POST /tasks simultâneas com mesma Idempotency-Key e api_key_id
  Quando todas completam
  Então exatamente 1 tarefa criada no banco
  E uma resposta 202, 49 respostas 200 ou 409
  E todas respostas 200/202 têm mesmo task_id

Cenário: CI fumaça obrigatória em módulo crítico
  Dado PR altera src/task_state_machine/
  Quando CI roda
  Então job detect-changes retorna critical=true
  E fumaça de caos (5 execuções C1+C2) executa e passa
  Se flaky → 1 retry → falha de novo = PR bloqueado
```

---

## 8. Perguntas Abertas

⚠️ **ABERTO:** `visibility_timeout` valor reduzido no caos — qual valor exato? (registrar no relatório)
⚠️ **ABERTO:** Hardware e concorrência workers para Locust — registrar no relatório de carga
⚠️ **ABERTO:** Distribuição exata de kills por cenário no relatório (formato JSON)
⚠️ **ABERTO:** Teste de carga 429 (rate limit) — separado do teste de vazão

---

## 9. Valores Iniciais (a medir)

| Parâmetro | Valor Inicial | Fonte |
|-----------|---------------|-------|
| 🟡 Execuções caos total | 100 | Fixado |
| 🟡 C1 execuções | 20 | Fixado |
| 🟡 C2 execuções (3 variantes) | 21 (7 cada) | Fixado |
| 🟡 C3 execuções | 20 | Fixado |
| 🟡 C4 execuções | 20 | Fixado |
| 🟡 C5 execuções | 19 | Fixado |
| 🟡 Fumaça CI execuções | 5 | Arbitrário |
| 🟡 Locust req/s | 10 | Arbitrário |
| 🟡 Locust duração | 60s | Arbitrário |
| 🟡 LLM stub latency | 50ms | Fixado |
| 🟡 Flaky retry count | 1 | Fixado |

---

## 10. Relatório de Avaliação (Scoring)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCORE TOTAL: 88/100
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Breakdown:
  Completude:    90/100 (peso 30%)
  Testabilidade: 90/100 (peso 25%)
  Clareza:       85/100 (peso 20%)
  Escopo:        85/100 (peso 15%)
  Edge Cases:    90/100 (peso 10%)

Gaps críticos:
  - visibility_timeout reduzido no caos: valor exato a definir e registrar
  - Hardware/concorrência Locust para metas de p95
  - Métricas de "duplicadas" e "perdidas" dependem de instrumentação no Publisher de teste

Sugestões:
  1. Implementar Publisher de teste com contador de entregas por task_id
  2. Definir visibility_timeout caos = task_time_limit / 2 (ex: 300s) e registrar
  3. Executar fumaça de caos no CI antes de ativar branch protection
  4. Separar teste de rate limit (429) do teste de vazão Locust
```