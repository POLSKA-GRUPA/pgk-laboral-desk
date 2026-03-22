/* PGK Laboral Desk — app.js */
(function () {
  'use strict';

  // ------------------------------------------------------------------
  // Utilidades
  // ------------------------------------------------------------------
  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const fmt = n => n == null ? '—' : Number(n).toLocaleString('es-ES', {minimumFractionDigits: 2, maximumFractionDigits: 2}) + '\u00a0€';
  const fmtShort = n => n == null ? '—' : Number(n).toLocaleString('es-ES', {minimumFractionDigits: 0, maximumFractionDigits: 0}) + '\u00a0€';

  function md(text) {
    return String(text ?? '')
      .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.+?)\*/g, '<em>$1</em>')
      .replace(/\n/g, '<br>');
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
    const [cats, types, tiposDespido] = await Promise.all([
      api('/api/categories'),
      api('/api/contract-types'),
      api('/api/tipos-despido'),
    ]);

    state.categories = cats || [];
    state.contractTypes = types || [];
    state.tiposDespido = tiposDespido || [];

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
  // Chat conversacional
  // ------------------------------------------------------------------
  function setupChat() {
    const form = $('chatForm');
    const input = $('chatInput');
    const resetBtn = $('chatResetBtn');

    form.addEventListener('submit', async e => {
      e.preventDefault();
      const msg = input.value.trim();
      if (!msg) return;
      input.value = '';
      addBubble(msg, 'user');
      const res = await api('/api/chat', { method: 'POST', body: JSON.stringify({ message: msg }) });
      if (res) handleChatResponse(res);
    });

    resetBtn.addEventListener('click', async () => {
      await api('/api/chat/reset', { method: 'POST' });
      $('chatLog').innerHTML = '<div class="chat-bubble system">Hola. Dime qu\u00e9 puesto quieres cubrir y te calculo el coste real.</div>';
      $('resultSection').hidden = true;
      $('resultPlaceholder').hidden = false;
    });
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

    if (res.type === 'not_found') {
      addBubble(res.message || 'No encontré esa categoría. Intenta con otra descripción.', 'system');
    }
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
      };
      const res = await api('/api/simulate', { method: 'POST', body: JSON.stringify(data) });
      if (res?.error) { alert(res.error); return; }
      if (res) renderResult(res);
    });
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

    const tbody = $('devengosTable').querySelector('tbody');
    tbody.innerHTML = (d.devengos || []).map(dv =>
      `<tr><td>${esc(dv.concepto)}</td><td>${fmt(dv.eur)}</td><td style="color:var(--muted);font-size:12px">${esc(dv.fuente || '')}</td></tr>`
    ).join('');

    const ssD = d.ss_detalle || {};
    $('ssDetalle').innerHTML = Object.entries(ssD)
      .filter(([k]) => !['grupo_cotizacion', 'emp_total', 'trab_total'].includes(k))
      .map(([k, v]) => `<div class="desglose-row"><span>${esc(k.replace(/_/g, ' '))}</span><span>${typeof v === 'number' ? fmt(v) : esc(String(v))}</span></div>`)
      .join('') || '<span style="color:var(--muted);font-size:13px">—</span>';

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

    $('desgloseDetails').open = true;
    $('resultSection').scrollIntoView({ behavior: 'smooth', block: 'nearest' });
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
      if (res?.error) { alert(res.error); return; }
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
      box.innerHTML = '<p class="empty-msg">Sin trabajadores registrados. Añade el primero para hacer seguimiento y calcular despidos en un clic.</p>';
      if (badge) badge.hidden = true;
      return;
    }

    if (badge) {
      badge.textContent = employees.length;
      badge.hidden = false;
    }

    const today = new Date().toISOString().split('T')[0];
    box.innerHTML = `
      <table class="clients-table">
        <thead><tr><th>Nombre</th><th>Categoría</th><th>Contrato</th><th>Inicio</th><th>Bruto/mes</th><th>Acciones</th></tr></thead>
        <tbody>
          ${employees.map(emp => {
            const vence = emp.fecha_fin ? (emp.fecha_fin <= today ? '⚠ Vencido' : emp.fecha_fin) : '—';
            return `<tr>
              <td><strong>${esc(emp.nombre)}</strong></td>
              <td>${esc(emp.categoria.replace(/\.$/, ''))}</td>
              <td>${esc(emp.contrato_tipo)} · ${emp.jornada_horas}h/sem</td>
              <td>${esc(emp.fecha_inicio)}${emp.fecha_fin ? `<br><span style="font-size:11px;color:var(--muted)">${esc(vence)}</span>` : ''}</td>
              <td>${emp.salario_bruto_mensual ? fmt(emp.salario_bruto_mensual) : '<span style="color:var(--muted)">—</span>'}</td>
              <td>
                <button class="btn-link" style="font-size:12px;color:var(--danger)" onclick="window._despidirEmpleado(${emp.id})">Despedir</button>
                &nbsp;·&nbsp;
                <button class="btn-link" style="font-size:12px" onclick="window._darDeBajaEmpleado(${emp.id})">Dar de baja</button>
              </td>
            </tr>`;
          }).join('')}
        </tbody>
      </table>`;
  }

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
      };
      const res = await api('/api/employees', { method: 'POST', body: JSON.stringify(data) });
      if (res?.error) { alert(res.error); return; }
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

  document.addEventListener('DOMContentLoaded', () => {
    init().then(() => {
      if (state.user?.role === 'admin') setupClientForm();
    });
  });

})();
