const form = document.getElementById("upload-form");
const fileInput = document.getElementById("file-input");
const progressWrap = document.getElementById("progress-wrap");
const progressFill = document.getElementById("progress-fill");
const progressText = document.getElementById("progress-text");
const errorMsg = document.getElementById("error-msg");
const resultsSection = document.getElementById("results-section");
const resultsBody = document.getElementById("results-body");
const fitFilter = document.getElementById("fit-filter");
const downloadLink = document.getElementById("download-link");
const fileName = document.getElementById("file-name");

let allResults = [];

fileInput.addEventListener("change", () => {
  fileName.textContent = fileInput.files[0]?.name || "Choose CSV file";
});

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  errorMsg.hidden = true;
  resultsSection.hidden = true;
  const file = fileInput.files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append("file", file);

  const resp = await fetch("/upload", { method: "POST", body: formData });
  const data = await resp.json();
  if (!resp.ok) {
    showError(data.error || "Upload failed");
    return;
  }

  progressWrap.hidden = false;
  poll(data.job_id);
});

async function poll(jobId) {
  const resp = await fetch(`/status/${jobId}`);
  const data = await resp.json();
  if (!resp.ok) {
    showError(data.error || "Something went wrong");
    return;
  }

  const pct = data.total ? Math.round((data.done / data.total) * 100) : 0;
  progressFill.style.width = pct + "%";
  progressText.textContent = `${data.done} / ${data.total} processed`;

  if (data.status === "done") {
    progressWrap.hidden = true;
    allResults = data.results;
    downloadLink.href = `/download/${jobId}`;
    renderResults();
    resultsSection.hidden = false;
  } else {
    setTimeout(() => poll(jobId), 1200);
  }
}

fitFilter.addEventListener("change", renderResults);

function renderResults() {
  const filter = fitFilter.value;
  resultsBody.innerHTML = "";
  for (const r of allResults) {
    if (filter && r.fit !== filter) continue;
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(r.name)}</td>
      <td>${escapeHtml(r.email)}</td>
      <td>${escapeHtml(r.company)}</td>
      <td><span class="fit-badge fit-${r.fit}">${r.fit}</span></td>
      <td>${escapeHtml(r.fit_reason)}</td>
      <td>${escapeHtml(r.subject)}<br><button class="copy-btn" data-copy="subject">Copy</button></td>
      <td class="body-cell">${escapeHtml(r.body)}<br><button class="copy-btn" data-copy="body">Copy</button></td>
    `;
    tr.querySelectorAll(".copy-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const field = btn.dataset.copy;
        navigator.clipboard.writeText(r[field]);
        btn.textContent = "Copied!";
        setTimeout(() => (btn.textContent = "Copy"), 1600);
      });
    });
    resultsBody.appendChild(tr);
  }
}

function showError(msg) {
  errorMsg.textContent = msg;
  errorMsg.hidden = false;
  progressWrap.hidden = true;
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str || "";
  return div.innerHTML;
}
