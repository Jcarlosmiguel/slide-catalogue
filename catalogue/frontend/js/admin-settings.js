async function loadSettings() {

    const response = await fetch(
        "/api/admin/settings",
        {
            credentials: "include"
        }
    );

    if (!response.ok) {
        console.error("Unable to load settings");
        return;
    }

    const settings = await response.json();

    document.getElementById(
        "system-name"
    ).value =
        settings.system_name || "";

    document.getElementById(
        "contact-email"
    ).value =
        settings.contact_email || "";

    document.getElementById(
        "registration-email"
    ).value =
        settings.registration_notification_email || "";

    document.getElementById(
        "registration-notify-on-submission"
    ).checked =
        settings.registration_notify_on_submission === "true";

    document.getElementById(
        "registration-notify-on-activation"
    ).checked =
        settings.registration_notify_on_activation === "true";

    document.getElementById(
        "registration-subject"
    ).value =
   	settings.registration_notification_subject || "";

    document.getElementById(
        "registration-message"
    ).value =
        settings.registration_notification_message || "";

    document.getElementById(
        "activation-invite-subject"
    ).value =
        settings.activation_invite_subject || "";

    document.getElementById(
        "activation-invite-message"
    ).value =
        settings.activation_invite_message || "";

    document.getElementById(
        "password-reset-subject"
    ).value =
        settings.password_reset_subject || "";

    document.getElementById(
        "password-reset-message"
    ).value =
        settings.password_reset_message || "";

    document.getElementById(
        "share-access-email"
    ).value =
        settings.share_access_notification_email || "";

    document.getElementById(
        "share-access-subject"
    ).value =
        settings.share_access_notification_subject || "";

    document.getElementById(
        "share-access-message"
    ).value =
        settings.share_access_notification_message || "";

    document.getElementById(
        "contribution-ticker-enabled"
    ).checked =
        settings.contribution_ticker_enabled === "true";

    document.getElementById(
        "contribution-ticker-message"
    ).value =
        settings.contribution_ticker_message || "";

}

async function saveSettings() {

    const payload = {

        system_name:
            document.getElementById(
                "system-name"
            ).value,

        contact_email:
            document.getElementById(
                "contact-email"
            ).value,

        registration_notification_email:
            document.getElementById(
                "registration-email"
            ).value,

        registration_notification_subject:
            document.getElementById(
                "registration-subject"
            ).value,

        registration_notification_message:
            document.getElementById(
                "registration-message"
            ).value,

        registration_notify_on_submission:
            document.getElementById(
                "registration-notify-on-submission"
            ).checked.toString(),

        registration_notify_on_activation:
            document.getElementById(
                "registration-notify-on-activation"
            ).checked.toString(),

        activation_invite_subject:
            document.getElementById(
                "activation-invite-subject"
            ).value,

        activation_invite_message:
            document.getElementById(
                "activation-invite-message"
            ).value,

        password_reset_subject:
            document.getElementById(
                "password-reset-subject"
            ).value,

        password_reset_message:
            document.getElementById(
                "password-reset-message"
            ).value,

        share_access_notification_email:
            document.getElementById(
                "share-access-email"
            ).value,

        share_access_notification_subject:
            document.getElementById(
                "share-access-subject"
            ).value,

        share_access_notification_message:
            document.getElementById(
                "share-access-message"
            ).value,

        contribution_ticker_enabled:
            document.getElementById(
                "contribution-ticker-enabled"
            ).checked.toString(),

        contribution_ticker_message:
            document.getElementById(
                "contribution-ticker-message"
            ).value,

    };

document.getElementById(
        "settings-status"
    ).textContent =
        "Saving...";

    const response = await fetch(
        "/api/admin/settings",
        {
            method: "PATCH",
            credentials: "include",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
        }
    );

    if (!response.ok) {

        document.getElementById(
            "settings-status"
        ).textContent =
            "Unable to save settings.";

        return;
    }

    document.getElementById(
        "settings-status"
    ).textContent =
        "Settings saved.";

}

document.addEventListener(
    "DOMContentLoaded",
    function () {

        loadSettings();

        document.getElementById(
            "save-settings"
        ).addEventListener(
            "click",
            saveSettings
        );
    }
);
