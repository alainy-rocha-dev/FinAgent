# Spec SDD: Report Writer Agent (`report-writer-agent`)

> Selo 🟡 PLANEJADO em todos os requisitos, comportamentos e critérios de aceite.

**Versão:** 1.0  
**Data:** 2026-09-21T20:26:00Z  
**Componente:** `report-writer-agent`  
**Status:** 🟡 PLANEJADO  

---

## 1. Visão Geral e Objetivo

🟡 O `report-writer-agent` consolida as saídas estruturadas provenientes do `data-collector-agent` e do `quant-analyst-agent` em um relatório executivo fluido, bem formatado (Markdown / PDF) e orientado a tomadores de decisão. Possui uma camada de **revisão e validação cruzada anti-alucinação** que verifica se todos os números citados no texto final correspondem exatamente aos valores retornados pela análise quantitativa.

---

## 2. Requisitos Funcionais

- 🟡 **RF-01 (Geração de Markdown Estruturado):** Produzir relatório técnico contendo seções de Resumo Executivo, Análise de Mercado, Indicadores Quantitativos e Recomendações/Conclusão.
- 🟡 **RF-02 (Validação Cruzada Anti-Alucinação):** Executar verificação programática que compara cada valor numérico impresso no texto final com a fonte de dados do `quant-analyst-agent`.
- 🟡 **RF-03 (Exportação em PDF/Markdown):** Permitir a renderização e gravação da saída final em arquivo `.md` e, opcionalmente, compilação para `.pdf`.
- 🟡 **RF-04 (Template Parametrizável):** Utilizar templates de síntese com marcações claras para garantir consistência visual e editorial.

---

## 3. Comportamentos e Regras de Negócio

- 🟡 O relatório não pode alterar o sentido ou os valores das estatísticas calculadas pelo `quant-analyst-agent`.
- 🟡 Caso a validação anti-alucinação detecte uma divergência entre a síntese em texto e os números calculados, o relatório deve ser rejeitado e re-submetido ao modelo com feedback corretivo explícito.

---

## 4. Edge Cases e Tratamento de Erros

- 🟡 **Divergência Numérica Detectada:** O sistema detecta um número no texto que não existe na análise prévia. Ação: rejeita o rascunho e força uma re-síntese focada na exatidão.
- 🟡 **Entrada Incompleta:** Se os dados do analista quantitativo vierem vazios ou marcados com erro, o agente deve gerar um relatório de alerta de falha de dados em vez de uma análise sintética.

---

## 5. Non-Goals (Fora de Escopo)

- 🟡 Alterar ou re-calcular métricas quantitativas.
- 🟡 Executar requisições externas para buscar novas cotações.

---

## 6. Critérios de Aceite

- 🟡 **Dado** os resultados numéricos `{media_movel: 15.4, volatilidade: 2.1%}`, **Quando** o relatório for sintetizado, **Então** o texto final deve citar exatamente `15.4` e `2.1%`, sem arredondamentos arbitrários ou números alucinados.
- 🟡 **Dado** a geração concluída, **Quando** o arquivo for salvo em disco, **Then** deve ter formato Markdown válido e selo de validação técnica.

---

## 7. Avaliação de Qualidade

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCORE TOTAL: 91/100
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Breakdown:
  Completude:    90/100 (peso 30%)
  Testabilidade: 90/100 (peso 25%)
  Clareza:       95/100 (peso 20%)
  Escopo:        90/100 (peso 15%)
  Edge Cases:    90/100 (peso 10%)

Gaps críticos:
  Nenhum gap bloqueador identificado.

Sugestões:
  1. Incluir suporte a tabelas em Markdown e gráficos ASCII simples ou imagens exportadas para o PDF.
```

---

Gerado por reversa-spec-sdd em 2026-09-21T20:26:00Z  
Fonte: prd.md
