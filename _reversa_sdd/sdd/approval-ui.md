# Spec: approval-ui

> Selo 🟡 PLANEJADO. Componente gerado pelo reversa-spec-sdd a partir do PRD FinAgent + AgentPulse.

---

## 1. Resumo

🟡 Página HTML mínima de aprovação servida pelo FastAPI (template Jinja2). Exibe `data_quality` em destaque, `X-Snapshot-Hash` no formulário, `autoescape` ligado, aviso para não colocar dados pessoais no motivo. Requer API key com papel `approver`.

---

## 2. Requisitos Funcionais

| ID | Requisito | Prioridade | Critério de Aceite |
|----|-----------|------------|---------------------|
| 🟡 RF-01 | `GET /approval/{task_id}` serve template Jinja2 | Must | Requer `Authorization: Bearer <key>` com role `approver`; 403 se papel incorreto ou tarefa não em `AWAITING_APPROVAL` |
| 🟡 RF-02 | Exibe `data_quality` em destaque com badge colorido: `LIVE`=verde, `STALE`=amarelo, `SIMULATED`=vermelho | Must | Badge visível no topo da página; tooltip com explicação |
| 🟡 RF-03 | Exibe resumo: símbolo, `QuantAnalysisMetrics` formatadas, relatório draft (HTML seguro), `audit_result`, `snapshot_hash` | Must | `snapshot_hash` exibido em código monoespaçado e incluído no formulário |
| 🟡 RF-04 | Formulário: dois botões (Aprovar, Rejeitar) | Must | Aprovar → POST `/api/tasks/{task_id}/approve` com `X-Snapshot-Hash` (obrigatório) + `justification` (opcional). Rejeitar → POST `/api/tasks/{task_id}/reject` com `X-Snapshot-Hash`, `reject_reason` (enum obrigatório), `justification` (obrigatório se `other`) |
| 🟡 RF-05 | Segurança: `autoescape` Jinja2 **ligado** (padrão); CSP header restritivo | Must | XSS prevenido; CSP: `default-src 'self'; script-src 'self'; style-src 'self'` |
| 🟡 RF-06 | Aviso visível: "Não insira dados pessoais no motivo da rejeição" | Must | Próximo ao campo `justification` |
| 🟡 RF-07 | Confirmação em duas etapas (modal) antes de enviar | Should | Clica botão → modal confirma → envia |
| 🟡 RF-08 | Estados de resposta: 200 → página sucesso com task_id e status; 409 (hash mismatch) → erro com expected/received; 410 (EXPIRED) → aviso expirou; 403/404 → genérico | Must | UX clara para cada caso |

---

## 3. Comportamentos

🟡 **Template Jinja2 (`templates/approval.html`):**
```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Aprovação - {{ task.symbol }}</title>
    <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; style-src 'self'">
    <style>/* CSS mínimo inline */</style>
</head>
<body>
    <header>
        <h1>Aprovação de Análise: {{ task.symbol }}</h1>
        <span class="badge badge-{{ task.data_quality.lower() }}">{{ task.data_quality }}</span>
        {% if task.data_quality == "STALE" %}<span class="warning">Dados desatualizados (> {{ stale_max_age_days }} dias)</span>{% endif %}
        {% if task.data_quality == "SIMULATED" %}<span class="danger">DADOS SIMULADOS — acknowledge_simulated={{ task.acknowledge_simulated }}</span>{% endif %}
    </header>
    
    <section>
        <h2>Métricas Quantitativas</h2>
        <pre>{{ task.quant_metrics | tojson(indent=2) }}</pre>
    </section>
    
    <section>
        <h2>Relatório Preliminar</h2>
        <div>{{ task.report_draft | safe }}</div>  {# autoescape ligado; report_draft já é HTML seguro #}
    </section>
    
    <section>
        <h2>Auditoria Numérica</h2>
        <pre>{{ task.audit_result | tojson(indent=2) }}</pre>
    </section>
    
    <section>
        <h2>Snapshot Hash</h2>
        <code id="snapshot-hash">{{ task.snapshot_hash }}</code>
        <input type="hidden" name="snapshot_hash" value="{{ task.snapshot_hash }}">
    </section>
    
    <form id="approval-form" method="post" action="/api/tasks/{{ task.id }}/approve">
        <input type="hidden" name="snapshot_hash" value="{{ task.snapshot_hash }}">
        <div>
            <label>Justificativa (opcional):</label>
            <textarea name="justification" placeholder="Motivo da aprovação..."></textarea>
        </div>
        <button type="submit" id="btn-approve" onclick="return confirmApproval()">Aprovar</button>
    </form>
    
    <form id="rejection-form" method="post" action="/api/tasks/{{ task.id }}/reject">
        <input type="hidden" name="snapshot_hash" value="{{ task.snapshot_hash }}">
        <div>
            <label>Motivo da rejeição *:</label>
            <select name="reject_reason" required>
                <option value="">Selecione...</option>
                <option value="data_quality">Qualidade dos dados</option>
                <option value="numbers_mismatch">Números não conferem</option>
                <option value="policy">Política interna</option>
                <option value="other">Outro</option>
            </select>
        </div>
        <div id="justification-group" style="display:none;">
            <label>Justificativa detalhada *:</label>
            <textarea name="justification" required placeholder="Explique..."></textarea>
            <p class="warning">⚠️ Não insira dados pessoais no motivo da rejeição</p>
        </div>
        <button type="submit" id="btn-reject" onclick="return confirmRejection()">Rejeitar</button>
    </form>
    
    <script>
    // JS mínimo: toggle justification para 'other', confirmação modal
    document.querySelector('[name="reject_reason"]').addEventListener('change', function(e) {
        document.getElementById('justification-group').style.display = e.target.value === 'other' ? 'block' : 'none';
    });
    function confirmApproval() { return confirm('Confirmar aprovação desta análise?'); }
    function confirmRejection() { return confirm('Confirmar rejeição? Esta ação não pode ser desfeita.'); }
    </script>
</body>
</html>
```

🟡 **Endpoint FastAPI:**
```python
@app.get("/approval/{task_id}", response_class=HTMLResponse)
async def approval_page(task_id: str, request: Request, api_key: APIKey = Depends(get_approver_key)):
    task = await get_task_for_approval(task_id)
    if not task or task.status != "AWAITING_APPROVAL":
        raise HTTPException(403, "Task not available for approval")
    return templates.TemplateResponse("approval.html", {"request": request, "task": task})
```

🟡 **Autoescape Jinja2:**
```python
from jinja2 import Environment, select_autoescape
templates = Jinja2Templates(directory="templates", autoescape=select_autoescape(["html", "xml"]))
# select_autoescape ligado por padrão para .html/.xml
```

---

## 4. Edge Cases

| Cenário | Comportamento |
|---------|---------------|
| 🟡 Aprovador acessa tarefa já `APPROVED` | 403 "Task not available for approval" |
| 🟡 Hash mismatch no submit | 409 → página re-renderiza com erro: "Hash do snapshot não confere. Esperado: H123, Recebido: H456" |
| 🟡 Tarefa `EXPIRED` | 410 → "Esta tarefa expirou (TTL de aprovação: 7 dias)" |
| 🟡 `reject_reason = other` sem `justification` | 422 validation error (campo obrigatório) |
| 🟡 XSS attempt no `justification` | `autoescape` escapa HTML; CSP bloqueia scripts inline |
| 🟡 Dados pessoais no `justification` | Aviso visível; não validado tecnicamente (responsabilidade do aprovador) |

---

## 5. Não-Gols

🟡 Não implementar front-end completo para Analista (fora de escopo)
🟡 Não implementar autenticação OAuth/SSO (apenas API key)
🟡 Não implementar dashboard de aprovações pendentes (lista)
🟡 Não implementar notificações (email, Slack) — aprovador acessa via link direto
🟡 Não definir CSS framework (CSS mínimo inline ou arquivo estático simples)

---

## 6. Interface de Integração

🟡 **Entrada:** `task_id` na URL, API key `approver` no header
🟡 **Saída:** HTML page; submete para `POST /api/tasks/{id}/approve|reject` (endpoints da `task-api`)
🟡 **Dependências:** `task-api` (endpoints approve/reject), `approval-flow` (hash, TTL, reject_reason), `audit-trail` (evento `APPROVAL_DECISION`), `observability` (trace, logs)

---

## 7. Critérios de Aceite (Gherkin)

```gherkin
Cenário: Página exibe data_quality em destaque
  Dado tarefa em AWAITING_APPROVAL com data_quality = SIMULATED
  Quando aprovador acessa /approval/{task_id}
  Então badge vermelho "SIMULATED" visível no topo
  E aviso "DADOS SIMULADOS — acknowledge_simulated=true" exibido
  E snapshot_hash exibido e incluído no formulário hidden

Cenário: Aprovação com hash correto
  Dado aprovador na página com snapshot_hash = "H123"
  Quando clica "Aprovar", confirma no modal, envia
  Então POST /api/tasks/{id}/approve com X-Snapshot-Hash: H123
  E resposta 200 → redireciona para página sucesso com status APPROVED

Cenário: Rejeição com categoria obrigatória
  Dado aprovador na página
  Quando seleciona "data_quality", preenche justificativa, clica "Rejeitar", confirma
  Então POST /api/tasks/{id}/reject com reject_reason=data_quality
  E resposta 200 → página sucesso com status REJECTED

Cenário: Autoescape previne XSS
  Dado relatório draft contém "<script>alert(1)</script>"
  Quando página renderiza
  Então HTML escapado: "<script>alert(1)</script>"
  E CSP bloqueia execução mesmo se escapado falhar
```

---

## 8. Perguntas Abertas

⚠️ **ABERTO:** CSS: inline no template vs arquivo estático `/static/approval.css`
⚠️ **ABERTO:** `stale_max_age_days` por classe de ativo exibido no badge STALE — valor vem de config ou fixo no template?
⚠️ **ABERTO:** Link direto para página de aprovação — como entregue ao aprovador? (fora de escopo: link manual)

---

## 9. Valores Iniciais (a medir)

| Parâmetro | Valor Inicial | Fonte |
|-----------|---------------|-------|
| 🟡 `approval_ttl_hours` | 168 (7 dias) | Arbitrário |
| 🟡 Limite motivo rejeição (min/max chars) | 10 / 1000 | Arbitrário |

---

## 10. Relatório de Avaliação (Scoring)

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SCORE TOTAL: 87/100
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Breakdown:
  Completude:    90/100 (peso 30%)
  Testabilidade: 85/100 (peso 25%)
  Clareza:       85/100 (peso 20%)
  Escopo:        90/100 (peso 15%)
  Edge Cases:    85/100 (peso 10%)

Gaps críticos:
  - CSS strategy (inline vs estático)
  - Como o aprovador recebe o link (fora de escopo, mas afeta UX)

Sugestões:
  1. Usar CSS inline no template para zero dependências estáticas
  2. Testar autoescape com payloads XSS reais
  3. Validar CSP header em navegador real
```