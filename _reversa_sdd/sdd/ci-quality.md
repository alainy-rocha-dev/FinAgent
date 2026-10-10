# Spec: ci-quality

> Selo 🟡 PLANEJADO. Componente gerado pelo reversa-spec-sdd a partir do PRD FinAgent + AgentPulse.

---

## 1. Resumo

🟡 Pipeline de CI de PR, job noturno de caos, cobertura do caminho crítico e regra de merge. Garante que toda mudança passe nos checks obrigatórios antes de entrar na main.

---

## 2. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|------------|---------------------|
| 🟡 RF-01 | Workflow CI de PR (GitHub Actions) que roda sempre | Must | Primeiro job detecta arquivos alterados; se nenhum módulo crítico, check passa verde (não fica pendente) |
| 🟡 RF-02 | Checks obrigatórios em PR: ruff (check + format), mypy, unitários, integração (Postgres/Redis service containers), testes de retomada sem kill, cobertura ramos caminho crítico ≥ 85%, pip-audit | Must | Branch protection exige todos verdes; falha bloqueia merge |
| 🟡 RF-03 | Fumaça de caos (~5 execuções, pontos nomeados C1 e C2) obrigatória em PRs que tocam módulos críticos | Must | Módulos críticos: `task-state-machine`, `langgraph-checkpointer`, `worker-queue`, `analysis-graph`, `approval-flow`, `publication`, `audit-trail`, `numeric-audit` |
| 🟡 RF-04 | Teste instável (flaky): falha → uma repetição → se repete, falhou | Must | Não mascara instabilidade; relatório mostra retry |
| 🟡 RF-05 | Job noturno (schedule diário + workflow_dispatch): 100 execuções de caos completas | Must | Runner Actions com Docker Compose efêmero; não bloqueia merge diretamente |
| 🟡 RF-06 | Job noturno vermelho → abre issue automática com relatório | Must | Política: "corrigir antes de novo merge no caminho crítico" |
| 🟡 RF-07 | Cobertura de ramos no caminho crítico ≥ 85% (valor único em todas specs) | Must | `pytest-cov` com `--cov-fail-under=85` nos módulos críticos |
| 🟡 RF-08 | Badge do workflow noturno no README (status + link para relatório) | Should | Branch reports ou GitHub Pages para relatórios históricos |
| 🟡 RF-09 | Relatório de caos: JSON + Markdown com métricas por cenário, distribuição kills, tempo recuperação, falhas lock | Must | Publicado como artifact do workflow noturno |

---

## 3. Comportamentos

🟡 **Workflow PR (`ci.yml`):**
```yaml
jobs:
  detect-changes:
    runs-on: ubuntu-latest
    outputs:
      critical: ${{ steps.filter.outputs.critical }}
    steps:
      - uses: actions/checkout@v4
      - uses: dorny/paths-filter@v2
        id: filter
        with:
          filters: |
            critical:
              - 'src/task_state_machine/**'
              - 'src/langgraph_checkpointer/**'
              - 'src/worker_queue/**'
              - 'src/analysis_graph/**'
              - 'src/approval_flow/**'
              - 'src/publication/**'
              - 'src/audit_trail/**'
              - 'src/numeric_audit/**'
  
  lint-typecheck:
    needs: detect-changes
    runs-on: ubuntu-latest
    steps: [...]
  
  unit-tests:
    needs: detect-changes
    runs-on: ubuntu-latest
    services: {postgres, redis}
    steps: [...]
  
  integration-tests:
    needs: detect-changes
    runs-on: ubuntu-latest
    services: {postgres, redis}
    steps: [...]
  
  resume-tests:
    needs: detect-changes
    if: needs.detect-changes.outputs.critical == 'true'
    runs-on: ubuntu-latest
    services: {postgres, redis}
    steps:
      - name: Fumaça caos (5 execuções)
        run: pytest tests/chaos_smoke.py -v
  
  coverage:
    needs: [unit-tests, integration-tests]
    runs-on: ubuntu-latest
    steps:
      - name: Coverage critical path
        run: pytest --cov=src/task_state_machine --cov=src/langgraph_checkpointer ... --cov-fail-under=85
  
  security:
    needs: detect-changes
    runs-on: ubuntu-latest
    steps:
      - name: pip-audit
        run: pip-audit
```

🟡 **Workflow Noturno (`nightly-chaos.yml`):**
```yaml
on:
  schedule:
    - cron: '0 2 * * *'  # 02:00 UTC
  workflow_dispatch:
jobs:
  chaos-100:
    runs-on: ubuntu-latest
    timeout-minutes: 120
    steps:
      - uses: actions/checkout@v4
      - name: Run 100 chaos executions
        run: python -m tests.chaos_runner --executions 100 --output chaos-report.json
      - name: Upload report
        uses: actions/upload-artifact@v4
        with:
          name: chaos-report
          path: chaos-report.*
      - name: Create issue on failure
        if: failure()
        uses: actions/github-script@v7
        with:
          script: |
            github.rest.issues.create({
              owner: context.repo.owner,
              repo: context.repo.repo,
              title: '🔴 Nightly Chaos Failed - ${{ github.run_id }}',
              body: 'See workflow run for details.',
              labels: ['chaos', 'nightly', 'blocking']
            })
```

---

## 4. Edge Cases

| Cenário | Comportamento |
|---------|---------------|
| 🟡 PR não toca módulos críticos | `detect-changes` → `critical=false` → jobs pesados pulados → check passa verde |
| 🟡 Teste flaky falha na primeira, passa na retry | Retry conta como sucesso; log registra "flaky detectado" |
| 🟡 Teste flaky falha nas duas | Job falha; PR bloqueado |
| 🟡 Job noturno excede timeout (120 min) | Falha; issue aberta; investigação manual |
| 🟡 Cobertura < 85% no caminho crítico | Job `coverage` falha; PR bloqueado |
| 🟡 `pip-audit` encontra vulnerabilidade crítica | Job `security` falha; PR bloqueado |

---

## 5. Não-Gols

🟡 Não implementar testes de caos (componente `chaos-load-tests` — este componente só orquestra a execução no CI)
🟡 Não implementar testes de carga Locust (componente `chaos-load-tests`)
🟡 Não definir métricas de observabilidade (componente `observability`)
🟡 Não implementar deploy (fora de escopo)

---

## 6. Interface de Integração

🟡 **Entrada:** Código alterado no PR, schedule noturno
🟡 **Saída:** Checks verdes/vermelhos, issue automática, relatórios de caos, badge
🟡 **Dependências:** Todos os componentes (testes vivem junto ao código testado), `chaos-load-tests` (fornece runner de caos)

---

## 7. Critérios de Aceite (Gherkin)

```gherkin
Cenário: PR sem mudanças críticas passa rápido
  Dado PR altera apenas documentação
  Quando CI roda
  Então detect-changes retorna critical=false
  E jobs de teste pesados são pulados
  E check final fica verde em < 2 min

Cenário: PR em módulo crítico roda fumaça de caos
  Dado PR altera src/task_state_machine/
  Quando CI roda
  Então detect-changes retorna critical=true
  E resume-tests executa 5 execuções de caos
  E falha se duplicadas > 0 ou perdidas > 0

Cenário: Job noturno falha abre issue
  Dado job noturno de caos falha (duplicadas > 0)
  Quando workflow termina
  Então issue automática criada com label 'chaos', 'nightly', 'blocking'
  E política: "corrigir antes de novo merge no caminho crítico"
```

---

## 8. Perguntas Abertas

⚠️ **ABERTO:** Caminhos exatos dos módulos críticos no repo (acima são estimados)
⚠️ **ABERTO:** Branch reports vs GitHub Pages para relatórios históricos de caos
⚠️ **ABERTO:** Timeout do job noturno (120 min inicial) — ajustar após medir duração real

---

## 9. Valores Iniciais (a medir)

| Parâmetro | Valor Inicial | Fonte |
|-----------|---------------|-------|
| 🟡 Cobertura mínima caminho crítico | 85% | Fixado (único) |
| 🟡 Fumaça de caos execuções | 5 | Arbitrário |
| 🟡 Job noturno execuções | 100 | Fixado |
| 🟡 Job noturno timeout | 120 min | Arbitrário |
| 🟡 Schedule noturno | 02:00 UTC | Arbitrário |
| 🟡 Flaky retry count | 1 | Fixado |

---

## 10. Relatório de Avaliação (Scoring)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCORE TOTAL: 89/100
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Breakdown:
  Completude:    90/100 (peso 30%)
  Testabilidade: 90/100 (peso 25%)
  Clareza:       85/100 (peso 20%)
  Escopo:        90/100 (peso 15%)
  Edge Cases:    85/100 (peso 10%)

Gaps críticos:
  - Caminhos exatos dos módulos críticos dependem de estrutura final do repo
  - Destino dos relatórios históricos (branch reports vs Pages)

Sugestões:
  1. Definir estrutura de pastas `src/<modulo>/` antes de escrever workflow
  2. Testar workflow com PR de exemplo antes de ativar branch protection
  3. Automatizar publicação de relatórios em GitHub Pages se branch reports não suportar histórico
```