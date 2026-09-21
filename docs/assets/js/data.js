window.RV_DATA = {
  projectName: "FinAgent",
  seedShort: "d8b28f80",
  modules: {
    "agentes": { "file_count": 4, "loc": 320, "complexity": "média", "purpose": "Agentes especialistas (Coletor, Analista, Relator)" },
    "orquestradores": { "file_count": 3, "loc": 180, "complexity": "média", "purpose": "Motores de orquestração (LangGraph / CrewAI)" },
    "utilitarios": { "file_count": 2, "loc": 40, "complexity": "baixa", "purpose": "Logs e salvaguardas" },
    "nucleo": { "file_count": 3, "loc": 110, "complexity": "baixa", "purpose": "CLI, Configuração e Schemas Pydantic" }
  },
  deps: {
    "nodes": [
      { "id": "agents", "label": "agentes", "group": "dominio" },
      { "id": "orchestrators", "label": "orquestradores", "group": "motor" },
      { "id": "utils", "label": "utilitarios", "group": "suporte" },
      { "id": "core", "label": "nucleo/modelos", "group": "dados" }
    ],
    "links": [
      { "source": "orchestrators", "target": "agents", "value": 3 },
      { "source": "orchestrators", "target": "core", "value": 2 },
      { "source": "agents", "target": "core", "value": 2 },
      { "source": "orchestrators", "target": "utils", "value": 1 }
    ],
    "cycles": []
  },
  metrics: {
    "total_files": 12,
    "total_loc": 650,
    "confidence_general": "95.7%",
    "modules_count": 3
  },
  glossary: [
    { "term": "Símbolo / Ticker", "def": "Identificador único de ativo financeiro ou par de moedas (ex: AAPL, PETR4, USD/BRL)." },
    { "term": "Payload de Dados de Mercado", "def": "Dados brutos de preços históricos e volume coletados de APIs de mercado ou base simulada." },
    { "term": "Métricas Quantitativas", "def": "Cálculos estatísticos determinísticos sem risco de alucinação por IA." },
    { "term": "Validação Anti-Alucinação", "def": "Camada de auditoria que valida a precisão numérica antes de salvar o relatório." },
    { "term": "Salvaguarda de Iterações Máximas", "def": "Interrupção de segurança do motor LangGraph ao atingir o limite estipulado de iterações." }
  ],
  featuresIndex: {
    "agents": "features/agents.html",
    "orchestrators": "features/orchestrators.html",
    "utils": "features/utils.html"
  },
  nav: [
    { "id": "index", "href": "index.html", "label": "🏠 Início" },
    { "id": "arquitetura", "href": "arquitetura.html", "label": "🏙️ Cidade do Código 3D" },
    { "id": "modulos", "href": "modulos.html", "label": "🔗 Módulos 2D" },
    { "id": "metricas", "href": "metricas.html", "label": "📊 Painel de Métricas" },
    { "id": "glossario", "href": "glossario.html", "label": "📖 Glossário de Termos" }
  ],
  config: {
    "visualStyle": "exploratory",
    "readerProfile": "other",
    "depth": "full"
  }
};
