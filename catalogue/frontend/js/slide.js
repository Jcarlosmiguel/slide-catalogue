let currentSlideData = null;

function autoSizeTextarea(el) {
  el.style.height = "auto";
  el.style.height = el.scrollHeight + "px";
}

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
  let os = getCookie("vmc_preferred_os");
  if (!os) {
    os = guessOS();
    setCookie("vmc_preferred_os", os);
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
  badge.className = "vmc-badge";
  if (extraClass) badge.classList.add(extraClass);
  badge.textContent = text;
  badge.title = title;
  badge.setAttribute("aria-label", title);
  return badge;
}

function createNotepadBadge() {
  return createBadge("EXP", "Expert contributor notes available", "vmc-badge-gold");
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
    container.appendChild(createBadge(mag, "Objective magnification: " + mag));
  }

  if ((slide.slide_annotations || []).length > 0) {
    container.appendChild(createBadge("ANN", "Slide annotations available"));
  }

  if ((slide.david_notes || []).length > 0) {
    container.appendChild(createNotepadBadge());
  }

  if (boolValue(metadata.is_z_stack) || metadata.z_plane_count > 1) {
    container.appendChild(createBadge("ZST", "Z-stack slide", "vmc-badge-green"));
  }

  if (metadata.meaningful_view_count && metadata.meaningful_view_count > 1) {
    container.appendChild(createBadge("MVI", "Multiview slide", "vmc-badge-purple"));
  }

  if (boolValue(metadata.is_comparison_slide)) {
    container.appendChild(createBadge("CMP", "Comparison slide", "vmc-badge-maroon"));
  }

  if (boolValue(metadata.legacy_thick_section)) {
    container.appendChild(createBadge("TSL", "Thick section", "vmc-badge-slate"));
  }
}


function appendSubjectDivider(root) {
  const divider = document.createElement("hr");
  divider.className = "vmc-subject-divider";
  root.appendChild(divider);
}

function appendAnnotationSeparator(root) {
  const divider = document.createElement("hr");
  divider.className = "vmc-annotation-separator";
  root.appendChild(divider);
}

function createDetailItem(label, value) {
  const item = createEl("div", "vmc-detail-item");
  item.appendChild(createEl("span", "vmc-detail-label", label));
  item.appendChild(createEl("div", "", textOrDash(value)));
  return item;
}

function renderDetailGrid(container, items) {
  const grid = createEl("div", "vmc-detail-grid");
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


function createSectionNavigator(root, slide) {
  const nav = createEl("nav", "vmc-section-nav");
  nav.setAttribute("aria-label", "Slide detail sections");

  const hasAnnotations = (slide.slide_annotations || []).length > 0;
  const hasExpertNotes = (slide.david_notes || []).length > 0;

  const sections = [
    ["slide-top", "IMG", "Image and share path", ""],
    ["slide-metadata", "MET", "Metadata", ""],
    ["slide-annotations", "ANN", "Slide annotations", hasAnnotations ? "vmc-section-nav-gold" : "vmc-section-nav-muted"],
    ["slide-david", "EXP", "Expert contributor notes", hasExpertNotes ? "vmc-section-nav-gold" : "vmc-section-nav-muted"],
    ["slide-technical", "TEC", "Technical metadata", ""],
  ];

  for (const [targetId, label, title, extraClass] of sections) {
    const button = createEl("button", "vmc-section-nav-button", label);
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

  const top = createEl("div", "vmc-slide-top vmc-section-anchor");
  top.id = "slide-top";

  const imageBlock = createEl("div");
  const imageButton = createEl("button", "vmc-slide-preview-button");
  imageButton.type = "button";
  imageButton.title = "Open larger preview";

  const image = document.createElement("img");
  image.className = "vmc-slide-preview";
  image.src = slide.thumbnails.detail;
  image.alt = "Preview image for slide " + slide.slide_id;

  imageButton.appendChild(image);
  imageButton.addEventListener("click", () => openModal(slide.thumbnails.large));

  imageBlock.appendChild(imageButton);
  imageBlock.appendChild(createEl("p", "vmc-muted", "Click image to open larger preview."));

  const archivePartsForImage = splitArchivePath(fileLocation.archive_relative_path);
  const filenamePanel = createEl("div", "vmc-filename-panel");
  filenamePanel.appendChild(createEl("strong", "", "Filename"));
  filenamePanel.appendChild(createEl("div", "vmc-filename-text", archivePartsForImage.filename || identity.filename || "—"));
  imageBlock.appendChild(filenamePanel);

  const summary = createEl("div", "vmc-slide-summary");

  const organ = textOrDash(metadata.organ);
  const tissue = getTissueSummary(slide);
  const species = textOrDash(metadata.species);
  const stain = textOrDash(metadata.canonical_stain || metadata.raw_stain);

  summary.appendChild(createEl("h2", "", "Slide " + slide.slide_id));
  summary.appendChild(createEl("p", "vmc-summary-highlight", organ + (tissue !== "—" ? " / " + tissue : "")));
  summary.appendChild(createEl("p", "vmc-summary-line", species + " · " + stain));
  summary.appendChild(createEl("p", "vmc-slide-id", "Slide ID: " + slide.slide_id));

  const badgeRow = createEl("div", "vmc-badge-row");
  addBadges(badgeRow, slide);
  summary.appendChild(badgeRow);

  const sharePanel = createEl("div", "vmc-share-panel");
  sharePanel.appendChild(createEl("h3", "", "Share path"));

  const controls = createEl("div", "vmc-share-controls");

  const osField = createEl("div", "vmc-field");
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
    setCookie("vmc_preferred_os", osSelect.value);
    loadSlide(osSelect.value);
  });

  osField.appendChild(osLabel);
  osField.appendChild(osSelect);
  controls.appendChild(osField);

  sharePanel.appendChild(controls);

  const archiveParts = splitArchivePath(fileLocation.archive_relative_path);
  const shareParts = splitArchivePath(fileLocation.resolved_share_path);

  sharePanel.appendChild(createEl("p", "vmc-path-label", "Archive folder"));
  const archiveFolder = createEl("div", "vmc-path-box vmc-path-box-wrap", textOrDash(archiveParts.folder));
  sharePanel.appendChild(archiveFolder);

  sharePanel.appendChild(createEl("p", "vmc-path-label", "Filename"));
  const archiveFilename = createEl("div", "vmc-path-box vmc-path-box-wrap", textOrDash(archiveParts.filename || identity.filename));
  sharePanel.appendChild(archiveFilename);

  sharePanel.appendChild(createEl("p", "vmc-path-label", fileLocation.display_name + " share path"));
  const sharePath = createEl("div", "vmc-path-box vmc-path-box-wrap", textOrDash(fileLocation.resolved_share_path));
  sharePath.id = "resolved-share-path";
  sharePanel.appendChild(sharePath);

  const copyRow = createEl("div", "vmc-actions");
  const copyButton = createEl("button", "vmc-button", "Copy path");
  copyButton.type = "button";
  const copyStatus = createEl("span", "vmc-copy-status", "");

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
  if (window.VMC_USER) {
    return {
      username: window.VMC_USER.username || "unknown_user",
      email: window.VMC_USER.email || "",
      displayName: window.VMC_USER.display_name || window.VMC_USER.username || "Authenticated user",
      role: window.VMC_USER.role || ""
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
    return "Please describe why the organ may be incorrect and provide the suggested organ if known. Useful reasoning may reference the slide's appearance, filename, archive folder, teaching context, or annotation notes.";
  }

  if (category === "tissue") {
    return "Please describe the tissue correction or addition. If possible, explain whether the current tissue category is wrong, incomplete, or too broad.";
  }

  if (category === "species") {
    return "Please provide the suspected species and the reasoning behind it, such as the filename, teaching collection, morphology, or associated notes.";
  }

  if (category === "stain") {
    return "Please provide the suspected stain and describe any visual clues or context that support it. If the raw stain and canonical stain differ, mention which value appears wrong.";
  }

  if (category === "description") {
    return "Please suggest a correction or addition to the slide's description, and explain why the current description is wrong, incomplete, or misleading.";
  }

  if (category === "notes") {
    return "Please suggest a correction or addition to the slide's notes, and explain what should change and why.";
  }

  return "Please describe the metadata issue, correction, or useful teaching context. Include as much reasoning as possible so the catalogue can be reviewed safely.";
}

const dictionaryValueCache = {};

async function fetchDictionaryValues(category) {
  if (dictionaryValueCache[category]) {
    return dictionaryValueCache[category];
  }

  const response = await fetch("/api/dictionaries/" + category, {
    credentials: "include"
  });

  if (!response.ok) {
    return [];
  }

  const result = await response.json();
  dictionaryValueCache[category] = result.values || [];
  return dictionaryValueCache[category];
}

async function updateSuggestedValueControl(category) {
  const container = document.getElementById("feedback-suggested-value-container");
  const otherField = document.getElementById("feedback-suggested-other-field");
  const otherInput = document.getElementById("feedback-suggested-other");

  otherField.style.display = "none";
  otherInput.value = "";

  const dictionaryBackedCategories = ["organ", "tissue", "species", "stain"];

  if (dictionaryBackedCategories.indexOf(category) === -1) {
    container.innerHTML = "";
    const input = document.createElement("input");
    input.id = "feedback-suggested-value";
    input.name = "feedback-suggested-value";
    input.type = "text";
    input.placeholder = "Optional comment or context";
    container.appendChild(input);
    return;
  }

  container.innerHTML = "<em>Loading options...</em>";

  const values = await fetchDictionaryValues(category);

  const select = document.createElement("select");
  select.id = "feedback-suggested-value";
  select.name = "feedback-suggested-value";

  const blank = document.createElement("option");
  blank.value = "";
  blank.textContent = "Select a value...";
  select.appendChild(blank);

  for (const item of values) {
    const option = document.createElement("option");
    option.value = item.value;
    option.textContent = item.label;
    select.appendChild(option);
  }

  const otherOption = document.createElement("option");
  otherOption.value = "__other__";
  otherOption.textContent = "Other (not listed)";
  select.appendChild(otherOption);

  select.addEventListener("change", function () {
    otherField.style.display = select.value === "__other__" ? "block" : "none";
    if (select.value !== "__other__") {
      otherInput.value = "";
    }
  });

  container.innerHTML = "";
  container.appendChild(select);
}

function getSuggestedValue() {
  const control = document.getElementById("feedback-suggested-value");

  if (control && control.value === "__other__") {
    const other = document.getElementById("feedback-suggested-other");
    return other ? other.value.trim() : "";
  }

  return control ? control.value.trim() : "";
}

function ensureMetadataFeedbackModal() {
  let modal = document.getElementById("metadata-correction-modal");

  if (modal) {
    return modal;
  }

  modal = createEl("div", "vmc-feedback-modal");
  modal.id = "metadata-correction-modal";
  modal.setAttribute("aria-hidden", "true");

  const dialog = createEl("div", "vmc-feedback-dialog");
  dialog.setAttribute("role", "dialog");
  dialog.setAttribute("aria-modal", "true");
  dialog.setAttribute("aria-labelledby", "metadata-correction-title");

  const title = createEl("h2", "", "Metadata corrections");
  title.id = "metadata-correction-title";
  dialog.appendChild(title);

  const guidance = createEl("div", "vmc-feedback-guidance");
  guidance.id = "feedback-guidance";
  dialog.appendChild(guidance);

  const form = document.createElement("form");
  form.id = "metadata-correction-form";

  const grid = createEl("div", "vmc-feedback-grid");

  const readonlyFields = [
    ["feedback-slide-id", "Slide ID", "text"],
    ["feedback-filename", "Filename", "text"],
    ["feedback-username", "Username", "text"],
    ["feedback-email", "Email", "email"]
  ];

  for (const [id, labelText, type] of readonlyFields) {
    const field = createEl("div", "vmc-field");

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

  const categoryField = createEl("div", "vmc-field");
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
    ["description", "Description"],
    ["notes", "Notes"],
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

  const suggestedField = createEl("div", "vmc-field");
  const suggestedLabel = createEl("label", "", "Suggested correction");
  suggestedLabel.setAttribute("for", "feedback-suggested-value");

  const suggestedControl = createEl("div", "");
  suggestedControl.id = "feedback-suggested-value-container";

  const suggestedInput = document.createElement("input");
  suggestedInput.id = "feedback-suggested-value";
  suggestedInput.name = "feedback-suggested-value";
  suggestedInput.type = "text";
  suggestedInput.placeholder = "Optional comment or context";
  suggestedControl.appendChild(suggestedInput);

  const otherField = createEl("div", "vmc-field");
  otherField.id = "feedback-suggested-other-field";
  otherField.style.display = "none";
  otherField.style.marginTop = "0.5rem";

  const otherGuidance = createEl(
    "div",
    "vmc-feedback-guidance",
    "Not listed? Describe the new term below so an administrator can review it and add it to the dictionary."
  );

  const otherInput = document.createElement("input");
  otherInput.id = "feedback-suggested-other";
  otherInput.name = "feedback-suggested-other";
  otherInput.type = "text";
  otherInput.placeholder = "e.g. the new organ, tissue, species, or stain name you're suggesting";

  otherField.appendChild(otherGuidance);
  otherField.appendChild(otherInput);

  suggestedField.appendChild(suggestedLabel);
  suggestedField.appendChild(suggestedControl);
  suggestedField.appendChild(otherField);
  grid.appendChild(suggestedField);

  form.appendChild(grid);

  const currentField = createEl("div", "vmc-field");
  currentField.style.marginTop = "0.85rem";

  const currentLabel = createEl("label", "", "Current value / context");
  currentLabel.setAttribute("for", "feedback-current-value");

  const currentBox = createEl("div", "vmc-feedback-current-context");
  currentBox.id = "feedback-current-value";

  currentField.appendChild(currentLabel);
  currentField.appendChild(currentBox);
  form.appendChild(currentField);

  const commentsField = createEl("div", "vmc-field");
  commentsField.style.marginTop = "0.85rem";

  const commentsLabel = createEl("label", "", "Comments and reasoning ");
  const required = createEl("span", "vmc-feedback-required", "*");
  commentsLabel.appendChild(required);
  commentsLabel.setAttribute("for", "feedback-comments");

  const comments = document.createElement("textarea");
  comments.id = "feedback-comments";
  comments.name = "feedback-comments";
  comments.placeholder = "Please explain what should be reviewed and why. Describe your reasoning - for example, referencing the filename, slide appearance, an annotation, an expert contributor note, or teaching context. You can enter multiple corrections from the same slide on different metadata areas.";

  commentsField.appendChild(commentsLabel);
  commentsField.appendChild(comments);
  form.appendChild(commentsField);

  const requiredNote = createEl("p", "vmc-muted", "* Please describe your reasoning to help reviewers");
  requiredNote.style.fontSize = "0.85rem";
  requiredNote.style.marginTop = "0.35rem";
  form.appendChild(requiredNote);

  const actions = createEl("div", "vmc-feedback-modal-actions");

  const submit = createEl("button", "vmc-button", "Submit correction");
  submit.type = "submit";

  const cancel = createEl("button", "vmc-button vmc-button-secondary", "Cancel");
  cancel.type = "button";
  cancel.addEventListener("click", closeMetadataFeedbackModal);

  const status = createEl("span", "vmc-feedback-status", "");
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
      suggested_value: getSuggestedValue(),
      feedback_text: document.getElementById("feedback-comments").value.trim(),
      created_at_client: new Date().toISOString()
    };

    try {
      status.textContent = "Submitting feedback...";

      const response = await fetch("/api/slides/" + payload.slide_id + "/metadata-correction", {
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
    if (event.target.id === "metadata-correction-modal") {
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

  if (category === "description") {
    return metadata.description || "No description currently recorded.";
  }

  if (category === "notes") {
    return metadata.notes || "No notes currently recorded.";
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
  document.getElementById("feedback-comments").value = "";
  document.getElementById("feedback-status").textContent = "";

  updateFeedbackModalContext(slide);
  updateSuggestedValueControl("general_comment");

  document.getElementById("feedback-category").onchange = function () {
    updateFeedbackModalContext(slide);
    updateSuggestedValueControl(document.getElementById("feedback-category").value);
  };

  modal.classList.add("is-open");
  modal.setAttribute("aria-hidden", "false");
  document.getElementById("feedback-comments").focus();
}

function closeMetadataFeedbackModal() {
  const modal = document.getElementById("metadata-correction-modal");
  if (modal) {
    modal.classList.remove("is-open");
    modal.setAttribute("aria-hidden", "true");
  }
}

function addMetadataFeedbackButton(section, slide) {
  const row = createEl("div", "vmc-feedback-button-row");
  const button = createEl("button", "vmc-button", "Metadata corrections");
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

  const section = createEl("section", "vmc-section vmc-section-anchor");
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

function buildQupathScriptToolbar(slideId) {
  const toolbar = createEl("div", "vmc-qupath-toolbar");

  const link = createEl("a", "vmc-button vmc-button-secondary", "Download QuPath script");
  link.id = "qupath-script-link";

  const optionsWrap = createEl("div", "vmc-qupath-options");

  const optionsToggle = createEl("button", "vmc-button vmc-button-secondary vmc-qupath-options-toggle", "Options ▾");
  optionsToggle.type = "button";
  optionsToggle.setAttribute("aria-haspopup", "true");
  optionsToggle.setAttribute("aria-expanded", "false");

  const popup = createEl("div", "vmc-qupath-popup");
  popup.hidden = true;

  const zoomCheckbox = document.createElement("input");
  zoomCheckbox.type = "checkbox";
  zoomCheckbox.id = "qupath-apply-zoom";
  zoomCheckbox.checked = true;

  const colorPicker = document.createElement("input");
  colorPicker.type = "color";
  colorPicker.id = "qupath-annotation-color";
  colorPicker.value = "#ffff00";
  colorPicker.title = "Annotation colour in the generated script";

  function updateLink() {
    const applyZoom = zoomCheckbox.checked ? "true" : "false";
    const color = colorPicker.value.replace("#", "");
    link.href = "/api/slides/" + slideId + "/qupath-script?apply_zoom=" + applyZoom + "&color=" + color;
  }

  zoomCheckbox.addEventListener("change", updateLink);
  colorPicker.addEventListener("change", updateLink);
  updateLink();

  const zoomLabel = createEl("label", "vmc-qupath-popup-row");
  zoomLabel.appendChild(zoomCheckbox);
  zoomLabel.appendChild(document.createTextNode(
    " Apply zoom scaling (experimental - untick and try again if annotations look misplaced in QuPath)"
  ));

  const colorLabel = createEl("label", "vmc-qupath-popup-row");
  colorLabel.appendChild(colorPicker);
  colorLabel.appendChild(document.createTextNode(" Annotation colour"));

  const helpLink = createEl("a", "vmc-qupath-popup-row vmc-qupath-help-link", "How to apply this in QuPath");
  helpLink.href = "/documents/script_annotation.html";
  helpLink.target = "_blank";
  helpLink.rel = "noopener";

  const reportLink = createEl("a", "vmc-qupath-popup-row vmc-qupath-help-link", "Report annotation error");
  reportLink.href = "/annotation-review.html?id=" + slideId;

  popup.appendChild(zoomLabel);
  popup.appendChild(colorLabel);
  popup.appendChild(createEl("hr", "vmc-qupath-popup-divider"));
  popup.appendChild(helpLink);
  popup.appendChild(reportLink);

  function closePopup() {
    popup.hidden = true;
    optionsToggle.setAttribute("aria-expanded", "false");
  }

  optionsToggle.addEventListener("click", function (event) {
    event.stopPropagation();
    const willOpen = popup.hidden;
    popup.hidden = !willOpen;
    optionsToggle.setAttribute("aria-expanded", String(willOpen));
  });

  document.addEventListener("click", function (event) {
    if (!optionsWrap.contains(event.target)) {
      closePopup();
    }
  });

  optionsWrap.appendChild(optionsToggle);
  optionsWrap.appendChild(popup);

  toolbar.appendChild(link);
  toolbar.appendChild(optionsWrap);
  return toolbar;
}

function renderAnnotations(root, slide) {
  const annotations = slide.slide_annotations || [];

  const section = createEl("section", "vmc-section vmc-section-anchor");
  section.id = "slide-annotations";
  section.appendChild(createEl("h2", "", "Slide annotations"));

  if (!annotations.length) {
    section.appendChild(createEl("div", "vmc-placeholder", "No slide annotations are currently linked to this slide."));
    root.appendChild(section);
    return;
  }

  section.appendChild(buildQupathScriptToolbar(slide.slide_id));

  annotations.forEach(function (ann, index) {
    if (index > 0) {
      appendAnnotationSeparator(section);
    }

    const card = createEl("article", "vmc-annotation-card");
    card.appendChild(createEl("h3", "", ann.title || "Annotation " + ann.annotation_id));
    card.appendChild(createEl("p", "vmc-annotation-meta", "Type: " + textOrDash(ann.annotation_type) + " · Annotation ID: " + ann.annotation_id));

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

function canWriteExpertNotes() {
  const role = window.VMC_USER && window.VMC_USER.role;
  return role === "expert" || role === "admin" || role === "system_admin";
}

function buildAddExpertNoteForm(slideId, onSaved) {
  const card = createEl("article", "vmc-annotation-card");
  card.appendChild(createEl("h3", "", "Add an expert note"));

  const titleField = createEl("div", "vmc-field");
  titleField.appendChild(createEl("label", "", "Title (optional)"));
  const titleInput = document.createElement("input");
  titleInput.type = "text";
  titleField.appendChild(titleInput);

  const textField = createEl("div", "vmc-field");
  textField.appendChild(createEl("label", "", "Note"));
  const textInput = document.createElement("textarea");
  textInput.style.minHeight = "80px";
  textInput.style.resize = "none";
  textInput.style.overflow = "hidden";
  textInput.addEventListener("input", function () {
    autoSizeTextarea(textInput);
  });
  textField.appendChild(textInput);

  const actions = createEl("div", "vmc-actions");
  const submitButton = createEl("button", "vmc-button", "Add note");
  submitButton.type = "button";
  const status = createEl("span", "vmc-muted");

  submitButton.addEventListener("click", async function () {
    const noteText = textInput.value.trim();
    if (!noteText) {
      status.textContent = "Note text is required.";
      return;
    }

    status.textContent = "Saving...";

    const response = await fetch("/api/slides/" + slideId + "/expert-notes", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ note_title: titleInput.value.trim() || null, note_text: noteText }),
    });

    if (!response.ok) {
      const error = await response.json().catch(function () {
        return {};
      });
      status.textContent = error.detail || "Could not save note.";
      return;
    }

    status.textContent = "Saved.";
    titleInput.value = "";
    textInput.value = "";
    onSaved();
  });

  actions.appendChild(submitButton);
  actions.appendChild(status);

  card.appendChild(titleField);
  card.appendChild(textField);
  card.appendChild(actions);

  return card;
}

function buildExpertNoteCard(slideId, note, onChanged) {
  const card = createEl("article", "vmc-annotation-card");
  card.appendChild(createEl("h3", "", note.note_title || "Expert note " + note.note_id));
  card.appendChild(createEl(
    "p",
    "vmc-annotation-meta",
    (note.author_display_name || note.author_username) + " · " + note.created_at
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

  if (canWriteExpertNotes()) {
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

      onChanged();
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

      onChanged();
    });

    actions.appendChild(editButton);
    actions.appendChild(saveButton);
    actions.appendChild(deleteButton);
    card.appendChild(actions);
  }

  return card;
}

function buildDavidNoteCard(note, onChanged) {
  const card = createEl("article", "vmc-david-card");

  const canEdit = canWriteExpertNotes();
  let titleInput = null;

  if (canEdit) {
    titleInput = document.createElement("input");
    titleInput.type = "text";
    titleInput.className = "vmc-note-title";
    titleInput.value = note.annotation_title || "";
    titleInput.disabled = true;
    titleInput.style.marginBottom = "0.5rem";
    card.appendChild(titleInput);
  } else {
    card.appendChild(createEl("h3", "", note.annotation_title || "Expert note " + note.david_record_id));
  }

  const textArea = document.createElement("textarea");
  textArea.className = "vmc-note-text";
  textArea.value = note.note_text || "";
  textArea.style.overflow = "hidden";
  textArea.disabled = true;
  textArea.addEventListener("input", function () {
    autoSizeTextarea(textArea);
  });
  card.appendChild(textArea);
  requestAnimationFrame(function () {
    autoSizeTextarea(textArea);
  });

  renderDetailGrid(card, [
    ["David record ID", note.david_record_id],
    ["Confidence score", note.confidence_score],
    ["Reconciliation method", note.reconciliation_method],
    ["Reconciliation notes", note.reconciliation_notes],
  ]);

  if (canEdit) {
    const actions = createEl("div", "vmc-actions");

    const editButton = createEl("button", "vmc-button vmc-button-secondary", "Edit");
    editButton.type = "button";
    const saveButton = createEl("button", "vmc-button", "Save");
    saveButton.type = "button";
    saveButton.hidden = true;

    editButton.addEventListener("click", function () {
      titleInput.disabled = false;
      textArea.disabled = false;
      autoSizeTextarea(textArea);
      editButton.hidden = true;
      saveButton.hidden = false;
    });

    saveButton.addEventListener("click", async function () {
      const response = await fetch("/api/david-notes/" + note.david_record_id, {
        method: "PATCH",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ annotation_title: titleInput.value, note_text: textArea.value }),
      });

      if (!response.ok) {
        alert("Could not save this note.");
        return;
      }

      onChanged();
    });

    actions.appendChild(editButton);
    actions.appendChild(saveButton);
    card.appendChild(actions);
  }

  return card;
}

function renderDavidNotes(root, slide) {
  const notes = slide.david_notes || [];
  const expertNotes = slide.expert_notes || [];

  const section = createEl("section", "vmc-section vmc-section-anchor");
  section.id = "slide-david";
  section.appendChild(createEl("h2", "", "Expert contributor notes"));

  if (canWriteExpertNotes()) {
    section.appendChild(buildAddExpertNoteForm(slide.slide_id, function () {
      loadSlide();
    }));
  }

  if (expertNotes.length) {
    expertNotes.forEach(function (note) {
      section.appendChild(buildExpertNoteCard(slide.slide_id, note, function () {
        loadSlide();
      }));
    });
  }

  if (!notes.length && !expertNotes.length) {
    section.appendChild(createEl("div", "vmc-placeholder", "No expert contributor notes are currently linked to this slide."));
    root.appendChild(section);
    return;
  }

  notes.forEach(function (note, index) {
    if (index > 0 || expertNotes.length) {
      appendAnnotationSeparator(section);
    }

    section.appendChild(buildDavidNoteCard(note, function () {
      loadSlide();
    }));
  });

  root.appendChild(section);
}

function renderTechnical(root, slide) {
  const technical = slide.technical || {};

  const section = createEl("section", "vmc-section vmc-section-anchor");
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

  createSectionNavigator(root, slide);
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

if (window.vmcRequireLogin) {
  window.vmcRequireLogin().then(function (user) {
    if (user) {
      loadSlide();
    }
  });
} else {
  loadSlide();
}
