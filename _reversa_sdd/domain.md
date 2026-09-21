# Domínio e Regras de Negócio (Domain Specs) — sisanalisefinanceira

> **Status:** 🟢 CONFIRMADO / 🟡 INFERIDO  
> **Nível de Documentação:** Essencial  
> **Gerado por:** Detetive  

---

## 1. Glossário do Domínio

| Termo | Conceito / Definição | Confiança |
|---|---|---|
| **Símbolo / Ticker** | Identificador único de um ativo financeiro ou par de moedas (ex: `AAPL`, `PETR4`, `USD/BRL`). | 🟢 CONFIRMADO |
| **Payload de Dados de Mercado (`MarketDataPayload`)** | Objeto contendo os dados brutos de preços históricos de fechamento e volumes coletados. | 🟢 CONFIRMADO |
| **Métricas Quantitativas (`QuantAnalysisMetrics`)** | Indicadores estatísticos calculados de forma 100% determinística (sem alucinação por LLM). | 🟢 CONFIRMADO |
| **Validação Anti-Alucinação** | Mecanismo que audita o texto do relatório comparando números gerados com as métricas exatas calculadas por ferramentas Python. | 🟢 CONFIRMADO |
| **Mock Fallback** | Salvaguarda que provê dados simulados caso a API/scraping online de mercado falhe ou seja desativada. | 🟢 CONFIRMADO |
| **Salvaguarda `MAX_ITER_REACHED`** | Evento de término forçado do orquestrador LangGraph quando atinge o limite máximo de iterações (`max_iter`). | 🟢 CONFIRMADO |

---

## 2. Regras de Negócio Implícitas (Business Rules)

### RN-01: Sanitização de Símbolos
- Símbolos fornecidos via CLI ou API devem ser sanitizados para letras maiúsculas e sem espaços nas extremidades (`strip().upper()`).
- Símbolos vazios ou nulos disparam erro imediato `INVALID_SYMBOL`.
- *Localização:* `sisanalisefinanceira/agents/data_collector.py:23-31`
- *Confiança:* 🟢 CONFIRMADO

### RN-02: Garantia de Coleta e Resiliência (Mock Fallback)
- Por padrão (`use_mock_fallback = True`), se a coleta HTTP via Yahoo Finance falhar, o sistema deve acionar automaticamente a base mock predefinida sem interromper a execução do fluxo.
- *Localização:* `sisanalisefinanceira/agents/data_collector.py:33-40`
- *Confiança:* 🟢 CONFIRMADO

### RN-03: Tamanho Mínimo de Série Temporal para Média Móvel
- Para calcular a média móvel simples de janela $W$, a série de preços limpa deve possuir no mínimo $W$ pontos válidos. Se a quantidade de preços válidos for menor que $W$, a análise é interrompida com o código `INSUFFICIENT_DATA_POINTS`.
- *Localização:* `sisanalisefinanceira/agents/quant_analyst.py:108-113`
- *Confiança:* 🟢 CONFIRMADO

### RN-04: Cálculo Determinístico e Descarte de Valores Nulos (NaN)
- Quaisquer valores nulos ou `NaN` recebidos na série de preços brutos são descartados durante a sanitização antes da execução dos cálculos estatísticos. Um alerta é anexado no relatório.
- *Localização:* `sisanalisefinanceira/agents/quant_analyst.py:99-107`
- *Confiança:* 🟢 CONFIRMADO

### RN-05: Contrato da Validação Anti-Alucinação
- O relatório executivo gerado só é considerado válido se contiver obrigatoriamente a string exata do preço médio (`mean_price`) e da volatilidade (`volatility`).
- Se a validação reprovar, o agente relator efetua uma regeração determinística antes de aceitar o resultado final.
- *Localização:* `sisanalisefinanceira/agents/report_writer.py:71`
- *Confiança:* 🟢 CONFIRMADO

### RN-06: Teto Estrito de Iterações (`max_iter`)
- O motor `LangGraphOrchestrator` executa em ciclo até que um relatório válido seja gerado ou até que a contagem de iterações atinja `max_iter` (padrão: 3). Atingindo o teto, o sistema é abortado em estado `MAX_ITER_REACHED`.
- *Localização:* `sisanalisefinanceira/orchestrators/langgraph_orchestrator.py:30-67`
- *Confiança:* 🟢 CONFIRMADO
