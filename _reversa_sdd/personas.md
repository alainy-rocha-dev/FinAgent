# Personas e Jornadas

> Selo 🟡 PLANEJADO em todos os itens.

## Persona 1: analista-dados
- **Perfil:** 🟡 Analista de dados ou tesouraria em uma fintech, que precisa entregar relatórios de mercado que um gestor possa aprovar e auditar, e não apenas relatórios bem escritos.
- **Contexto:** 🟡 Trabalha em uma fintech, em um time pequeno de dados ou tesouraria, e passa o dia entre notebooks, planilhas e consultas a fontes de mercado. Boa parte do trabalho é preparar análises recorrentes (variação, volatilidade, extremos de preço de ativos e câmbio) para que um gestor tome decisões ou envie números a outras áreas. Quando o problema aparece: no fechamento do dia ou antes de uma reunião com prazo. Ela dispara a análise, a fonte de dados cai ou devolve algo estranho, o processo trava no meio e ela não sabe se o relatório parcial foi enviado, se rodou com dado real ou simulado, ou se precisa recomeçar. Depois, quando o gestor pergunta "de onde saiu este número?", ela tem que refazer o cálculo à mão para explicar. O problema é menos a análise em si e mais a falta de confiança no processo em volta dela.
- **Nível técnico:** 🟡 intermediário, em Python para análise de dados (Pandas, notebooks), SQL, consumo de APIs (chamar um endpoint com curl, Postman ou o Swagger, ler JSON e interpretar códigos de status). Entende estatística descritiva (média móvel, volatilidade, desvio padrão) e conhece as fontes de dados de mercado do dia a dia. Não sabe (e não deveria precisar saber): infraestrutura (Docker, filas, workers, Postgres), nem como agentes de IA funcionam por dentro. Não sabe depurar por que um worker caiu, e não quer aprender.
- **Dor principal:** 🟡 Não saber se o relatório foi gerado com dado real ou simulado, ter que refazer análises quando algo cai, não conseguir explicar de onde veio um número, falta de confiança no processo em volta da análise.
- **Objetivo final:** 🟡 Ser vista como a pessoa cujos números podem ser usados sem conferência extra. Ela quer que o gestor aprove seus relatórios com confiança, que uma auditoria ou uma pergunta do tipo "de onde saiu isto?" seja respondida em minutos e não em horas, e não ter que passar o fim do dia refazendo trabalho quando algo falha.

### Jornada principal
1. 🟡 Submeter análise de ativo via POST /tasks com Idempotency-Key
2. 🟡 Acompanhar status da tarefa via GET /tasks/{id}
3. 🟡 Receber notificação de AWAITING_APPROVAL
4. 🟡 Consultar resumo de decisão e veredito da auditoria numérica
5. 🟡 Ver aprovação concedida e status PUBLISHED
6. 🟡 Acessar relatório final com data_quality e proveniência dos números
7. 🟡 Responder a perguntas do gestor com trilha de auditoria completa

---

## Persona 2: aprovador
- **Perfil:** 🟡 Gestor de tesouraria ou de risco em uma fintech, que libera relatórios de mercado produzidos pelo time de analistas e responde pela qualidade do que é publicado.
- **Contexto:** 🟡 Gestor de tesouraria ou de risco em uma fintech. Passa o dia em reuniões, decisões e revisões, com pouco tempo para cada item. Recebe relatórios de mercado de analistas do time, muitas vezes perto de um prazo (fechamento do dia, reunião de comitê), e precisa liberá-los para outras áreas ou usá-los em uma decisão. Sua assinatura ou aprovação o torna responsável pelo que sai. Quando o problema aparece: no momento de aprovar. Ele tem minutos, não horas, e o relatório chega sem indicação clara de que os números foram conferidos, de que os dados são reais e atuais, ou de quem já revisou o quê. Refazer o cálculo é inviável, e não aprovar atrasa o time. Ele acaba decidindo por confiança na pessoa, não por evidência. O receio é aprovar algo errado e ser cobrado depois, sem ter como mostrar o que verificou.
- **Nível técnico:** 🟡 avançado no domínio, básico em tecnologia. Sabe fazer: avaliar risco e qualidade de números financeiros, interpretar volatilidade, extremos e variações, questionar premissas de uma análise, reconhecer quando um valor parece incoerente. Usa planilhas e ferramentas de BI no dia a dia. Não sabe (e não deveria precisar saber): consumir APIs, ler JSON, usar Swagger ou linha de comando; nada sobre filas, workers ou agentes de IA. Implicação para o produto: a aprovação não pode depender de chamadas de API feitas à mão. O MVP inclui uma página web mínima de aprovação (uma tela servida pela própria API, sem framework de front-end) que mostra o resumo de decisão e os botões Aprovar e Rejeitar (com justificativa). Os endpoints continuam existindo para automação e testes.
- **Dor principal:** 🟡 Decidir sem evidência sob pressão de tempo, medo de publicar dado simulado ou desatualizado, ausência de registro de quem aprovou o quê, não ter como conferir os números sem refazer o cálculo.
- **Objetivo final:** 🟡 Proteger a instituição e a si mesmo de decisões baseadas em números errados, sem se tornar gargalo. Ele quer aprovar rápido o que está correto, barrar com segurança o que não está e, meses depois, conseguir mostrar a quem perguntar o que foi verificado, com qual dado e quando.

### Jornada principal
1. 🟡 Receber notificação de tarefa aguardando aprovação
2. 🟡 Acessar página de aprovação via link direto (token na URL ou API key)
3. 🟡 Ver resumo de decisão: veredito da auditoria, data_quality (LIVE/SIMULATED), fonte e horário dos dados, custo
4. 🟡 Conferir relatório completo e detalhes da auditoria numérica se necessário
5. 🟡 Aprovar ou rejeitar com justificativa
6. 🟡 Ver confirmação de decisão registrada na trilha de auditoria imutável
7. 🟡 Consultar histórico de aprovações passadas se questionado

---
Gerado por reversa-researcher em 2026-09-29T20:15:00Z
Fonte: ideation.md