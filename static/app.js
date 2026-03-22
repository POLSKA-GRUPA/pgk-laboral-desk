const queryInput = document.getElementById("queryInput");
const analyzeButton = document.getElementById("analyzeButton");
const clearButton = document.getElementById("clearButton");
const answerBox = document.getElementById("answerBox");
const clarificationsBox = document.getElementById("clarificationsBox");
const requestSummary = document.getElementById("requestSummary");
const payrollBox = document.getElementById("payrollBox");
const conditionsBox = document.getElementById("conditionsBox");
const apiStatus = document.getElementById("apiStatus");
const responseBadge = document.getElementById("responseBadge");
const convenioName = document.getElementById("convenioName");
const decisionBody = document.querySelector(".decision-body");
const kpiBar = document.getElementById("kpiBar");
const kpiTotal = document.getElementById("kpiTotal");

document.querySelectorAll(".prompt-chip").forEach((button) => {
  button.addEventListener("click", () => {
    queryInput.value = button.dataset.prompt || "";
    queryInput.focus();
  });
});

function resetKpi() {
  kpiTotal.textContent = "\u2014";
  kpiBar.classList.add("kpi-pending");
}

function updateKpi(totalEur) {
  kpiTotal.textContent = totalEur.toFixed(2);
  kpiBar.classList.remove("kpi-pending");
}

clearButton.addEventListener("click", () => {
  queryInput.value = "";
  answerBox.textContent = "La respuesta aparecer\u00e1 aqu\u00ed.";
  answerBox.classList.add("empty");
  clarificationsBox.classList.add("hidden");
  clarificationsBox.innerHTML = "";
  decisionBody.classList.add("no-clarifications");
  requestSummary.innerHTML = "Esperando an\u00e1lisis.";
  payrollBox.innerHTML = "Sin c\u00e1lculo todav\u00eda.";
  conditionsBox.innerHTML = "Aqu\u00ed se mostrar\u00e1n las condiciones relevantes.";
  responseBadge.textContent = "Pendiente";
  responseBadge.className = "response-badge muted";
  resetKpi();
});

analyzeButton.addEventListener("click", analyzeQuery);
queryInput.addEventListener("keydown", (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
    analyzeQuery();
  }
});

async function analyzeQuery() {
  const query = queryInput.value.trim();
  if (!query) {
    return;
  }

  analyzeButton.disabled = true;
  analyzeButton.textContent = "Analizando...";
  responseBadge.textContent = "Interpretando";
  responseBadge.className = "response-badge muted";

  try {
    const response = await fetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.error || "Error de an\u00e1lisis");
    }

    renderResult(result);
  } catch (error) {
    answerBox.textContent = error.message;
    answerBox.classList.remove("empty");
    responseBadge.textContent = "Error";
    responseBadge.className = "response-badge needs";
    resetKpi();
  } finally {
    analyzeButton.disabled = false;
    analyzeButton.textContent = "Analizar";
  }
}

function renderResult(result) {
  convenioName.textContent = result.convenio.nombre;
  answerBox.textContent = result.answer;
  answerBox.classList.remove("empty");

  responseBadge.textContent = result.status === "ready"
    ? "Pre-n\u00f3mina disponible"
    : `Faltan ${result.clarifications.length} datos`;
  responseBadge.className = result.status === "ready" ? "response-badge ready" : "response-badge needs";

  if (result.clarifications.length > 0) {
    clarificationsBox.classList.remove("hidden");
    decisionBody.classList.remove("no-clarifications");
    clarificationsBox.innerHTML = `
      <h3>Datos que faltan para cerrar el caso</h3>
      <ul>${result.clarifications.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>
    `;
  } else {
    clarificationsBox.classList.add("hidden");
    clarificationsBox.innerHTML = "";
    decisionBody.classList.add("no-clarifications");
  }

  if (result.payroll_draft) {
    updateKpi(result.payroll_draft.totals.total_devengado_convenio_eur);
  } else {
    resetKpi();
  }

  requestSummary.innerHTML = buildRequestSummary(result.request, result.contract_fit);
  payrollBox.innerHTML = buildPayroll(result.payroll_draft);
  conditionsBox.innerHTML = buildConditions(result.relevant_sections);
}

function buildRequestSummary(request, contractFit) {
  const sensitivePoint = buildSensitivePoint(contractFit);
  const cards = [
    summaryCard("Categor\u00eda", request.category_match.row ? request.category_match.row.category : "Sin cerrar"),
    summaryCard("Modalidad", request.contract_type || "No detectada"),
    summaryCard("Jornada", request.weekly_hours ? `${request.weekly_hours} h/semana` : "No detectada"),
    summaryCard("Trienios", `${request.trienios}`),
    summaryCard("Pagas extra", request.extras_prorated === null ? "No indicado" : request.extras_prorated ? "Prorrateadas" : "14 pagas"),
    summaryCard("Punto sensible", sensitivePoint),
  ];
  return cards.join("");
}

function buildSensitivePoint(contractFit) {
  if (!contractFit || contractFit.status === "not_requested") {
    return "Sin alerta contractual";
  }
  if (contractFit.status === "clear") {
    return "Encaje provisional correcto";
  }
  return "Periodo de actividad por definir";
}

function summaryCard(label, value) {
  return `
    <div class="summary-card">
      <span class="label">${escapeHtml(label)}</span>
      <span class="value">${escapeHtml(String(value))}</span>
    </div>
  `;
}

function buildPayroll(payroll) {
  if (!payroll) {
    return "La pre-n\u00f3mina se genera cuando la categor\u00eda y la jornada est\u00e1n claras.";
  }

  const metrics = [
    payrollMetric("Categor\u00eda", payroll.category),
    payrollMetric("Jornada aplicada", `${Math.round(payroll.jornada_ratio * 100)} %`),
    payrollMetric("Salario base 14 pagas", `${payroll.monthly_reference_14_payments_eur.toFixed(2)} EUR`),
    payrollMetric("Hora referencia", `${payroll.hourly_reference_eur.toFixed(2)} EUR`),
  ].join("");

  const rows = payroll.devengos.map((row) => `
    <tr>
      <td>
        <strong>${escapeHtml(row.concept)}</strong>
        <div class="condition-source">${escapeHtml(row.source)}</div>
        ${row.note ? `<div class="condition-source">${escapeHtml(row.note)}</div>` : ""}
      </td>
      <td>${row.amount_eur.toFixed(2)} EUR</td>
    </tr>
  `).join("");

  const notes = payroll.pending_items.map((item) => `<li>${escapeHtml(item)}</li>`).join("");

  return `
    <div class="payroll-summary">${metrics}</div>
    <table class="payroll-table">
      <thead>
        <tr>
          <th>Concepto</th>
          <th>Importe</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
    </table>
    <div class="payroll-total">Total devengado convenio: ${payroll.totals.total_devengado_convenio_eur.toFixed(2)} EUR</div>
    <ul class="payroll-notes">${notes}</ul>
  `;
}

function payrollMetric(label, value) {
  return `
    <div class="payroll-metric">
      <span class="label">${escapeHtml(label)}</span>
      <span class="value">${escapeHtml(value)}</span>
    </div>
  `;
}

function buildConditions(sections) {
  return sections.map((section) => `
    <details class="conditions-section" open>
      <summary class="conditions-title">
        <strong>${escapeHtml(section.title)}</strong>
        <span class="conditions-preview">${escapeHtml(buildSectionPreview(section.items))}</span>
      </summary>
      ${section.items.map((item) => `
        <div class="condition-item">
          <strong>${escapeHtml(item.label)}</strong>
          <div>${escapeHtml(item.detail)}</div>
          <div class="condition-source">${escapeHtml(item.source)}</div>
        </div>
      `).join("")}
    </details>
  `).join("");
}

function buildSectionPreview(items) {
  return items.slice(0, 3).map((item) => item.label).join(" \u00b7 ");
}

async function loadHealth() {
  try {
    const response = await fetch("/api/health");
    const result = await response.json();
    if (result.ok) {
      apiStatus.textContent = "API conectada";
      convenioName.textContent = "Convenio acu\u00e1ticas 2025-2027";
    }
  } catch (error) {
    apiStatus.textContent = "API no disponible";
  }
}

function escapeHtml(value) {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

decisionBody.classList.add("no-clarifications");
resetKpi();
loadHealth();
