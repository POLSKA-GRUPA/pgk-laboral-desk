/* PGK Laboral Desk — app.js */
(function () {
  'use strict';

  // ------------------------------------------------------------------
  // Utilidades
  // ------------------------------------------------------------------
  const $ = id => document.getElementById(id);
  const _str = v => (v == null ? '' : typeof v === 'object' ? JSON.stringify(v) : String(v));
  const esc = s => _str(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt = n => n == null ? '—' : (typeof n === 'object' ? '—' : Number(n).toLocaleString('es-ES', {minimumFractionDigits: 2, maximumFractionDigits: 2}) + '\u00a0€');
  const fmtShort = n => n == null ? '—' : (typeof n === 'object' ? '—' : Number(n).toLocaleString('es-ES', {minimumFractionDigits: 0, maximumFractionDigits: 0}) + '\u00a0€');

  // Toast notification system
  function showToast(message, type = 'error') {
    let container = document.querySelector('.toast-container');
    if (!container) {
      container = document.createElement('div');
      container.className = 'toast-container';
      document.body.appendChild(container);
    }
    const toast = document.createElement('div');
    toast.className = `toast toast--${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 4500);
  }

  function md(text) {
    return String(text ?? '')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      .replace(/\n/g, '<br>');
  }

  // Richer markdown for agent responses (tables, headers, code, lists)
  // Escapes HTML first to prevent XSS from LLM-generated output.
  function mdAgent(text) {
    let s = esc(String(text ?? ''));
    // Code blocks (```...```)
    s = s.replace(/```(?:\w+)?\n([\s\S]*?)```/g, '<pre class="agent-code"><code>$1</code></pre>');
    // Inline code
    s = s.replace(/`([^`]+)`/g, '<code class="agent-inline-code">$1</code>');
    // Headers (### / ## / #)
    s = s.replace(/^### (.+)$/gm, '<h5 class="agent-h">$1</h5>');
    s = s.replace(/^## (.+)$/gm, '<h4 class="agent-h">$1</h4>');
    s = s.replace(/^# (.+)$/gm, '<h3 class="agent-h">$1</h3>');
    // Bold / italic
    s = s.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    s = s.replace(/\*(.+?)\*/g, '<em>$1</em>');
    // Unordered lists
    s = s.replace(/^[-*] (.+)$/gm, '<li>$1</li>');
    s = s.replace(/(<li>.*<\/li>)/gs, '<ul class="agent-list">$1</ul>');
    // Simple table detection (| col | col |)
    s = s.replace(/^(\|.+\|)$/gm, (line) => {
      if (/^\|[-: ]+\|$/.test(line)) return ''; // separator row
      const cells = line.split('|').filter(c => c.trim());
      const isHeader = false; // simplified
      const tag = 'td';
      return '<tr>' + cells.map(c => `<${tag}>${c.trim()}</${tag}>`).join('') + '</tr>';
    });
    s = s.replace(/(<tr>.*<\/tr>(?:\s*<tr>.*<\/tr>)*)/gs, '<table class="agent-table">$1</table>');
    // Newlines
    s = s.replace(/\n/g, '<br>');
    // Clean up extra <br> around block elements
    s = s.replace(/<br>\s*(<(?:pre|h[3-5]|ul|table|li))/g, '$1');
    s = s.replace(/(<\/(?:pre|h[3-5]|ul|table|li)>)\s*<br>/g, '$1');
    return s;
  }

  async function api(path, options = {}) {
    const res = await fetch(path, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    });
    if (res.status === 401) { location.href = '/'; return; }
    return res.json();
  }

  function daysUntil(dateStr) {
    const d = new Date(dateStr);
    const today = new Date(); today.setHours(0,0,0,0);
    return Math.ceil((d - today) / 86400000);
  }

  // ------------------------------------------------------------------
  // Estado global
  // ------------------------------------------------------------------
  const state = {
    user: null,
    categories: [],
    contractTypes: [],
    tiposDespido: [],
    employees: [],
    conveniosList: [],
  };

  // ------------------------------------------------------------------
  // Arranque
  // ------------------------------------------------------------------
  async function init() {
    const user = await api('/api/auth/me');
    if (!user || user.error) { location.href = '/'; return; }
    state.user = user;

    $('empresaName').textContent = user.empresa_nombre;
    $('logoutBtn').addEventListener('click', async () => {
      await api('/api/auth/logout', { method: 'POST' });
      location.href = '/';
    });

    await Promise.all([
      loadCategoriesAndTypes(),
      loadConvenioInfo(),
      loadAlerts(),
      loadHistory(),
      loadEmployees(),
    ]);

    if (user.role === 'admin') {
      $('clientsSection').hidden = false;
      loadClients();
      loadConveniosList();
    }

    setupToolTabs();
    setupModeTabs();
    setupChat();
    setupSimForm();
    setupDespidoForm();
    setupPlantillaForm();
    setupAlertForm();
  }

  // ------------------------------------------------------------------
  // Datos base
  // ------------------------------------------------------------------
  async function loadCategoriesAndTypes() {
    const [cats, types, tiposDespido, regions] = await Promise.all([
      api('/api/categories'),
      api('/api/contract-types'),
      api('/api/tipos-despido'),
      api('/api/regions'),
    ]);

    state.categories = cats || [];
    state.contractTypes = types || [];
    state.tiposDespido = tiposDespido || [];
    state.regions = regions || [];

    // Formulario contratar
    const catSel = $('category');
    if (catSel) {
      catSel.innerHTML = state.categories.map(c =>
        `<option value="${esc(c.value)}">${esc(c.label)}</option>`
      ).join('');
    }
    const typeSel = $('contractType');
    if (typeSel) {
      typeSel.innerHTML = state.contractTypes.map(t =>
        `<option value="${esc(t.value)}">${esc(t.label)}</option>`
      ).join('');
    }

    // Formulario despido — tipo
    const despTipo = $('despidoTipo');
    if (despTipo) {
      despTipo.innerHTML = state.tiposDespido.map(t =>
        `<option value="${esc(t.value)}">${esc(t.label)}</option>`
      ).join('');
    }

    // Formulario empleado — categoría y tipo contrato
    const empCat = $('empCategoria');
    if (empCat) {
      empCat.innerHTML = state.categories.map(c =>
        `<option value="${esc(c.value)}">${esc(c.label)}</option>`
      ).join('');
    }
    const empCon = $('empContrato');
    if (empCon) {
      empCon.innerHTML = state.contractTypes.map(t =>
        `<option value="${esc(t.value)}">${esc(t.label)}</option>`
      ).join('');
    }

    // Region selectors (simulation form + employee form)
    const regionOptions = (state.regions || []).map(r =>
      `<option value="${esc(r.value)}">${esc(r.label)}</option>`
    ).join('');
    const simRegion = $('simRegion');
    if (simRegion) simRegion.innerHTML = regionOptions;
    const empRegion = $('empRegion');
    if (empRegion) empRegion.innerHTML = regionOptions;
  }

  // ------------------------------------------------------------------
  // Tabs: Contratar / Despedir
  // ------------------------------------------------------------------
  function setupToolTabs() {
    document.querySelectorAll('.tool-tab').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.tool-tab').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const tool = btn.dataset.tool;
        $('toolContratar').hidden = tool !== 'contratar';
        $('toolDespedir').hidden = tool !== 'despedir';
        // Reset result placeholder on tool switch
        if (tool === 'despedir') {
          $('resultSection').hidden = true;
          $('despidoResultSection').hidden = false;
          // Only show placeholder if no result yet
          const hasResult = $('heroTotal').textContent !== '—';
          $('resultPlaceholder').hidden = hasResult;
          if (!hasResult) $('despidoResultSection').hidden = true;
        } else {
          $('despidoResultSection').hidden = true;
          const hasResult = $('heroCoste').textContent !== '—';
          $('resultSection').hidden = !hasResult;
          $('resultPlaceholder').hidden = hasResult;
        }
      });
    });
  }

  // ------------------------------------------------------------------
  // Subtabs: Chat / Formulario
  // ------------------------------------------------------------------
  function setupModeTabs() {
    document.querySelectorAll('.mode-tab').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.mode-tab').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const mode = btn.dataset.mode;
        $('chatSection').hidden = mode !== 'chat';
        $('formSection').hidden = mode !== 'form';
      });
    });
  }

  // ------------------------------------------------------------------
  // Chat conversacional (con soporte Agent CodeAct + Clásico)
  // ------------------------------------------------------------------
  let chatMode = 'agent'; // 'agent' | 'classic'
  let agentAvailable = false;

  async function checkAgentStatus() {
    try {
      const res = await api('/api/agent/status');
      agentAvailable = res && res.available;
    } catch (_e) {
      agentAvailable = false;
    }
    const badge = $('agentStatusBadge');
    const agentBtn = $('btnModeAgent');
    if (!agentAvailable) {
      if (badge) { badge.hidden = false; badge.textContent = 'Sin API key'; }
      if (agentBtn) agentBtn.classList.add('disabled');
      chatMode = 'classic';
      document.querySelectorAll('.chat-mode-btn').forEach(b => b.classList.remove('active'));
      const classicBtn = $('btnModeClassic');
      if (classicBtn) classicBtn.classList.add('active');
    } else {
      if (badge) badge.hidden = true;
      if (agentBtn) agentBtn.classList.remove('disabled');
    }
  }

  function setupChat() {
    const form = $('chatForm');
    const input = $('chatInput');
    const resetBtn = $('chatResetBtn');

    // Mode toggle
    document.querySelectorAll('.chat-mode-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const mode = btn.dataset.chatMode;
        if (mode === 'agent' && !agentAvailable) return;
        chatMode = mode;
        document.querySelectorAll('.chat-mode-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
      });
    });

    checkAgentStatus();

    async function sendMessage(msg) {
      if (!msg) return;
      hideSuggestions();
      addBubble(msg, 'user');

      if (chatMode === 'agent' && agentAvailable) {
        await sendAgentMessage(msg);
      } else {
        const typing = showTypingIndicator();
        try {
          const res = await api('/api/chat', { method: 'POST', body: JSON.stringify({ message: msg }) });
          if (res) handleChatResponse(res);
        } finally {
          typing.remove();
        }
      }
    }

    form.addEventListener('submit', async e => {
      e.preventDefault();
      const msg = input.value.trim();
      if (!msg) return;
      input.value = '';
      await sendMessage(msg);
    });

    // Suggestion chips
    document.querySelectorAll('.chat-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        const msg = chip.dataset.msg;
        sendMessage(msg);
      });
    });

    resetBtn.addEventListener('click', async () => {
      await api('/api/chat/reset', { method: 'POST' });
      const greeting = chatMode === 'agent'
        ? 'Hola. Soy tu asistente laboral con IA. Pregunta lo que quieras.'
        : 'Hola. Dime qu\u00e9 puesto quieres cubrir y te calculo el coste real.';
      $('chatLog').innerHTML = `<div class="chat-bubble system">${greeting}</div>`;
      $('resultSection').hidden = true;
      $('resultPlaceholder').hidden = false;
      showSuggestions();
    });
  }

  function hideSuggestions() {
    const el = $('chatSuggestions');
    if (el) el.hidden = true;
  }

  function showSuggestions() {
    const el = $('chatSuggestions');
    if (el) el.hidden = false;
  }

  function showTypingIndicator() {
    const log = $('chatLog');
    const div = document.createElement('div');
    div.className = 'typing-indicator';
    div.innerHTML = '<span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span>';
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
    return div;
  }

  // ------------------------------------------------------------------
  // Agent streaming (SSE)
  // ------------------------------------------------------------------
  async function sendAgentMessage(msg) {
    const log = $('chatLog');

    // Create bubble for streaming response
    const bubble = document.createElement('div');
    bubble.className = 'chat-bubble system agent-bubble';
    bubble.innerHTML = '<span class="agent-thinking">Pensando...</span>';
    log.appendChild(bubble);
    log.scrollTop = log.scrollHeight;

    let fullText = '';
    let hasStarted = false;

    try {
      const res = await fetch('/api/agent/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg }),
      });

      if (res.status === 401) { location.href = '/'; return; }
      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: 'Error del servidor' }));
        bubble.innerHTML = `<span class="agent-error">${esc(err.error || 'Error')}</span>`;
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          let event;
          try { event = JSON.parse(line.slice(6)); } catch (_e) { continue; }

          if (event.type === 'token') {
            if (!hasStarted) {
              bubble.innerHTML = '';
              hasStarted = true;
            }
            fullText += event.content;
            bubble.innerHTML = mdAgent(fullText);
            log.scrollTop = log.scrollHeight;
          } else if (event.type === 'code') {
            // Show code execution indicator
            const codeEl = document.createElement('div');
            codeEl.className = 'agent-code-exec';
            codeEl.innerHTML = '<span class="agent-code-badge">Ejecutando c\u00f3digo...</span>';
            bubble.appendChild(codeEl);
            log.scrollTop = log.scrollHeight;
          } else if (event.type === 'result') {
            // Replace code execution indicator with result
            const codeExec = bubble.querySelector('.agent-code-exec:last-child');
            if (codeExec) {
              codeExec.innerHTML = `<pre class="agent-result"><code>${esc(event.content)}</code></pre>`;
            }
            fullText = ''; // Reset for next response after code exec
            hasStarted = false;
            log.scrollTop = log.scrollHeight;
          } else if (event.type === 'done') {
            // Final
            if (!hasStarted && !fullText) {
              bubble.innerHTML = '<span class="agent-error">Sin respuesta del agente.</span>';
            }
          }
        }
      }
    } catch (err) {
      if (!hasStarted) {
        bubble.innerHTML = `<span class="agent-error">Error de conexi\u00f3n: ${esc(String(err))}</span>`;
      }
    }
  }

  function addBubble(text, type, html = false) {
    const log = $('chatLog');
    const div = document.createElement('div');
    div.className = `chat-bubble ${type}`;
    div.innerHTML = html ? text : md(esc(text));
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
    return div;
  }

  function handleChatResponse(res) {
    if (res.type === 'result') {
      if (res.data.contract_warnings?.length) {
        res.data.contract_warnings.forEach(w => addBubble(w, 'system'));
      }
      addBubble('Aquí tienes el cálculo completo:', 'system');
      renderResult(res.data);
      return;
    }

    if (res.type === 'question') {
      let html = `<span>${md(res.message)}</span>`;
      const opts = res.options || [];
      if (opts.length) {
        html += '<div class="chat-opts">' + opts.map(opt => {
          const val = opt.category || opt.label || opt;
          const label = opt.label || opt;
          const sub = [opt.description, opt.salary ? opt.salary + '/mes' : ''].filter(Boolean).join(' · ');
          return `<button class="chat-opt" data-val="${esc(String(val))}">`
            + `<span class="chat-opt-label">${esc(label)}</span>`
            + (sub ? `<span class="chat-opt-sub">${esc(sub)}</span>` : '')
            + '</button>';
        }).join('') + '</div>';
      }
      const bubble = addBubble(html, 'system', true);
      bubble.querySelectorAll('.chat-opt').forEach(btn => {
        btn.addEventListener('click', async () => {
          const val = btn.dataset.val;
          addBubble(btn.querySelector('.chat-opt-label').textContent, 'user');
          const r = await api('/api/chat', { method: 'POST', body: JSON.stringify({ message: val }) });
          if (r) handleChatResponse(r);
        });
      });
      return;
    }

    if (res.type === 'budget_result') {
      renderBudgetResult(res.data);
      return;
    }

    if (res.type === 'not_found') {
      addBubble(res.message || 'No encontré esa categoría. Intenta con otra descripción.', 'system');
    }
  }

  function renderBudgetResult(data) {
    let html = `<span>${md(data.mensaje)}</span>`;
    if (data.opciones && data.opciones.length) {
      html += '<div class="budget-results">';
      html += '<table class="budget-table"><thead><tr>'
        + '<th>Contrato</th><th>Jornada</th><th>Coste empresa</th><th>Bruto</th><th>Neto est.</th><th>Margen</th>'
        + '</tr></thead><tbody>';
      data.opciones.forEach(op => {
        const highlight = op.margen < 50 ? ' style="background:rgba(220,203,179,0.15)"' : '';
        html += `<tr${highlight}>`
          + `<td>${esc(op.contrato)}</td>`
          + `<td>${op.jornada_horas}h (${op.jornada_pct}%)</td>`
          + `<td><strong>${fmt(op.coste_empresa_mes)}</strong></td>`
          + `<td>${fmt(op.bruto_mensual)}</td>`
          + `<td>${fmt(op.neto_estimado)}</td>`
          + `<td style="color:var(--muted)">${fmt(op.margen)}</td>`
          + '</tr>';
      });
      html += '</tbody></table></div>';
      html += `<div style="margin-top:8px;font-size:12px;color:var(--muted)">Presupuesto máx: ${fmt(data.presupuesto_max)} · ${data.opciones.length} combinaciones encontradas</div>`;
    }
    addBubble(html, 'system', true);
  }

  // ------------------------------------------------------------------
  // Formulario de simulación (contratar)
  // ------------------------------------------------------------------
  function setupSimForm() {
    $('simForm').addEventListener('submit', async e => {
      e.preventDefault();
      const extrasVal = document.querySelector('input[name="extras"]:checked')?.value || '14';
      const data = {
        category: $('category').value,
        contract_type: $('contractType').value,
        weekly_hours: Number($('weeklyHours').value),
        seniority_years: Number($('seniorityYears').value),
        extras_prorated: extrasVal === '12',
        num_children: Number($('numChildren').value),
        children_under_3: Number($('childrenUnder3')?.value || 0),
        region: $('simRegion')?.value || 'generica',
      };
      const btn = e.target.querySelector('button[type="submit"]');
      if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner"></span>Calculando…'; }
      const res = await api('/api/simulate', { method: 'POST', body: JSON.stringify(data) });
      if (btn) { btn.disabled = false; btn.textContent = 'Calcular coste'; }
      if (res?.error) { showToast(res.error, 'error'); return; }
      if (res) renderResult(res);
    });
  }

  // ------------------------------------------------------------------
  // Render SS detalle (handles nested empresa/trabajador objects)
  // ------------------------------------------------------------------
  function renderSSDetalle(ssD) {
    if (!ssD || !Object.keys(ssD).length) {
      return '<span style="color:var(--muted);font-size:13px">—</span>';
    }
    const labelMap = {
      base_cotizacion_eur: 'Base cotización',
      contingencias_comunes: 'Contingencias comunes',
      desempleo: 'Desempleo',
      fogasa: 'FOGASA',
      formacion_profesional: 'Formación profesional',
      mei: 'MEI',
      at_ep: 'AT/EP',
      total_eur: 'Total',
      pct_total: '% sobre base',
      recargo_contrato_corto_eur: 'Recargo contrato corto',
      grupo_cotizacion: 'Grupo cotización',
    };
    const fmtVal = (k, v) => {
      if (typeof v === 'object' && v !== null) return '—';
      if (k === 'pct_total') return (typeof v === 'number' ? v.toFixed(2) : String(v ?? '')) + ' %';
      if (k === 'grupo_cotizacion') return esc(v);
      if (typeof v === 'number') return fmt(v);
      return esc(v);
    };
    let html = '';
    // Base de cotización
    if (ssD.base_cotizacion_eur != null) {
      html += `<div class="desglose-row"><span>Base cotización</span><span>${fmt(ssD.base_cotizacion_eur)}</span></div>`;
    }
    // Empresa
    if (ssD.empresa && typeof ssD.empresa === 'object') {
      html += '<h5 style="margin:10px 0 4px;font-size:12px;text-transform:uppercase;letter-spacing:0.05em;color:var(--muted)">Empresa</h5>';
      for (const [k, v] of Object.entries(ssD.empresa)) {
        html += `<div class="desglose-row"><span>${esc(labelMap[k] || k.replace(/_/g, ' '))}</span><span>${fmtVal(k, v)}</span></div>`;
      }
    }
    // Trabajador
    if (ssD.trabajador && typeof ssD.trabajador === 'object') {
      html += '<h5 style="margin:10px 0 4px;font-size:12px;text-transform:uppercase;letter-spacing:0.05em;color:var(--muted)">Trabajador</h5>';
      for (const [k, v] of Object.entries(ssD.trabajador)) {
        html += `<div class="desglose-row"><span>${esc(labelMap[k] || k.replace(/_/g, ' '))}</span><span>${fmtVal(k, v)}</span></div>`;
      }
    }
    // Grupo cotización
    if (ssD.grupo_cotizacion) {
      html += `<div class="desglose-row"><span>Grupo cotización</span><span>${esc(ssD.grupo_cotizacion)}</span></div>`;
    }
    // Recargo
    if (ssD.recargo_contrato_corto_eur) {
      html += `<div class="desglose-row"><span>Recargo contrato corto</span><span>${fmt(ssD.recargo_contrato_corto_eur)}</span></div>`;
    }
    return html || '<span style="color:var(--muted);font-size:13px">—</span>';
  }

  // ------------------------------------------------------------------
  // Cost breakdown bar
  // ------------------------------------------------------------------
  function renderCostBreakdownBar(d) {
    const bar = $('costBreakdownBar');
    if (!bar) return;
    const neto = d.neto_mensual_eur || 0;
    const ssTrab = d.ss_trabajador_mes_eur || 0;
    const irpf = d.irpf_mensual_eur || 0;
    const ssEmp = d.ss_empresa_mes_eur || 0;
    const total = neto + ssTrab + irpf + ssEmp;
    if (total <= 0) { bar.hidden = true; return; }

    const pct = v => ((v / total) * 100).toFixed(1);
    bar.innerHTML = `
      <div class="cost-bar-track">
        <div class="cost-bar-seg" data-type="neto" style="width:${pct(neto)}%"></div>
        <div class="cost-bar-seg" data-type="ss_trab" style="width:${pct(ssTrab)}%"></div>
        <div class="cost-bar-seg" data-type="irpf" style="width:${pct(irpf)}%"></div>
        <div class="cost-bar-seg" data-type="ss_emp" style="width:${pct(ssEmp)}%"></div>
      </div>
      <div class="cost-bar-legend">
        <span class="cost-bar-item"><span class="cost-bar-dot" data-type="neto"></span>Neto ${pct(neto)}%</span>
        <span class="cost-bar-item"><span class="cost-bar-dot" data-type="ss_trab"></span>SS trab. ${pct(ssTrab)}%</span>
        <span class="cost-bar-item"><span class="cost-bar-dot" data-type="irpf"></span>IRPF ${pct(irpf)}%</span>
        <span class="cost-bar-item"><span class="cost-bar-dot" data-type="ss_emp"></span>SS emp. ${pct(ssEmp)}%</span>
      </div>`;
    bar.hidden = false;
  }

  // ------------------------------------------------------------------
  // Render resultado CONTRATAR
  // ------------------------------------------------------------------
  function renderResult(d) {
    // Activar tab contratar si no estaba
    document.querySelectorAll('.tool-tab').forEach(b => b.classList.toggle('active', b.dataset.tool === 'contratar'));
    $('toolContratar').hidden = false;
    $('toolDespedir').hidden = true;

    $('resultPlaceholder').hidden = true;
    $('despidoResultSection').hidden = true;
    $('resultSection').hidden = false;

    $('fichaContext').innerHTML = d.categoria
      ? `<strong>${esc(d.categoria)}</strong> &mdash; ${esc(d.contrato)} &mdash; ${d.jornada_pct ?? 100}%`
      : '';
    $('heroCoste').textContent = fmt(d.coste_total_empresa_mes_eur);
    $('valBruto').textContent = fmt(d.bruto_mensual_eur);
    $('valNeto').textContent = fmt(d.neto_mensual_eur);
    $('valAnual').textContent = fmt(d.coste_total_empresa_anual_eur);
    $('valSSEmp').textContent = fmt(d.ss_empresa_mes_eur);
    $('valSSTrab').textContent = fmt(d.ss_trabajador_mes_eur);
    $('valIRPFPct').textContent = d.irpf_retencion_pct ?? 0;
    $('valIRPF').textContent = fmt(d.irpf_mensual_eur);

    // Cost breakdown bar
    renderCostBreakdownBar(d);

    const tbody = $('devengosTable').querySelector('tbody');
    tbody.innerHTML = (d.devengos || []).map(dv =>
      `<tr><td>${esc(dv.concepto)}</td><td>${fmt(dv.eur)}</td><td style="color:var(--muted);font-size:12px">${esc(dv.fuente || '')}</td></tr>`
    ).join('');

    const ssD = d.ss_detalle || {};
    $('ssDetalle').innerHTML = renderSSDetalle(ssD);

    const notas = d.notas || [];
    $('notasBox').innerHTML = notas.length
      ? notas.map(n => `<p>${esc(n)}</p>`).join('')
      : '';
    $('notasBox').style.display = notas.length ? '' : 'none';

    const cBox = $('condicionesBox');
    const cDet = $('condicionesDetalles');
    if (cBox && cDet && d.condiciones_convenio?.length) {
      cBox.innerHTML = d.condiciones_convenio.map(s =>
        `<details style="margin-bottom:8px;border:1px solid var(--line);border-radius:8px;overflow:hidden">
          <summary style="padding:10px 14px;cursor:pointer;font-size:13px;font-weight:500;color:var(--pgk-green);background:rgba(220,203,179,.1);list-style:none">${esc(s.title)}</summary>
          ${(s.items || []).map(item =>
            `<div style="padding:10px 14px;border-top:1px solid var(--line);font-size:13px;line-height:1.55">
              <strong>${esc(item.label)}</strong><br>${esc(item.detail)}
              ${item.source ? `<br><span style="color:var(--muted);font-size:11px">${esc(item.source)}</span>` : ''}
            </div>`
          ).join('')}
        </details>`
      ).join('');
      cDet.hidden = false;
    } else if (cDet) {
      cDet.hidden = true;
    }

    // Botón descargar pre-nómina desde simulación
    state._lastSimData = d;
    let nominaBtn = $('btnDescargarNomina');
    if (!nominaBtn) {
      nominaBtn = document.createElement('button');
      nominaBtn.id = 'btnDescargarNomina';
      nominaBtn.className = 'btn btn-outline';
      nominaBtn.style.cssText = 'margin-top:12px;width:100%;font-size:14px';
      nominaBtn.textContent = '📄 Descargar Pre-nómina PDF';
      nominaBtn.addEventListener('click', downloadNominaFromSim);
      $('resultSection').appendChild(nominaBtn);
    }
    nominaBtn.hidden = false;

    $('desgloseDetails').open = true;
    $('resultSection').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  async function downloadNominaFromSim() {
    const d = state._lastSimData;
    if (!d) return;
    const now = new Date();
    const periodo = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}`;
    try {
      const res = await fetch('/api/nomina', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          category: d.categoria,
          contract_type: d.contrato,
          weekly_hours: d.jornada_horas_semana ?? 40,
          seniority_years: d.antiguedad_anos ?? 0,
          extras_prorated: d.extras_prorated ?? false,
          num_children: 0,
          nombre_trabajador: d.categoria,
          periodo: periodo,
          format: 'pdf',
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        alert(err.error || 'Error generando nómina');
        return;
      }
      const ct = res.headers.get('content-type') || '';
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = ct.includes('pdf') ? 'pre_nomina.pdf' : 'pre_nomina.html';
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch(e) {
      showToast('Error descargando pre-nómina', 'error');
    }
  }

  // ------------------------------------------------------------------
  // Formulario DESPEDIR
  // ------------------------------------------------------------------
  function setupDespidoForm() {
    const empSel = $('despidoEmpleado');
    empSel?.addEventListener('change', () => {
      const empId = empSel.value;
      if (!empId) return;
      const emp = state.employees.find(e => String(e.id) === empId);
      if (!emp) return;
      $('despidoNombre').value = emp.nombre || '';
      $('despidoCategoria').value = emp.categoria || '';
      $('despidoFechaInicio').value = emp.fecha_inicio || '';
      if (emp.salario_bruto_mensual) $('despidoSalario').value = emp.salario_bruto_mensual;
    });

    $('despidoForm').addEventListener('submit', async e => {
      e.preventDefault();
      const data = {
        tipo_despido: $('despidoTipo').value,
        fecha_inicio: $('despidoFechaInicio').value,
        salario_bruto_mensual: Number($('despidoSalario').value),
        fecha_despido: $('despidoFechaFin').value || null,
        dias_vacaciones_pendientes: Number($('despidoVacaciones').value || 0),
        dias_preaviso_empresa: Number($('despidoPreaviso').value || 0),
        nombre_trabajador: $('despidoNombre').value || '',
        categoria: $('despidoCategoria').value || '',
      };

      const empId = $('despidoEmpleado').value;
      let res;
      if (empId) {
        res = await api(`/api/employees/${empId}/despido`, { method: 'POST', body: JSON.stringify(data) });
      } else {
        res = await api('/api/despido', { method: 'POST', body: JSON.stringify(data) });
      }
      if (res?.error) { showToast(res.error, 'error'); return; }
      if (res) renderDespidoResult(res);
    });
  }

  // ------------------------------------------------------------------
  // Render resultado DESPEDIR
  // ------------------------------------------------------------------
  function renderDespidoResult(d) {
    // Activar tab despedir
    document.querySelectorAll('.tool-tab').forEach(b => b.classList.toggle('active', b.dataset.tool === 'despedir'));
    $('toolContratar').hidden = true;
    $('toolDespedir').hidden = false;

    $('resultPlaceholder').hidden = true;
    $('resultSection').hidden = true;
    $('despidoResultSection').hidden = false;

    // Encabezado
    const nombre = d.nombre_trabajador ? `${esc(d.nombre_trabajador)} · ` : '';
    const cat = d.categoria ? esc(d.categoria) + ' · ' : '';
    $('despidoResultNombre').innerHTML = `${nombre}${cat}${esc(d.antiguedad_anos)} años de antigüedad`;
    $('despidoTipoLabel').textContent = d.tipo_despido_label || '';

    // Hero
    $('heroTotal').textContent = fmt(d.total_eur);
    $('valIndem').textContent = fmt(d.indemnizacion_eur);
    $('valFiniquito').textContent = fmt(d.finiquito?.total_finiquito_eur);
    $('despidoAntiguedad').innerHTML = `<span>Indemnización:</span> <strong>${esc(d.indemnizacion_calculo)}</strong>`;

    // Desglose finiquito
    const fin = d.finiquito || {};
    $('despidoDiasPendientesLabel').textContent = `Salario ${fin.salario_dias_pendientes_n || '—'} días pendientes del mes`;
    $('valDiasPend').textContent = fmt(fin.salario_dias_pendientes_eur);
    $('valPPagas').textContent = `${fmt(fin.parte_proporcional_pagas_eur)} (${fin.parte_proporcional_pagas_n || 0} pagas)`;
    $('valVacaciones').textContent = `${fmt(fin.vacaciones_pendientes_eur)} (${fin.vacaciones_pendientes_dias || 0} días)`;
    $('valPrinfo').textContent = fin.preaviso_pendiente_dias > 0
      ? `${fmt(fin.preaviso_pendiente_eur)} (${fin.preaviso_pendiente_dias} días)`
      : '—';
    $('valTotalFiniquito').textContent = fmt(fin.total_finiquito_eur);

    $('indemCalculo').innerHTML = [
      d.indemnizacion_calculo,
      d.tope_aplicado ? `⚠ Tope máximo aplicado: ${fmt(d.tope_maximo_eur)}` : '',
    ].filter(Boolean).map(s => `<div class="desglose-row"><span>${esc(s)}</span></div>`).join('');

    // Notas
    const notas = d.notas || [];
    $('despidoNotas').innerHTML = notas.map(n => `<p>${esc(n)}</p>`).join('');
    $('despidoNotas').style.display = notas.length ? '' : 'none';

    // Comparativa escenarios
    const esc_d = d.escenarios || {};
    const tipoActual = d.tipo_despido;
    $('escenariosGrid').innerHTML = [
      {
        tipo: 'Baja voluntaria',
        coste: 0,
        nota: '0€ indemnización, pero el trabajador necesita firmar',
        active: tipoActual === 'voluntario',
        color: 'green',
      },
      {
        tipo: 'Mutuo acuerdo',
        coste: esc_d.objetivo_eur,
        nota: 'Negociado. El trabajador NO cobra el paro.',
        active: tipoActual === 'mutuo_acuerdo',
        color: 'neutral',
      },
      {
        tipo: 'Despido objetivo',
        coste: esc_d.objetivo_eur,
        nota: '20 días/año. Requiere causa documentada.',
        active: tipoActual === 'objetivo',
        color: 'neutral',
      },
      {
        tipo: 'Despido improcedente',
        coste: esc_d.improcedente_eur,
        nota: '33 días/año. Sin causa o juicio perdido.',
        active: tipoActual === 'improcedente',
        color: 'danger',
      },
    ].map(sc => `
      <div class="escenario-card ${sc.active ? 'active' : ''} ${sc.color}">
        <div class="escenario-tipo">${esc(sc.tipo)}</div>
        <div class="escenario-coste">${sc.coste != null ? fmtShort(sc.coste) : '0\u00a0€'}</div>
        <div class="escenario-nota">${esc(sc.nota)}</div>
      </div>
    `).join('');

    // Consejo estratégico
    const consejos = d.consejo || [];
    if (consejos.length) {
      $('consejoBlock').innerHTML = `
        <div class="consejo-header">Consejo PGK</div>
        ${consejos.map(c => `<div class="consejo-item">${md(esc(c))}</div>`).join('')}
      `;
      $('consejoBlock').hidden = false;
    } else {
      $('consejoBlock').hidden = true;
    }

    // Fuentes
    const fuentes = d.fuentes || [];
    $('despidoFuentes').innerHTML = fuentes.length
      ? `<p>${fuentes.map(f => esc(f)).join(' · ')}</p>`
      : '';

    $('despidoDesgloseDetails').open = true;
    $('despidoResultSection').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  // ------------------------------------------------------------------
  // Plantilla de trabajadores
  // ------------------------------------------------------------------
  async function loadEmployees() {
    const employees = await api('/api/employees');
    state.employees = employees || [];
    renderPlantilla(state.employees);
    populateDespidoEmpleadoSelect(state.employees);
  }

  function renderPlantilla(employees) {
    const box = $('plantillaBox');
    const badge = $('plantillaBadge');

    if (!employees.length) {
      box.innerHTML = '<div style="padding:24px;text-align:center"><svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round" style="opacity:.25;margin-bottom:8px"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg><p class="empty-msg">Sin trabajadores registrados</p><p style="font-size:12px;color:var(--muted);margin:0">Añade el primero para hacer seguimiento y calcular despidos en un clic.</p></div>';
      if (badge) badge.hidden = true;
      return;
    }

    if (badge) {
      badge.textContent = employees.length;
      badge.hidden = false;
    }

    const today = new Date().toISOString().split('T')[0];
    box.innerHTML = `<div class="emp-card-grid">
      ${employees.map(emp => {
        const initials = (emp.nombre || '').split(/\s+/).map(w => w[0]).join('').toUpperCase().slice(0, 2);
        const cat = (emp.categoria || '').replace(/\.$/, '');
        const expired = emp.fecha_fin && emp.fecha_fin <= today;
        return `<div class="emp-card">
          <div class="emp-avatar">${esc(initials)}</div>
          <div class="emp-info">
            <div class="emp-name">${esc(emp.nombre)}</div>
            <div class="emp-meta">${esc(cat)} · ${emp.jornada_horas}h/sem · desde ${esc(emp.fecha_inicio)}</div>
            <div class="emp-badges">
              <span class="emp-badge emp-badge--contract">${esc(emp.contrato_tipo)}</span>
              ${emp.salario_bruto_mensual ? `<span class="emp-badge emp-badge--cost">${fmt(emp.salario_bruto_mensual)}</span>` : ''}
              ${expired ? '<span class="emp-badge emp-badge--expired">Vencido</span>' : ''}
            </div>
            <div class="emp-actions">
              <button class="btn-link" onclick="window._descargarNomina(${emp.id})">Nómina</button>
              <span style="color:var(--line-strong)">·</span>
              <button class="btn-link" onclick="window._despidirEmpleado(${emp.id})">Despedir</button>
              <span style="color:var(--line-strong)">·</span>
              <button class="btn-link" onclick="window._darDeBajaEmpleado(${emp.id})">Baja</button>
            </div>
          </div>
        </div>`;
      }).join('')}
    </div>`;  }

  function populateDespidoEmpleadoSelect(employees) {
    const sel = $('despidoEmpleado');
    if (!sel) return;
    sel.innerHTML = '<option value="">— Introduzco los datos manualmente —</option>'
      + employees.map(e =>
        `<option value="${e.id}">${esc(e.nombre)} (${esc(e.categoria.replace(/\.$/, ''))})</option>`
      ).join('');
  }

  // Botones inline de la tabla de plantilla
  window._despidirEmpleado = function(empId) {
    const emp = state.employees.find(e => e.id === empId);
    if (!emp) return;
    // Switch to despedir tab and prefill
    document.querySelectorAll('.tool-tab').forEach(b => b.classList.remove('active'));
    document.querySelector('.tool-tab[data-tool="despedir"]').classList.add('active');
    $('toolContratar').hidden = true;
    $('toolDespedir').hidden = false;
    // Prefill
    $('despidoEmpleado').value = empId;
    $('despidoNombre').value = emp.nombre || '';
    $('despidoCategoria').value = emp.categoria || '';
    $('despidoFechaInicio').value = emp.fecha_inicio || '';
    if (emp.salario_bruto_mensual) $('despidoSalario').value = emp.salario_bruto_mensual;
    $('toolDespedir').scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  window._darDeBajaEmpleado = async function(empId) {
    if (!confirm('¿Marcar este trabajador como dado de baja?')) return;
    await api(`/api/employees/${empId}`, { method: 'PUT', body: JSON.stringify({ status: 'baja' }) });
    await loadEmployees();
  };

  window._descargarNomina = function(empId) {
    const now = new Date();
    const periodo = `${now.getFullYear()}-${String(now.getMonth()+1).padStart(2,'0')}`;
    window.open(`/api/employees/${empId}/nomina?periodo=${periodo}`, '_blank');
  };

  function setupPlantillaForm() {
    const toggleBtn = $('toggleEmpleadoForm');
    const form = $('empleadoForm');
    const cancelBtn = $('cancelEmpleadoBtn');

    toggleBtn?.addEventListener('click', () => {
      form.hidden = !form.hidden;
      toggleBtn.textContent = form.hidden ? '+ Añadir trabajador' : '— Cancelar';
    });

    cancelBtn?.addEventListener('click', () => {
      form.hidden = true;
      toggleBtn.textContent = '+ Añadir trabajador';
      form.reset();
    });

    form?.addEventListener('submit', async e => {
      e.preventDefault();
      const data = {
        nombre: $('empNombre').value,
        categoria: $('empCategoria').value,
        contrato_tipo: $('empContrato').value,
        jornada_horas: Number($('empHoras').value),
        fecha_inicio: $('empFechaInicio').value,
        fecha_fin: $('empFechaFin').value || null,
        salario_bruto_mensual: Number($('empSalario').value) || null,
        num_hijos: Number($('empHijos').value || 0),
        notas: $('empNotas').value,
        nif: $('empNif')?.value || '',
        naf: $('empNaf')?.value || '',
        domicilio: $('empDomicilio')?.value || '',
        email: $('empEmail')?.value || '',
        telefono: $('empTelefono')?.value || '',
        region: $('empRegion')?.value || 'generica',
      };
      const res = await api('/api/employees', { method: 'POST', body: JSON.stringify(data) });
      if (res?.error) { showToast(res.error, 'error'); return; }
      showToast('Trabajador guardado correctamente', 'success');
      form.reset();
      form.hidden = true;
      toggleBtn.textContent = '+ Añadir trabajador';
      await loadEmployees();
      await loadAlerts(); // puede haber nuevas alertas automáticas
      $('plantillaSection').open = true;
    });
  }

  // ------------------------------------------------------------------
  // Convenio
  // ------------------------------------------------------------------
  async function loadConvenioInfo() {
    try {
      const data = await api('/api/convenio');
      renderWelcomeCard(data.convenio);
      renderConvenioBox(data);
    } catch {
      $('convenioBox').textContent = 'Error cargando convenio.';
    }
  }

  function renderWelcomeCard(conv) {
    $('welcomeEmpresa').textContent = state.user.empresa_nombre || state.user.username;
    $('welcomeConvenio').textContent = conv.nombre;
    $('welcomeVigencia').textContent = `Vigencia ${conv.vigencia_desde_ano}–${conv.vigencia_hasta_ano}`;
    $('welcomeCard').hidden = false;
  }

  function renderConvenioBox(data) {
    const conv = data.convenio;
    const sections = data.sections || [];
    let html = `
      <p style="font-family:var(--font-heading);font-size:18px;color:var(--pgk-green);margin:0 0 4px">${esc(conv.nombre)}</p>
      <p style="font-size:13px;color:var(--muted);margin:0 0 14px">
        ${conv.codigo ? `Código ${esc(conv.codigo)} · ` : ''}Vigencia ${esc(conv.vigencia_desde_ano)}–${esc(conv.vigencia_hasta_ano)}
      </p>`;
    html += sections.map(s => `
      <details style="margin-bottom:8px;border:1px solid var(--line);border-radius:8px;overflow:hidden">
        <summary style="padding:10px 14px;cursor:pointer;font-size:14px;font-weight:500;color:var(--pgk-green);background:rgba(220,203,179,.1);list-style:none">${esc(s.title)}</summary>
        ${(s.items || []).map(item => `
          <div style="padding:10px 14px;border-top:1px solid var(--line);font-size:13px;line-height:1.55">
            <strong>${esc(item.label)}</strong><br>${esc(item.detail)}
            ${item.source ? `<br><span style="color:var(--muted);font-size:11px;margin-top:2px;display:block">${esc(item.source)}</span>` : ''}
          </div>`).join('')}
      </details>`).join('');
    $('convenioBox').innerHTML = html;
  }

  // ------------------------------------------------------------------
  // Alertas
  // ------------------------------------------------------------------
  async function loadAlerts() {
    const alerts = await api('/api/alerts') || [];
    const box = $('alertsBox');
    const urgent = $('alertsUrgent');
    const badge = $('alertsBadge');

    if (!alerts.length) {
      box.innerHTML = '<p class="empty-msg">Sin alertas pendientes.</p>';
      urgent.hidden = true;
      if (badge) badge.hidden = true;
      return;
    }

    if (badge) {
      badge.textContent = `${alerts.length} alerta${alerts.length !== 1 ? 's' : ''}`;
      badge.hidden = false;
    }

    const urgentAlerts = alerts.filter(a => daysUntil(a.due_date) <= 7);
    if (urgentAlerts.length) {
      urgent.hidden = false;
      urgent.innerHTML = urgentAlerts.map(a => {
        const days = daysUntil(a.due_date);
        const label = days < 0 ? 'VENCIDA' : days === 0 ? 'HOY' : `${days}d`;
        return `<div class="urgent-alert">
          <span class="urgent-badge">${esc(label)}</span>
          <strong>${esc(a.title)}</strong>
          ${a.worker_name ? `<span style="color:var(--muted)"> · ${esc(a.worker_name)}</span>` : ''}
          <button class="btn-link" style="font-size:12px;margin-left:auto" onclick="window._dismissAlert(${a.id})">Resolver</button>
        </div>`;
      }).join('');
    } else {
      urgent.hidden = true;
    }

    const typeLabels = {
      fin_contrato: 'Fin de contrato',
      fin_prueba: 'Fin período de prueba',
      vencimiento_titulo: 'Vencimiento título',
      otro: 'Otro',
    };
    box.innerHTML = alerts.map(a => {
      const days = daysUntil(a.due_date);
      const urgencyClass = days < 0 ? 'alert-overdue' : days <= 7 ? 'alert-urgent' : 'alert-ok';
      return `<div class="historial-row ${urgencyClass}">
        <div>
          <strong>${esc(a.title)}</strong>
          ${a.worker_name ? `<span style="color:var(--muted);font-size:12px"> · ${esc(a.worker_name)}</span>` : ''}
          <br><span style="font-size:12px;color:var(--muted)">${esc(typeLabels[a.alert_type] || a.alert_type)} · Vence: ${esc(a.due_date)}</span>
          ${a.description ? `<br><span style="font-size:12px;color:var(--muted)">${esc(a.description)}</span>` : ''}
        </div>
        <div style="display:flex;align-items:center;gap:8px">
          <span class="alert-days">${days < 0 ? 'Vencida' : days === 0 ? 'Hoy' : `${days}d`}</span>
          <button class="btn-link" style="font-size:12px" onclick="window._dismissAlert(${a.id})">Resolver</button>
        </div>
      </div>`;
    }).join('');
  }

  window._dismissAlert = async function(id) {
    await api(`/api/alerts/${id}/dismiss`, { method: 'POST' });
    await loadAlerts();
  };

  function setupAlertForm() {
    const toggleBtn = $('toggleAlertForm');
    const form = $('alertForm');

    toggleBtn?.addEventListener('click', () => {
      form.hidden = !form.hidden;
      toggleBtn.textContent = form.hidden ? '+ Añadir alerta' : '— Cancelar';
    });

    form?.addEventListener('submit', async e => {
      e.preventDefault();
      const type = $('alertType').value;
      const typeLabels = {
        fin_contrato: 'Fin de contrato',
        fin_prueba: 'Fin período de prueba',
        vencimiento_titulo: 'Vencimiento título',
        otro: 'Alerta',
      };
      const data = {
        alert_type: type,
        title: `${typeLabels[type] || 'Alerta'}${$('alertWorker').value ? ' — ' + $('alertWorker').value : ''}`,
        description: $('alertDesc').value,
        due_date: $('alertDate').value,
        worker_name: $('alertWorker').value,
      };
      const res = await api('/api/alerts', { method: 'POST', body: JSON.stringify(data) });
      if (res?.error) { alert(res.error); return; }
      form.reset();
      form.hidden = true;
      toggleBtn.textContent = '+ Añadir alerta';
      await loadAlerts();
    });
  }

  // ------------------------------------------------------------------
  // Historial
  // ------------------------------------------------------------------
  async function loadHistory() {
    const consultations = await api('/api/history') || [];
    const box = $('historialBox');
    if (!consultations.length) {
      box.innerHTML = '<p class="empty-msg">Sin consultas previas.</p>';
      return;
    }
    box.innerHTML = consultations.map(c => `
      <div class="historial-row">
        <div>
          <strong>${esc(c.query_summary)}</strong>
          <br><span style="font-size:12px;color:var(--muted)">${esc(c.created_at?.slice(0, 16).replace('T', ' ') || '')}</span>
        </div>
        <div style="font-size:14px;font-weight:600;color:var(--pgk-green)">${c.coste_empresa ? fmt(c.coste_empresa) : '—'}</div>
      </div>`).join('');
  }

  // ------------------------------------------------------------------
  // Clientes (admin)
  // ------------------------------------------------------------------
  async function loadClients() {
    const clients = await api('/api/clients') || [];
    const box = $('clientsBox');
    if (!clients.length) {
      box.innerHTML = '<p class="empty-msg">Sin clientes registrados.</p>';
      return;
    }
    box.innerHTML = `
      <table class="clients-table">
        <thead><tr><th>Empresa</th><th>CIF</th><th>Convenio</th></tr></thead>
        <tbody>${clients.map(c => `<tr>
          <td>${esc(c.empresa)}</td>
          <td>${esc(c.cif)}</td>
          <td style="font-size:12px;color:var(--muted)">${esc((c.convenio_id || '').replace(/_/g, ' '))}</td>
        </tr>`).join('')}</tbody>
      </table>`;
  }

  async function loadConveniosList() {
    const list = await api('/api/convenios') || [];
    state.conveniosList = list;
    const sel = $('clientConvenio');
    if (!sel) return;
    sel.innerHTML = list.map(c =>
      `<option value="${esc(c.id)}">${esc(c.nombre)}</option>`
    ).join('');
  }

  function setupClientForm() {
    const toggleBtn = $('toggleClientForm');
    const form = $('clientForm');

    toggleBtn?.addEventListener('click', () => {
      form.hidden = !form.hidden;
      toggleBtn.textContent = form.hidden ? '+ Nuevo cliente' : '— Cancelar';
    });

    form?.addEventListener('submit', async e => {
      e.preventDefault();
      const data = {
        empresa: $('clientEmpresa').value,
        cif: $('clientCif').value,
        convenio_id: $('clientConvenio').value,
        provincia: $('clientProvincia').value,
      };
      const res = await api('/api/clients', { method: 'POST', body: JSON.stringify(data) });
      if (res?.error) { alert(res.error); return; }
      form.reset();
      form.hidden = true;
      toggleBtn.textContent = '+ Nuevo cliente';
      await loadClients();
    });
  }

  // ------------------------------------------------------------------
  // Verificación de tasas SS (orientativa — usa Perplexity)
  // ------------------------------------------------------------------
  async function loadRatesVerification(force = false) {
    const strip = $('ratesVerifyStrip');
    if (!strip) return;

    strip.hidden = false;
    strip.dataset.status = 'checking';
    $('ratesStripIcon').textContent = '🔄';
    $('ratesStripMsg').textContent = 'Verificando SS, IRPF, SMI y convenios…';
    $('ratesStripDate').textContent = '';

    const url = force ? '/api/verify-rates?force=1' : '/api/verify-rates';
    const res = await api(url);

    if (!res) {
      strip.dataset.status = 'unavailable';
      $('ratesStripIcon').textContent = '⚪';
      $('ratesStripMsg').textContent = 'Verificación no disponible.';
      return;
    }

    const { overall_status, checks = [], verified_at = '' } = res;
    const iconMap = { ok: '✅', warning: '⚠️', uncertain: '❓', unavailable: '⚪', error: '🔴' };

    strip.dataset.status = overall_status;
    $('ratesStripIcon').textContent = iconMap[overall_status] || '⚪';
    $('ratesStripDate').textContent = verified_at ? `Verificado: ${verified_at}` : '';

    // Resumen en el strip
    const nOk = checks.filter(c => c.status === 'ok').length;
    const nWarn = checks.filter(c => c.status === 'warning').length;
    const nUncertain = checks.filter(c => ['uncertain', 'unavailable', 'error'].includes(c.status)).length;
    if (overall_status === 'unavailable' || checks.length === 0) {
      $('ratesStripMsg').textContent = checks[0]?.message || 'Verificación no disponible.';
    } else {
      const parts = [];
      if (nOk) parts.push(`${nOk} ✅`);
      if (nWarn) parts.push(`${nWarn} ⚠️`);
      if (nUncertain) parts.push(`${nUncertain} ❓`);
      $('ratesStripMsg').textContent = `Verificación: ${parts.join(' · ')} — ${overall_status === 'ok' ? 'todo correcto' : 'ver detalle'}`;
    }

    // Card de detalle
    const card = $('ratesDiscrepanciesCard');
    const box = $('ratesDiscrepanciesBox');
    if (!card || !box) return;

    const hasDetail = checks.some(c => c.status !== 'ok' || c.discrepancies?.length > 0);
    if (!hasDetail && overall_status === 'ok') {
      card.hidden = true;
      return;
    }

    card.hidden = false;
    const cardSummary = card.querySelector('summary');
    if (cardSummary) {
      const icons = { ok: '✅', warning: '⚠️', uncertain: '❓', unavailable: '⚪', error: '🔴' };
      cardSummary.textContent = `${icons[overall_status] || '❓'} Verificación de datos normativos — detalle`;
    }

    box.innerHTML = checks.map(c => {
      const icon = iconMap[c.status] || '⚪';
      const discsHtml = c.discrepancies?.length ? `
        <table class="rates-discrepancy-table" style="margin-top:6px">
          <thead><tr><th>Concepto</th><th>Nuestro</th><th>Perplexity</th><th>Δ</th></tr></thead>
          <tbody>
            ${c.discrepancies.map(d => `
              <tr>
                <td>${esc(d.label)}</td>
                <td>${esc(String(d.nuestro ?? '—'))}</td>
                <td>${esc(String(d.perplexity ?? d.notas ?? '—'))}</td>
                <td class="disc-diff">${esc(String(d.diferencia ?? ''))}</td>
              </tr>`).join('')}
          </tbody>
        </table>` : '';
      const srcHtml = c.sources?.length
        ? `<p style="margin:4px 0 0;font-size:11px;color:#a0aec0">Fuente: ${esc(c.sources.join(', '))}</p>`
        : '';
      return `
        <div class="rates-check-item" data-status="${esc(c.status)}">
          <div class="rates-check-header">
            <span class="rates-check-icon">${icon}</span>
            <span class="rates-check-label">${esc(c.label)}</span>
          </div>
          <div class="rates-check-msg">${esc(c.message)}</div>
          ${discsHtml}${srcHtml}
        </div>`;
    }).join('');
  }

  function setupRatesVerifyBtn() {
    const btn = $('ratesVerifyBtn');
    if (!btn) return;
    btn.addEventListener('click', async () => {
      btn.disabled = true;
      btn.textContent = 'Verificando…';
      await loadRatesVerification(true);
      btn.disabled = false;
      btn.textContent = 'Verificar ahora';
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    init().then(() => {
      if (state.user?.role === 'admin') setupClientForm();
      // Cargar verificación de tasas en background (silencioso si no hay API key)
      loadRatesVerification(false);
      setupRatesVerifyBtn();
    });
  });

})();
