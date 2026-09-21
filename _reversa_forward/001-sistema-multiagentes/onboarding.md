# Manual de Onboarding e Testes: Feature 001-sistema-multiagentes

> Feature: `001-sistema-multiagentes`
> Data: `2026-09-21`

## 1. Pré-requisitos

- Python 3.11 ou superior instalado
- Virtualenv configurado (`python -m venv .venv`)
- Dependências instaladas (`pip install -r requirements.txt`)

## 2. Passo a Passo de Execução CLI

### Passagem 1: Execução com Mock (Offline)
Para testar a pipeline completa usando a engine LangGraph com dados de teste:
```bash
python -m sisanalisefinanceira.cli --ticker PETR4 --engine langgraph --mock
```

### Passagem 2: Execução em modo CrewAI
Para testar a pipeline usando o orquestrador CrewAI:
```bash
python -m sisanalisefinanceira.cli --ticker PETR4 --engine crewai --mock
```

## 3. Validação dos Resultados

1. Verifique se o relatório Markdown foi gerado no diretório de saída:
   `output/reports/PETR4_report.md`
2. Abra o arquivo gerado e confirme que:
   - Contém seção de Resumo Executivo.
   - Contém Tabela de Métricas com Média Móvel e Desvio Padrão.
   - Não há valores nulos ou alucinações numéricas.
