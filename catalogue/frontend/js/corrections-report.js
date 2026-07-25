let dictionaryCache = {
  organ: null,
  tissue: null,
  species: null,
  stain: null
};

const DICTIONARY_BACKED_TYPES = ["organ", "tissue", "species", "stain"];
const FREE_TEXT_CORRECTION_TYPES = ["description", "notes"];

const FEEDBACK_TYPE_LABELS = {
  organ: "Organ",
  tissue: "Tissue",
  species: "Species",
  stain: "Stain",
  description: "Description",
  notes: "Notes",
  general_comment: "General metadata comment"
};

function correctionTypeLabel(type) {
  return FEEDBACK_TYPE_LABELS[type] || type;
}

function textOrDash(value) {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  return value;
}

function buildFilters() {
  const params = new URLSearchParams();

  const source = document.getElementById("correction-source-filter").value;
  const status = document.getElementById("correction-status-filter").value;
  const type = document.getElementById("correction-type-filter").value.trim();
  const slideId = document.getElementById("correction-slide-filter").value.trim();

  if (source) params.set("feedback_source", source);
  if (status) params.set("status", status);
  if (type) params.set("feedback_type", type);
  if (slideId) params.set("slide_id", slideId);

  return params;
}

function updateCsvLink() {
  const params = buildFilters();
  const url = "/api/admin/corrections/export.csv" + (params.toString() ? "?" + params.toString() : "");
  document.getElementById("download-corrections-csv").href = url;
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

  const container = document.getElementById("corrections-summary");
  container.innerHTML = "";

  container.appendChild(createEl("h3", "", "Summary"));
  container.appendChild(createEl("p", "", "Total corrections: " + textOrDash(summary.total_feedback)));

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
    (DICTIONARY_BACKED_TYPES.includes(row.feedback_type) || FREE_TEXT_CORRECTION_TYPES.includes(row.feedback_type));
}

function createStatusControls(row, card) {
  const wrapper = createEl("div", "vmc-feedback-button-row");

  const notesField = createEl("div", "vmc-field");
  const notesLabel = createEl("label", "", "Admin notes");
  const notes = document.createElement("textarea");
  notes.value = row.admin_notes || "";
  notes.placeholder = "Add review notes... (included in the thank-you email if you Thank contributor)";
  notes.style.minHeight = "70px";

  notesField.appendChild(notesLabel);
  notesField.appendChild(notes);
  wrapper.appendChild(notesField);

  const buttonRow = createEl("div", "vmc-actions");

  const isUnderReview = row.status === "under_review";

  const statuses = [
    ["accepted", "Approve"],
    [isUnderReview ? "new" : "under_review", isUnderReview ? "Unmark under review" : "Mark under review"],
    ["rejected", "Reject"],
    ["resolved", "Thank contributor"]
  ];

  for (const [statusValue, label] of statuses) {
    const button = createEl("button", "vmc-button vmc-button-secondary", label);
    button.type = "button";

    button.addEventListener("click", async function () {
      const response = await fetch("/api/admin/corrections/" + row.feedback_id + "/review", {
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
        alert("Could not update correction status.");
        return;
      }

      await loadCorrectionsReport();
    });

    buttonRow.appendChild(button);
  }

  wrapper.appendChild(buttonRow);
  card.appendChild(wrapper);
}

async function applyMetadataCorrection(row, fieldName, newValue, adminNotes, skipConfirm) {
  if (!skipConfirm) {
    const confirmed = confirm(
      "Apply correction?\n\n" +
      "Slide: " + row.slide_id + "\n" +
      "Field: " + correctionTypeLabel(fieldName) + "\n" +
      "New value: " + newValue + "\n\n" +
      "This will update the slide's metadata."
    );

    if (!confirmed) {
      return false;
    }
  }

  const response = await fetch("/api/admin/corrections/" + row.feedback_id + "/apply", {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      field_name: fieldName,
      new_value: newValue,
      admin_notes: adminNotes
    })
  });

  if (!response.ok) {
    const error = await response.json().catch(function () {
      return {};
    });

    alert(error.detail || "Could not apply correction.");
    return false;
  }

  const result = await response.json();

  alert(
    "Correction applied.\n\n" +
    "Old value: " + textOrDash(result.old_value) + "\n" +
    "New value: " + textOrDash(result.new_value)
  );

  return true;
}

function createAddToDictionaryControl(fieldName, row, adminNotesInput) {
  const wrapper = createEl("div", "vmc-field");
  wrapper.style.marginTop = "0.5rem";

  wrapper.appendChild(createEl(
    "p",
    "vmc-muted",
    "'" + row.suggested_value + "' isn't in the " + correctionTypeLabel(fieldName) + " dictionary yet. " +
      "Correct any typos or stray punctuation below before adding - this becomes a permanent entry."
  ));

  const newTermInput = document.createElement("input");
  newTermInput.type = "text";
  newTermInput.value = row.suggested_value;

  const addButton = createEl("button", "vmc-button vmc-button-secondary", "Add to dictionary & apply");
  addButton.type = "button";

  addButton.addEventListener("click", async function () {
    const newTerm = newTermInput.value.trim();

    if (!newTerm) {
      return;
    }

    const confirmed = confirm(
      "Add '" + newTerm + "' to the " + correctionTypeLabel(fieldName) + " dictionary and apply it as this " +
        "slide's " + correctionTypeLabel(fieldName).toLowerCase() + "?\n\n" +
      "Double-check spelling and punctuation first - this becomes a permanent, selectable entry.\n" +
      "Cancel to keep editing the text above."
    );

    if (!confirmed) {
      return;
    }

    const response = await fetch("/api/admin/dictionaries/" + fieldName, {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({ value: newTerm })
    });

    if (!response.ok) {
      const error = await response.json().catch(function () {
        return {};
      });

      alert(error.detail || "Could not add to dictionary.");
      return;
    }

    dictionaryCache[fieldName] = null;

    await applyMetadataCorrection(row, fieldName, newTerm, adminNotesInput.value, true);
    await loadCorrectionsReport();
  });

  wrapper.appendChild(newTermInput);
  wrapper.appendChild(addButton);
  return wrapper;
}

async function createCorrectionControls(row, card) {
  if (!canApplyMetadataCorrection(row)) {
    return;
  }

  const fieldName = row.feedback_type;
  const isDictionaryBacked = DICTIONARY_BACKED_TYPES.includes(fieldName);

  const panel = createEl("div", "vmc-feedback-button-row");
  panel.appendChild(createEl("h4", "", "Apply correction"));
  panel.appendChild(createEl("p", "vmc-muted", "Saves this value to the database and thanks the contributor."));

  const notesField = createEl("div", "vmc-field");
  notesField.style.marginTop = "0.75rem";

  const notesLabel = createEl("label", "", "Correction notes");
  const notes = document.createElement("textarea");
  notes.placeholder = "Explain why this correction was applied.";
  notes.style.minHeight = "70px";

  notesField.appendChild(notesLabel);
  notesField.appendChild(notes);

  const field = createEl("div", "vmc-field");
  let valueControl;

  if (isDictionaryBacked) {
    const values = await loadDictionary(fieldName);

    const label = createEl("label", "", "Dictionary value for " + correctionTypeLabel(fieldName));
    const select = document.createElement("select");

    let suggestedIsListed = false;

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
        suggestedIsListed = true;
      }

      select.appendChild(option);
    }

    field.appendChild(label);
    field.appendChild(select);
    valueControl = select;
    panel.appendChild(field);

    if (row.suggested_value && !suggestedIsListed) {
      panel.appendChild(createAddToDictionaryControl(fieldName, row, notes));
    }
  } else {
    const label = createEl("label", "", "New " + correctionTypeLabel(fieldName).toLowerCase() + " text");
    const textarea = document.createElement("textarea");
    textarea.style.minHeight = "70px";
    textarea.value = row.suggested_value || "";

    field.appendChild(label);
    field.appendChild(textarea);
    valueControl = textarea;
    panel.appendChild(field);
  }

  panel.appendChild(notesField);

  const applyButton = createEl("button", "vmc-button", "Apply correction & thank contributor");
  applyButton.type = "button";

  applyButton.addEventListener("click", async function () {
    const newValue = valueControl.value;

    if (!newValue || !newValue.trim()) {
      alert("Please provide a value to apply.");
      return;
    }

    const applied = await applyMetadataCorrection(row, fieldName, newValue, notes.value, false);

    if (applied) {
      await loadCorrectionsReport();
    }
  });

  panel.appendChild(applyButton);
  card.appendChild(panel);
}

async function createCorrectionCard(row) {
  const card = document.createElement("article");
  card.className = "vmc-annotation-card";

  const isResolved = row.status === "resolved";

  if (isResolved || row.status === "rejected") {
    card.style.opacity = "0.55";
  }

  if (row.status === "under_review") {
    card.classList.add("vmc-feedback-under-review");
  }

  card.appendChild(createEl("h3", "", "Correction #" + row.feedback_id + " · Slide " + row.slide_id));

  card.appendChild(createEl(
    "p",
    "vmc-annotation-meta",
    row.feedback_source +
      " · " +
      row.status +
      " · submitted by " +
      row.submitter_username +
      " · " +
      row.created_at
  ));

  card.appendChild(createEl("p", "", "Filename: " + textOrDash(row.slide_filename)));
  card.appendChild(createEl("p", "", "Metadata area: " + correctionTypeLabel(row.feedback_type)));
  card.appendChild(createEl("p", "", "Current value / context: " + textOrDash(row.current_value)));
  card.appendChild(createEl("p", "", "Suggested correction: " + textOrDash(row.suggested_value)));
  card.appendChild(createEl("p", "", "Comments and reasoning: " + textOrDash(row.feedback_text)));

  const openSlide = document.createElement("a");
  openSlide.className = "vmc-button vmc-button-secondary";
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
  const list = document.getElementById("corrections-report-list");
  list.innerHTML = "";

  if (!rows.length) {
    const empty = createEl("div", "vmc-empty-state", "No corrections found for the selected filters.");
    list.appendChild(empty);
    return;
  }

  for (const row of rows) {
    const card = await createCorrectionCard(row);
    list.appendChild(card);
  }
}

async function loadCorrectionsReport() {
  const user = await window.vmcRequireLogin();

  if (!user) {
    return;
  }

  if (
    !["admin", "system_admin"].includes(user.role)
  ) {
    document.querySelector(".vmc-result-shell").innerHTML =
      "<h2>Admin access required</h2><p>You do not have permission to view correction reports.</p>";
    return;
  }

  updateCsvLink();

  const params = buildFilters();
  const url = "/api/admin/corrections/report" + (params.toString() ? "?" + params.toString() : "");

  const response = await fetch(url, {
    credentials: "include"
  });

  if (!response.ok) {
    document.getElementById("corrections-summary").textContent = "Could not load corrections report.";
    return;
  }

  const data = await response.json();

  renderSummary(data);
  await renderRows(data.rows || []);
}

document.getElementById("load-corrections-report").addEventListener("click", loadCorrectionsReport);
document.getElementById("correction-source-filter").addEventListener("change", updateCsvLink);
document.getElementById("correction-status-filter").addEventListener("change", updateCsvLink);
document.getElementById("correction-type-filter").addEventListener("input", updateCsvLink);
document.getElementById("correction-slide-filter").addEventListener("input", updateCsvLink);

loadCorrectionsReport();
