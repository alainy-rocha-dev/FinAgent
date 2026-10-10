# Interface: Approval UI (HTML servido por FastAPI)

> Feature: `002-finagent-agentpulse`
> Endpoint: `GET /approval/{task_id}`
> Template: Jinja2 (`templates/approval.html`)
> Autenticação: API Key `approver` via header `Authorization: Bearer <key>`

## 1. GET /approval/{task_id}

### Request

```http
GET /approval/{task_id} HTTP/1.1
Host: localhost:8000
Authorization: Bearer <approver-api-key>
Accept: text/html
```

### Response

| Status | Condição | Content-Type |
|--------|----------|--------------|
| `200` | Sucesso | `text/html` |
| `403` | Role incorreta ou tarefa não em `AWAITING_APPROVAL` | `text/html` (página de erro) |
| `404` | Tarefa não existe | `text/html` |
| `410` | Tarefa `EXPIRED` | `text/html` (página de expiração) |

## 2. Template Jinja2 (`templates/approval.html`)

### Características de segurança

- **Autoescape ligado**: `select_autoescape(["html", "xml"])` — padrão para `.html`
- **CSP Header**: `default-src 'self'; script-src 'self'; style-src 'self'`
- **Sem dependências externas**: CSS/JS inline no template
- **Aviso PII**: Visível próximo ao campo `justification` de rejeição

### Estrutura da página

```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Aprovação - {{ task.symbol }}</title>
    <meta http-equiv="Content-Security-Policy" content="default-src 'self'; script-src 'self'; style-src 'self'">
    <style>
        /* CSS mínimo inline */
        .badge { padding: 4px 8px; border-radius: 4px; font-weight: bold; }
        .badge-live { background: #d4edda; color: #155724; }
        .badge-stale { background: #fff3cd; color: #856404; }
        .badge-simulated { background: #f8d7da; color: #721c24; }
        .warning { color: #856404; background: #fff3cd; padding: 8px; border-radius: 4px; margin: 8px 0; }
        .danger { color: #721c24; background: #f8d7da; padding: 8px; border-radius: 4px; margin: 8px 0; }
        .modal { display: none; position: fixed; top: 50%; left: 50%; transform: translate(-50%, -50%); background: white; padding: 20px; border: 1px solid #ccc; box-shadow: 0 2px 10px rgba(0,0,0,0.2); z-index: 1000; }
        .overlay { display: none; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 999; }
    </style>
</head>
<body>
    <header>
        <h1>Aprovação de Análise: {{ task.symbol }}</h1>
        <span class="badge badge-{{ task.data_quality.lower() }}">{{ task.data_quality }}</span>
        {% if task.data_quality == "STALE" %}
        <span class="warning">Dados desatualizados (> {{ stale_max_age_days }} dias)</span>
        {% endif %}
        {% if task.data_quality == "SIMULATED" %}
        <span class="danger">DADOS SIMULADOS — acknowledge_simulated={{ task.acknowledge_simulated }}</span>
        {% endif %}
    </header>

    <section>
        <h2>Métricas Quantitativas</h2>
        <pre>{{ task.quant_metrics | tojson(indent=2) }}</pre>
    </section>

    <section>
        <h2>Relatório Preliminar</h2>
        <div>{{ task.report_draft | safe }}</div>
    </section>

    <section>
        <h2>Auditoria Numérica</h2>
        <pre>{{ task.audit_result | tojson(indent=2) }}</pre>
    </section>

    <section>
        <h2>Snapshot Hash</h2>
        <code id="snapshot-hash">{{ task.snapshot_hash }}</code>
    </section>

    <form id="approval-form" method="post" action="/api/tasks/{{ task.id }}/approve">
        <input type="hidden" name="snapshot_hash" value="{{ task.snapshot_hash }}">
        <div>
            <label>Justificativa (opcional):</label>
            <textarea name="justification" placeholder="Motivo da aprovação..."></textarea>
        </div>
        <button type="button" onclick="openModal('approve')">Aprovar</button>
    </form>

    <form id="rejection-form" method="post" action="/api/tasks/{{ task.id }}/reject">
        <input type="hidden" name="snapshot_hash" value="{{ task.snapshot_hash }}">
        <div>
            <label>Motivo da rejeição *:</label>
            <select name="reject_reason" required onchange="toggleJustification(this)">
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
        <button type="button" onclick="openModal('reject')">Rejeitar</button>
    </form>

    <!-- Modal de confirmação -->
    <div class="overlay" id="overlay" onclick="closeModal()"></div>
    <div class="modal" id="modal">
        <h3 id="modal-title"></h3>
        <p id="modal-message"></p>
        <button onclick="confirmAction()">Confirmar</button>
        <button onclick="closeModal()">Cancelar</button>
    </div>

    <script>
        let pendingAction = null;
        let pendingForm = null;

        function toggleJustification(select) {
            document.getElementById('justification-group').style.display = 
                select.value === 'other' ? 'block' : 'none';
        }

        function openModal(action) {
            pendingAction = action;
            pendingForm = document.getElementById(action === 'approve' ? 'approval-form' : 'rejection-form');
            const isApprove = action === 'approve';
            document.getElementById('modal-title').textContent = isApprove ? 'Confirmar aprovação' : 'Confirmar rejeição';
            document.getElementById('modal-message').textContent = isApprove 
                ? 'Tem certeza que deseja aprovar esta análise?' 
                : 'Confirmar rejeição? Esta ação não pode ser desfeita.';
            document.getElementById('overlay').style.display = 'block';
            document.getElementById('modal').style.display = 'block';
        }

        function closeModal() {
            document.getElementById('overlay').style.display = 'none';
            document.getElementById('modal').style.display = 'none';
            pendingAction = null;
            pendingForm = null;
        }

        function confirmAction() {
            if (pendingForm) {
                pendingForm.submit();
            }
            closeModal();
        }
    </script>
</body>
</html>
```

## 3. Contexto do template (variáveis disponíveis)

| Variável | Tipo | Descrição |
|----------|------|-----------|
| `task.id` | UUID | `task_id` |
| `task.symbol` | string | Ativo (ex: `PETR4`) |
| `task.data_quality` | `LIVE`\|`STALE`\|`SIMULATED` | Qualidade dos dados |
| `task.stale_warning` | boolean | `true` se `STALE` |
| `task.acknowledge_simulated` | boolean | Flag da request |
| `task.quant_metrics` | dict | Métricas determinísticas |
| `task.report_draft` | string (HTML) | Relatório preliminar (já sanitizado) |
| `task.audit_result` | dict | Resultado da auditoria numérica |
| `task.snapshot_hash` | string (hex) | Hash do snapshot para `X-Snapshot-Hash` |
| `stale_max_age_days` | int | Valor de configuração (ex: 5) |

## 4. Segurança

| Medida | Implementação |
|--------|---------------|
| **Autoescape** | `Jinja2Templates(autoescape=select_autoescape(["html", "xml"]))` |
| **CSP** | `default-src 'self'; script-src 'self'; style-src 'self'` |
| **X-Snapshot-Hash** | Campo hidden no form + header na submissão (via JS se AJAX, ou form nativo) |
| **Aviso PII** | `<p class="warning">⚠️ Não insira dados pessoais no motivo da rejeição</p>` |
| **Confirmação 2 etapas** | Modal JS antes de submit (aprovar/rejeitar) |
| **Role check** | Endpoint valida `approver` role antes de renderizar |
| **Estado check** | Só renderiza se `status == AWAITING_APPROVAL` |

## 5. Estados de resposta da UI

| Cenário | Comportamento |
|---------|---------------|
| **Sucesso (200)** | Redirect para página de sucesso com `task_id` e status final (`APPROVED`/`REJECTED`/`PUBLISHED`) |
| **Hash mismatch (409)** | Re-renderiza página com erro: `Hash do snapshot não confere. Esperado: H123, Recebido: H456` |
| **Expirado (410)** | Página: "Esta tarefa expirou (TTL de aprovação: 7 dias)" |
| **Forbidden (403/404)** | Página genérica de erro |

## 6. Endpoint FastAPI

```python
@app.get("/approval/{task_id}", response_class=HTMLResponse)
async def approval_page(
    task_id: str,
    request: Request,
    api_key: APIKey = Depends(get_approver_key)  # valida role=approver
):
    task = await get_task_for_approval(task_id)
    if not task or task.status != "AWAITING_APPROVAL":
        raise HTTPException(403, "Task not available for approval")
    
    # Busca stale_max_age_days do config para exibição
    stale_max_age = config.stale_max_age_days.get(task.asset_class, 5)
    
    return templates.TemplateResponse("approval.html", {
        "request": request,
        "task": task,
        "stale_max_age_days": stale_max_age
    })
```

## 7. Acessibilidade e UX

- **Contraste**: Badges com cores acessíveis (WCAG AA)
- **Navegação por teclado**: Modal focável, `Tab`/`Enter`/`Esc` funcionam
- **Responsivo**: CSS flexível, funciona em mobile
- **Feedback visual**: Loading state nos botões durante submit
- **Mensagens claras**: Erros em português, próximos passos óbvios