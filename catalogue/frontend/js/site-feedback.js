document.addEventListener("DOMContentLoaded", async function () {
  // Open to anonymous visitors as well as logged-in users - credentials:
  // "include" below still sends a session cookie when one exists, so a
  // logged-in submission is still attributed; an anonymous one just has
  // no submitter recorded (see get_optional_user() in app/main.py).
  const form = document.getElementById("site-feedback-form");
  const textarea = document.getElementById("site-feedback-text");
  const status = document.getElementById("site-feedback-status");

  form.addEventListener("submit", async function (event) {
    event.preventDefault();

    const feedbackText = textarea.value.trim();

    if (!feedbackText) {
      status.textContent = "Please enter some feedback before submitting.";
      return;
    }

    status.textContent = "Submitting feedback...";

    try {
      const response = await fetch("/api/site-feedback", {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          feedback_text: feedbackText,
          page_url: window.location.href
        })
      });

      if (!response.ok) {
        const errorBody = await response.json().catch(function () {
          return {};
        });

        status.textContent = errorBody.detail || "Feedback submission failed.";
        return;
      }

      textarea.value = "";
      status.textContent = "Thank you - your feedback has been submitted.";

    } catch (error) {
      console.error("Site feedback submission failed:", error);
      status.textContent = "Feedback submission failed. Please try again.";
    }
  });
});
