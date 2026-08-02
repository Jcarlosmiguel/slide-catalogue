function textOrDash(value) {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  return value;
}

function createEl(tagName, className, text) {
  const el = document.createElement(tagName);
  if (className) el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
}

function createSiteFeedbackStatusControls(row, card) {
  const wrapper = createEl("div", "vmc-feedback-button-row");

  const notesField = createEl("div", "vmc-field");
  const notesLabel = createEl("label", "", "Admin notes");
  const notes = document.createElement("textarea");
  notes.value = row.admin_notes || "";
  notes.placeholder = "Add review notes...";
  notes.style.minHeight = "70px";

  notesField.appendChild(notesLabel);
  notesField.appendChild(notes);
  wrapper.appendChild(notesField);

  const buttonRow = createEl("div", "vmc-actions");

  const isUnderReview = row.status === "under_review";

  const statuses = [
    [isUnderReview ? "new" : "under_review", isUnderReview ? "Unmark under review" : "Mark under review"],
    ["rejected", "Reject"],
    ["resolved", "Mark resolved"]
  ];

  for (const [statusValue, label] of statuses) {
    const button = createEl("button", "vmc-button vmc-button-secondary", label);
    button.type = "button";

    button.addEventListener("click", async function () {
      const response = await fetch("/api/admin/site-feedback/" + row.feedback_id + "/review", {
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

      await loadSiteFeedbackReport();
    });

    buttonRow.appendChild(button);
  }

  wrapper.appendChild(buttonRow);
  card.appendChild(wrapper);
}

function createSiteFeedbackCard(row) {
  const card = document.createElement("article");
  card.className = "vmc-annotation-card";

  const isResolved = row.status === "resolved";

  if (isResolved || row.status === "rejected") {
    card.style.opacity = "0.55";
  }

  if (row.status === "under_review") {
    card.classList.add("vmc-feedback-under-review");
  }

  card.appendChild(createEl("h3", "", "Feedback #" + row.feedback_id));

  card.appendChild(createEl(
    "p",
    "vmc-annotation-meta",
    row.status +
      " · submitted by " +
      (row.submitter_username || "Anonymous") +
      " · " +
      row.created_at
  ));

  card.appendChild(createEl("p", "", "Page: " + textOrDash(row.page_url)));
  card.appendChild(createEl("p", "", "Feedback: " + textOrDash(row.feedback_text)));

  if (!isResolved) {
    createSiteFeedbackStatusControls(row, card);
  }

  return card;
}

function renderSiteFeedbackRows(rows) {
  const list = document.getElementById("site-feedback-report-list");
  list.innerHTML = "";

  if (!rows.length) {
    const empty = createEl("div", "vmc-empty-state", "No site feedback found for the selected filter.");
    list.appendChild(empty);
    return;
  }

  for (const row of rows) {
    const card = createSiteFeedbackCard(row);
    list.appendChild(card);
  }
}

async function loadSiteFeedbackReport() {
  const user = await window.vmcRequireLogin();

  if (!user) {
    return;
  }

  if (!["admin", "system_admin"].includes(user.role)) {
    document.querySelector(".vmc-card").innerHTML =
      "<h2>Admin access required</h2><p>You do not have permission to view site feedback.</p>";
    return;
  }

  const status = document.getElementById("site-feedback-status-filter").value;
  const params = new URLSearchParams();
  if (status) params.set("status", status);

  const url = "/api/admin/site-feedback/report" + (params.toString() ? "?" + params.toString() : "");

  const response = await fetch(url, {
    credentials: "include"
  });

  if (!response.ok) {
    document.getElementById("site-feedback-report-list").textContent = "Could not load site feedback.";
    return;
  }

  const data = await response.json();
  renderSiteFeedbackRows(data.rows || []);
}

document.getElementById("load-site-feedback-report").addEventListener("click", loadSiteFeedbackReport);
document.getElementById("site-feedback-status-filter").addEventListener("change", loadSiteFeedbackReport);

loadSiteFeedbackReport();
