# Dependências do Projeto — sisanalisefinanceira

## 📦 Gerenciador de Pacotes
- **Gerenciador:** `pip`
- **Ambiente:** Python 3.10+

---

## 📚 Bibliotecas e Frameworks Principais

| Biblioteca | Versão Estimada | Finalidade / Uso no Projeto | Arquivo Fonte |
|------------|-----------------|-----------------------------|---------------|
| `pydantic` | `>=2.0.0` | Schemas de dados, validações e configurações (`BaseModel`) | `models.py`, `config.py` |
| `pandas` | `>=2.0.0` | Manipulação de DataFrames e séries temporais de preços | `agents/quant_analyst.py` |
| `numpy` | `>=1.24.0` | Cálculos numéricos, retorno percentual e volatilidade | `agents/quant_analyst.py` |
| `scipy` | `>=1.10.0` | Análise estatística avançada | `agents/quant_analyst.py` |
| `requests` | `>=2.28.0` | Ingestão HTTP de cotações em APIs de mercado | `agents/data_collector.py` |
| `beautifulsoup4` | `>=4.12.0` | Web scraping de páginas de finanças | `agents/data_collector.py` |
| `unittest` | Stdlib | Execução de suíte de testes automatizada | `tests/` |

---

## ⚙️ Variáveis de Ambiente Suportadas

- `OPENAI_API_KEY`: Chave de API da OpenAI (opcional se usando mock/local).
- `ANTHROPIC_API_KEY`: Chave de API da Anthropic (opcional se usando mock/local).
