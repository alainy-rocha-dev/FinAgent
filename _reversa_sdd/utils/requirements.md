# Unit: `utils` — Requisitos do Módulo

> Utilitários transversais de configuração de logs e salvaguardas.

## Visão Geral
O módulo `utils` fornece suporte transversal de registro de eventos (logging) e manipuladores de mensagens de salvaguarda de erro para o ecossistema do projeto.

## Responsabilidades
- Configurar formatadores e níveis de log de console via `StreamHandler` (`setup_logging`).
- Emitir mensagens formatadas de salvaguarda quando o evento `MAX_ITER_REACHED` for disparado (`handle_max_iter_reached`).

## Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|-----------|-------------------|
| RF-UT-01 | Configurar logging global | Must | Configurar o logger raiz sem duplicar handlers. |
| RF-UT-02 | Emitir log de salvaguarda de max_iter | Must | Emitir mensagem `SALVAGUARDA ATIVADA` no canal de log. |

## Rastreabilidade de Código

| Arquivo | Função / Classe | Cobertura |
|---------|-----------------|-----------|
| `sisanalisefinanceira/utils/logging.py` | `setup_logging`, `handle_max_iter_reached` | 🟢 |
