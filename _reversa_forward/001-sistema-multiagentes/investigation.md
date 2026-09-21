# Investigação Técnica: Sistema Multiagentes de Análise Financeira

> Feature: `001-sistema-multiagentes`
> Data: `2026-09-21`

## 1. Pesquisa de Fundo

Para a implementação do sistema multiagentes, avaliou-se o uso de orquestração declarativa de grafo (`LangGraph`) vs orquestração baseada em papéis/tarefas (`CrewAI`). Ambos os frameworks oferecem abstrações sólidas, porém com paradigmas diferentes:

- **CrewAI**: Foco em declaração de papéis (`Agent`), metas (`Goal`), estórias de fundo (`Backstory`) e sequenciamento de tarefas (`Task`). Excelente para rápido protótipo e síntese narrativa.
- **LangGraph**: Foco em grafos de estado finitos (`StateGraph`), controle determinístico de nós (`Nodes`) e arestas condicionais (`Conditional Edges`). Ideal para validação rígida de fluxos, recuperação de erros e controle fino de loops (`max_iter`).

## 2. Alternativas Avaliadas

### Alternativa A: Orquestrador Único em CrewAI
- **Vantagens**: Simplicidade de código inicial.
- **Desvantagens**: Menor controle sobre o estado interno e transições condicionais rígidas com Pydantic.
- **Veredito**: Descartada como opção única; será mantida como uma das opções de engine suportadas.

### Alternativa B: Orquestrador Duplo com Abstração Comum (Escolhida)
- **Vantagens**: Permite comparar diretamente a performance, usabilidade e estabilidade de ambos os frameworks sob o mesmo contrato de dados (`MarketDataState`).
- **Desvantagens**: Requer um padrão Adapter (`AgentOrchestrator`) para unificar as entradas e saídas.
- **Veredito**: **Adotada**.

## 3. Padrões de Projeto Aplicados

1. **Adapter Pattern**: Para isolar as especificidades do CrewAI e do LangGraph sob uma interface uniforme `OrchestratorInterface`.
2. **Tool/Function Calling Pattern**: Para garantir que execuções matemáticas (Pandas/NumPy) ocorram estritamente em sandbox Python determinístico.
3. **Repository/Provider Pattern**: Para alternar de forma transparente entre APIs reais (`yfinance`, scraping) e Mocks locais (`MockMarketDataProvider`).
