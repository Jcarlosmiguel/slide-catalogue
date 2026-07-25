function createEl(tagName, className, text) {
  const el = document.createElement(tagName);
  if (className) el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
}

function autoSizeTextarea(el) {
  el.style.height = "auto";
  el.style.height = el.scrollHeight + "px";
}

function textOrDash(value) {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  return value;
}

function switchTab(tabName) {
  document.querySelectorAll(".vmc-tab-button").forEach(function (button) {
    button.classList.toggle("vmc-tab-active", button.dataset.tab === tabName);
  });
  document.querySelectorAll(".vmc-tab-panel").forEach(function (panel) {
    panel.hidden = panel.id !== "tab-" + tabName;
  });
}

function createStatusControls(row, card, reload) {
  const wrapper = createEl("div", "vmc-feedback-button-row");

  const notesField = createEl("div", "vmc-field");
  notesField.appendChild(createEl("label", "", "Review notes"));
  const notes = document.createElement("textarea");
  notes.value = row.admin_notes || "";
  notes.style.minHeight = "70px";
  notes.style.resize = "none";
  notes.style.overflow = "hidden";
  notes.addEventListener("input", function () {
    autoSizeTextarea(notes);
  });
  notesField.appendChild(notes);
  wrapper.appendChild(notesField);
  requestAnimationFrame(function () {
    autoSizeTextarea(notes);
  });

  const buttonRow = createEl("div", "vmc-actions");
  const isUnderReview = row.status === "under_review";

  const statuses = [
    ["accepted", "Approve"],
    [isUnderReview ? "new" : "under_review", isUnderReview ? "Unmark under review" : "Mark under review"],
    ["rejected", "Reject"],
    ["resolved", "Thank contributor"],
  ];

  for (const [statusValue, label] of statuses) {
    const button = createEl("button", "vmc-button vmc-button-secondary", label);
    button.type = "button";

    button.addEventListener("click", async function () {
      const response = await fetch("/api/reviewer/corrections/" + row.feedback_id + "/review", {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: statusValue, admin_notes: notes.value }),
      });

      if (!response.ok) {
        alert("Could not update correction status.");
        return;
      }

      await reload();
    });

    buttonRow.appendChild(button);
  }

  wrapper.appendChild(buttonRow);
  card.appendChild(wrapper);
}

function createCorrectionCard(row, reload) {
  const card = createEl("article", "vmc-annotation-card");

  if (row.status === "resolved" || row.status === "rejected") {
    card.style.opacity = "0.55";
  }
  if (row.status === "under_review") {
    card.classList.add("vmc-feedback-under-review");
  }

  card.appendChild(createEl("h3", "", "Correction #" + row.feedback_id + " · Slide " + row.slide_id));

  const metaParts = [row.feedback_source, row.status, "submitted by " + row.submitter_username, row.created_at];
  card.appendChild(createEl("p", "vmc-annotation-meta", metaParts.join(" · ")));

  if (row.submitter_role === "expert") {
    const badge = createEl("span", "vmc-badge vmc-badge-gold", "Expert review");
    card.appendChild(badge);
  }

  card.appendChild(createEl("p", "", "Filename: " + textOrDash(row.slide_filename)));
  card.appendChild(createEl("p", "", "Type: " + textOrDash(row.feedback_type)));
  if (row.source_annotation_id) {
    card.appendChild(createEl("p", "", "Annotation ID: " + row.source_annotation_id));
  }
  card.appendChild(createEl("p", "", "Current value / context: " + textOrDash(row.current_value)));
  card.appendChild(createEl("p", "", "Suggested value / verdict: " + textOrDash(row.suggested_value)));
  card.appendChild(createEl("p", "", "Comments: " + textOrDash(row.feedback_text)));

  const openSlide = createEl("a", "vmc-button vmc-button-secondary", "Open slide in new tab");
  openSlide.href = "/slide.html?id=" + row.slide_id;
  openSlide.target = "_blank";
  openSlide.rel = "noopener noreferrer";
  card.appendChild(openSlide);

  if (row.status !== "resolved") {
    createStatusControls(row, card, reload);
  }

  return card;
}

async function loadCorrectionsTab(feedbackSource, summaryElId, listElId) {
  const summaryEl = document.getElementById(summaryElId);
  const listEl = document.getElementById(listElId);

  const response = await fetch("/api/reviewer/corrections?feedback_source=" + feedbackSource, {
    credentials: "include",
  });

  if (!response.ok) {
    summaryEl.textContent = "Could not load this report.";
    listEl.innerHTML = "";
    return;
  }

  const data = await response.json();
  const summary = data.summary || {};

  summaryEl.innerHTML = "";
  summaryEl.appendChild(createEl(
    "p",
    "",
    "Total: " + textOrDash(summary.total_feedback) +
      " · New: " + textOrDash(summary.new_feedback) +
      " · Under review: " + textOrDash(summary.under_review_feedback) +
      " · Accepted: " + textOrDash(summary.accepted_feedback) +
      " · Rejected: " + textOrDash(summary.rejected_feedback) +
      " · Resolved: " + textOrDash(summary.resolved_feedback)
  ));

  listEl.innerHTML = "";

  if (!data.rows.length) {
    listEl.appendChild(createEl("div", "vmc-empty-state", "Nothing here yet."));
    return;
  }

  const reload = function () {
    return loadCorrectionsTab(feedbackSource, summaryElId, listElId);
  };

  for (const row of data.rows) {
    listEl.appendChild(createCorrectionCard(row, reload));
  }
}

function createExpertNoteCard(note, reload) {
  const card = createEl("article", "vmc-annotation-card");
  card.appendChild(createEl("h3", "", note.note_title || "Expert note " + note.note_id));
  card.appendChild(createEl(
    "p",
    "vmc-annotation-meta",
    "Slide " + note.slide_id + " (" + textOrDash(note.slide_filename) + ") · " +
      note.author_display_name + " · " + note.created_at
  ));

  const textArea = document.createElement("textarea");
  textArea.className = "vmc-note-text";
  textArea.value = note.note_text;
  textArea.style.overflow = "hidden";
  textArea.disabled = true;
  textArea.addEventListener("input", function () {
    autoSizeTextarea(textArea);
  });
  card.appendChild(textArea);
  requestAnimationFrame(function () {
    autoSizeTextarea(textArea);
  });

  const actions = createEl("div", "vmc-actions");

  const editButton = createEl("button", "vmc-button vmc-button-secondary", "Edit");
  editButton.type = "button";

  const saveButton = createEl("button", "vmc-button", "Save");
  saveButton.type = "button";
  saveButton.hidden = true;

  editButton.addEventListener("click", function () {
    textArea.disabled = false;
    autoSizeTextarea(textArea);
    editButton.hidden = true;
    saveButton.hidden = false;
  });

  saveButton.addEventListener("click", async function () {
    const response = await fetch("/api/expert-notes/" + note.note_id, {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ note_title: note.note_title, note_text: textArea.value }),
    });

    if (!response.ok) {
      alert("Could not save this note.");
      return;
    }

    await reload();
  });

  const deleteButton = createEl("button", "vmc-button vmc-button-secondary", "Delete");
  deleteButton.type = "button";
  deleteButton.addEventListener("click", async function () {
    if (!confirm("Delete this expert note?")) {
      return;
    }

    const response = await fetch("/api/expert-notes/" + note.note_id, {
      method: "DELETE",
      credentials: "include",
    });

    if (!response.ok) {
      alert("Could not delete this note.");
      return;
    }

    await reload();
  });

  const openSlide = createEl("a", "vmc-button vmc-button-secondary", "Open slide");
  openSlide.href = "/slide.html?id=" + note.slide_id;
  openSlide.target = "_blank";
  openSlide.rel = "noopener noreferrer";

  actions.appendChild(editButton);
  actions.appendChild(saveButton);
  actions.appendChild(deleteButton);
  actions.appendChild(openSlide);
  card.appendChild(actions);

  return card;
}

async function loadExpertNotesTab() {
  const listEl = document.getElementById("expert-notes-list");
  const response = await fetch("/api/expert-notes", { credentials: "include" });

  if (!response.ok) {
    listEl.innerHTML = "";
    listEl.appendChild(createEl("div", "vmc-empty-state", "Could not load expert notes."));
    return;
  }

  const data = await response.json();
  listEl.innerHTML = "";

  if (!data.notes.length) {
    listEl.appendChild(createEl("div", "vmc-empty-state", "No expert notes yet."));
    return;
  }

  for (const note of data.notes) {
    listEl.appendChild(createExpertNoteCard(note, loadExpertNotesTab));
  }
}

function wireExpertNoteForm() {
  const submitButton = document.getElementById("expert-note-submit");
  const status = document.getElementById("expert-note-status");

  submitButton.addEventListener("click", async function () {
    const slideId = document.getElementById("expert-note-slide-id").value;
    const noteTitle = document.getElementById("expert-note-title").value.trim();
    const noteText = document.getElementById("expert-note-text").value.trim();

    if (!slideId || !noteText) {
      status.textContent = "Slide ID and note text are required.";
      return;
    }

    status.textContent = "Saving...";

    const response = await fetch("/api/slides/" + slideId + "/expert-notes", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ note_title: noteTitle || null, note_text: noteText }),
    });

    if (!response.ok) {
      const error = await response.json().catch(function () {
        return {};
      });
      status.textContent = error.detail || "Could not save note.";
      return;
    }

    status.textContent = "Note added.";
    document.getElementById("expert-note-title").value = "";
    document.getElementById("expert-note-text").value = "";
    await loadExpertNotesTab();
  });
}

async function initReviewerDashboard() {
  const user = await window.vmcRequireLogin();
  if (!user) {
    return;
  }

  if (!["admin", "system_admin", "reviewer", "expert"].includes(user.role)) {
    document.querySelector("main").innerHTML =
      '<section class="vmc-card"><p>You do not have access to this page.</p></section>';
    return;
  }

  const canWriteExpertNotes = ["admin", "system_admin", "expert"].includes(user.role);
  const expertTabButton = document.querySelector('.vmc-tab-button[data-tab="expert-notes"]');
  if (canWriteExpertNotes) {
    expertTabButton.hidden = false;
  }

  document.querySelectorAll(".vmc-tab-button").forEach(function (button) {
    button.addEventListener("click", function () {
      switchTab(button.dataset.tab);
    });
  });

  switchTab("metadata");

  await loadCorrectionsTab("metadata", "metadata-summary", "metadata-list");
  await loadCorrectionsTab("slide_annotation", "annotations-summary", "annotations-list");

  if (canWriteExpertNotes) {
    wireExpertNoteForm();
    await loadExpertNotesTab();
  }
}

initReviewerDashboard();
