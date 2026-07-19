async function loadProfile() {
  const status = document.getElementById("profile-status");
  status.textContent = "Loading profile...";

  try {
    const response = await fetch("/api/me/profile", {
      credentials: "include"
    });

    if (!response.ok) {
      throw new Error("Unable to load profile");
    }

    const data = await response.json();
    const profile = data.profile || {};

    document.getElementById("username").value = profile.username || "";
    document.getElementById("full_name").value = profile.full_name || "";
    document.getElementById("email").value = profile.email || "";
    document.getElementById("institution").value = profile.institution || "";
    document.getElementById("guid").value = profile.guid || "";
    status.textContent = "";
  } catch (error) {
    console.error("Unable to load profile", error);
    status.textContent = "Unable to load your profile.";
  }
}

async function saveProfile(event) {
  event.preventDefault();
  const status = document.getElementById("profile-status");
  status.textContent = "Saving...";

  const username = document.getElementById("username").value.trim();
  const guid = document.getElementById("guid").value.trim();
  const email = document.getElementById("email").value.trim();

  if (guid && username !== guid) {
    status.textContent = "When a GUID is present, the username must match the GUID.";
    return;
  }

  if (email && !email.toLowerCase().endsWith("glasgow.ac.uk") && !email.toLowerCase().endsWith("glasgow.ac.uk")) {
    status.textContent = "University email is preferred. Non-University email addresses are allowed but should be used only when appropriate.";
  }

  const payload = {
    username,
    full_name: document.getElementById("full_name").value.trim(),
    email,
    institution: document.getElementById("institution").value.trim(),
    guid,
    current_password: document.getElementById("current_password").value,
    new_password: document.getElementById("new_password").value
  };

  if (payload.new_password && !payload.current_password) {
    status.textContent = "Please enter your current password before changing it.";
    return;
  }

  if (!payload.new_password) {
    delete payload.new_password;
  }
  if (!payload.current_password) {
    delete payload.current_password;
  }

  try {
    const response = await fetch("/api/me/profile", {
      method: "PUT",
      headers: {
        "Content-Type": "application/json"
      },
      credentials: "include",
      body: JSON.stringify(payload)
    });

    const data = await response.json().catch(() => ({}));

    if (!response.ok) {
      throw new Error(data.detail || "Unable to save changes");
    }

    status.textContent = "Profile updated successfully.";
    document.getElementById("current_password").value = "";
    document.getElementById("new_password").value = "";
  } catch (error) {
    status.textContent = error.message || "Unable to save changes.";
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  const user = await window.mvlsRequireLogin?.();
  if (!user) {
    return;
  }

  const form = document.getElementById("profile-form");
  if (form) {
    form.addEventListener("submit", saveProfile);
  }

  await loadProfile();
});
