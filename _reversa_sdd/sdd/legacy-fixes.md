# Legacy Fixes Checklist

> Selo 🟡 PLANEJADO. Itens de correção de precisão nos repositórios legados (FinAgent e AgentPulse).  
> **Prazo:** Itens de precisão antes das etapas pesadas (semanas 1-3); reescrita final do README + vídeo na Etapa 5.

---

## Atribuição por Repositório

| Item | Repositório | Status |
|------|-------------|--------|
| Typo "Altura Escala" → "Alta Escala" | **AgentPulse** | 🟡 Pendente |
| Diagrama de arquitetura não renderiza (Mermaid/PlantUML) | **AgentPulse** | 🟡 Pendente |
| Caminho `file:///C:/...` vazado no README | **FinAgent** | 🟡 Pendente |
| Claim "100% determinístico" → "Determinístico nas métricas; LLM em prosa com auditoria numérica (classes cobertas e não cobertas listadas)" | **FinAgent** | 🟡 Pendente (nova redação só quando `numeric-audit` existir) |
| `unittest` → `pytest` nos exemplos e badges | **FinAgent** | 🟡 Pendente |
| Badge de framework de teste → **Badge do CI** | **FinAgent** | 🟡 Pendente |
| Mock/fallback silencioso documentado como apenas teste/CI | **FinAgent** | 🟡 Pendente |
| CLI: padrão sem fallback; mock só com flag explícita | **FinAgent** | 🟡 Pendente |
| `data_quality = SIMULATED` bloqueia publicação; `ALLOW_SIMULATED_PUBLICATION=true` fora de prod exige `acknowledge_simulated=true`; em prod recusa iniciar com flag e rejeita campo sem flag (422) | **FinAgent** | 🟡 Pendente |
| `cli.py --help`: aviso de que modo legacy não tem durabilidade, retomada nem aprovação | **FinAgent** | 🟡 Pendente |
| Comandos de cliente da API (opcionais, cortar se prazo apertar) | **FinAgent** | 🟡 Opcional |

---

## Detalhamento por Item

### 1. Typo "Altura Escala" → "Alta Escala" (AgentPulse)
- **Arquivo:** `README.md` (raiz do AgentPulse)
- **Linha:** Procurar "Altura Escala"
- **Correção:** "Alta Escala"
- **Critério:** `grep -r "Altura Escala" .` retorna 0

### 2. Diagrama de Arquitetura (AgentPulse)
- **Arquivo:** `README.md` (raiz do AgentPulse)
- **Problema:** Diagrama Mermaid/PlantUML não renderiza no GitHub
- **Solução:** 
  - Usar Mermaid (suportado nativo no GitHub) com sintaxe correta
  - Ou renderizar como imagem (SVG/PNG) e embutir
  - Validar: `markdownlint` ou visualização no GitHub
- **Critério:** Diagrama visível no README do GitHub

### 3. Caminho `file:///C:/...` (FinAgent)
- **Arquivo:** `README.md` (raiz do FinAgent) e possivelmente `docs/`
- **Problema:** Caminho local Windows vazado
- **Correção:** Remover ou substituir por caminho relativo / link válido
- **Critério:** `grep -r "file:///C:/" .` retorna 0

### 4. Claim "100% Determinístico" (FinAgent)
- **Arquivo:** `README.md`, `docs/`, `cli.py --help`
- **Redação antiga:** "100% determinístico"
- **Nova redação (só quando `numeric-audit` existir):**
  > "Determinístico nas métricas quantitativas; prosa gerada por LLM com auditoria numérica automática (classes cobertas: dígito trocado, unidade trocada, arredondamento agressivo, valor inventado, valor de outro ativo, sinal invertido, ordem de magnitude; classes não cobertas: omissão seletiva, rótulo/unidade textual errada, afirmações qualitativas, datas/períodos, cálculo errado no Quant — coberto por testes golden)"
- **Critério:** Claim atualizado e auditável

### 5. `unittest` → `pytest` (FinAgent)
- **Arquivos:** `README.md`, `CONTRIBUTING.md`, `setup.py`/`pyproject.toml`, scripts de teste
- **Correção:** Substituir referências a `unittest` por `pytest`
- **Exemplo:** `python -m unittest` → `pytest`
- **Critério:** `grep -r "unittest" . --include="*.md" --include="*.rst" --include="*.txt"` retorna 0 (exceto menções históricas em changelog)

### 6. Badge de Framework → Badge do CI (FinAgent)
- **Arquivo:** `README.md` (badges no topo)
- **Problema:** Badge mostra "unittest" ou "pytest" — não informa status real
- **Correção:** Substituir por badge do GitHub Actions / GitLab CI:
  ```markdown
  ![CI](https://github.com/ORG/REPO/actions/workflows/ci.yml/badge.svg)
  ```
- **Critério:** Badge reflete status real do pipeline

### 7. Mock/Fallback Silencioso Documentado (FinAgent)
- **Arquivos:** `README.md`, `docs/architecture.md`, `agents/data_collector.py`
- **Documentação obrigatória:**
  - `MockProvider` é **apenas para testes/CI**
  - Não usar em produção
  - `data_quality = SIMULATED` bloqueia publicação por padrão
  - `ALLOW_SIMULATED_PUBLICATION=true` (fora de prod) habilita aprovação com `acknowledge_simulated=true`
  - Em `APP_ENV=prod`: aplicação recusa iniciar se `ALLOW_SIMULATED_PUBLICATION=true`; campo `acknowledge_simulated` sem a flag → 422
- **Critério:** Documentação clara em README e docstrings do `MockProvider`

### 8. CLI: Padrão Sem Fallback; Mock Só Com Flag Explícita (FinAgent)
- **Arquivo:** `cli.py`
- **Comportamento atual (problemático):** Mock é padrão; `--no-mock` para ir online
- **Novo comportamento:**
  - Padrão: **sem fallback** (provedor real obrigatório)
  - Flag explícita para mock: `--mock` ou `--provider mock`
  - `--mock` só funciona se `ALLOW_SIMULATED_PUBLICATION=true` e `APP_ENV!=prod`
- **Critério:** `python -m sisanalisefinanceira.cli --help` mostra `--mock` como opcional; sem `--mock` usa provedor real

### 9. Comportamento `data_quality = SIMULATED` e `ALLOW_SIMULATED_PUBLICATION` (FinAgent)
| Ambiente | `ALLOW_SIMULATED_PUBLICATION` | `acknowledge_simulated` | Resultado |
|----------|-------------------------------|-------------------------|-----------|
| prod | false (padrão) | ignorado | **Bloqueia** publicação; app recusa iniciar se true |
| prod | true | ignorado | **Erro startup**: "ALLOW_SIMULATED_PUBLICATION não permitido em prod" |
| dev/test | false | ignorado | **Bloqueia** publicação (padrão seguro) |
| dev/test | true | false | **Bloqueia** publicação (DATA_QUALITY_BLOCKED) |
| dev/test | true | true | **Permite** com aviso no relatório |

- **Nada é ignorado em silêncio.** Comportamento explícito em todos os casos.
- **Critério:** Testes de integração cobrem todas as 5 linhas da tabela acima

### 10. `cli.py --help`: Aviso Modo Legacy (FinAgent)
- **Arquivo:** `cli.py`
- **Adicionar ao `--help`:**
  ```
  --legacy          Executa pipeline original local sem AgentPulse/Postgres.
                    AVISO: Modo legacy NÃO tem durabilidade, retomada nem aprovação humana.
                    Use apenas para compatibilidade/debug.
  ```
- **Critério:** `python -m sisanalisefinanceira.cli --help` mostra aviso

### 11. Comandos de Cliente da API (FinAgent — Opcional)
- **Escopo:** `agentpulse run <symbol>`, `agentpulse status <id>`, `agentpulse approve <id>`, `agentpulse reject <id>`, `agentpulse replay <id>`
- **Decisão:** Opcionais; cortar se prazo apertar
- **Critério:** Se implementados, `agentpulse --help` lista comandos

### 12. Reescrita Final do README + Vídeo (Etapa 5 — Ambos Repos)
- **Cenário no topo:** "Do caos à confiança: como o FinAgent + AgentPulse garante 0 duplicadas e 0 perdidas"
- **Resultados com data:** Métricas do spike e noturno (ex: "Spike 2026-10-15: 0/100 duplicadas, p95 recuperação 2.3s")
- **Vídeo de 2 minutos:** Mostra `docker kill` do worker + clique em "Aprovar" na UI + tarefa retoma sem duplicar
- **Critério:** README atualizado; vídeo hospedado (YouTube/Loom) linkado no README

---

## Ordem de Execução Sugerida

| Semana | Itens |
|--------|-------|
| 1-2 (antes trabalho pesado) | 1, 2, 3, 5, 6, 7, 8, 9, 10 |
| 3-4 | 4 (após `numeric-audit` existir) |
| 5 (Etapa 5) | 11 (se tempo), 12 |

---

## Validação

```bash
# Verificar todos os itens de precisão
grep -r "Altura Escala" .                    # Deve retornar 0 (AgentPulse)
grep -r "file:///C:/" .                      # Deve retornar 0 (FinAgent)
grep -r "100% deterministico" . --include="*.md"  # Deve retornar 0 (FinAgent)
grep -r "unittest" . --include="*.md" --include="*.rst"  # Deve retornar 0 (FinAgent)
grep -r "MockProvider" . --include="*.py" -A 2 -B 2  # Verificar docstring "apenas testes/CI"
python -m sisanalisefinanceira.cli --help    # Verificar aviso --legacy e flag --mock
```

---

## Relatório de Avaliação (Scoring)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCORE TOTAL: 90/100
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Breakdown:
  Completude:    95/100 (peso 30%)
  Testabilidade: 90/100 (peso 25%)
  Clareza:       90/100 (peso 20%)
  Escopo:        85/100 (peso 15%)
  Edge Cases:    90/100 (peso 10%)

Gaps críticos:
  - Nova redação do claim "determinístico" depende de numeric-audit existir
  - Vídeo da Etapa 5 depende de sistema funcional

Sugestões:
  1. Executar itens 1-3, 5-10 nas semanas 1-2 (baixo esforço, alto impacto visual)
  2. Agendar item 4 para logo após numeric-audit passar no CI
  3. Gravar vídeo na Etapa 5 com cenário real de caos (docker kill + approve)
```