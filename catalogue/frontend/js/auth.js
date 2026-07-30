async function vmcGetCurrentUser() {
  const response = await fetch("/api/me", {
    credentials: "include"
  });

  if (!response.ok) {
    return null;
  }

  const data = await response.json();
  return data.user;
}

let vmcInstitutionIdLabelCache = null;

// The underlying field is always "guid" in the database/API - this is just
// what a deploying institution wants it called on screen (set via the
// INSTITUTION_ID_LABEL env var, see /api/public-config).
async function vmcGetInstitutionIdLabel() {
  if (vmcInstitutionIdLabelCache) {
    return vmcInstitutionIdLabelCache;
  }

  try {
    const response = await fetch("/api/public-config");
    const data = await response.json();
    vmcInstitutionIdLabelCache = data.institution_id_label || "Institution ID";
  } catch (err) {
    vmcInstitutionIdLabelCache = "Institution ID";
  }

  return vmcInstitutionIdLabelCache;
}

function vmcApplyInstitutionIdLabel(label) {
  document.querySelectorAll(".vmc-institution-id-label").forEach(function (el) {
    el.textContent = label;
  });
}

function vmcLoginUrl() {
  const next = encodeURIComponent(window.location.pathname + window.location.search);
  return "/login.html?next=" + next;
}

function vmcUpdateAdminVisibility(user) {
  const adminLinks = document.querySelectorAll(".vmc-admin-nav");

  for (const link of adminLinks) {
    // system_admin is deliberately excluded here, not just admin-or-above:
    // they see the separate "Sysadmin" link instead (below), which links
    // back to /admin/ itself via a breadcrumb, so nothing is unreachable -
    // showing both "Admin" and "Sysadmin" side by side for the same user
    // was redundant and confusing.
    if (user && user.role === "admin") {
      link.style.display = "inline-block";
    } else {
      link.style.display = "none";
    }
  }

  const systemAdminLinks = document.querySelectorAll(".vmc-system-admin-nav");

  for (const link of systemAdminLinks) {
    if (user && user.role === "system_admin") {
      link.style.display = "inline-block";
    } else {
      link.style.display = "none";
    }
  }

  const reviewerLinks = document.querySelectorAll(".vmc-reviewer-nav");

  for (const link of reviewerLinks) {
    if (
      user &&
      ["admin", "system_admin", "reviewer", "expert"].includes(user.role)
    ) {
      link.style.display = "inline-block";
    } else {
      link.style.display = "none";
    }
  }
}

function vmcRenderAuthArea(user) {
  const nav = document.querySelector(".vmc-nav");

  if (!nav) {
    return;
  }

  const existing = document.getElementById("vmc-auth-area");
  if (existing) {
    existing.remove();
  }

  const area = document.createElement("span");
  area.id = "vmc-auth-area";
  area.className = "vmc-auth-area";

  if (user) {
    const label = document.createElement("span");
    label.className = "vmc-auth-user";
    label.textContent = "Signed in: " + user.display_name + " (" + user.role + ")";

    const accountLink = document.createElement("a");
    accountLink.className = "vmc-auth-button";
    accountLink.href = "/my-account.html";
    accountLink.textContent = "My account";

    const button = document.createElement("button");
    button.className = "vmc-auth-button";
    button.type = "button";
    button.textContent = "Log out";
    button.addEventListener("click", vmcLogout);

    area.appendChild(label);
    area.appendChild(accountLink);
    area.appendChild(button);
  } else {
    const link = document.createElement("a");
    link.className = "vmc-auth-button";
    link.href = vmcLoginUrl();
    link.textContent = "Log in";

    area.appendChild(link);
    const requestLink =
        document.createElement("a");

    requestLink.className =
        "vmc-auth-button";

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

async function vmcRequireLogin() {
  const path = window.location.pathname;

  if (path.endsWith("/login.html")) {
    return null;
  }

  const user = await vmcGetCurrentUser();

  if (!user) {
    window.location.href = vmcLoginUrl();
    return null;
  }

  window.VMC_USER = user;

  vmcUpdateAdminVisibility(user);
  vmcRenderAuthArea(user);

  return user;
}

async function vmcLogout() {
  await fetch("/api/logout", {
    method: "POST",
    credentials: "include"
  });

  window.location.href = "/";
}

window.vmcGetCurrentUser = vmcGetCurrentUser;
window.vmcRequireLogin = vmcRequireLogin;
window.vmcLogout = vmcLogout;
window.vmcGetInstitutionIdLabel = vmcGetInstitutionIdLabel;

document.addEventListener("DOMContentLoaded", async function () {
  const user = await vmcGetCurrentUser();

  vmcUpdateAdminVisibility(user);
  vmcRenderAuthArea(user);

  const institutionIdLabel = await vmcGetInstitutionIdLabel();
  vmcApplyInstitutionIdLabel(institutionIdLabel);
});
