const state = {
  originalParams: new URLSearchParams(window.location.search),
  offset: 0,
  total: 0,
  limit: 50,
  mode: "paged"
};

function valueOrUnknown(value, fallback) {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }
  return value;
}

function normaliseMagnification(value) {
  if (!value) return null;
  return String(value).replace("x", "X");
}

function createBadge(text, title, extraClass) {
  const badge = document.createElement("span");
  badge.className = "vmc-badge";
  if (extraClass) {
    badge.classList.add(extraClass);
  }
  badge.textContent = text;
  badge.title = title;
  badge.setAttribute("aria-label", title);
  return badge;
}

function addBadges(container, slide) {
  if (slide.slide_format) {
    container.appendChild(createBadge(slide.slide_format, "Slide format: " + slide.slide_format));
  }

  const mag = normaliseMagnification(slide.objective_magnifications);
  if (mag) {
    container.appendChild(createBadge(mag, "Objective magnification: " + mag));
  }

  if (slide.has_slide_annotations) {
    container.appendChild(createBadge("ANN", "Slide annotations available"));
  }

  if (slide.has_david_notes) {
    container.appendChild(createBadge("EXP", "Expert contributor notes available", "vmc-badge-gold"));
  }

  if (slide.is_z_stack || slide.z_plane_count > 1) {
    container.appendChild(createBadge("ZST", "Z-stack slide", "vmc-badge-green"));
  }

  if (slide.is_multiview) {
    container.appendChild(createBadge("MVI", "Multiview slide", "vmc-badge-purple"));
  }

  if (slide.is_comparison_slide) {
    container.appendChild(createBadge("CMP", "Comparison slide", "vmc-badge-maroon"));
  }

  if (slide.legacy_thick_section) {
    container.appendChild(createBadge("TSL", "Thick section", "vmc-badge-slate"));
  }
}

function buildQueryParams(limit, offset) {
  const params = new URLSearchParams();

  for (const [key, value] of state.originalParams.entries()) {
    if (value && !["limit", "offset", "order_by", "order_dir"].includes(key)) {
      params.set(key, value);
    }
  }

  params.set("limit", String(limit));
  params.set("offset", String(offset));
  params.set("order_by", document.getElementById("order-by").value);
  params.set("order_dir", document.getElementById("order-dir").value);

  return params;
}

function createResultCard(slide) {
  const slideId = slide.slide_id;

  const organ = valueOrUnknown(slide.organ, "Unknown organ");
  const tissue = slide.tissue_summary ? " / " + slide.tissue_summary : "";
  const species = valueOrUnknown(slide.species, "Unknown species");
  const stain = valueOrUnknown(slide.canonical_stain || slide.raw_stain, "Unknown stain");

  const card = document.createElement("article");
  card.className = "vmc-result-card";
  card.tabIndex = 0;

  card.addEventListener("click", function () {
    window.location.href = "/slide.html?id=" + slideId;
  });

  card.addEventListener("keydown", function (event) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      window.location.href = "/slide.html?id=" + slideId;
    }
  });

  const imageWrap = document.createElement("div");

  const image = document.createElement("img");
  image.className = "vmc-result-thumb";
  image.src = "/thumbnails/512/" + slideId + ".jpg";
  image.alt = "Thumbnail for slide " + slideId;

  imageWrap.appendChild(image);

  const main = document.createElement("div");
  main.className = "vmc-result-main";

  const title = document.createElement("h3");
  title.textContent = organ + tissue;

  const summary = document.createElement("p");
  summary.className = "vmc-result-summary";
  summary.textContent = species + " · " + stain;

  const slideIdLine = document.createElement("p");
  slideIdLine.className = "vmc-slide-id";
  slideIdLine.textContent = "Slide ID: " + slideId;

  const badgeRow = document.createElement("div");
  badgeRow.className = "vmc-badge-row";
  addBadges(badgeRow, slide);

  main.appendChild(title);
  main.appendChild(summary);
  main.appendChild(slideIdLine);
  main.appendChild(badgeRow);

  card.appendChild(imageWrap);
  card.appendChild(main);

  return card;
}

function renderResults(results) {
  const list = document.getElementById("results-list");
  list.innerHTML = "";

  if (!results.length) {
    const empty = document.createElement("div");
    empty.className = "vmc-empty-state";
    empty.textContent = "No matching slides found.";
    list.appendChild(empty);
    return;
  }

  for (const slide of results) {
    list.appendChild(createResultCard(slide));
  }
}

async function loadResults() {
  const summary = document.getElementById("results-summary");
  const pagination = document.querySelector(".vmc-pagination");

  summary.textContent = "Loading results...";

  state.mode = document.getElementById("view-mode").value;
  state.limit = parseInt(document.getElementById("page-size").value, 10);

  if (state.mode === "all") {
    pagination.style.display = "none";
    await loadAllResults();
    return;
  }

  pagination.style.display = "flex";

  const params = buildQueryParams(state.limit, state.offset);
  const response = await fetch("/api/search?" + params.toString());
  const data = await response.json();

  state.total = data.total;

  renderResults(data.results);

  const start = data.total === 0 ? 0 : state.offset + 1;
  const end = Math.min(state.offset + state.limit, data.total);

  summary.textContent = data.total + " matching slides. Showing " + start + "–" + end + ".";
  document.getElementById("pagination-status").textContent = start + "–" + end + " of " + data.total;

  document.getElementById("prev-page").disabled = state.offset === 0;
  document.getElementById("next-page").disabled = state.offset + state.limit >= data.total;
}

async function loadAllResults() {
  const summary = document.getElementById("results-summary");

  let all = [];
  let offset = 0;
  const chunkSize = 200;
  let total = null;

  while (total === null || offset < total) {
    const params = buildQueryParams(chunkSize, offset);
    const response = await fetch("/api/search?" + params.toString());
    const data = await response.json();

    total = data.total;
    all = all.concat(data.results);
    offset += chunkSize;

    if (data.results.length === 0) {
      break;
    }
  }

  state.total = total || 0;
  renderResults(all);
  summary.textContent = state.total + " matching slides. Showing all results in one scrollable page.";
}

document.getElementById("apply-results-options").addEventListener("click", function () {
  state.offset = 0;
  if (window.vmcRequireLogin) {
  window.vmcRequireLogin().then(function (user) {
    if (user) {
      loadResults();
    }
  });
} else {
  loadResults();
}
});

document.getElementById("prev-page").addEventListener("click", function () {
  state.offset = Math.max(0, state.offset - state.limit);
  if (window.vmcRequireLogin) {
  window.vmcRequireLogin().then(function (user) {
    if (user) {
      loadResults();
    }
  });
} else {
  loadResults();
}
});

document.getElementById("next-page").addEventListener("click", function () {
  state.offset = state.offset + state.limit;
  if (window.vmcRequireLogin) {
  window.vmcRequireLogin().then(function (user) {
    if (user) {
      loadResults();
    }
  });
} else {
  loadResults();
}
});

if (window.vmcRequireLogin) {
  window.vmcRequireLogin().then(function (user) {
    if (user) {
      loadResults();
    }
  });
} else {
  loadResults();
}
