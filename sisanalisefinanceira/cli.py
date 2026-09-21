"""
Interface de Linha de Comando (CLI) para o Sistema Multiagentes de Análise Financeira.
"""

import sys
import argparse
import logging

from sisanalisefinanceira.config import settings
from sisanalisefinanceira.orchestrators.langgraph_orchestrator import LangGraphOrchestrator
from sisanalisefinanceira.orchestrators.crewai_orchestrator import CrewAIOrchestrator
from sisanalisefinanceira.agents.report_writer import ReportWriterAgent
from sisanalisefinanceira.utils.logging import setup_logging


def main():
    parser = argparse.ArgumentParser(
        description="Sistema Multiagentes de Análise Financeira (CrewAI / LangGraph)"
    )
    parser.add_argument(
        "--symbol", "-s",
        type=str,
        default="AAPL",
        help="Símbolo do ativo ou moeda para análise (ex: AAPL, USD/BRL, PETR4)"
    )
    parser.add_argument(
        "--engine", "-e",
        choices=["langgraph", "crewai"],
        default="langgraph",
        help="Engine de orquestração a utilizar (padrão: langgraph)"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        default=True,
        help="Usar dados mock de fallback para evitar bloqueios de API/Rate Limit"
    )
    parser.add_argument(
        "--no-mock",
        dest="mock",
        action="store_false",
        help="Tentar conexão online via scraping/API real"
    )
    parser.add_argument(
        "--save",
        action="store_true",
        default=True,
        help="Salvar o relatório resultante em arquivo .md no disco"
    )
    parser.add_argument(
        "--max-iter",
        type=int,
        default=settings.max_iter,
        help="Limite máximo de iterações do orquestrador"
    )

    args = parser.parse_args()

    setup_logging(level=settings.log_level)
    logger = logging.getLogger("sisanalisefinanceira.cli")

    print("\n" + "=" * 60)
    print(f"SISTEMA MULTIAGENTES DE ANALISE FINANCEIRA")
    print(f"Simbolo: {args.symbol} | Engine: {args.engine.upper()} | Mock: {args.mock}")
    print("=" * 60 + "\n")

    if args.engine == "crewai":
        orchestrator = CrewAIOrchestrator(use_mock=args.mock)
    else:
        orchestrator = LangGraphOrchestrator(max_iter=args.max_iter, use_mock=args.mock)

    state = orchestrator.run(args.symbol)

    if state.error_state and state.error_state != "INSUFFICIENT_DATA_POINTS":
        print(f"\nERRO NA EXECUCAO: {state.error_state}")
        if state.error_state == "MAX_ITER_REACHED":
            print(f"Limite estrito de {args.max_iter} iterações atingido sem convergencia.")
        sys.exit(1)

    if state.final_report:
        print("\n" + "RELATORIO FINAL GERADO:" + "\n")
        try:
            print(state.final_report)
        except UnicodeEncodeError:
            # Fallback seguro para consoles Windows cp1252
            print(state.final_report.encode('ascii', errors='replace').decode('ascii'))
        print("-" * 60)

        if args.save:
            writer = ReportWriterAgent()
            filepath = writer.save_report_to_file(args.symbol, state.final_report)
            print(f"Relatorio salvo com sucesso em: {filepath}\n")
    else:
        print("\nNenhum relatorio gerado.")

if __name__ == "__main__":
    main()
