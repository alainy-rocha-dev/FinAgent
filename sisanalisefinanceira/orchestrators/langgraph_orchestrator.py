"""
Orquestrador baseado no conceito de StateGraph (LangGraph) para o pipeline multiagente.
"""

import logging
from typing import Dict, Any

from sisanalisefinanceira.config import settings
from sisanalisefinanceira.models import AgentState
from sisanalisefinanceira.agents.data_collector import DataCollectorAgent
from sisanalisefinanceira.agents.quant_analyst import QuantAnalystAgent
from sisanalisefinanceira.agents.report_writer import ReportWriterAgent

logger = logging.getLogger(__name__)


class LangGraphOrchestrator:
    """Orquestrador StateGraph com suporte a controle estrito de iterações e contratos Pydantic."""

    def __init__(self, max_iter: int = settings.max_iter, use_mock: bool = settings.use_mock_fallback):
        self.max_iter = max_iter
        self.collector = DataCollectorAgent(use_mock=use_mock)
        self.analyst = QuantAnalystAgent()
        self.writer = ReportWriterAgent()

    def run(self, symbol: str) -> AgentState:
        """Executa a máquina de estados do pipeline multiagente."""
        state = AgentState(input_params={"symbol": symbol}, iteration_count=0)

        while state.iteration_count < self.max_iter:
            state.iteration_count += 1
            logger.info(f"[LangGraph] Iteração {state.iteration_count}/{self.max_iter} iniciada para símbolo: {symbol}")

            # Etapa 1: Coleta de dados
            if state.raw_data is None:
                state.raw_data = self.collector.fetch_data(symbol)
                if state.raw_data.metadata.get("error_code") == "INVALID_SYMBOL":
                    state.error_state = "INVALID_SYMBOL"
                    logger.error(f"[LangGraph] Símbolo inválido: {symbol}")
                    break

            # Etapa 2: Análise Quantitativa
            if state.quant_analysis is None and state.raw_data:
                state.quant_analysis = self.analyst.analyze(state.raw_data)
                if state.quant_analysis.error_code:
                    state.error_state = state.quant_analysis.error_code
                    logger.warning(f"[LangGraph] Alerta na análise quantitativa: {state.quant_analysis.error_code}")
                    # Gerar relatório de erro controlado
                    report, _ = self.writer.generate_report(state.raw_data, state.quant_analysis)
                    state.final_report = report
                    break

            # Etapa 3: Geração de Relatório
            if state.final_report is None and state.raw_data and state.quant_analysis:
                report, is_valid = self.writer.generate_report(state.raw_data, state.quant_analysis)
                if is_valid:
                    state.final_report = report
                    logger.info("[LangGraph] Relatório final gerado com sucesso e validado anti-alucinação.")
                    break
                else:
                    logger.warning("[LangGraph] Validação anti-alucinação falhou. Re-tentando iteração...")
                    continue

        # Verificação de limite máximo de iterações atingido sem sucesso
        if state.final_report is None and state.error_state is None:
            state.error_state = "MAX_ITER_REACHED"
            logger.error(f"[LangGraph] Limite máximo de {self.max_iter} iterações atingido. Estado abortado.")

        return state
