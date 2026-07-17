let currentSlideData = null;

function getSlideId() {
  const params = new URLSearchParams(window.location.search);
  const id = params.get("id");
  return id ? parseInt(id, 10) : null;
}

function getCookie(name) {
  const value = "; " + document.cookie;
  const parts = value.split("; " + name + "=");
  if (parts.length === 2) {
    return parts.pop().split(";").shift();
  }
  return null;
}

function setCookie(name, value, days = 365) {
  const maxAge = days * 24 * 60 * 60;
  document.cookie = name + "=" + value + "; path=/; max-age=" + maxAge + "; SameSite=Lax";
}

function guessOS() {
  const ua = navigator.userAgent.toLowerCase();
  if (ua.includes("windows")) return "windows";
  if (ua.includes("mac os") || ua.includes("macintosh")) return "macos";
  if (ua.includes("linux")) return "linux";
  return "windows";
}

function getPreferredOS() {
  let os = getCookie("mvls_preferred_os");
  if (!os) {
    os = guessOS();
    setCookie("mvls_preferred_os", os);
  }
  return os;
}

function textOrDash(value) {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  return value;
}

function splitArchivePath(path) {
  if (!path) {
    return {
      folder: null,
      filename: null
    };
  }

  const normalised = String(path).replace(/\\/g, "/");
  const parts = normalised.split("/");
  const filename = parts.pop();
  const folder = parts.join("/");

  return {
    folder: folder || null,
    filename: filename || null
  };
}


function boolValue(value) {
  return value === true || value === 1 || value === "1";
}

function normaliseMagnification(value) {
  if (!value) return null;
  return String(value).replace("x", "X");
}

function createEl(tagName, className, text) {
  const el = document.createElement(tagName);
  if (className) el.className = className;
  if (text !== undefined) el.textContent = text;
  return el;
}

function createBadge(text, title, extraClass) {
  const badge = document.createElement("span");
  badge.className = "mvls-badge";
  if (extraClass) badge.classList.add(extraClass);
  badge.textContent = text;
  badge.title = title;
  badge.setAttribute("aria-label", title);
  return badge;
}

function createNotepadBadge() {
  return createBadge("", "David Jenkinson notes available", "mvls-badge-notepad");
}

function addBadges(container, slide) {
  const identity = slide.identity || {};
  const metadata = slide.metadata || {};
  const technical = slide.technical || {};

  if (identity.slide_format) {
    container.appendChild(createBadge(identity.slide_format, "Slide format: " + identity.slide_format));
  }

  const mag = normaliseMagnification(technical.objective_magnifications || metadata.magnification);
  if (mag) {
    container.appendChild(createBadge(mag, "Objective magnification: " + mag, "mvls-badge-gold"));
  }

  if ((slide.slide_annotations || []).length > 0) {
    container.appendChild(createBadge("ANN", "Slide annotations available"));
  }

  if ((slide.david_notes || []).length > 0) {
    container.appendChild(createNotepadBadge());
  }

  if (boolValue(metadata.is_z_stack) || metadata.z_plane_count > 1) {
    container.appendChild(createBadge("ZST", "Z-stack slide"));
  }

  if (metadata.meaningful_view_count && metadata.meaningful_view_count > 1) {
    container.appendChild(createBadge("MVI", "Multiview slide"));
  }

  if (boolValue(metadata.is_comparison_slide)) {
    container.appendChild(createBadge("CMP", "Comparison slide"));
  }

  if (boolValue(metadata.legacy_thick_section)) {
    container.appendChild(createBadge("TSL", "Thick section"));
  }
}


function appendSubjectDivider(root) {
  const divider = document.createElement("hr");
  divider.className = "mvls-subject-divider";
  root.appendChild(divider);
}

function appendAnnotationSeparator(root) {
  const divider = document.createElement("hr");
  divider.className = "mvls-annotation-separator";
  root.appendChild(divider);
}

function createDetailItem(label, value) {
  const item = createEl("div", "mvls-detail-item");
  item.appendChild(createEl("span", "mvls-detail-label", label));
  item.appendChild(createEl("div", "", textOrDash(value)));
  return item;
}

function renderDetailGrid(container, items) {
  const grid = createEl("div", "mvls-detail-grid");
  for (const [label, value] of items) {
    grid.appendChild(createDetailItem(label, value));
  }
  container.appendChild(grid);
}

function getTissueSummary(slide) {
  const tissues = slide.tissue_annotations || [];
  if (!tissues.length) return "—";

  return tissues
    .map(t => t.canonical_tissue || t.tissue_name)
    .filter(Boolean)
    .join("; ");
}


function createSectionNavigator(root) {
  const nav = createEl("nav", "mvls-section-nav");
  nav.setAttribute("aria-label", "Slide detail sections");

  const sections = [
    ["slide-top", "IM", "Image and share path", ""],
    ["slide-metadata", "MD", "Metadata", ""],
    ["slide-annotations", "AN", "Slide annotations", ""],
    ["slide-david", "NT", "David Jenkinson notes", "mvls-section-nav-gold"],
    ["slide-technical", "TM", "Technical metadata", ""],
  ];

  for (const [targetId, label, title, extraClass] of sections) {
    const button = createEl("button", "mvls-section-nav-button", label);
    button.type = "button";
    button.title = title;
    button.setAttribute("aria-label", title);

    if (extraClass) {
      button.classList.add(extraClass);
    }

    button.addEventListener("click", function () {
      const target = document.getElementById(targetId);
      if (target) {
        target.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });

    nav.appendChild(button);
  }

  root.appendChild(nav);
}

function renderTopSection(root, slide) {
  const identity = slide.identity || {};
  const metadata = slide.metadata || {};
  const fileLocation = slide.file_location || {};
  const technical = slide.technical || {};

  const top = createEl("div", "mvls-slide-top mvls-section-anchor");
  top.id = "slide-top";

  const imageBlock = createEl("div");
  const imageButton = createEl("button", "mvls-slide-preview-button");
  imageButton.type = "button";
  imageButton.title = "Open larger preview";

  const image = document.createElement("img");
  image.className = "mvls-slide-preview";
  image.src = slide.thumbnails.detail;
  image.alt = "Preview image for slide " + slide.slide_id;

  imageButton.appendChild(image);
  imageButton.addEventListener("click", () => openModal(slide.thumbnails.large));

  imageBlock.appendChild(imageButton);
  imageBlock.appendChild(createEl("p", "mvls-muted", "Click image to open larger preview."));

  const archivePartsForImage = splitArchivePath(fileLocation.archive_relative_path);
  const filenamePanel = createEl("div", "mvls-filename-panel");
  filenamePanel.appendChild(createEl("strong", "", "Filename"));
  filenamePanel.appendChild(createEl("div", "mvls-filename-text", archivePartsForImage.filename || identity.filename || "—"));
  imageBlock.appendChild(filenamePanel);

  const summary = createEl("div", "mvls-slide-summary");

  const organ = textOrDash(metadata.organ);
  const tissue = getTissueSummary(slide);
  const species = textOrDash(metadata.species);
  const stain = textOrDash(metadata.canonical_stain || metadata.raw_stain);

  summary.appendChild(createEl("h2", "", "Slide " + slide.slide_id));
  summary.appendChild(createEl("p", "mvls-summary-highlight", organ + (tissue !== "—" ? " / " + tissue : "")));
  summary.appendChild(createEl("p", "mvls-summary-line", species + " · " + stain));
  summary.appendChild(createEl("p", "mvls-slide-id", "Slide ID: " + slide.slide_id));

  const badgeRow = createEl("div", "mvls-badge-row");
  addBadges(badgeRow, slide);
  summary.appendChild(badgeRow);

  const sharePanel = createEl("div", "mvls-share-panel");
  sharePanel.appendChild(createEl("h3", "", "Share path"));

  const controls = createEl("div", "mvls-share-controls");

  const osField = createEl("div", "mvls-field");
  const osLabel = createEl("label", "", "Path format");
  osLabel.setAttribute("for", "os-select");

  const osSelect = document.createElement("select");
  osSelect.id = "os-select";
  for (const [value, label] of [["windows", "Windows"], ["macos", "macOS"], ["linux", "Linux"]]) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    if (fileLocation.selected_os === value) option.selected = true;
    osSelect.appendChild(option);
  }

  osSelect.addEventListener("change", function () {
    setCookie("mvls_preferred_os", osSelect.value);
    loadSlide(osSelect.value);
  });

  osField.appendChild(osLabel);
  osField.appendChild(osSelect);
  controls.appendChild(osField);

  sharePanel.appendChild(controls);

  const archiveParts = splitArchivePath(fileLocation.archive_relative_path);
  const shareParts = splitArchivePath(fileLocation.resolved_share_path);

  sharePanel.appendChild(createEl("p", "mvls-path-label", "Archive folder"));
  const archiveFolder = createEl("div", "mvls-path-box mvls-path-box-wrap", textOrDash(archiveParts.folder));
  sharePanel.appendChild(archiveFolder);

  sharePanel.appendChild(createEl("p", "mvls-path-label", "Filename"));
  const archiveFilename = createEl("div", "mvls-path-box mvls-path-box-wrap", textOrDash(archiveParts.filename || identity.filename));
  sharePanel.appendChild(archiveFilename);

  sharePanel.appendChild(createEl("p", "mvls-path-label", fileLocation.display_name + " share path"));
  const sharePath = createEl("div", "mvls-path-box mvls-path-box-wrap", textOrDash(fileLocation.resolved_share_path));
  sharePath.id = "resolved-share-path";
  sharePanel.appendChild(sharePath);

  const copyRow = createEl("div", "mvls-actions");
  const copyButton = createEl("button", "mvls-button", "Copy path");
  copyButton.type = "button";
  const copyStatus = createEl("span", "mvls-copy-status", "");

  copyButton.addEventListener("click", async function () {
    try {
      await navigator.clipboard.writeText(fileLocation.resolved_share_path || "");
      copyStatus.textContent = "Copied";
      setTimeout(() => copyStatus.textContent = "", 1800);
    } catch {
      copyStatus.textContent = "Copy failed";
    }
  });

  copyRow.appendChild(copyButton);
  copyRow.appendChild(copyStatus);
  sharePanel.appendChild(copyRow);

  summary.appendChild(sharePanel);

  top.appendChild(imageBlock);
  top.appendChild(summary);

  root.appendChild(top);
}



function getFeedbackUser() {
  if (window.MVLS_USER) {
    return {
      username: window.MVLS_USER.username || "unknown_user",
      email: window.MVLS_USER.email || "",
      displayName: window.MVLS_USER.display_name || window.MVLS_USER.username || "Authenticated user",
      role: window.MVLS_USER.role || ""
    };
  }

  return {
    username: "unknown_user",
    email: "",
    displayName: "Authenticated user",
    role: ""
  };
}

function feedbackGuidanceText(category) {
  if (category === "organ") {
    return "Please describe why the organ may be incorrect and provide the suggested organ if known. Useful evidence may include the slide image, filename, archive folder, teaching context, or annotation notes.";
  }

  if (category === "tissue") {
    return "Please describe the tissue correction or addition. If possible, explain whether the current tissue category is wrong, incomplete, or too broad.";
  }

  if (category === "species") {
    return "Please provide the suspected species and the evidence used, such as filename, teaching collection, morphology, or associated notes.";
  }

  if (category === "stain") {
    return "Please provide the suspected stain and any visual clues or contextual evidence. If the raw stain and canonical stain differ, mention which value appears wrong.";
  }

  return "Please describe the metadata issue, correction, or useful teaching context. Include as much evidence as possible so the catalogue can be reviewed safely.";
}

function ensureMetadataFeedbackModal() {
  let modal = document.getElementById("metadata-feedback-modal");

  if (modal) {
    return modal;
  }

  modal = createEl("div", "mvls-feedback-modal");
  modal.id = "metadata-feedback-modal";
  modal.setAttribute("aria-hidden", "true");

  const dialog = createEl("div", "mvls-feedback-dialog");
  dialog.setAttribute("role", "dialog");
  dialog.setAttribute("aria-modal", "true");
  dialog.setAttribute("aria-labelledby", "metadata-feedback-title");

  const title = createEl("h2", "", "Metadata feedback");
  title.id = "metadata-feedback-title";
  dialog.appendChild(title);

  const guidance = createEl("div", "mvls-feedback-guidance");
  guidance.id = "feedback-guidance";
  dialog.appendChild(guidance);

  const form = document.createElement("form");
  form.id = "metadata-feedback-form";

  const grid = createEl("div", "mvls-feedback-grid");

  const readonlyFields = [
    ["feedback-slide-id", "Slide ID", "text"],
    ["feedback-filename", "Filename", "text"],
    ["feedback-username", "Username", "text"],
    ["feedback-email", "Email", "email"]
  ];

  for (const [id, labelText, type] of readonlyFields) {
    const field = createEl("div", "mvls-field");

    const label = createEl("label", "", labelText);
    label.setAttribute("for", id);

    const input = document.createElement("input");
    input.id = id;
    input.name = id;
    input.type = type;
    input.readOnly = true;

    field.appendChild(label);
    field.appendChild(input);
    grid.appendChild(field);
  }

  const categoryField = createEl("div", "mvls-field");
  const categoryLabel = createEl("label", "", "Metadata area");
  categoryLabel.setAttribute("for", "feedback-category");

  const categorySelect = document.createElement("select");
  categorySelect.id = "feedback-category";
  categorySelect.name = "feedback-category";

  const categories = [
    ["organ", "Organ"],
    ["tissue", "Tissue"],
    ["species", "Species"],
    ["stain", "Stain"],
    ["general_comment", "General metadata comment"]
  ];

  for (const [value, label] of categories) {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = label;
    categorySelect.appendChild(option);
  }

  categoryField.appendChild(categoryLabel);
  categoryField.appendChild(categorySelect);
  grid.appendChild(categoryField);

  const suggestedField = createEl("div", "mvls-field");
  const suggestedLabel = createEl("label", "", "Suggested correction");
  suggestedLabel.setAttribute("for", "feedback-suggested-value");

  const suggestedInput = document.createElement("input");
  suggestedInput.id = "feedback-suggested-value";
  suggestedInput.name = "feedback-suggested-value";
  suggestedInput.type = "text";
  suggestedInput.placeholder = "Optional, e.g. PAS, Mouse, Kidney, Epithelium";

  suggestedField.appendChild(suggestedLabel);
  suggestedField.appendChild(suggestedInput);
  grid.appendChild(suggestedField);

  form.appendChild(grid);

  const currentField = createEl("div", "mvls-field");
  currentField.style.marginTop = "0.85rem";

  const currentLabel = createEl("label", "", "Current value / context");
  currentLabel.setAttribute("for", "feedback-current-value");

  const currentBox = createEl("div", "mvls-feedback-current-context");
  currentBox.id = "feedback-current-value";

  currentField.appendChild(currentLabel);
  currentField.appendChild(currentBox);
  form.appendChild(currentField);

  const commentsField = createEl("div", "mvls-field");
  commentsField.style.marginTop = "0.85rem";

  const commentsLabel = createEl("label", "", "Comments, correction or evidence ");
  const required = createEl("span", "mvls-feedback-required", "*");
  commentsLabel.appendChild(required);
  commentsLabel.setAttribute("for", "feedback-comments");

  const comments = document.createElement("textarea");
  comments.id = "feedback-comments";
  comments.name = "feedback-comments";
  comments.placeholder = "Please explain what should be reviewed and why. Include the evidence used, such as filename, slide appearance, annotation, David note, or teaching context.";
  comments.required = true;

  commentsField.appendChild(commentsLabel);
  commentsField.appendChild(comments);
  form.appendChild(commentsField);

  const actions = createEl("div", "mvls-feedback-modal-actions");

  const submit = createEl("button", "mvls-button", "Submit feedback");
  submit.type = "submit";

  const cancel = createEl("button", "mvls-button mvls-button-secondary", "Cancel");
  cancel.type = "button";
  cancel.addEventListener("click", closeMetadataFeedbackModal);

  const status = createEl("span", "mvls-feedback-status", "");
  status.id = "feedback-status";

  actions.appendChild(submit);
  actions.appendChild(cancel);
  actions.appendChild(status);

  form.appendChild(actions);

  form.addEventListener("submit", async function (event) {
    event.preventDefault();

    const user = getFeedbackUser();

    const payload = {
      slide_id: document.getElementById("feedback-slide-id").value,
      filename: document.getElementById("feedback-filename").value,
      submitter_username: user.username,
      submitter_email: user.email,
      submitter_display_name: user.displayName,
      submitter_role: user.role,
      feedback_type: document.getElementById("feedback-category").value,
      current_value: document.getElementById("feedback-current-value").textContent,
      suggested_value: document.getElementById("feedback-suggested-value").value.trim(),
      feedback_text: document.getElementById("feedback-comments").value.trim(),
      created_at_client: new Date().toISOString()
    };

    if (!payload.feedback_text) {
      status.textContent = "Please add a comment or evidence before submitting.";
      return;
    }

    try {
      status.textContent = "Submitting feedback...";

      const response = await fetch("/api/slides/" + payload.slide_id + "/metadata-feedback", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        credentials: "include",
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        const errorBody = await response.json().catch(function () {
          return {};
        });

        status.textContent = errorBody.detail || "Feedback submission failed.";
        return;
      }

      const result = await response.json();

      console.log("Metadata feedback saved:", result);

      status.textContent = "Feedback submitted for review. Reference ID: " + result.feedback_id;

      setTimeout(function () {
        closeMetadataFeedbackModal();
      }, 1400);

    } catch (error) {
      console.error("Metadata feedback submission failed:", error);
      status.textContent = "Feedback submission failed. Please try again.";
    }
  });

  dialog.appendChild(form);
  modal.appendChild(dialog);

  modal.addEventListener("click", function (event) {
    if (event.target.id === "metadata-feedback-modal") {
      closeMetadataFeedbackModal();
    }
  });

  document.body.appendChild(modal);
  return modal;
}

function metadataCurrentValue(slide, category) {
  const metadata = slide.metadata || {};

  if (category === "organ") {
    return metadata.organ || "No organ value currently recorded.";
  }

  if (category === "tissue") {
    return getTissueSummary(slide) || "No tissue annotation currently displayed.";
  }

  if (category === "species") {
    return metadata.species || "No species value currently recorded.";
  }

  if (category === "stain") {
    const raw = metadata.raw_stain || "—";
    const canonical = metadata.canonical_stain || "—";
    const family = metadata.stain_family || "—";
    return "Raw stain: " + raw + " | Canonical stain: " + canonical + " | Stain family: " + family;
  }

  return [
    "Organ: " + textOrDash(metadata.organ),
    "Tissue: " + textOrDash(getTissueSummary(slide)),
    "Species: " + textOrDash(metadata.species),
    "Raw stain: " + textOrDash(metadata.raw_stain),
    "Canonical stain: " + textOrDash(metadata.canonical_stain),
    "Stain family: " + textOrDash(metadata.stain_family)
  ].join(" | ");
}

function updateFeedbackModalContext(slide) {
  const category = document.getElementById("feedback-category").value;
  document.getElementById("feedback-current-value").textContent = metadataCurrentValue(slide, category);
  document.getElementById("feedback-guidance").innerHTML = "<strong>Guidance:</strong> " + feedbackGuidanceText(category);
}

function openMetadataFeedbackModal(slide) {
  const modal = ensureMetadataFeedbackModal();
  const user = getFeedbackUser();
  const identity = slide.identity || {};

  document.getElementById("feedback-slide-id").value = slide.slide_id;
  document.getElementById("feedback-filename").value = identity.filename || "";
  document.getElementById("feedback-username").value = user.username;
  document.getElementById("feedback-email").value = user.email;

  document.getElementById("feedback-category").value = "general_comment";
  document.getElementById("feedback-suggested-value").value = "";
  document.getElementById("feedback-comments").value = "";
  document.getElementById("feedback-status").textContent = "";

  updateFeedbackModalContext(slide);

  document.getElementById("feedback-category").onchange = function () {
    updateFeedbackModalContext(slide);
  };

  modal.classList.add("is-open");
  modal.setAttribute("aria-hidden", "false");
  document.getElementById("feedback-comments").focus();
}

function closeMetadataFeedbackModal() {
  const modal = document.getElementById("metadata-feedback-modal");
  if (modal) {
    modal.classList.remove("is-open");
    modal.setAttribute("aria-hidden", "true");
  }
}

function addMetadataFeedbackButton(section, slide) {
  const row = createEl("div", "mvls-feedback-button-row");
  const button = createEl("button", "mvls-button", "Metadata feedback");
  button.type = "button";
  button.addEventListener("click", function () {
    openMetadataFeedbackModal(slide);
  });

  row.appendChild(button);
  section.appendChild(row);
}


function renderMetadataSection(root, slide) {
  const identity = slide.identity || {};
  const metadata = slide.metadata || {};
  const technical = slide.technical || {};

  const section = createEl("section", "mvls-section mvls-section-anchor");
  section.id = "slide-metadata";
  section.appendChild(createEl("h2", "", "Metadata"));

  renderDetailGrid(section, [
    ["Organ", metadata.organ],
    ["Tissue", getTissueSummary(slide)],
    ["Species", metadata.species],
    ["Raw stain", metadata.raw_stain],
    ["Canonical stain", metadata.canonical_stain],
    ["Stain family", metadata.stain_family],
    ["Slide format", identity.slide_format],
    ["Magnification", technical.objective_magnifications || metadata.magnification],
    ["Description", metadata.description],
    ["Notes", metadata.notes],
  ]);

  addMetadataFeedbackButton(section, slide);

  root.appendChild(section);
}

function renderAnnotations(root, slide) {
  const annotations = slide.slide_annotations || [];

  const section = createEl("section", "mvls-section mvls-section-anchor");
  section.id = "slide-annotations";
  section.appendChild(createEl("h2", "", "Slide annotations"));

  if (!annotations.length) {
    section.appendChild(createEl("div", "mvls-placeholder", "No slide annotations are currently linked to this slide."));
    root.appendChild(section);
    return;
  }

  annotations.forEach(function (ann, index) {
    if (index > 0) {
      appendAnnotationSeparator(section);
    }

    const card = createEl("article", "mvls-annotation-card");
    card.appendChild(createEl("h3", "", ann.title || "Annotation " + ann.annotation_id));
    card.appendChild(createEl("p", "mvls-annotation-meta", "Type: " + textOrDash(ann.annotation_type) + " · Annotation ID: " + ann.annotation_id));

    if (ann.description) {
      card.appendChild(createEl("p", "", ann.description));
    }

    renderDetailGrid(card, [
      ["Rectangle", `x ${ann.rect_x}, y ${ann.rect_y}, w ${ann.rect_w}, h ${ann.rect_h}`],
      ["Window", `x ${ann.window_x}, y ${ann.window_y}, w ${ann.window_w}, h ${ann.window_h}`],
      ["Arrow", `start ${ann.arrow_start_x},${ann.arrow_start_y} · end ${ann.arrow_end_x},${ann.arrow_end_y}`],
      ["Zoom", ann.zoom],
      ["Focal plane", ann.focal_plane],
      ["Current frame", ann.current_frame],
      ["Line colour", ann.line_colour],
      ["Area", ann.area],
    ]);

    section.appendChild(card);
  });

  root.appendChild(section);
}

function renderDavidNotes(root, slide) {
  const notes = slide.david_notes || [];

  const section = createEl("section", "mvls-section mvls-section-anchor");
  section.id = "slide-david";
  section.appendChild(createEl("h2", "", "David Jenkinson notes"));

  if (!notes.length) {
    section.appendChild(createEl("div", "mvls-placeholder", "No David Jenkinson notes are currently linked to this slide."));
    root.appendChild(section);
    return;
  }

  notes.forEach(function (note, index) {
    if (index > 0) {
      appendAnnotationSeparator(section);
    }

    const card = createEl("article", "mvls-david-card");
    card.appendChild(createEl("h3", "", note.annotation_title || "David note " + note.david_record_id));

    if (note.note_text) {
      card.appendChild(createEl("p", "", note.note_text));
    }

    renderDetailGrid(card, [
      ["David record ID", note.david_record_id],
      ["Confidence score", note.confidence_score],
      ["Reconciliation method", note.reconciliation_method],
      ["Reconciliation notes", note.reconciliation_notes],
    ]);

    section.appendChild(card);
  });

  root.appendChild(section);
}

function renderTechnical(root, slide) {
  const technical = slide.technical || {};

  const section = createEl("section", "mvls-section mvls-section-anchor");
  section.id = "slide-technical";
  section.appendChild(createEl("h2", "", "Technical metadata"));

  renderDetailGrid(section, [
    ["File size bytes", technical.file_size_bytes],
    ["Width pixels", technical.width_pixels],
    ["Height pixels", technical.height_pixels],
    ["OpenSlide status", technical.openslide_status],
    ["OpenSlide vendor", technical.openslide_vendor],
    ["OpenSlide MPP X", technical.openslide_mpp_x],
    ["OpenSlide MPP Y", technical.openslide_mpp_y],
    ["TiffSlide status", technical.tiffslide_status],
    ["TiffSlide vendor", technical.tiffslide_vendor],
    ["Technical metadata source", technical.technical_metadata_source],
    ["Technical metadata updated", technical.technical_metadata_updated],
  ]);

  root.appendChild(section);
}

function renderSlide(slide) {
  currentSlideData = slide;
  const root = document.getElementById("slide-detail");
  root.innerHTML = "";

  createSectionNavigator(root);
  renderTopSection(root, slide);

  appendSubjectDivider(root);
  renderMetadataSection(root, slide);

  appendSubjectDivider(root);
  renderAnnotations(root, slide);

  appendSubjectDivider(root);
  renderDavidNotes(root, slide);

  appendSubjectDivider(root);
  renderTechnical(root, slide);
}

async function loadSlide(osKey) {
  const slideId = getSlideId();

  if (!slideId) {
    document.getElementById("slide-detail").innerHTML = "<p>Missing slide ID.</p>";
    return;
  }

  const preferredOS = osKey || getPreferredOS();
  const response = await fetch("/api/slides/" + slideId + "?os=" + encodeURIComponent(preferredOS));

  if (!response.ok) {
    document.getElementById("slide-detail").innerHTML = "<p>Slide not found.</p>";
    return;
  }

  const slide = await response.json();
  renderSlide(slide);
}

function openModal(src) {
  const modal = document.getElementById("image-modal");
  const image = document.getElementById("modal-image");
  image.src = src;
  modal.classList.add("is-open");
  modal.setAttribute("aria-hidden", "false");
}

function closeModal() {
  const modal = document.getElementById("image-modal");
  const image = document.getElementById("modal-image");
  modal.classList.remove("is-open");
  modal.setAttribute("aria-hidden", "true");
  image.src = "";
}

document.getElementById("back-to-results").addEventListener("click", function () {
  history.back();
});

document.getElementById("modal-close").addEventListener("click", closeModal);

document.getElementById("image-modal").addEventListener("click", function (event) {
  if (event.target.id === "image-modal") {
    closeModal();
  }
});

document.addEventListener("keydown", function (event) {
  if (event.key === "Escape") {
    closeModal();
  }
});

if (window.mvlsRequireLogin) {
  window.mvlsRequireLogin().then(function (user) {
    if (user) {
      loadSlide();
    }
  });
} else {
  loadSlide();
}
