# PRD: Sistema Multiagentes de Análise Financeira ou Logística

> Selo 🟡 PLANEJADO. Documento gerado a partir de ideation + personas.

**Versão:** 1.0  
**Data:** 2026-09-21T20:25:00Z  
**Autor:** reversa-drafter  
**Status:** rascunho  

---

## 1. Problema

🟡 O processo manual de coletar dados de mercado (preços de ativos, câmbio, tarifas logísticas), aplicar análises estatísticas quantitativas (médias móveis, desvio padrão, otimização) e redigir relatórios executivos para tomada de decisão é lento, repetitivo e propenso a erros de cálculo e digitação.

### Quem sente
🟡 Analistas financeiros, gestores de operações logísticas e tomadores de decisão que precisam de dados de mercado atualizados e confiáveis em tempo hábil para alocação de recursos ou investimentos.

---

## 2. Personas-alvo

🟡 Referência completa em [`personas.md`](./personas.md). Resumo:

- **Analista Financeiro / Gestor de Operações Logísticas**: 🟡 Profissional que necessita de visibilidade de mercado e relatórios quantitativos determinísticos sem risco de alucinação de dados.

---

## 3. Métricas de sucesso

🟡 Medição da eficácia e confiabilidade da pipeline de agentes:

| Métrica | Unidade | Alvo | Prazo |
|---|---|---|---|
| 🟡 Tempo de geração de relatório | Segundos | < 60s | Na entrega do MVP |
| 🟡 Taxa de alucinação numérica | Porcentagem | 0% (100% determinístico via Python) | Na entrega do MVP |
| 🟡 Cobertura de orquestração | Frameworks | 2 (CrewAI + LangGraph) | Na entrega final |

---

## 4. Escopo (in)

🟡 Funcionalidades e componentes inclusos no escopo do projeto:

- 🟡 **Agente 1 - Coletor de Dados de Mercado:** Varredura e extração de dados (preços, cotações, tarifas) via web scraping (`BeautifulSoup` / `requests`) ou APIs públicas (`Yahoo Finance`, `Alpha Vantage`, `ExchangeRate API`).
- 🟡 **Agente 2 - Analista Quantitativo:** Aplicação de modelos estatísticos/otimização (média móvel, desvio padrão, volatilidade, rota) através de chamadas determinísticas a bibliotecas Python (`Pandas`, `Numpy`, `Scipy`) expostas como Tools (Function Calling).
- 🟡 **Agente 3 - Redator de Relatório:** Consolidação dos dados e análises em um relatório estruturado em Markdown/PDF legível para executivos.
- 🟡 **Arquitetura Multiagente Dupla:** Orquestração inicial via CrewAI (encadeamento de Tasks) e reimplementação/comparativo via LangGraph (`StateGraph`).
- 🟡 **Mecanismos Anti-alucinação e Controle de Fluxo:** Validação de saída via Pydantic/JSON Schema, limite de iterações (`max_iter`) e verificação de contratos entre etapas.

---

## 5. Não-objetivos (out)

🟡 Funcionalidades explicitamente fora do escopo inicial:

- 🟡 Interface gráfica de usuário (GUI/Web) complexa (foco em execução CLI/Pipeline Python).
- 🟡 Execução automática de ordens de compra/venda de ativos ou contratação direta de fretes (trading ou execução financeira real).
- 🟡 Armazenamento persistente em banco de dados relacional complexo (foco nos relatórios finais e memória de estado da sessão).

---

## 6. Restrições

🟡 Restrições operacionais, tecnológicas e regulatórias:

| Tipo | Descrição |
|---|---|
| 🟡 Técnica | Linguagem Python 3.11+, uso de Function Calling para tools numéricas determinísticas |
| 🟡 Custo | Uso de modelos compactos/econômicos (OpenAI/Anthropic) para desenvolvimento contido |
| 🟡 Arquitetura | Obrigatoriedade de documentar StateGraph e Task Chaining com controle de `max_iter` |
| 🟡 Compliance | Respeito aos limites de rate-limit e termos de uso de APIs/sites raspados |

---

## 7. Dependências externas

🟡 Serviços e bibliotecas externas necessárias:

- 🟡 APIs de dados de mercado (Yahoo Finance / YFinance, Alpha Vantage, ExchangeRate API).
- 🟡 APIs de LLM (OpenAI API ou Anthropic API).
- 🟡 Packages Python: `crewai`, `langgraph`, `pandas`, `numpy`, `scipy`, `pydantic`, `beautifulsoup4`, `requests`.

---

## 8. Riscos

🟡 Riscos identificados e estratégias de mitigação:

| Risco | Impacto | Probabilidade | Mitigação proposta |
|---|---|---|---|
| 🟡 Alucinação de cálculos pelo LLM | Alto | Média | Isolamento completo dos cálculos em Tools Python determinísticas (Pandas/Numpy), nunca permitindo que o LLM calcule direto |
| 🟡 Bloqueio/Rate limit de APIs de mercado | Médio | Média | Fallback para dados de teste (mock JSON) e cache local de respostas |
| 🟡 Loop infinito de decisão inter-agente | Alto | Baixa | Definição rígida de `max_iter` e validação Pydantic de estado de parada |

---

## 9. Critérios de aceite (alto nível)

🟡 Validação funcional do sistema:

- 🟡 **Dado** um parâmetro de ativo/moeda e período, **Quando** a pipeline for disparada, **Então** o Agente Coletor deve buscar dados válidos e repassá-los ao Agente Analista.
- 🟡 **Dado** que o Agente Analista recebe os dados brutos, **Quando** a Tool Python for invocada, **Então** os cálculos de média e desvio padrão devem ser retornados com precisão determinística.
- 🟡 **Dado** que o Agente Relator recebe as métricas validadas, **Quando** o relatório final for montado, **Então** a saída deve ser um Markdown legível e com 100% dos dados coerentes com a análise.

---

## Pendências de cobertura

🟡 Nenhuma pendência crítica. Todas as seções foram preenchidas a partir das especificações do projeto.

---

Gerado por reversa-drafter em 2026-09-21T20:25:00Z  
Fontes: ideation.md, personas.md
