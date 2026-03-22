// =============================================
// PGK Laboral Desk — Panel JS (reescrito)
// Endpoints: /api/auth/me, /api/auth/logout,
//   /api/categories, /api/contract-types,
//   /api/simulate, /api/chat, /api/chat/reset,
//   /api/history, /api/alerts, /api/convenio,
//   /api/clients, /api/convenios
// =============================================
(function () {
  'use strict';

  // -------------------------------------------------------
  // Estado global
  // -------------------------------------------------------
  const state = {
    user: null,
    categories: [],
    contractTypes: [],
    conveniosList: [],
  };

  // -------------------------------------------------------
  // Utilidades
  // -------------------------------------------------------
  const $ = id => document.getElementById(id);

  function esc(v) {
    return String(v ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  // Convierte markdown mínimo a HTML (bold, italic, saltos de línea)
  function md(text) {
    return esc(text)
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      .replace(/\n/g, '<br>');
  }

  function fmt(n) {
    return Number(n).toLocaleString('es-ES', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) + '\u00a0€';
  }

  function fmtDate(s) {
    if (!s) return '—';
    try {
      return new Date(s.includes('T') ? s : s + 'T12:00:00').toLocaleDateString('es-ES', { day: '2-digit', month: 'short', year: 'numeric' });
    } catch { return s; }
  }

  async function api(path, opts = {}) {
    const res = await fetch(path, { headers: { 'Content-Type': 'application/json' }, ...opts });
    const json = await res.json();
    if (!res.ok) throw new Error(json.error || `Error ${res.status}`);
    return json;
  }

  // -------------------------------------------------------
  // Arranque
  // -------------------------------------------------------
  async function init() {
    try {
      state.user = await api('/api/auth/me');
    } catch {
      window.location.href = '/';
      return;
    }

    // Cabecera
    $('empresaName').textContent = state.user.empresa_nombre || state.user.username;

    // Sección admin
    if (state.user.role === 'admin') {
      $('clientsSection').hidden = false;
      loadClients();
      loadConveniosList();
    }

    // Carga paralela
    await Promise.allSettled([
      loadCategoriesAndTypes(),
      loadConvenioInfo(),
      loadHistory(),
      loadAlerts(),
    ]);
  }

  // -------------------------------------------------------
  // Tabs: Chat / Formulario
  // -------------------------------------------------------
  document.querySelectorAll('.mode-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.mode-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      const mode = tab.dataset.mode;
      $('chatSection').hidden = mode !== 'chat';
      $('formSection').hidden = mode !== 'form';
    });
  });

  // -------------------------------------------------------
  // Categorías y tipos de contrato
  // -------------------------------------------------------
  async function loadCategoriesAndTypes() {
    try {
      [state.categories, state.contractTypes] = await Promise.all([
        api('/api/categories'),
        api('/api/contract-types'),
      ]);
      const catSel = $('category');
      catSel.innerHTML = '<option value="">— Elige categoría —</option>' +
        state.categories.map(c => `<option value="${esc(c.value)}">${esc(c.label)}</option>`).join('');
      const ctrSel = $('contractType');
      ctrSel.innerHTML = state.contractTypes.map(t => `<option value="${esc(t.value)}">${esc(t.label)}</option>`).join('');
    } catch (e) {
      console.error('Error cargando categorías:', e);
    }
  }

  // -------------------------------------------------------
  // Convenio info (panel lateral + welcome card)
  // -------------------------------------------------------
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

  // -------------------------------------------------------
  // Chat conversacional
  // -------------------------------------------------------
  const chatLog = $('chatLog');

  function addBubble(role, content, isHtml = false) {
    const div = document.createElement('div');
    div.className = `chat-bubble ${role}`;
    if (isHtml) div.innerHTML = content;
    else div.textContent = content;
    chatLog.appendChild(div);
    chatLog.scrollTop = chatLog.scrollHeight;
    return div;
  }

  $('chatForm').addEventListener('submit', async e => {
    e.preventDefault();
    const msg = $('chatInput').value.trim();
    if (!msg) return;
    $('chatInput').value = '';
    $('chatInput').disabled = true;
    addBubble('user', msg);
    const thinking = addBubble('system', '…');
    try {
      const res = await api('/api/chat', { method: 'POST', body: JSON.stringify({ message: msg }) });
      thinking.remove();
      handleChatResponse(res);
    } catch (err) {
      thinking.remove();
      addBubble('system', `Error: ${err.message}`);
    } finally {
      $('chatInput').disabled = false;
      $('chatInput').focus();
    }
  });

  $('chatResetBtn').addEventListener('click', async () => {
    try { await api('/api/chat/reset', { method: 'POST' }); } catch {}
    chatLog.innerHTML = '<div class="chat-bubble system">Hola. Dime qué puesto quieres cubrir y te calculo el coste real. Por ejemplo: <em>"Necesito un socorrista para verano a jornada completa"</em></div>';
    $('resultSection').hidden = true;
  });

  function handleChatResponse(res) {
    if (res.type === 'question') {
      let html = `<span>${md(res.message)}</span>`;
      if (res.options && res.options.length) {
        html += '<div class="chat-options">';
        html += res.options.map(opt => {
          // options can be objects {category, label, salary, description} or plain strings
          const val = typeof opt === 'object' ? (opt.category || opt.label || String(opt)) : String(opt);
          const label = typeof opt === 'object' ? (opt.label || opt.category) : String(opt);
          const desc = typeof opt === 'object' && opt.description ? opt.description : '';
          const salary = typeof opt === 'object' && opt.salary ? opt.salary : '';
          const sublabel = [desc, salary].filter(Boolean).join(' · ');
          return `<button class="chat-opt" data-val="${esc(val)}">
            <span class="chat-opt-label">${esc(label)}</span>
            ${sublabel ? `<span class="chat-opt-sub">${esc(sublabel)}</span>` : ''}
          </button>`;
        }).join('');
        html += '</div>';
      }
      const bubble = addBubble('assistant', html, true);
      bubble.querySelectorAll('.chat-opt').forEach(btn => {
        btn.addEventListener('click', () => {
          $('chatInput').value = btn.dataset.val;
          $('chatForm').requestSubmit();
        });
      });
    } else if (res.type === 'result') {
      const d = res.data;
      addBubble('assistant', `✓ ${d.categoria} · ${d.contrato} · Coste empresa: ${fmt(d.coste_total_empresa_mes_eur)}/mes`);
      // Mostrar warnings legales del contrato en el chat
      if (res.data.contract_warnings && res.data.contract_warnings.length) {
        const warnHtml = '<strong>⚠ Avisos legales para este contrato:</strong><br>' +
          res.data.contract_warnings.map(w => `· ${esc(w)}`).join('<br>');
        addBubble('system', warnHtml, true);
      }
      renderResult(d);
      loadHistory();
    } else {
      addBubble('system', res.message || 'Error desconocido.');
    }
  }

  // -------------------------------------------------------
  // Formulario de simulación
  // -------------------------------------------------------
  $('simForm').addEventListener('submit', async e => {
    e.preventDefault();
    const btn = e.target.querySelector('[type=submit]');
    btn.disabled = true;
    btn.textContent = 'Calculando…';

    const extrasVal = document.querySelector('input[name="extras"]:checked')?.value ?? '14';
    const payload = {
      category: $('category').value,
      contract_type: $('contractType').value,
      weekly_hours: parseFloat($('weeklyHours').value) || 40,
      seniority_years: parseInt($('seniorityYears').value) || 0,
      extras_prorated: extrasVal === '12',
      num_children: parseInt($('numChildren').value) || 0,
    };

    if (!payload.category) {
      alert('Selecciona una categoría profesional.');
      btn.disabled = false;
      btn.textContent = 'Calcular coste';
      return;
    }

    try {
      const result = await api('/api/simulate', { method: 'POST', body: JSON.stringify(payload) });
      renderResult(result);
      $('resultSection').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      loadHistory();
    } catch (err) {
      alert(`Error: ${err.message}`);
    } finally {
      btn.disabled = false;
      btn.textContent = 'Calcular coste';
    }
  });

  // -------------------------------------------------------
  // Renderizado del resultado de simulación
  // -------------------------------------------------------
  function renderResult(d) {
    const rs = $('resultSection');
    rs.hidden = false;
    // Auto-abrir desglose
    const desgloseDetails = rs.querySelector('details.details-block');
    if (desgloseDetails) desgloseDetails.open = true;

    // Ficha principal
    $('heroCoste').textContent = fmt(d.coste_total_empresa_mes_eur);
    $('valBruto').textContent = fmt(d.bruto_mensual_eur);
    $('valNeto').textContent = fmt(d.neto_mensual_eur);
    $('valAnual').textContent = fmt(d.coste_total_empresa_anual_eur);
    $('fichaContext').textContent = `${d.categoria} · ${d.contrato} · ${d.jornada_pct}% jornada · ${d.pagas} pagas`;

    // Cifras mensuales
    $('valSSEmp').textContent = fmt(d.ss_empresa_mes_eur);
    $('valSSTrab').textContent = fmt(d.ss_trabajador_mes_eur);
    $('valIRPFPct').textContent = (d.irpf_retencion_pct ?? 0).toFixed(1);
    $('valIRPF').textContent = fmt(d.irpf_mensual_eur);

    // Devengos
    const tbody = $('devengosTable').querySelector('tbody');
    tbody.innerHTML = (d.devengos || []).map(dv => `
      <tr>
        <td>${esc(dv.concepto)}</td>
        <td>${fmt(dv.eur)}</td>
        <td style="color:var(--muted);font-size:11px">${esc(dv.fuente || '')}</td>
      </tr>`).join('');

    // SS detalle
    const ss = d.ss_detalle || {};
    const ssRows = Object.entries(ss)
      .filter(([, v]) => typeof v === 'number')
      .map(([k, v]) => `<div class="desglose-row"><span>${esc(k.replace(/_/g, ' '))}</span><span>${fmt(v)}</span></div>`)
      .join('');
    $('ssDetalle').innerHTML = ssRows || '<span style="color:var(--muted)">Sin detalle disponible.</span>';

    // Notas
    $('notasBox').innerHTML = (d.notas || []).map(n => `<p style="margin:3px 0">⚠ ${esc(n)}</p>`).join('');

    // Condiciones del convenio para este tipo de contrato
    const cBox = $('condicionesBox');
    const cDet = $('condicionesDetalles');
    if (cBox && cDet && d.condiciones_convenio && d.condiciones_convenio.length) {
      cBox.innerHTML = d.condiciones_convenio.map(s => `
        <details style="margin-bottom:6px;border:1px solid var(--line);border-radius:8px;overflow:hidden">
          <summary style="padding:9px 14px;cursor:pointer;font-size:13px;font-weight:500;color:var(--pgk-green);background:rgba(220,203,179,.08);list-style:none">${esc(s.title)}</summary>
          ${(s.items || []).map(item => `
            <div style="padding:9px 14px;border-top:1px solid var(--line);font-size:13px;line-height:1.5">
              <strong>${esc(item.label)}</strong>: ${esc(item.detail)}
              ${item.source ? `<span style="color:var(--muted);font-size:11px"> · ${esc(item.source)}</span>` : ''}
            </div>`).join('')}
        </details>`).join('');
      cDet.hidden = false;
    } else if (cDet) {
      cDet.hidden = true;
    }
  }

  // -------------------------------------------------------
  // Alertas
  // -------------------------------------------------------
  const ALERT_LABELS = {
    fin_contrato: 'Fin de contrato',
    fin_prueba: 'Fin período de prueba',
    vencimiento_titulo: 'Vencimiento título',
    otro: 'Otro',
  };

  async function loadAlerts() {
    const box = $('alertsBox');
    try {
      const alerts = await api('/api/alerts');
      if (!alerts.length) {
        box.innerHTML = '<p class="empty-msg">Sin alertas activas.</p>';
        return;
      }
      const today = new Date().toISOString().slice(0, 10);
      box.innerHTML = alerts.map(a => {
        const urgent = a.due_date <= today;
        return `
          <div class="historial-row">
            <div>
              <span style="font-size:13px;font-weight:500;color:${urgent ? 'var(--warn)' : 'var(--ink)'}">${esc(a.title)}</span>
              ${a.worker_name ? `<span style="font-size:12px;color:var(--muted)"> · ${esc(a.worker_name)}</span>` : ''}
              <br>
              <span style="font-size:12px;color:var(--muted)">${esc(ALERT_LABELS[a.alert_type] || a.alert_type)} · ${fmtDate(a.due_date)}</span>
            </div>
            <button class="btn-link" onclick="window._dismissAlert(${a.id})" style="font-size:12px;white-space:nowrap">Resolver ✓</button>
          </div>`;
      }).join('');
    } catch {
      box.textContent = 'Error cargando alertas.';
    }
  }

  window._dismissAlert = async function (id) {
    try {
      await api(`/api/alerts/${id}/dismiss`, { method: 'POST' });
      loadAlerts();
    } catch (e) { alert(e.message); }
  };

  $('toggleAlertForm').addEventListener('click', () => {
    const af = $('alertForm');
    af.hidden = !af.hidden;
    $('toggleAlertForm').textContent = af.hidden ? '+ Añadir alerta' : '− Cancelar';
  });

  $('alertForm').addEventListener('submit', async e => {
    e.preventDefault();
    const alertType = $('alertType').value;
    const worker = $('alertWorker').value.trim();
    const title = worker
      ? `${ALERT_LABELS[alertType] || alertType} — ${worker}`
      : (ALERT_LABELS[alertType] || alertType);
    try {
      await api('/api/alerts', {
        method: 'POST',
        body: JSON.stringify({
          alert_type: alertType,
          title,
          due_date: $('alertDate').value,
          worker_name: worker,
          description: $('alertDesc').value.trim(),
        }),
      });
      e.target.reset();
      $('alertForm').hidden = true;
      $('toggleAlertForm').textContent = '+ Añadir alerta';
      loadAlerts();
    } catch (err) { alert(err.message); }
  });

  // -------------------------------------------------------
  // Historial de consultas
  // -------------------------------------------------------
  async function loadHistory() {
    const box = $('historialBox');
    try {
      const history = await api('/api/history');
      if (!history.length) {
        box.innerHTML = '<p class="empty-msg">Sin consultas previas.</p>';
        return;
      }
      box.innerHTML = history.map(h => `
        <div class="historial-row">
          <span style="font-size:13px;color:var(--ink)">${esc(h.query_summary)}</span>
          <span style="font-size:13px;font-weight:500;color:var(--pgk-green);white-space:nowrap">${typeof h.coste_empresa === 'number' ? fmt(h.coste_empresa) : '—'}</span>
        </div>`).join('');
    } catch {
      box.textContent = 'Error cargando historial.';
    }
  }

  // -------------------------------------------------------
  // Clientes (solo admin)
  // -------------------------------------------------------
  async function loadConveniosList() {
    try {
      state.conveniosList = await api('/api/convenios');
      const sel = $('clientConvenio');
      if (sel) {
        sel.innerHTML = state.conveniosList.map(c =>
          `<option value="${esc(c.id)}">${esc(c.nombre)}</option>`
        ).join('');
      }
    } catch {}
  }

  async function loadClients() {
    const box = $('clientsBox');
    if (!box) return;
    try {
      const clients = await api('/api/clients');
      if (!clients.length) {
        box.innerHTML = '<p class="empty-msg">Sin clientes registrados.</p>';
        return;
      }
      box.innerHTML = `
        <table class="clients-table">
          <thead>
            <tr>
              <th>Empresa</th>
              <th>CIF</th>
              <th>Convenio</th>
            </tr>
          </thead>
          <tbody>
            ${clients.map(c => `
              <tr>
                <td>${esc(c.empresa)}</td>
                <td style="color:var(--muted)">${esc(c.cif)}</td>
                <td style="color:var(--muted);font-size:12px">${esc((c.convenio_id || '').replace('convenio_', '').replace(/_/g, ' '))}</td>
              </tr>`).join('')}
          </tbody>
        </table>`;
    } catch (e) {
      box.innerHTML = `<p class="empty-msg">Error: ${esc(e.message)}</p>`;
    }
  }

  const toggleClientForm = $('toggleClientForm');
  const clientForm = $('clientForm');
  if (toggleClientForm && clientForm) {
    toggleClientForm.addEventListener('click', () => {
      clientForm.hidden = !clientForm.hidden;
      toggleClientForm.textContent = clientForm.hidden ? '+ Nuevo cliente' : '− Cancelar';
    });
    clientForm.addEventListener('submit', async e => {
      e.preventDefault();
      try {
        await api('/api/clients', {
          method: 'POST',
          body: JSON.stringify({
            empresa: $('clientEmpresa').value.trim(),
            cif: $('clientCif').value.trim(),
            convenio_id: $('clientConvenio').value,
            provincia: $('clientProvincia').value.trim(),
          }),
        });
        clientForm.reset();
        clientForm.hidden = true;
        toggleClientForm.textContent = '+ Nuevo cliente';
        loadClients();
      } catch (err) { alert(err.message); }
    });
  }

  // -------------------------------------------------------
  // Logout
  // -------------------------------------------------------
  $('logoutBtn').addEventListener('click', async () => {
    try { await api('/api/auth/logout', { method: 'POST' }); } catch {}
    window.location.href = '/';
  });

  // -------------------------------------------------------
  // Arranque
  // -------------------------------------------------------
  init();
})();
