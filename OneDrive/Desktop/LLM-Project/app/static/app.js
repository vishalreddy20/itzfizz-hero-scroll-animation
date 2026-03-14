const statusEl = document.getElementById("status");
const extractionEl = document.getElementById("extraction");
const analysisEl = document.getElementById("analysis");
const redlinesEl = document.getElementById("redlines");
const reportEl = document.getElementById("report");
const playbookOutputEl = document.getElementById("playbookOutput");
const datasetOutputEl = document.getElementById("datasetOutput");
const datasetStatusSummaryEl = document.getElementById("datasetStatusSummary");
const datasetCatalogEl = document.getElementById("datasetCatalog");
const summaryModeEl = document.getElementById("summaryMode");
const summaryRiskEl = document.getElementById("summaryRisk");
const summaryClausesEl = document.getElementById("summaryClauses");
const summaryRedlinesEl = document.getElementById("summaryRedlines");
const criticalListEl = document.getElementById("criticalList");
const highListEl = document.getElementById("highList");
const clauseTableBodyEl = document.getElementById("clauseTableBody");
const redlineCardsEl = document.getElementById("redlineCards");

function setStatus(text, tone = "ok") {
  statusEl.textContent = text;
  statusEl.classList.remove("error", "loading");
  if (tone === "error") {
    statusEl.classList.add("error");
  }
  if (tone === "loading") {
    statusEl.classList.add("loading");
  }
}

function authHeaders(extra = {}) {
  const apiKey = document.getElementById("apiKey").value.trim();
  if (!apiKey) {
    return extra;
  }
  return { ...extra, "X-API-Key": apiKey };
}

function getPayload() {
  return {
    contract_text: document.getElementById("contractText").value,
    jurisdiction: document.getElementById("jurisdiction").value || "Unknown",
    contract_type: document.getElementById("contractType").value || "Unknown",
    counterparty_type: document.getElementById("counterpartyType").value || "Vendor",
    stance: document.getElementById("stance").value,
    audience: document.getElementById("audience").value,
    pipeline_mode: document.getElementById("pipelineMode").value,
  };
}

function renderResult(result) {
  extractionEl.textContent = JSON.stringify(result.extraction, null, 2);
  analysisEl.textContent = JSON.stringify(result.analysis, null, 2);
  redlinesEl.textContent = JSON.stringify(result.redlines, null, 2);
  const header = [
    `Request ID: ${result.request_id || "n/a"}`,
    `Mode: ${result.pipeline_mode_used || "unknown"}`,
    `Providers: ${(result.providers_used || []).join(", ")}`,
    `Fallback: ${result.fallback_reason || "none"}`,
    "",
  ].join("\n");
  reportEl.textContent = `${header}${result.report_markdown}`;
  summaryModeEl.textContent = result.pipeline_mode_used || "unknown";
  summaryRiskEl.textContent = result.analysis?.overall_contract_risk || "N/A";
  summaryClausesEl.textContent = String((result.extraction?.clauses || []).length);
  summaryRedlinesEl.textContent = String((result.redlines || []).length);

  renderRiskPriorityLists(result.analysis?.analysis || []);
  renderClauseTable(result.analysis?.analysis || []);
  renderRedlineCards(result.redlines || []);
}

function renderRiskPriorityLists(items) {
  const critical = items.filter((item) => item.legal_risk === "CRITICAL" || item.negotiation_priority === "MUST CHANGE");
  const high = items.filter((item) => item.legal_risk === "HIGH" || item.negotiation_priority === "SHOULD CHANGE");

  criticalListEl.innerHTML = critical.length
    ? critical
        .map(
          (item) =>
            `<li><strong>${escapeHtml(item.clause_id)} ${escapeHtml(item.clause_type)}</strong><br>${escapeHtml(item.legal_risk_reasoning || item.deviation_summary || "Risk noted")}</li>`,
        )
        .join("")
    : "<li>No critical issues.</li>";

  highListEl.innerHTML = high.length
    ? high
        .map(
          (item) =>
            `<li><strong>${escapeHtml(item.clause_id)} ${escapeHtml(item.clause_type)}</strong><br>${escapeHtml(item.legal_risk_reasoning || item.deviation_summary || "Risk noted")}</li>`,
        )
        .join("")
    : "<li>No high-priority issues.</li>";
}

function renderClauseTable(items) {
  if (!items.length) {
    clauseTableBodyEl.innerHTML = '<tr><td colspan="5" class="empty-row">Run a review to populate clause analysis.</td></tr>';
    return;
  }

  clauseTableBodyEl.innerHTML = items
    .map((item) => {
      const reviewText = item.human_review_required ? "Required" : "Not required";
      return `
        <tr>
          <td>${escapeHtml(item.clause_id)}</td>
          <td>${escapeHtml(item.clause_type)}</td>
          <td><span class="pill ${escapeHtml(item.legal_risk)}">${escapeHtml(item.legal_risk)}</span></td>
          <td><span class="pill ${escapeHtml(priorityPillClass(item.negotiation_priority))}">${escapeHtml(item.negotiation_priority)}</span></td>
          <td>${escapeHtml(reviewText)}</td>
        </tr>
      `;
    })
    .join("");
}

function renderRedlineCards(redlines) {
  if (!redlines.length) {
    redlineCardsEl.innerHTML = '<div class="empty-redline">No redlines generated for the current contract.</div>';
    return;
  }

  redlineCardsEl.innerHTML = redlines
    .map((item) => {
      const preferred = item.redline_versions?.preferred;
      const fallback = item.redline_versions?.fallback;
      const walkAway = item.redline_versions?.walk_away;

      return `
        <article class="redline-card">
          <h4>${escapeHtml(item.clause_id)} ${escapeHtml(item.clause_type)}</h4>
          <div class="redline-meta">${escapeHtml(item.issue_summary || "No issue summary")}</div>
          <div class="redline-tone">
            ${toneChip("Preferred", preferred?.tone)}
            ${toneChip("Fallback", fallback?.tone)}
            ${toneChip("Walk-away", walkAway?.tone)}
          </div>
        </article>
      `;
    })
    .join("");
}

function toneChip(label, tone) {
  if (!tone) {
    return `<span class="pill LOW">${escapeHtml(label)}: n/a</span>`;
  }
  return `<span class="pill MEDIUM">${escapeHtml(label)}: ${escapeHtml(tone)}</span>`;
}

function priorityPillClass(priority) {
  if (priority === "MUST CHANGE") {
    return "CRITICAL";
  }
  if (priority === "SHOULD CHANGE") {
    return "HIGH";
  }
  if (priority === "NICE TO HAVE") {
    return "MEDIUM";
  }
  return "ACCEPT";
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/\"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function renderPayload(element, payload) {
  element.textContent = JSON.stringify(payload, null, 2);
}

function formatDatasetReason(reason) {
  if (!reason) {
    return "Unknown";
  }
  return String(reason)
    .replace("[WinError 10061] No connection could be made because the target machine actively refused it", "Ollama is not running on http://127.0.0.1:11434")
    .replace("No (supported) data files found in cuad", "CUAD could not be resolved from the current source");
}

function renderDatasetStatus(payload) {
  const processState = payload.process_record_ready ? "Ready" : "Blocked";
  const cuadState = payload.cuad_ingest_ready ? "Ready" : "Blocked";
  datasetStatusSummaryEl.innerHTML = `
    <div><strong>Process Record:</strong> ${escapeHtml(processState)}</div>
    <div>${escapeHtml(formatDatasetReason(payload.process_record_reason))}</div>
    <div><strong>Ingest CUAD:</strong> ${escapeHtml(cuadState)}</div>
    <div>${escapeHtml(formatDatasetReason(payload.cuad_ingest_reason))}</div>
  `;
}

function renderDatasetCatalog(datasets) {
  if (!datasets.length) {
    datasetCatalogEl.innerHTML = '<div class="dataset-empty">No datasets configured.</div>';
    return;
  }

  datasetCatalogEl.innerHTML = datasets
    .map(
      (dataset) => `
        <article class="dataset-card">
          <div class="dataset-card-head">
            <h3>${escapeHtml(dataset.name)}</h3>
            <span class="pill LOW">${escapeHtml(dataset.purpose)}</span>
          </div>
          <p>${escapeHtml(dataset.notes || "")}</p>
          <div class="dataset-links">
            ${dataset.huggingface ? `<a href="${escapeHtml(dataset.huggingface)}" target="_blank" rel="noreferrer">Source</a>` : ""}
            ${dataset.direct_download ? `<a href="${escapeHtml(dataset.direct_download)}" target="_blank" rel="noreferrer">Download</a>` : ""}
            ${dataset.paper ? `<a href="${escapeHtml(dataset.paper)}" target="_blank" rel="noreferrer">Paper</a>` : ""}
            ${dataset.github ? `<a href="${escapeHtml(dataset.github)}" target="_blank" rel="noreferrer">Repo</a>` : ""}
          </div>
        </article>
      `,
    )
    .join("");
}

async function refreshDatasetStatus() {
  try {
    const [statusResponse, catalogResponse] = await Promise.all([
      fetch("/api/datasets/status", { headers: authHeaders() }),
      fetch("/api/datasets/catalog", { headers: authHeaders() }),
    ]);

    if (!statusResponse.ok || !catalogResponse.ok) {
      datasetStatusSummaryEl.textContent = "Dataset diagnostics unavailable.";
      datasetCatalogEl.innerHTML = '<div class="dataset-empty">Failed to load dataset catalog.</div>';
      return;
    }

    const status = await statusResponse.json();
    const catalog = await catalogResponse.json();
    renderDatasetStatus(status.payload);
    renderDatasetCatalog(catalog.payload.datasets || []);
  } catch (error) {
    datasetStatusSummaryEl.textContent = `Dataset diagnostics unavailable: ${error}`;
    datasetCatalogEl.innerHTML = '<div class="dataset-empty">Failed to load dataset catalog.</div>';
  }
}

async function runTextReview() {
  const payload = getPayload();
  if (!payload.contract_text.trim()) {
    setStatus("Please paste contract text or upload a file.");
    return;
  }

  setBusy(["runText", "runFile", "runTextAsync"], true);
  setStatus("Running full review pipeline...", "loading");
  const response = await fetch("/api/review", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const data = await response.json();
    setStatus(`Error: ${data.detail || "Unknown error"}`, "error");
    setBusy(["runText", "runFile", "runTextAsync"], false);
    return;
  }

  const result = await response.json();
  renderResult(result);
  setStatus("Review complete. Artifacts also saved in output/.");
  setBusy(["runText", "runFile", "runTextAsync"], false);
}

async function runFileReview() {
  const fileInput = document.getElementById("contractFile");
  const file = fileInput.files[0];
  if (!file) {
    setStatus("Choose a contract file first (.txt, .pdf, .docx).");
    return;
  }

  const formData = new FormData();
  formData.append("contract_file", file);
  formData.append("jurisdiction", document.getElementById("jurisdiction").value || "Unknown");
  formData.append("contract_type", document.getElementById("contractType").value || "Unknown");
  formData.append("counterparty_type", document.getElementById("counterpartyType").value || "Vendor");
  formData.append("stance", document.getElementById("stance").value);
  formData.append("audience", document.getElementById("audience").value);
  formData.append("pipeline_mode", document.getElementById("pipelineMode").value);

  setBusy(["runText", "runFile", "runTextAsync"], true);
  setStatus("Uploading and analyzing contract file...", "loading");
  const response = await fetch("/api/review-file", {
    method: "POST",
    headers: authHeaders(),
    body: formData,
  });

  if (!response.ok) {
    const data = await response.json();
    setStatus(`Error: ${data.detail || "Unknown error"}`, "error");
    setBusy(["runText", "runFile", "runTextAsync"], false);
    return;
  }

  const result = await response.json();
  renderResult(result);
  setStatus("File review complete. Artifacts also saved in output/.");
  setBusy(["runText", "runFile", "runTextAsync"], false);
}

async function ingestPlaybook() {
  const rawText = document.getElementById("playbookText").value.trim();
  if (!rawText) {
    setStatus("Paste playbook text before ingesting.");
    return;
  }

  setBusy(["ingestPlaybook"], true);
  setStatus("Ingesting playbook rules...", "loading");
  const response = await fetch("/api/ingest/playbook", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ raw_text: rawText }),
  });

  if (!response.ok) {
    const data = await response.json();
    setStatus(`Error: ${data.detail || "Unknown error"}`, "error");
    setBusy(["ingestPlaybook"], false);
    return;
  }

  const result = await response.json();
  renderPayload(playbookOutputEl, result.payload);
  setStatus("Playbook ingestion complete.");
  setBusy(["ingestPlaybook"], false);
}

async function processDatasetRecord() {
  const datasetRecord = document.getElementById("datasetRecord").value.trim();
  if (!datasetRecord) {
    setStatus("Paste a dataset record before processing.");
    return;
  }

  setBusy(["processDatasetRecord"], true);
  setStatus("Processing dataset record...", "loading");
  const response = await fetch("/api/process-dataset-record", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ dataset_record: datasetRecord }),
  });

  if (!response.ok) {
    const data = await response.json();
    setStatus(`Error: ${data.detail || "Unknown error"}`, "error");
    setBusy(["processDatasetRecord"], false);
    refreshDatasetStatus();
    return;
  }

  const result = await response.json();
  renderPayload(datasetOutputEl, result.payload);
  setStatus("Dataset record processed.");
  setBusy(["processDatasetRecord"], false);
  refreshDatasetStatus();
}

async function ingestCuad() {
  const limit = Number(document.getElementById("cuadLimit").value || 100);
  setBusy(["ingestCuad"], true);
  setStatus("Running CUAD ingestion...", "loading");
  const response = await fetch("/api/ingest/cuad", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ limit }),
  });

  if (!response.ok) {
    const data = await response.json();
    setStatus(`Error: ${data.detail || "Unknown error"}`, "error");
    setBusy(["ingestCuad"], false);
    refreshDatasetStatus();
    return;
  }

  const result = await response.json();
  if (!result.payload.job_id) {
    renderPayload(datasetOutputEl, result.payload);
    setStatus("CUAD ingestion finished.");
    setBusy(["ingestCuad"], false);
    return;
  }
  setStatus(`CUAD job queued: ${result.payload.job_id}. Polling status...`);
  await pollJobStatus(result.payload.job_id, datasetOutputEl);
  setBusy(["ingestCuad"], false);
  refreshDatasetStatus();
}

async function runTextReviewAsync() {
  const payload = getPayload();
  if (!payload.contract_text.trim()) {
    setStatus("Please paste contract text before running async review.");
    return;
  }

  setBusy(["runText", "runFile", "runTextAsync"], true);
  setStatus("Submitting async review job...", "loading");
  const response = await fetch("/api/review-async", {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const data = await response.json();
    setStatus(`Error: ${data.detail || "Unknown error"}`, "error");
    setBusy(["runText", "runFile", "runTextAsync"], false);
    return;
  }

  const result = await response.json();
  setStatus(`Review job queued: ${result.job_id}. Polling status...`);
  await pollJobStatus(result.job_id, null);
  setBusy(["runText", "runFile", "runTextAsync"], false);
}

async function pollJobStatus(jobId, outputElement) {
  for (let attempt = 0; attempt < 180; attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, 1000));

    const statusResponse = await fetch(`/api/jobs/${jobId}`, {
      headers: authHeaders(),
    });
    if (!statusResponse.ok) {
      const data = await statusResponse.json();
      setStatus(`Job polling error: ${data.detail || "Unknown error"}`, "error");
      return;
    }

    const status = await statusResponse.json();
    if (outputElement) {
      renderPayload(outputElement, status);
    }
    if (status.status === "completed") {
      if (status.job_type === "review" && status.result) {
        renderResult(status.result);
      }
      setStatus(`Job ${jobId} completed.`);
      return;
    }
    if (status.status === "failed") {
      setStatus(`Job ${jobId} failed: ${status.error || "Unknown error"}`, "error");
      return;
    }
  }
  setStatus(`Job ${jobId} is still running. Check again in a moment.`);
}

function setBusy(buttonIds, busy) {
  buttonIds.forEach((id) => {
    const button = document.getElementById(id);
    if (button) {
      button.disabled = busy;
    }
  });
}

function loadSampleText() {
  document.getElementById("contractText").value = [
    "MASTER SERVICES AGREEMENT",
    "This Agreement is effective January 10, 2026 between Alpha Systems Inc. and Beta Retail LLC.",
    "Customer may terminate for convenience with 10 days notice.",
    "Provider shall indemnify Customer for claims arising from this Agreement.",
    "Provider liability shall be unlimited.",
    "This Agreement is governed by the laws of California.",
  ].join("\n\n");
  setStatus("Sample contract text loaded.");
}

function clearForm() {
  document.getElementById("contractFile").value = "";
  document.getElementById("contractText").value = "";
  document.getElementById("playbookText").value = "";
  document.getElementById("datasetRecord").value = "";
  setStatus("Form cleared.");
}

document.getElementById("runText").addEventListener("click", runTextReview);
document.getElementById("runFile").addEventListener("click", runFileReview);
document.getElementById("runTextAsync").addEventListener("click", runTextReviewAsync);
document.getElementById("ingestPlaybook").addEventListener("click", ingestPlaybook);
document.getElementById("processDatasetRecord").addEventListener("click", processDatasetRecord);
document.getElementById("ingestCuad").addEventListener("click", ingestCuad);
document.getElementById("refreshDatasetStatus").addEventListener("click", refreshDatasetStatus);
document.getElementById("loadSample").addEventListener("click", loadSampleText);
document.getElementById("clearForm").addEventListener("click", clearForm);

refreshDatasetStatus();
