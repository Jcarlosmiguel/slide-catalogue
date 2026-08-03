document.addEventListener("DOMContentLoaded", async () => {
  const placeholders = document.querySelectorAll("[data-template-root]");

  if (!placeholders.length) {
    return;
  }

  try {
    const response = await fetch("/documents/master-template.html");

    if (!response.ok) {
      throw new Error("Unable to load shared template");
    }

    let template = await response.text();
    const subtitle = document.documentElement.dataset.pageSubtitle || "Search, review and prepare teaching slides from the virtual microscopy archive.";
    const footerText = document.documentElement.dataset.footerText || "";

    template = template.replace("{{pageSubtitle}}", subtitle);
    template = template.replace("{{footerText}}", footerText ? ` · ${footerText}` : "");

    placeholders.forEach((placeholder) => {
      placeholder.innerHTML = template;
    });
  } catch (error) {
    console.warn("Shared template could not be loaded.", error);
  }
});
