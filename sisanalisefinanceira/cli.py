
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
from sisanalisefinanceira.agents.narrative_writer import NarrativeWriterAgent
from sisanalisefinanceira.llm.client import client_from_env
from sisanalisefinanceira.utils.logging import setup_logging


def main():
    parser = argparse.ArgumentParser(
        description="Sistema Multiagentes de Análise Financeira (StateGraph-style / Chain-style)"
    )
    parser.add_argument(
        "--symbol", "-s",
        type=str,
        default="AAPL",
        help="Símbolo do ativo ou moeda para análise (ex: AAPL, USD/BRL, PETR4)"
    )
    parser.add_argument(
        "--engine", "-e",
        choices=["stategraph", "chain", "langgraph", "crewai"],
        default="stategraph",
        help=(
            "Padrão de orquestração: stategraph (iterativo, padrão) ou chain (sequencial). "
            "Implementações próprias, sem as bibliotecas LangGraph/CrewAI. "
            "Os nomes antigos 'langgraph' e 'crewai' continuam aceitos."
        )
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
        "--narrative",
        choices=["template", "llm"],
        default="template",
        help=(
            "Texto da análise: template (fixo, padrão) ou llm (escrito por LLM e auditado pelo "
            "guardrail numérico; requer GROQ_API_KEY ou OPENAI_API_KEY)"
        )
    )
    parser.add_argument(
        "--max-iter",
        type=int,
        default=settings.max_iter,
        help="Limite máximo de iterações do orquestrador"
    )

    args = parser.parse_args()
    # Compatibilidade com os nomes antigos das flags
    args.engine = {"langgraph": "stategraph", "crewai": "chain"}.get(args.engine, args.engine)

    setup_logging(level=settings.log_level)
    logger = logging.getLogger("sisanalisefinanceira.cli")

    print("\n" + "=" * 60)
    print(f"SISTEMA MULTIAGENTES DE ANALISE FINANCEIRA")
    print(f"Simbolo: {args.symbol} | Engine: {args.engine.upper()} | Mock: {args.mock}")
    print("=" * 60 + "\n")

    narrative_writer = None
    if args.narrative == "llm":
        llm = client_from_env()
        if llm is None:
            print("Aviso: --narrative llm sem GROQ_API_KEY/OPENAI_API_KEY. Usando o texto padrao.\n")
        else:
            narrative_writer = NarrativeWriterAgent(llm, window=settings.default_moving_average_window)
            print(f"Narrativa por LLM: {llm.label} (auditada pelo guardrail numerico)\n")

    if args.engine == "chain":
        orchestrator = CrewAIOrchestrator(use_mock=args.mock, narrative_writer=narrative_writer)
    else:
        orchestrator = LangGraphOrchestrator(
            max_iter=args.max_iter, use_mock=args.mock, narrative_writer=narrative_writer
        )

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
