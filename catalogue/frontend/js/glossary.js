// Third element matches the colour of the actual badge/button shown
// elsewhere on the page for that term - "blue" is the default badge
// colour, everything else names a vmc-badge-<variant> class - so the
// glossary looks consistent with what you actually see on the page.
const VMC_GLOSSARY_TERMS = [
  ["IMG", "Image and share path - the top section of a slide's detail page: the slide image and where to find the file on the network share.", "blue"],
  ["MET", "Metadata - organ, species, stain, and other descriptive information recorded for a slide.", "blue"],
  ["ANN", "Slide annotations - teacher and workflow annotations attached to a slide.", "blue"],
  ["EXP", "Expert contributor notes - commentary and notes added by expert contributors (see About).", "gold"],
  ["TEC", "Technical metadata - image dimensions, scanner information, and other file-level technical details.", "blue"],
  ["ZST", "Z-stack - this slide was captured as multiple focal planes rather than a single flat image.", "green"],
  ["MVI", "Multiview - this slide has more than one associated image or view.", "purple"],
  ["CMP", "Comparison slide - intended for side-by-side comparison with another slide.", "maroon"],
  ["TSL", "Thick section - a thicker-than-standard tissue section.", "slate"],
  ["MPP", "Microns per pixel - the real-world distance one image pixel represents; a measure of scan resolution.", "blue"],
  ["NDPI", "A whole-slide image file format produced by Hamamatsu NanoZoomer scanners.", "blue"],
  ["SCN", "A whole-slide image file format (.scn).", "blue"],
  ["20X", "Objective magnification - this slide was scanned at 20x magnification.", "blue"],
  ["40X", "Objective magnification - this slide was scanned at 40x magnification.", "blue"]
];

function vmcCreateGlossaryWidget() {
  const wrapper = document.createElement("div");
  wrapper.className = "vmc-glossary-wrapper";

  const toggle = document.createElement("button");
  toggle.type = "button";
  toggle.className = "vmc-glossary-toggle";
  toggle.textContent = "GLO";
  toggle.title = "Glossary of abbreviations used on this page";
  toggle.setAttribute("aria-label", "Show glossary of abbreviations");
  toggle.setAttribute("aria-expanded", "false");

  const panel = document.createElement("div");
  panel.className = "vmc-glossary-panel";
  panel.setAttribute("aria-hidden", "true");

  panel.appendChild(document.createElement("h3")).textContent = "Glossary";

  const list = document.createElement("dl");
  list.className = "vmc-glossary-list";

  for (const [term, definition, variant] of VMC_GLOSSARY_TERMS) {
    const dt = document.createElement("dt");
    dt.textContent = term;

    if (variant !== "blue") {
      dt.classList.add("vmc-badge-" + variant);
    }

    const dd = document.createElement("dd");
    dd.textContent = definition;

    list.appendChild(dt);
    list.appendChild(dd);
  }

  panel.appendChild(list);

  toggle.addEventListener("click", function () {
    const isOpen = wrapper.classList.toggle("is-open");
    toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
    panel.setAttribute("aria-hidden", isOpen ? "false" : "true");
  });

  document.addEventListener("click", function (event) {
    if (!wrapper.contains(event.target) && wrapper.classList.contains("is-open")) {
      wrapper.classList.remove("is-open");
      toggle.setAttribute("aria-expanded", "false");
      panel.setAttribute("aria-hidden", "true");
    }
  });

  wrapper.appendChild(toggle);
  wrapper.appendChild(panel);
  return wrapper;
}

document.addEventListener("DOMContentLoaded", function () {
  const page = document.querySelector("main.vmc-page");

  if (!page) {
    return;
  }

  page.insertBefore(vmcCreateGlossaryWidget(), page.firstChild);
});
