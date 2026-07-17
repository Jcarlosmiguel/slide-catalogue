function nextUrl() {
  const params = new URLSearchParams(window.location.search);
  return params.get("next") || "/";
}

document.getElementById("login-form").addEventListener("submit", async function (event) {
  event.preventDefault();

  const status = document.getElementById("login-status");
  status.textContent = "Signing in...";

  const payload = {
    username: document.getElementById("username").value.trim(),
    password: document.getElementById("password").value
  };

  try {
    const response = await fetch("/api/login", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      credentials: "include",
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      status.textContent = "Invalid username or password.";
      return;
    }

    window.location.href = nextUrl();

  } catch (error) {
    status.textContent = "Login failed. Please try again.";
  }
});
