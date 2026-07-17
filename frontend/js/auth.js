async function mvlsGetCurrentUser() {
  const response = await fetch("/api/me", {
    credentials: "include"
  });

  if (!response.ok) {
    return null;
  }

  const data = await response.json();
  return data.user;
}

function mvlsLoginUrl() {
  const next = encodeURIComponent(window.location.pathname + window.location.search);
  return "/login.html?next=" + next;
}

function mvlsUpdateAdminVisibility(user) {
  const adminLinks = document.querySelectorAll(".mvls-admin-nav");

  for (const link of adminLinks) {
    if (
      user &&
      (user.role === "admin" || user.role === "system_admin")
    ) {
      link.style.display = "inline-block";
    } else {
      link.style.display = "none";
    }
  }
}

function mvlsRenderAuthArea(user) {
  const nav = document.querySelector(".mvls-nav");

  if (!nav) {
    return;
  }

  const existing = document.getElementById("mvls-auth-area");
  if (existing) {
    existing.remove();
  }

  const area = document.createElement("span");
  area.id = "mvls-auth-area";
  area.className = "mvls-auth-area";

  if (user) {
    const label = document.createElement("span");
    label.className = "mvls-auth-user";
    label.textContent = "Signed in: " + user.display_name + " (" + user.role + ")";

    const accountLink = document.createElement("a");
    accountLink.className = "mvls-auth-button";
    accountLink.href = "/my-account.html";
    accountLink.textContent = "My account";

    const button = document.createElement("button");
    button.className = "mvls-auth-button";
    button.type = "button";
    button.textContent = "Log out";
    button.addEventListener("click", mvlsLogout);

    area.appendChild(label);
    area.appendChild(accountLink);
    area.appendChild(button);
  } else {
    const link = document.createElement("a");
    link.className = "mvls-auth-button";
    link.href = mvlsLoginUrl();
    link.textContent = "Log in";

    area.appendChild(link);
    const requestLink =
        document.createElement("a");

    requestLink.className =
        "mvls-auth-button";

    requestLink.href =
        "/request-access.html";

    requestLink.textContent =
        "Request Access";

    requestLink.style.marginLeft =
        "0.5rem";

    area.appendChild(
        requestLink
    );
  }

  nav.appendChild(area);
}

async function mvlsRequireLogin() {
  const path = window.location.pathname;

  if (path.endsWith("/login.html")) {
    return null;
  }

  const user = await mvlsGetCurrentUser();

  if (!user) {
    window.location.href = mvlsLoginUrl();
    return null;
  }

  window.MVLS_USER = user;

  mvlsUpdateAdminVisibility(user);
  mvlsRenderAuthArea(user);

  return user;
}

async function mvlsLogout() {
  await fetch("/api/logout", {
    method: "POST",
    credentials: "include"
  });

  window.location.href = "/login.html";
}

window.mvlsGetCurrentUser = mvlsGetCurrentUser;
window.mvlsRequireLogin = mvlsRequireLogin;
window.mvlsLogout = mvlsLogout;

document.addEventListener("DOMContentLoaded", async function () {
  const user = await mvlsGetCurrentUser();

  mvlsUpdateAdminVisibility(user);
  mvlsRenderAuthArea(user);
});
