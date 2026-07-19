let dictionaryCache = {
  organ: null,
  species: null,
  stain: null
};

function textOrDash(value) {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  return value;
}

function buildFilters() {
  const params = new URLSearchParams();

  const source = document.getElementById("feedback-source-filter").value;
  const status = document.getElementById("feedback-status-filter").value;
  const type = document.getElementById("feedback-type-filter").value.trim();
  const slideId = document.getElementById("feedback-slide-filter").value.trim();

  if (source) params.set("feedback_source", source);
  if (status) params.set("status", status);
  if (type) params.set("feedback_type", type);
  if (slideId) params.set("slide_id", slideId);

  return params;
}

function updateCsvLink() {
  const params = buildFilters();
  const url = "/api/admin/feedback/export.csv" + (params.toString() ? "?" + params.toString() : "");
  document.getElementById("download-feedback-csv").href = url;
}

async function loadDictionary(name) {
  if (dictionaryCache[name]) {
    return dictionaryCache[name];
  }

  const response = await fetch("/api/admin/dictionaries/" + name, {
    credentials: "include"
  });

  if (!response.ok) {
    return [];
  }

  const data = await response.json();
  dictionaryCache[name] = data.values || [];
  return dictionaryCache[name];
}

function createEl(tagName, className, text) {
  const el = document.createElement(tagName);
  if (className) el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
}

function renderSummary(data) {
  const summary = data.summary || {};
  const bySource = data.by_source || [];
  const byType = data.by_type || [];
  const byStatus = data.by_status || [];

  const container = document.getElementById("feedback-summary");
  container.innerHTML = "";

  container.appendChild(createEl("h3", "", "Summary"));
  container.appendChild(createEl("p", "", "Total feedback: " + textOrDash(summary.total_feedback)));

  container.appendChild(createEl(
    "p",
    "",
    "Source: " + (bySource.length ? bySource.map(item => item.feedback_source + " (" + item.n + ")").join(" · ") : "—")
  ));

  container.appendChild(createEl(
    "p",
    "",
    "Status: " + (byStatus.length ? byStatus.map(item => item.status + " (" + item.n + ")").join(" · ") : "—")
  ));

  container.appendChild(createEl(
    "p",
    "",
    "Type: " + (byType.length ? byType.map(item => item.feedback_type + " (" + item.n + ")").join(" · ") : "—")
  ));
}

function canApplyMetadataCorrection(row) {
  return row.feedback_source === "metadata" &&
    ["organ", "species", "stain"].includes(row.feedback_type);
}

function createStatusControls(row, card) {
  const wrapper = createEl("div", "mvls-feedback-button-row");

  const notesField = createEl("div", "mvls-field");
  const notesLabel = createEl("label", "", "Admin notes");
  const notes = document.createElement("textarea");
  notes.value = row.admin_notes || "";
  notes.placeholder = "Add review notes... (included in the thank-you email if you Thank contributor)";
  notes.style.minHeight = "70px";

  notesField.appendChild(notesLabel);
  notesField.appendChild(notes);
  wrapper.appendChild(notesField);

  const buttonRow = createEl("div", "mvls-actions");

  const statuses = [
    ["under_review", "Mark under review"],
    ["rejected", "Reject"],
    ["resolved", "Thank contributor"]
  ];

  for (const [statusValue, label] of statuses) {
    const button = createEl("button", "mvls-button mvls-button-secondary", label);
    button.type = "button";

    button.addEventListener("click", async function () {
      const response = await fetch("/api/admin/feedback/" + row.feedback_id + "/review", {
        method: "PATCH",
        credentials: "include",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          status: statusValue,
          admin_notes: notes.value
        })
      });

      if (!response.ok) {
        alert("Could not update feedback status.");
        return;
      }

      await loadFeedbackReport();
    });

    buttonRow.appendChild(button);
  }

  wrapper.appendChild(buttonRow);
  card.appendChild(wrapper);
}

async function createCorrectionControls(row, card) {
  if (!canApplyMetadataCorrection(row)) {
    return;
  }

  const dictionaryName = row.feedback_type;
  const values = await loadDictionary(dictionaryName);

  const panel = createEl("div", "mvls-feedback-button-row");
  panel.appendChild(createEl("h4", "", "Apply dictionary-controlled metadata correction"));
  panel.appendChild(createEl("p", "mvls-muted", "Saves this value to the database and thanks the contributor."));

  const field = createEl("div", "mvls-field");

  const label = createEl("label", "", "Dictionary value for " + dictionaryName);
  const select = document.createElement("select");

  for (const item of values) {
    const option = document.createElement("option");
    option.value = item.value;

    if (item.label && item.label !== item.value) {
      option.textContent = item.label + " [" + item.value + "]";
    } else {
      option.textContent = item.value;
    }

    if (
      row.suggested_value &&
      (
        row.suggested_value.toLowerCase() === String(item.value).toLowerCase() ||
        row.suggested_value.toLowerCase() === String(item.label).toLowerCase()
      )
    ) {
      option.selected = true;
    }

    select.appendChild(option);
  }

  field.appendChild(label);
  field.appendChild(select);
  panel.appendChild(field);

  const notesField = createEl("div", "mvls-field");
  notesField.style.marginTop = "0.75rem";

  const notesLabel = createEl("label", "", "Correction notes");
  const notes = document.createElement("textarea");
  notes.placeholder = "Explain why this correction was applied.";
  notes.style.minHeight = "70px";

  notesField.appendChild(notesLabel);
  notesField.appendChild(notes);
  panel.appendChild(notesField);

  const applyButton = createEl("button", "mvls-button", "Apply correction & thank contributor");
  applyButton.type = "button";

  applyButton.addEventListener("click", async function () {
    const newValue = select.value;

    const confirmed = confirm(
      "Apply metadata correction?\n\n" +
      "Slide: " + row.slide_id + "\n" +
      "Field: " + dictionaryName + "\n" +
      "New value: " + newValue + "\n\n" +
      "This will update slide_metadata."
    );

    if (!confirmed) {
      return;
    }

    const response = await fetch("/api/admin/feedback/" + row.feedback_id + "/apply-metadata-correction", {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        field_name: dictionaryName,
        new_value: newValue,
        admin_notes: notes.value
      })
    });

    if (!response.ok) {
      const error = await response.json().catch(function () {
        return {};
      });

      alert(error.detail || "Could not apply correction.");
      return;
    }

    const result = await response.json();

    alert(
      "Correction applied.\n\n" +
      "Old value: " + textOrDash(result.old_value) + "\n" +
      "New value: " + textOrDash(result.new_value)
    );

    await loadFeedbackReport();
  });

  panel.appendChild(applyButton);
  card.appendChild(panel);
}

async function createFeedbackCard(row) {
  const card = document.createElement("article");
  card.className = "mvls-annotation-card";

  const isResolved = row.status === "resolved";

  if (isResolved) {
    card.style.opacity = "0.55";
  }

  card.appendChild(createEl("h3", "", "Feedback #" + row.feedback_id + " · Slide " + row.slide_id));

  card.appendChild(createEl(
    "p",
    "mvls-annotation-meta",
    row.feedback_source +
      " · " +
      row.feedback_type +
      " · " +
      row.status +
      " · submitted by " +
      row.submitter_username +
      " · " +
      row.created_at
  ));

  card.appendChild(createEl("p", "", "Filename: " + textOrDash(row.slide_filename)));
  card.appendChild(createEl("p", "", "Current value/context: " + textOrDash(row.current_value)));
  card.appendChild(createEl("p", "", "Suggested value: " + textOrDash(row.suggested_value)));
  card.appendChild(createEl("p", "", "Feedback: " + textOrDash(row.feedback_text)));

  const openSlide = document.createElement("a");
  openSlide.className = "mvls-button mvls-button-secondary";
  openSlide.href = "/slide.html?id=" + row.slide_id;
  openSlide.target = "_blank";
  openSlide.rel = "noopener noreferrer";
  openSlide.textContent = "Open slide in new tab";
  card.appendChild(openSlide);

  if (!isResolved) {
    createStatusControls(row, card);
    await createCorrectionControls(row, card);
  }

  return card;
}

async function renderRows(rows) {
  const list = document.getElementById("feedback-report-list");
  list.innerHTML = "";

  if (!rows.length) {
    const empty = createEl("div", "mvls-empty-state", "No feedback found for the selected filters.");
    list.appendChild(empty);
    return;
  }

  for (const row of rows) {
    const card = await createFeedbackCard(row);
    list.appendChild(card);
  }
}

async function loadFeedbackReport() {
  const user = await window.mvlsRequireLogin();

  if (!user) {
    return;
  }

  if (
    !["admin", "system_admin"].includes(user.role)
  ) {
    document.querySelector(".mvls-result-shell").innerHTML =
      "<h2>Admin access required</h2><p>You do not have permission to view feedback reports.</p>";
    return;
  }

  updateCsvLink();

  const params = buildFilters();
  const url = "/api/admin/feedback/report" + (params.toString() ? "?" + params.toString() : "");

  const response = await fetch(url, {
    credentials: "include"
  });

  if (!response.ok) {
    document.getElementById("feedback-summary").textContent = "Could not load feedback report.";
    return;
  }

  const data = await response.json();

  renderSummary(data);
  await renderRows(data.rows || []);
}

document.getElementById("load-feedback-report").addEventListener("click", loadFeedbackReport);
document.getElementById("feedback-source-filter").addEventListener("change", updateCsvLink);
document.getElementById("feedback-status-filter").addEventListener("change", updateCsvLink);
document.getElementById("feedback-type-filter").addEventListener("input", updateCsvLink);
document.getElementById("feedback-slide-filter").addEventListener("input", updateCsvLink);

loadFeedbackReport();
