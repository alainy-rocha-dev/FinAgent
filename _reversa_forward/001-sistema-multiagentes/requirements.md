# Requirements: Sistema Multiagentes de Análise Financeira (CrewAI / LangGraph)

> Identificador: `001-sistema-multiagentes`
> Data: `2026-09-21`
> Pasta da extração reversa: `_reversa_sdd/`
> Confidência: 🟢 CONFIRMADO, 🟡 INFERIDO, 🔴 LACUNA / DÚVIDA

## 1. Resumo executivo

Esta feature implementa a infraestrutura completa do Sistema Multiagentes de Análise Financeira em Python. 
Ela entrega a captura de dados de mercado (preços/cotações via scrapers/APIs), processamento quantitativo determinístico em Python (Pandas/Numpy) e a geração autônoma de relatórios gerenciais estruturados em Markdown. A orquestração suportará execução dupla via CrewAI e LangGraph com travas estritas contra alucinação numérica.

## 2. Contexto a partir do legado

| Fonte | Trecho relevante | Confidência |
|-------|------------------|-------------|
| `_reversa_sdd/prd.md#4-escopo-in` | Especificação da arquitetura multiagente dupla (CrewAI e LangGraph) e ferramentas numéricas | 🟢 |
| `_reversa_sdd/sdd/multiagent-orchestrator.md#2-requisitos-funcionais` | Requisitos de orquestração `StateGraph`, Pydantic e controle de iteração `max_iter` | 🟡 |
| `_reversa_sdd/sdd/data-collector-agent.md#2-requisitos-funcionais` | Especificação do coletor de dados de mercado com suporte a scraping e fallback mock | 🟡 |
| `_reversa_sdd/sdd/quant-analyst-agent.md#2-requisitos-funcionais` | Especificação do agente analista com funções determinísticas em Pandas/Numpy | 🟡 |
| `_reversa_sdd/sdd/report-writer-agent.md#2-requisitos-funcionais` | Especificação do agente relator em Markdown | 🟡 |

## 3. Personas e cenários de uso

| Persona | Objetivo | Cenário-chave |
|---------|----------|---------------|
| Analista Financeiro / Gestor | Obter relatórios quantitativos determinísticos de mercado | Disparar a pipeline CLI informando um ticker/moeda e receber um relatório consolidado sem alucinações |

## 4. Regras de negócio novas ou alteradas

1. **RN-01:** Todo cálculo quantitativo (média móvel, desvio padrão, volatilidade) DEVE ser executado por código Python determinístico (Pandas/Numpy), sendo expressamente proibido o cálculo direto por LLM. 🟢
2. **RN-02:** O fluxo de execução DEVE possuir limite máximo configurável de iterações (`max_iter = 3`) para evitar loops de decisão infinitos entre agentes. 🟢
3. **RN-03:** A comunicação entre os nós da pipeline DEVE ser validada através de contratos rígidos tipados em Pydantic. 🟡

## 5. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de aceite | Confidência |
|----|-----------|------------|--------------------|-------------|
| RF-01 | Coleta de Dados de Mercado | Must | O agente coletor busca dados válidos via scraping/API ou utiliza fallback mock em caso de falha | 🟢 |
| RF-02 | Análise Quantitativa Determinística | Must | O agente analista executa ferramentas Python e retorna métricas com precisão de 100% | 🟢 |
| RF-03 | Geração de Relatório Markdown | Must | O agente relator produz relatório formatado em Markdown contendo resumo executivo e tabela de métricas | 🟢 |
| RF-04 | Orquestração LangGraph / CrewAI | Must | Suporte ao chaveamento da execução da pipeline entre CrewAI e LangGraph (`StateGraph`) | 🟡 |

## 6. Requisitos Não Funcionais

| Tipo | Requisito | Evidência ou justificativa | Confidência |
|------|-----------|----------------------------|-------------|
| Desempenho | Tempo total de execução < 60s | `_reversa_sdd/prd.md#3-métricas-de-sucesso` | 🟢 |
| Confiabilidade | 0% de alucinação numérica | `_reversa_sdd/prd.md#3-métricas-de-sucesso` | 🟢 |
| Arquitetura | Python 3.11+ com validação Pydantic | `_reversa_sdd/prd.md#6-restrições` | 🟢 |

## 7. Critérios de Aceitação

```gherkin
Cenário: Coleta e análise com sucesso via CLI
  Dado um ticker de ativo válido fornecido no CLI (ex: "PETR4")
  Quando a pipeline for executada com a engine LangGraph
  Então os dados de mercado devem ser coletados sem erro
  E as métricas quantitativas (média e desvio padrão) devem ser calculadas deterministicamente
  E um relatório Markdown válido deve ser salvo no diretório de saída

Cenário: Estouro de limite de iterações (max_iter)
  Dado que um dos agentes falha ao preencher a estrutura Pydantic esperada
  Quando a pipeline tentar re-executar pela terceira vez (max_iter = 3)
  Então a execução deve ser interrompida com mensagem de erro controlada MAX_ITER_REACHED
```

## 8. Prioridade MoSCoW

| Item | MoSCoW | Justificativa |
|------|--------|---------------|
| RF-01 (Coletor) | Must | Requisito base de entrada de dados |
| RF-02 (Analista Quant) | Must | Core da inteligência e valor do negócio |
| RF-03 (Relator Markdown) | Must | Entrega final legível para o usuário |
| RF-04 (Orquestrador Duplo) | Should | Permite flexibilidade de comparação entre CrewAI e LangGraph |

## 9. Esclarecimentos

> Nenhuma sessão de dúvidas registrada ainda. Rode `/reversa-clarify` quando houver `[DÚVIDA]` pendente.

## 10. Lacunas

- 🟢 Nenhuma dúvida pendente no momento. Todas as definições estão alinhadas com as specs SDD.

## 11. Histórico de alterações

| Data | Alteração | Autor |
|------|-----------|-------|
| 2026-09-21 | Versão inicial gerada por `/reversa-requirements` | reversa |
