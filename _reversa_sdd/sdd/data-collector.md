# Spec: data-collector

> Selo 🟡 PLANEJADO. Componente gerado pelo reversa-spec-sdd a partir do PRD FinAgent + AgentPulse.

---

## 1. Resumo

🟡 Coletor de dados de mercado com `data_quality` em 3 valores (`LIVE | STALE | SIMULATED`), interface plugável para provedores, `acknowledge_simulated`, trava `APP_ENV=prod`, proveniência no payload, `market_payloads` com `ON CONFLICT DO NOTHING`.

---

## 2. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|------------|---------------------|
| 🟡 RF-01 | `data_quality` com 3 valores: `LIVE` (fresco), `STALE` (provedor mas > TTL frescor), `SIMULATED` (mock/fallback) | Must | Enum no código e no banco; cada execução classifica |
| 🟡 RF-02 | `acknowledge_simulated` flag booleana na request (padrão `false`) | Must | Se `SIMULATED` e `acknowledge_simulated=false` → `DATA_QUALITY_BLOCKED`; se `true` → prossegue com aviso |
| 🟡 RF-03 | Trava `APP_ENV=prod`: em prod, `acknowledge_simulated` ignorado e `SIMULATED` sempre bloqueia | Must | Aplicação recusa iniciar se `ALLOW_SIMULATED_PUBLICATION=true` em prod; campo sem flag → 422 |
| 🟡 RF-04 | Proveniência no payload: `MarketDataPayload` ganha `source` (enum), `fetched_at`, `ttl_seconds`, `raw_sample_hash` (sha256 amostra) | Must | Rastreabilidade completa da origem do dado |
| 🟡 RF-05 | Tabela `market_payloads(task_id, symbol, source, payload_jsonb, fetched_at, UNIQUE(task_id, symbol, source))` com `ON CONFLICT DO NOTHING` | Must | Inserção idempotente por execução; mesma execução não duplica |
| 🟡 RF-06 | Interface plugável: `MarketDataProvider` protocol com `fetch(symbol) -> MarketDataPayload` | Must | Implementações: `YahooFinanceProvider`, `BCBProvider`, `MockProvider`; factory por config/env |
| 🟡 RF-07 | Limite STALE: `stale_max_age_days` por classe de ativo (valor inicial 5 dias, arbitrário, cobre fins de semana/feriados) | Should | Dado do provedor com `fetched_at` > `now() - stale_max_age_days[asset_class]` → `STALE`; prossegue com flag `stale_warning` no snapshot |

---

## 3. Comportamentos

🟡 **Fluxo do coletor (nó do grafo):**
1. Recebe `symbol`, `acknowledge_simulated` (da request), `task_id`
2. Factory seleciona provider: `YAHOO_FINANCE` (padrão) | `BCB` (câmbio) | `MOCK` (se `ALLOW_SIMULATED_PUBLICATION=true` e não prod)
3. Chama `provider.fetch(symbol)` → `MarketDataPayload`
4. Determina `asset_class` do símbolo (ex: `equity`, `fx`, `crypto`)
5. Calcula `data_quality`:
   - Se provider = `MOCK` → `SIMULATED`
   - Se `fetched_at` > `now() - stale_max_age_days[asset_class]` → `LIVE`
   - Caso contrário → `STALE`
6. Se `data_quality == SIMULATED`:
   - Se `APP_ENV=prod` → `DATA_QUALITY_BLOCKED` (falha precoce, antes do analista quant)
   - Se `acknowledge_simulated=false` → `DATA_QUALITY_BLOCKED`
   - Se `acknowledge_simulated=true` → prossegue, `stale_warning=false`, aviso no relatório
7. Se `data_quality == STALE` → prossegue, `stale_warning=true` no snapshot
8. Insere em `market_payloads` com `ON CONFLICT DO NOTHING` (idempotente por execução)
9. Retorna `MarketDataPayload` com proveniência completa

🟡 **`MarketDataPayload` (Pydantic):**
```python
class MarketDataPayload(BaseModel):
    symbol: str
    asset_class: Literal["equity", "fx", "crypto", "other"]
    data: dict  # preços, volumes, etc.
    source: Literal["yahoo_finance", "bcb", "mock"]
    fetched_at: datetime
    ttl_seconds: int
    raw_sample_hash: str  # sha256 de amostra bruta (ex: primeiras 1KB)
    data_quality: Literal["LIVE", "STALE", "SIMULATED"]
    stale_warning: bool = False
```

🟡 **Configuração de ambiente:**
```bash
# Produção
APP_ENV=prod
ALLOW_SIMULATED_PUBLICATION=false  # padrão
# Se true em prod → startup falha

# Desenvolvimento / CI
APP_ENV=dev
ALLOW_SIMULATED_PUBLICATION=true
# MockProvider disponível; acknowledge_simulated controla bloqueio

# STALE por classe de ativo (dias, cobre fins de semana/feriados)
STALE_MAX_AGE_EQUITY=5
STALE_MAX_AGE_FX=3
STALE_MAX_AGE_CRYPTO=1
STALE_MAX_AGE_OTHER=5
```

---

## 4. Edge Cases

| Cenário | Comportamento |
|---------|---------------|
| 🟡 Yahoo Finance retorna erro (rate limit, 5xx) | Retry exponencial + jitter (máx 3); se falha → `MockProvider` se `ALLOW_SIMULATED_PUBLICATION=true` → `SIMULATED`; senão → falha do nó → `FAILED` |
| 🟡 Mesmo `task_id` + `symbol` + `source` reexecutado | `ON CONFLICT DO NOTHING` → não duplica; payload existente usado |
| 🟡 `STALE` em prod | Permitido (dado real, só velho); `stale_warning=true` no snapshot; aprovação vê aviso |
| 🟡 `acknowledge_simulated=true` em prod | Ignorado; `SIMULATED` sempre bloqueia; campo rejeitado (422) se enviado |
| 🟡 Provider retorna dado vazio / inválido | Validação Pydantic falha → nó falha → retry → `FAILED` |

---

## 5. Não-Gols

🟡 Não implementar analista quant (componente `analysis-graph`)
🟡 Não implementar máquina de estados (componente `task-state-machine` — recebe `DATA_QUALITY_BLOCKED`)
🟡 Não implementar UI (componente `approval-ui` — exibe `data_quality` em destaque)
🟡 Não definir `stale_max_age_days` por classe de ativo final (valores iniciais: equity=5, fx=3, crypto=1, other=5 dias, a medir)
🟡 Não implementar provedores além de Yahoo Finance, BCB, Mock (extensível via protocol)

---

## 6. Interface de Integração

🟡 **Entrada:** `symbol`, `task_id`, `acknowledge_simulated` (bool), config de provider
🟡 **Saída:** `MarketDataPayload` com `data_quality`, `source`, proveniência; linha em `market_payloads`
🟡 **Dependências:** `task-state-machine` (transição `DATA_QUALITY_BLOCKED`), `analysis-graph` (nó coletor), `audit-trail` (evento `MARKET_DATA_COLLECTED`), `domain_pool` (transacional para `market_payloads`)

---

## 7. Critérios de Aceite (Gherkin)

```gherkin
Cenário: Dado simulado bloqueado sem acknowledge
  Dado APP_ENV=dev, ALLOW_SIMULATED_PUBLICATION=true
  Quando coletor executa com MockProvider e acknowledge_simulated=false
  Então data_quality = SIMULATED
  E task-state-machine transiciona para DATA_QUALITY_BLOCKED
  E tarefa termina sem analista quant

Cenário: Dado simulado permitido com acknowledge
  Dado APP_ENV=dev, ALLOW_SIMULATED_PUBLICATION=true
  Quando coletor executa com MockProvider e acknowledge_simulated=true
  Então data_quality = SIMULATED
  E tarefa prossegue para analista quant
  E snapshot inclui aviso "Dados simulados — acknowledge_simulated=true"

Cenário: Dado simulado em prod sempre bloqueia
  Dado APP_ENV=prod
  Quando coletor executa (mesmo com MockProvider e acknowledge_simulated=true)
  Então DATA_QUALITY_BLOCKED
  E aplicação recusa iniciar se ALLOW_SIMULATED_PUBLICATION=true

Cenário: Idempotência market_payloads
  Dado coletor executa duas vezes mesma task_id, symbol, source
  Quando segunda execução insere em market_payloads
  Então ON CONFLICT DO NOTHING → linha não duplicada
  E payload original preservado
```

---

## 8. Perguntas Abertas

⚠️ **ABERTO:** `stale_max_age_days` por classe de ativo — valores iniciais (equity=5, fx=3, crypto=1, other=5) cobrem fins de semana/feriados; medir frescor real por provedor
⚠️ **ABERTO:** `raw_sample_hash` — tamanho da amostra (1KB inicial) e algoritmo (sha256)
⚠️ **ABERTO:** Termos de uso Yahoo Finance / BCB — permitem uso em produção? Rate limits, atribuição, cache
⚠️ **ABERTO:** BCB provider — apenas para câmbio ou também ações brasileiras?

---

## 9. Valores Iniciais (a medir)

| Parâmetro | Valor Inicial | Fonte |
|-----------|---------------|-------|
| 🟡 `stale_max_age_days[equity]` | 5 dias | Arbitrário |
| 🟡 `stale_max_age_days[fx]` | 3 dias | Arbitrário |
| 🟡 `stale_max_age_days[crypto]` | 1 dia | Arbitrário |
| 🟡 `stale_max_age_days[other]` | 5 dias | Arbitrário |
| 🟡 `raw_sample_hash` sample size | 1 KB | Arbitrário |
| 🟡 Max retries Yahoo Finance | 3 | Padrão |
| 🟡 Retry backoff base | 2s + jitter | Padrão |

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
  - stale_max_age_days por classe de ativo e termos de uso provedores precisam validação
  - Comportamento BCB provider não totalmente especificado

Sugestões:
  1. Medir latência e frescor do Yahoo Finance em produção para calibrar stale_ttl
  2. Revisar termos de uso do Yahoo Finance e BCB antes de definir provedor padrão
  3. Testar idempotência market_payloads com concorrência real
```