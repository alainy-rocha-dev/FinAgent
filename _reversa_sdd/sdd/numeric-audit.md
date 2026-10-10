# Spec: numeric-audit

> Selo 🟡 PLANEJADO. Componente gerado pelo reversa-spec-sdd a partir do PRD FinAgent + AgentPulse.

---

## 1. Resumo

🟡 Auditoria numérica: registro de métricas no código como fonte de verdade (key → unit, source_step, formula_id, formato), Redator escreve prosa com marcadores `{{SYMBOL.key}}`, código substitui pelo valor formatado e preenche `CalculatedValue` para proveniência. Varredura rejeita número literal no texto fora de lista permitida. Compara com `quant_metrics` persistida (ON CONFLICT DO NOTHING). `isclose` para valores cheios, igualdade de formato para texto exibido. Último portão (após Revisor). Falha = 1 regeneração → `FAILED` com `AUDIT_FAILED`. Classes de mutação com efetividade, namespace de símbolo, 0 falsos positivos em 50 limpos.

---

## 2. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|------------|---------------------|
| 🟡 RF-01 | Registro de métricas no código: `METRICS_REGISTRY[key] = {unit, source_step, formula_id, display_format}` | Must | `key` com namespace de símbolo (ex: `AAPL.vol_30d`); fonte única para auditoria e formatação |
| 🟡 RF-02 | `StructuredReport` com `values: dict[str, CalculatedValue]` onde `CalculatedValue = {key, value, unit, source_step, formula_ref}` | Must | Redator **não** digita valores/unidades/referências; só escolhe chaves; código preenche a partir do registro e métricas |
| 🟡 RF-03 | Redator escreve prosa com marcadores `{{AAPL.vol_30d}}`; código substitui pelo valor formatado | Must | Texto final não contém números digitados pelo LLM; varredura rejeita literal fora de lista permitida |
| 🟡 RF-04 | Lista permitida para números literais no texto: datas ISO, anos, nomes de ativos | Must | Qualquer outro número literal → rejeição na varredura |
| 🟡 RF-05 | Tabela `quant_metrics(task_id, symbol, metrics_json, hash)` com `ON CONFLICT DO NOTHING` | Must | Persistida pelo `quant_analyst`; auditoria compara com esta, não só com checkpoint |
| 🟡 RF-06 | Validador: valores cheios → `isclose(rel_tol=1e-9, abs_tol=1e-12)` configuráveis; texto exibido → igualdade com `display_format` do registro | Must | Classe 3 (arredondamento agressivo) detectada pela comparação de formato |
| 🟡 RF-07 | Auditoria = último portão: roda **após** `revisor` e **antes** de `prepare_review` | Must | Se `revisor` edita texto → auditoria roda de novo; snapshot guarda hash do texto auditado |
| 🟡 RF-08 | Falha de auditoria: 1 regeneração do `redator` (conta no orçamento); persistindo → `FAILED` com código `AUDIT_FAILED` e detalhe por chave no evento | Must | Sem novo estado terminal (`FAILED` já existe) |
| 🟡 RF-09 | Proveniência: `source_step` e `formula_ref` vêm do registro; auditoria falha se marcador referencia chave inexistente no registro ou nas métricas, ou se proveniência gravada diverge do registro | Must | Rastreabilidade completa do número à fórmula |

---

## 3. Comportamentos

🟡 **Registro de métricas (código, não config):**
```python
METRICS_REGISTRY = {
    "AAPL.vol_30d": {
        "unit": "decimal",
        "source_step": "quant_analyst",
        "formula_id": "vol_30d",
        "display_format": "{:.4%}"
    },
    "AAPL.sharpe_1y": {
        "unit": "ratio",
        "source_step": "quant_analyst",
        "formula_id": "sharpe_1y",
        "display_format": "{:.4f}"
    },
}
```

🟡 **Fluxo Redator → Auditoria:**
1. `redator` recebe `quant_metrics` (dict) e `METRICS_REGISTRY`
2. Escreve prosa: `"A volatilidade de 30 dias foi de {{AAPL.vol_30d}}."`
3. Código processa: para cada marcador `{{key}}`:
   - Busca `key` no `METRICS_REGISTRY` → falha se inexistente
   - Busca `key` em `quant_metrics` → falha se inexistente
   - Formata valor com `display_format` → substitui no texto
   - Cria `CalculatedValue(key, value, unit, source_step, formula_id)`
4. `StructuredReport` montado com `values` e `text` final
5. `audit_gate` (no grafo) valida:
   - Para cada `CalculatedValue`: `isclose(cv.value, quant_metrics[key], rel_tol, abs_tol)`
   - Texto exibido no `StructuredReport.text` corresponde ao formato (sem dígitos extras)
   - Varredura: regex procura números literais no texto fora de lista permitida
6. Se falha → 1 regeneração `redator` (mesmo prompt, mesmo `quant_metrics`) → re-auditoria
7. Se persiste → `FAILED` com `AUDIT_FAILED` + `{key: {expected, actual, diff}}` no evento

🟡 **Classes de mutação (suíte obrigatória):**
| Classe | Descrição | Exemplo |
|--------|-----------|---------|
| 1 | Dígito trocado | 0.234 → 0.243 |
| 2 | Unidade trocada | decimal ↔ percentual |
| 3 | Arredondamento agressivo | 4 casas → 2 casas (detectado por formato) |
| 4 | Valor inventado | chave no relatório, ausente nas métricas |
| 5 | Valor de outro ativo | `AAPL.vol_30d` recebe valor de `PETR4.vol_30d` (namespace impede) |
| 6 | Sinal invertido | +0.234 → -0.234 |
| 7 | Ordem de magnitude | ×10, ÷10 |

**Condições de efetividade:**
- Mutação só conta se **altera o valor** (no-ops descartados e contabilizados)
- Mínimo 30 mutações efetivas por classe, semente fixa + testes por propriedade (Hypothesis)
- Classe 5 exige namespace de símbolo (`AAPL.` vs `PETR4.`)
- **Critério:** 100% das mutações efetivas das classes cobertas detectadas, com contagem por classe
- **Falso positivo:** 0 rejeições em 50 relatórios limpos (arbitrário)

**Classes NÃO cobertas (declaradas no README):**
- Omissão seletiva de métricas
- Rótulo ou unidade textual errada ("%" no lugar de "pontos")
- Afirmações qualitativas e comparativas ("alta expressiva")
- Datas e períodos
- Cálculo errado no Quant (testes golden contra valores de referência, fora da auditoria)

---

## 4. Edge Cases

| Cenário | Comportamento |
|---------|---------------|
| 🟡 Marcador `{{AAPL.inexistente}}` | Rejeitado na substituição (chave não está no registro) |
| 🟡 Marcador `{{PETR4.vol_30d}}` em relatório de AAPL | Rejeitado (namespace de símbolo diferente) |
| 🟡 `revisor` edita texto e adiciona número literal "23.4%" | Varredura rejeita → regeneração `redator` |
| 🟡 Métrica com valor 0, mutação sinal invertido | No-op → descartado da contagem de mutações efetivas |
| 🟡 `quant_metrics` não tem chave que `redator` usa | Falha na substituição → `AUDIT_FAILED` |
| 🟡 `display_format` produz string que não passa `isclose` ao parsear | Erro de configuração no registro → detectado em testes |

---

## 5. Não-Gols

🟡 Não implementar `quant_analyst` (componente `analysis-graph`)
🟡 Não implementar `redator` (componente `analysis-graph`)
🟡 Não implementar grafo (componente `analysis-graph`)
🟡 Não implementar testes golden do Quant (separados, planilha/implementação independente)
🟡 Não auditar afirmações qualitativas, datas, omissões (fora de escopo)

---

## 6. Interface de Integração

🟡 **Entrada:** `StructuredReport` (do `redator`), `quant_metrics` (persistida), `METRICS_REGISTRY` (código)
🟡 **Saída:** `AuditResult` (pass/fail, detalhes por chave), `StructuredReport` validado, hash do texto auditado
🟡 **Dependências:** `analysis-graph` (chama auditoria), `budget-control` (regeneração conta no orçamento), `task-state-machine` (transição `FAILED`/`AUDIT_FAILED`), `audit-trail` (evento `AUDIT_RESULT`)

---

## 7. Critérios de Aceite (Gherkin)

```gherkin
Cenário: Marcador substituído e auditado corretamente
  Dado METRICS_REGISTRY["AAPL.vol_30d"] = {unit: "decimal", display_format: "{:.4%}"}
  E quant_metrics["AAPL.vol_30d"] = 0.23456
  Quando redator escreve "Vol: {{AAPL.vol_30d}}"
  Então texto final = "Vol: 23.4560%"
  E CalculatedValue = {key: "AAPL.vol_30d", value: 0.23456, unit: "decimal", source_step: "quant_analyst", formula_ref: "vol_30d"}
  E auditoria isclose(0.23456, 0.23456) passa
  E formato "{:.4%}" corresponde ao texto exibido

Cenário: Número literal no texto rejeitado
  Dado redator escreve "A volatilidade foi de 23.4%"
  Quando varredura roda
  Então rejeitado: "número literal 23.4 não permitido fora de lista permitida"
  E redator regenera (1 tentativa)

Cenário: Mutação dígito trocado detectada
  Dado relatório correto auditado
  Quando injeta mutação classe 1: 0.23456 → 0.24356 no CalculatedValue
  Então auditoria falha no isclose
  E detectada na classe 1

Cenário: Falha persistente → FAILED com AUDIT_FAILED
  Dado redator falha na auditoria
  E regeneração (1 extra) também falha
  Então task-state-machine transiciona para FAILED
  E evento com código AUDIT_FAILED e detalhe por chave
```

---

## 8. Perguntas Abertas

⚠️ **ABERTO:** `METRICS_REGISTRY` completo — listar todas as chaves, unidades, fórmulas, formatos
⚠️ **ABERTO:** `rel_tol=1e-9, abs_tol=1e-12` — confirmar se adequado para todas as métricas
⚠️ **ABERTO:** 50 relatórios limpos para falso positivo — gerar como? (golden set versionado)

---

## 9. Valores Iniciais (a medir)

| Parâmetro | Valor Inicial | Fonte |
|-----------|---------------|-------|
| 🟡 `isclose rel_tol` | 1e-9 | Arbitrário |
| 🟡 `isclose abs_tol` | 1e-12 | Arbitrário |
| 🟡 Mutações efetivas por classe | 30 | Arbitrário |
| 🟡 Relatórios limpos (falso positivo) | 50 | Arbitrário |
| 🟡 Regenerações redator pós-auditoria | 1 | Fixado |

---

## 10. Relatório de Avaliação (Scoring)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCORE TOTAL: 87/100
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Breakdown:
  Completude:    90/100 (peso 30%)
  Testabilidade: 85/100 (peso 25%)
  Clareza:       85/100 (peso 20%)
  Escopo:        90/100 (peso 15%)
  Edge Cases:    85/100 (peso 10%)

Gaps críticos:
  - METRICS_REGISTRY completo não listado (precisa inventário de métricas do quant_analyst)
  - Tolerâncias isclose por métrica podem variar
  - Geração de 50 relatórios limpos para teste de falso positivo

Sugestões:
  1. Extrair METRICS_REGISTRY do código do quant_analyst (fonte única)
  2. Testar isclose com valores reais de cada métrica para validar tolerâncias
  3. Automatizar geração de relatórios limpos (golden set) no CI
  4. Documentar classes não cobertas no README do projeto
```