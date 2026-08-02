document.addEventListener("DOMContentLoaded", function () {
  fetch("/api/contact-info")
    .then(function (response) { return response.json(); })
    .then(function (data) {
      if (!data.contact_email) {
        return;
      }
      const container = document.getElementById("contact-direct-email");
      const link = document.getElementById("contact-direct-email-link");
      link.href = "mailto:" + data.contact_email;
      link.textContent = data.contact_email;
      container.style.display = "";
    })
    .catch(function (error) {
      console.error("Failed to load contact info:", error);
    });

  const form = document.getElementById("contact-form");
  const nameInput = document.getElementById("contact-name");
  const emailInput = document.getElementById("contact-email");
  const messageInput = document.getElementById("contact-message");
  const status = document.getElementById("contact-status");

  form.addEventListener("submit", async function (event) {
    event.preventDefault();

    const name = nameInput.value.trim();
    const email = emailInput.value.trim();
    const message = messageInput.value.trim();

    if (!name || !email || !message) {
      status.textContent = "Please fill in your name, email, and message before sending.";
      return;
    }

    status.textContent = "Sending...";

    try {
      const response = await fetch("/api/contact", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ name: name, email: email, message: message })
      });

      if (!response.ok) {
        const errorBody = await response.json().catch(function () {
          return {};
        });

        status.textContent = errorBody.detail || "Message could not be sent.";
        return;
      }

      form.reset();
      status.textContent = "Thank you - your message has been sent.";

    } catch (error) {
      console.error("Contact form submission failed:", error);
      status.textContent = "Message could not be sent. Please try again.";
    }
  });
});
