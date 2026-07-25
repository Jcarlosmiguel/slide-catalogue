function getReviewSlideId() {
  const params = new URLSearchParams(window.location.search);
  const id = params.get("id");
  return id ? parseInt(id, 10) : null;
}

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

function annotationSummary(ann) {
  if (ann.rect_x !== -1 && ann.rect_x !== null) {
    return `Rectangle: x ${ann.rect_x}, y ${ann.rect_y}, w ${ann.rect_w}, h ${ann.rect_h}`;
  }
  if (ann.arrow_start_x !== -1 && ann.arrow_start_x !== null) {
    return `Arrow: start ${ann.arrow_start_x},${ann.arrow_start_y} · end ${ann.arrow_end_x},${ann.arrow_end_y}`;
  }
  return "No coordinate summary available";
}

function buildAnnotationRow(slideId, ann, state) {
  const card = createEl("article", "vmc-annotation-card vmc-review-card");

  card.appendChild(createEl("h3", "", ann.title || "Annotation " + ann.annotation_id));
  card.appendChild(createEl(
    "p",
    "vmc-annotation-meta",
    "Type: " + textOrDash(ann.annotation_type) + " · Annotation ID: " + ann.annotation_id
  ));
  card.appendChild(createEl("p", "", annotationSummary(ann)));

  if (ann.description) {
    card.appendChild(createEl("p", "vmc-muted", ann.description));
  }

  const verdictRow = createEl("div", "vmc-review-verdict-row");

  const correctLabel = createEl("label", "vmc-review-radio-label");
  const correctRadio = document.createElement("input");
  correctRadio.type = "radio";
  correctRadio.name = "verdict-" + ann.annotation_id;
  correctRadio.value = "correct";
  correctLabel.appendChild(correctRadio);
  correctLabel.appendChild(document.createTextNode(" Correct"));

  const incorrectLabel = createEl("label", "vmc-review-radio-label");
  const incorrectRadio = document.createElement("input");
  incorrectRadio.type = "radio";
  incorrectRadio.name = "verdict-" + ann.annotation_id;
  incorrectRadio.value = "incorrect";
  incorrectLabel.appendChild(incorrectRadio);
  incorrectLabel.appendChild(document.createTextNode(" Incorrect"));

  correctRadio.addEventListener("change", function () {
    state.verdict = "correct";
  });
  incorrectRadio.addEventListener("change", function () {
    state.verdict = "incorrect";
  });

  verdictRow.appendChild(correctLabel);
  verdictRow.appendChild(incorrectLabel);

  const comment = document.createElement("textarea");
  comment.className = "vmc-review-comment";
  comment.placeholder = "Optional: explain what's wrong (or confirm why it's correct)";
  comment.addEventListener("input", function () {
    state.feedback_text = comment.value.trim();
    autoSizeTextarea(comment);
  });

  const status = createEl("p", "vmc-review-status");

  card.appendChild(verdictRow);
  card.appendChild(comment);
  card.appendChild(status);

  state.statusEl = status;
  state.inputs = [correctRadio, incorrectRadio, comment];

  return card;
}

async function submitAnnotationFeedback(slideId, annotationId, state) {
  const response = await fetch("/api/slides/" + slideId + "/annotation-feedback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({
      annotation_id: annotationId,
      verdict: state.verdict,
      feedback_text: state.feedback_text || "",
    }),
  });

  if (!response.ok) {
    const errorBody = await response.json().catch(function () {
      return {};
    });
    throw new Error(errorBody.detail || "Submission failed");
  }

  return response.json();
}

async function loadAnnotationsForReview() {
  const slideId = getReviewSlideId();
  const root = document.getElementById("annotation-review");
  const backLink = document.getElementById("back-to-slide");

  if (!slideId) {
    root.innerHTML = "";
    root.appendChild(createEl("div", "vmc-placeholder", "No slide specified - open this page from a slide's annotation section."));
    return;
  }

  backLink.href = "/slide.html?id=" + slideId;

  const response = await fetch("/api/slides/" + slideId, { credentials: "include" });

  if (!response.ok) {
    root.innerHTML = "";
    root.appendChild(createEl("div", "vmc-placeholder", "Could not load this slide's annotations."));
    return;
  }

  const slide = await response.json();
  const annotations = slide.slide_annotations || [];

  root.innerHTML = "";

  const section = createEl("section", "vmc-section");
  section.appendChild(createEl("h2", "", "Report annotation errors - Slide " + slideId + " (" + slide.identity.filename + ")"));
  section.appendChild(createEl(
    "p",
    "vmc-muted",
    "Mark each annotation as correct or incorrect, optionally explain why, then submit. " +
    "Only annotations you mark are submitted - the rest are left untouched."
  ));

  if (!annotations.length) {
    section.appendChild(createEl("div", "vmc-placeholder", "This slide has no stored annotations."));
    root.appendChild(section);
    return;
  }

  const states = annotations.map(function () {
    return { verdict: null, feedback_text: "" };
  });

  annotations.forEach(function (ann, index) {
    section.appendChild(buildAnnotationRow(slideId, ann, states[index]));
  });

  const actions = createEl("div", "vmc-actions");
  const submitButton = createEl("button", "vmc-button", "Submit report");
  submitButton.type = "button";
  const summary = createEl("span", "vmc-muted");

  submitButton.addEventListener("click", async function () {
    const toSubmit = [];
    annotations.forEach(function (ann, index) {
      if (states[index].verdict) {
        toSubmit.push({ ann: ann, state: states[index] });
      }
    });

    if (!toSubmit.length) {
      summary.textContent = "Mark at least one annotation as correct or incorrect first.";
      return;
    }

    submitButton.disabled = true;
    summary.textContent = "Submitting " + toSubmit.length + " report(s)...";

    let succeeded = 0;
    let failed = 0;

    for (const item of toSubmit) {
      try {
        await submitAnnotationFeedback(slideId, item.ann.annotation_id, item.state);
        item.state.statusEl.textContent = "Submitted ✓";
        item.state.inputs.forEach(function (input) {
          input.disabled = true;
        });
        succeeded += 1;
      } catch (error) {
        item.state.statusEl.textContent = "Failed: " + error.message;
        failed += 1;
      }
    }

    submitButton.disabled = false;
    summary.textContent = succeeded + " submitted" + (failed ? ", " + failed + " failed" : "") + ".";
  });

  actions.appendChild(submitButton);
  actions.appendChild(summary);
  section.appendChild(actions);

  root.appendChild(section);
}

if (window.vmcRequireLogin) {
  window.vmcRequireLogin().then(function (user) {
    if (user) {
      loadAnnotationsForReview();
    }
  });
} else {
  loadAnnotationsForReview();
}
