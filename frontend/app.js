const API_BASE = window.JOBTRACKER_CONFIG.API_BASE_URL;
const STATUSES = ["new", "reviewed", "accepted", "applied", "interviewing", "rejected", "filled"];

let currentTab = "active";
let editingJobId = null;

const $ = (selector) => document.querySelector(selector);

async function apiFetch(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (response.status === 204) return null;

  let body = null;
  const text = await response.text();
  if (text) body = JSON.parse(text);

  if (!response.ok) {
    const error = new Error((body && body.error) || `Request failed (${response.status})`);
    error.status = response.status;
    throw error;
  }
  return body;
}

// ---------- Auth ----------

async function init() {
  try {
    await apiFetch("/api/jobs?active=true");
    showDashboard();
  } catch (err) {
    await showAuthScreen();
  }
}

async function showAuthScreen() {
  const status = await apiFetch("/api/auth/status");
  const isSetup = !status.password_set;

  $("#auth-subtitle").textContent = isSetup
    ? "Set a password to secure your tracker"
    : "Sign in to continue";
  $("#auth-submit-label").textContent = isSetup ? "Set password" : "Sign in";
  $("#auth-form").dataset.mode = isSetup ? "setup" : "login";

  $("#auth-screen").classList.remove("hidden");
  $("#dashboard-screen").classList.add("hidden");
}

$("#auth-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const mode = e.target.dataset.mode;
  const password = $("#auth-password").value;
  $("#auth-error").classList.add("hidden");

  try {
    await apiFetch(`/api/auth/${mode}`, {
      method: "POST",
      body: JSON.stringify({ password }),
    });
    showDashboard();
  } catch (err) {
    $("#auth-error").textContent = err.message;
    $("#auth-error").classList.remove("hidden");
  }
});

// ---------- Dashboard ----------

function showDashboard() {
  $("#auth-screen").classList.add("hidden");
  $("#dashboard-screen").classList.remove("hidden");
  setTab("active");
}

function setTab(tab) {
  currentTab = tab;
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tab);
  });
  loadJobs();
}

document.querySelectorAll(".tab-btn").forEach((btn) => {
  btn.addEventListener("click", () => setTab(btn.dataset.tab));
});

async function loadJobs() {
  const active = currentTab === "active";
  let jobs;
  try {
    jobs = await apiFetch(`/api/jobs?active=${active}`);
  } catch (err) {
    if (err.status === 401) return showAuthScreen();
    throw err;
  }
  renderJobs(jobs);
}

function renderJobs(jobs) {
  const tbody = $("#jobs-tbody");
  tbody.innerHTML = "";
  $("#jobs-empty").classList.toggle("hidden", jobs.length > 0);

  for (const job of jobs) {
    const tr = document.createElement("tr");
    tr.className = "border-t border-slate-100";
    tr.innerHTML = `
      <td class="px-4 py-3">${escapeHtml(job.company_name)}</td>
      <td class="px-4 py-3">${escapeHtml(job.role_title)}</td>
      <td class="px-4 py-3"></td>
      <td class="px-4 py-3">
        ${job.job_url ? `<a href="${escapeHtml(job.job_url)}" target="_blank" rel="noopener" class="text-slate-500 hover:underline">Open ↗</a>` : ""}
      </td>
      <td class="px-4 py-3 text-slate-500">${formatDate(job.date_found)}</td>
      <td class="px-4 py-3 text-slate-500">${formatDate(job.date_posted) || "N/A"}</td>
      <td class="px-4 py-3"><span class="status-badge">${escapeHtml(job.found_by)}</span></td>
      <td class="px-4 py-3 text-right">
        <button class="edit-btn text-sm text-slate-500 hover:underline">Edit</button>
      </td>
    `;

    const statusSelect = document.createElement("select");
    statusSelect.className = "rounded-lg border border-slate-300 px-2 py-1 text-sm";
    for (const status of STATUSES) {
      const opt = document.createElement("option");
      opt.value = status;
      opt.textContent = status;
      opt.selected = status === job.status;
      statusSelect.appendChild(opt);
    }
    statusSelect.addEventListener("change", () => updateStatus(job.job_id, statusSelect.value));
    tr.children[2].appendChild(statusSelect);

    tr.querySelector(".edit-btn").addEventListener("click", () => openEditModal(job));
    tbody.appendChild(tr);
  }
}

async function updateStatus(jobId, status) {
  await apiFetch(`/api/jobs/${encodeURIComponent(jobId)}`, {
    method: "PUT",
    body: JSON.stringify({ status }),
  });
  loadJobs();
}

function formatDate(iso) {
  if (!iso) return "";
  return iso.slice(0, 10);
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str || "";
  return div.innerHTML;
}

// ---------- Add / Edit modal ----------

$("#add-job-btn").addEventListener("click", () => openAddModal());
$("#cancel-job-btn").addEventListener("click", closeModal);

function openAddModal() {
  editingJobId = null;
  $("#job-modal-title").textContent = "Add Manual Job";
  $("#delete-job-btn").classList.add("hidden");
  $("#job-form").reset();
  $("#job-modal").classList.remove("hidden");
}

function openEditModal(job) {
  editingJobId = job.job_id;
  $("#job-modal-title").textContent = "Edit Job";
  $("#delete-job-btn").classList.remove("hidden");

  const form = $("#job-form");
  form.company_name.value = job.company_name || "";
  form.role_title.value = job.role_title || "";
  form.status.value = job.status || "new";
  form.job_url.value = job.job_url || "";
  form.job_description.value = job.job_description || "";
  form.notes.value = job.notes || "";

  $("#job-modal").classList.remove("hidden");
}

function closeModal() {
  $("#job-modal").classList.add("hidden");
  editingJobId = null;
}

$("#job-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const payload = {
    company_name: form.company_name.value,
    role_title: form.role_title.value,
    status: form.status.value,
    job_url: form.job_url.value,
    job_description: form.job_description.value,
    notes: form.notes.value,
  };

  if (editingJobId) {
    await apiFetch(`/api/jobs/${encodeURIComponent(editingJobId)}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  } else {
    await apiFetch("/api/jobs", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  closeModal();
  loadJobs();
});

$("#delete-job-btn").addEventListener("click", async () => {
  if (!editingJobId) return;
  if (!confirm("Delete this position? This cannot be undone.")) return;
  await apiFetch(`/api/jobs/${encodeURIComponent(editingJobId)}`, { method: "DELETE" });
  closeModal();
  loadJobs();
});

init();
