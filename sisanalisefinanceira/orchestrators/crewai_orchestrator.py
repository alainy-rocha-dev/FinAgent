"""
Orquestrador de encadeamento de tarefas (Task Chaining) no estilo CrewAI.
"""

import logging
from sisanalisefinanceira.config import settings
from sisanalisefinanceira.models import AgentState
from sisanalisefinanceira.agents.data_collector import DataCollectorAgent
from sisanalisefinanceira.agents.quant_analyst import QuantAnalystAgent
from sisanalisefinanceira.agents.report_writer import ReportWriterAgent

logger = logging.getLogger(__name__)


class CrewAIOrchestrator:
    """Orquestrador baseado no paradigma de encadeamento de tarefas e contextos (CrewAI Adapter)."""

    def __init__(self, use_mock: bool = settings.use_mock_fallback):
        self.collector = DataCollectorAgent(use_mock=use_mock)
        self.analyst = QuantAnalystAgent()
        self.writer = ReportWriterAgent()

    def run(self, symbol: str) -> AgentState:
        """Executa a sequência de Tasks encadeadas entre os 3 agentes."""
        logger.info(f"[CrewAI] Iniciando execução em cadeia para símbolo: {symbol}")
        state = AgentState(input_params={"symbol": symbol}, iteration_count=1)

        # Task 1: Coleta de Dados
        raw_data = self.collector.fetch_data(symbol)
        state.raw_data = raw_data
        if raw_data.metadata.get("error_code") == "INVALID_SYMBOL":
            state.error_state = "INVALID_SYMBOL"
            return state

        # Task 2: Análise Quantitativa
        quant_analysis = self.analyst.analyze(raw_data)
        state.quant_analysis = quant_analysis
        if quant_analysis.error_code:
            state.error_state = quant_analysis.error_code
            report, _ = self.writer.generate_report(raw_data, quant_analysis)
            state.final_report = report
            return state

        # Task 3: Redação do Relatório
        final_report, is_valid = self.writer.generate_report(raw_data, quant_analysis)
        state.final_report = final_report
        
        if not is_valid:
            logger.warning("[CrewAI] Relatório final apresentou pequenos desalinhamentos de validação.")

        logger.info("[CrewAI] Execução finalizada com sucesso.")
        return state
