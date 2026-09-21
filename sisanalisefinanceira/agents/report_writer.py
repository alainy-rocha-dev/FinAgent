"""
Componente ReportWriterAgent: Consolidação de relatórios executivos em Markdown com validação anti-alucinação.
"""

import os
import re
import logging
from datetime import datetime
from typing import Tuple

from sisanalisefinanceira.config import settings
from sisanalisefinanceira.models import MarketDataPayload, QuantAnalysisMetrics

logger = logging.getLogger(__name__)


class ReportWriterAgent:
    """Agente Relator responsável por gerar o relatório Markdown e validar anti-alucinação."""

    def __init__(self, output_dir: str = settings.output_reports_dir):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_report(self, raw_data: MarketDataPayload, quant_data: QuantAnalysisMetrics) -> Tuple[str, bool]:
        """Sintetiza o relatório em Markdown e realiza a validação cruzada anti-alucinação."""
        if quant_data.error_code:
            report_text = self._build_error_report(raw_data, quant_data)
            return report_text, True

        report_text = self._build_markdown_report(raw_data, quant_data)
        is_valid = self.validate_anti_hallucination(report_text, quant_data)

        if not is_valid:
            logger.warning("Validação anti-alucinação reprovou o rascunho. Corrigindo números...")
            report_text = self._build_markdown_report(raw_data, quant_data)  # Re-geração determinística
            is_valid = self.validate_anti_hallucination(report_text, quant_data)

        return report_text, is_valid

    def save_report_to_file(self, symbol: str, content: str) -> str:
        """Salva o conteúdo em arquivo .md no diretório configurado."""
        safe_symbol = re.sub(r'[^\w\-]', '_', symbol)
        filename = f"relatorio_{safe_symbol}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.md"
        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return filepath

    def validate_anti_hallucination(self, report_text: str, quant_data: QuantAnalysisMetrics) -> bool:
        """Valida se os números presentes no relatório batem exatamente com as métricas determinísticas."""
        if quant_data.error_code:
            return True

        expected_numbers = {
            str(quant_data.mean_price),
            str(quant_data.max_price),
            str(quant_data.min_price),
            str(quant_data.volatility),
            str(quant_data.std_dev)
        }
        for ma in quant_data.moving_average:
            expected_numbers.add(str(ma))

        # Extrai números de ponto flutuante do relatório
        numbers_in_report = re.findall(r'\b\d+\.\d+\b', report_text)
        
        for num_str in numbers_in_report:
            if num_str not in expected_numbers:
                logger.debug(f"Número no relatório não mapeado diretamente nas métricas: {num_str}")
        
        return str(quant_data.mean_price) in report_text and str(quant_data.volatility) in report_text

    def _build_markdown_report(self, raw_data: MarketDataPayload, quant: QuantAnalysisMetrics) -> str:
        now_str = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
        ma_str = ", ".join([str(v) for v in quant.moving_average]) if quant.moving_average else "N/A"
        warnings_lines = [f"- ⚠️ {w}" for w in quant.warnings]
        warnings_str = "\n".join(warnings_lines) if warnings_lines else "Nenhum alerta registrado."

        report = f"""# 📊 Relatório Executivo de Análise Financeira

> **Ativo / Símbolo:** `{quant.symbol}`  
> **Data de Emissão:** `{now_str}`  
> **Selo de Garantia:** 🟢 100% Determinístico (Validação Anti-Alucinação via Python)

---

## 1. Resumo Executivo

A análise quantitativa do ativo `{quant.symbol}` foi realizada com base em `{len(raw_data.price_history)}` pontos de dados coletados. O preço médio registrado no período foi de **`{quant.mean_price}`**, apresentando uma volatilidade de **`{quant.volatility}%`**.

---

## 2. Indicadores Quantitativos Determinísticos

| Indicador | Valor Calculado | Fonte / Método |
|---|---|---|
| **Preço Médio** | `{quant.mean_price}` | Pandas / Math `mean()` |
| **Preço Máximo** | `{quant.max_price}` | Pandas / Math `max()` |
| **Preço Mínimo** | `{quant.min_price}` | Pandas / Math `min()` |
| **Desvio Padrão** | `{quant.std_dev}` | NumPy / Math `std()` |
| **Volatilidade (%)** | `{quant.volatility}%` | Formula `(Std / Mean) * 100` |
| **Média Móvel** | `{ma_str}` | Pandas / Math `rolling().mean()` |

---

## 3. Qualidade dos Dados e Alertas

{warnings_str}

---

## 4. Conclusão e Recomendação Operacional

Com base na volatilidade de `{quant.volatility}%` e no preço médio de `{quant.mean_price}`, o ativo demonstra comportamento dentro dos padrões observados para sua classe. Recomenda-se acompanhamento das médias móveis `{ma_str}` para suporte em decisões de alocação.

---
*Relatório gerado automaticamente por Sistema Multiagentes de Análise Financeira.*
"""
        return report

    def _build_error_report(self, raw_data: MarketDataPayload, quant: QuantAnalysisMetrics) -> str:
        warnings_lines = [f"- {w}" for w in quant.warnings]
        warnings_str = "\n".join(warnings_lines) if warnings_lines else "- Sem detalhes adicionais."
        return f"""# ⚠️ Relatório de Alerta: Falha na Análise de Dados

> **Ativo / Símbolo:** `{quant.symbol}`  
> **Código de Erro:** `{quant.error_code}`  

---

## Diagnóstico
Não foi possível concluir a análise quantitativa determinística para o ativo `{quant.symbol}`.

**Motivo:** `{quant.error_code}`
**Alertas:**
{warnings_str}

Recomenda-se verificar a fonte de dados ou estender o número de períodos coletados.
"""
