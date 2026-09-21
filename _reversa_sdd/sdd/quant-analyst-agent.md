# Spec SDD: Quant Analyst Agent (`quant-analyst-agent`)

> Selo 🟡 PLANEJADO em todos os requisitos, comportamentos e critérios de aceite.

**Versão:** 1.0  
**Data:** 2026-09-21T20:26:00Z  
**Componente:** `quant-analyst-agent`  
**Status:** 🟡 PLANEJADO  

---

## 1. Visão Geral e Objetivo

🟡 O `quant-analyst-agent` é responsável por processar os dados de mercado extraídos e executar cálculos quantitativos e estatísticos determinísticos (médias móveis simples/exponenciais, desvio padrão, volatilidade e otimização de rotas/tarifas). **Regra fundamental:** O agente invoca funções Python puras (`Pandas`, `Numpy`, `Scipy`) via Function Calling / Tools, proibindo categoricamente a geração de cálculos numéricos diretamente via LLM.

---

## 2. Requisitos Funcionais

- 🟡 **RF-01 (Tool de Média Móvel):** Expor função determinística Python `calculate_moving_average(series, window)` que retorna os valores calculados via Pandas.
- 🟡 **RF-02 (Tool de Desvio Padrão e Volatilidade):** Expor função determinística Python `calculate_volatility(series)` utilizando Numpy/Pandas.
- 🟡 **RF-03 (Tool de Otimização):** Expor função de otimização quantitativa via `scipy.optimize` para ajuste de peso de carteira ou otimização de frete/tarifa.
- 🟡 **RF-04 (Saída Estruturada Pydantic):** A resposta do agente deve seguir estritamente o modelo Pydantic contendo os resultados numéricos exatos, sem alteração de precisão.

---

## 3. Comportamentos e Regras de Negócio

- 🟡 O LLM atua apenas como roteador de intenção para selecionar a Tool correta e empacotar a resposta no contrato Pydantic.
- 🟡 Nenhum número presente na resposta pode ser fruto de alucinação do modelo de linguagem. Todos os valores numéricos devem obrigatoriamente possuir rastreabilidade para o retorno da Tool Python.

---

## 4. Edge Cases e Tratamento de Erros

- 🟡 **Série com Dados Insuficientes:** Se a janela de média móvel for maior que o tamanho da série histórica, retorna aviso de erro determinístico `INSUFFICIENT_DATA_POINTS`.
- 🟡 **Valores Nulos / NaN na Série:** A Tool Python deve filtrar ou imputar valores válidos antes de calcular estatísticas, emitindo aviso no payload.

---

## 5. Non-Goals (Fora de Escopo)

- 🟡 Coletar dados diretamente na Web ou APIs externas.
- 🟡 Formatar texto final de relatório para apresentação humana.

---

## 6. Critérios de Aceite

- 🟡 **Dado** uma lista de preços `[10.0, 12.0, 14.0, 16.0]`, **Quando** a função de média móvel com janela 2 for invocada, **Então** o resultado retornado deve ser idêntico ao valor retornado pelo Pandas (`[11.0, 13.0, 15.0]`).
- 🟡 **Dado** um payload de entrada sem o campo de série numérica, **Quando** o agente processar, **Then** deve falhar a validação Pydantic antes de acionar a LLM.

---

## 7. Avaliação de Qualidade

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCORE TOTAL: 94/100
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Breakdown:
  Completude:    95/100 (peso 30%)
  Testabilidade: 95/100 (peso 25%)
  Clareza:       95/100 (peso 20%)
  Escopo:        90/100 (peso 15%)
  Edge Cases:    90/100 (peso 10%)

Gaps críticos:
  Nenhum gap bloqueador identificado.

Sugestões:
  1. Definir limites padrão para janelas de média móvel (ex: 7, 14, 21, 50, 200 períodos).
```

---

Gerado por reversa-spec-sdd em 2026-09-21T20:26:00Z  
Fonte: prd.md
