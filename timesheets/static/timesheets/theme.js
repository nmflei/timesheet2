(function () {
  "use strict";

  const storageKey = "theme";
  const root = document.documentElement;

  function applyTheme(theme, persist) {
    const dark = theme === "dark";
    root.dataset.theme = dark ? "dark" : "light";
    if (persist) {
      try {
        window.localStorage.setItem(storageKey, dark ? "dark" : "light");
      } catch {
        // Keep the selected theme for this page when storage is unavailable.
      }
    }
    document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
      button.setAttribute("aria-pressed", String(dark));
      const label = dark ? button.dataset.lightLabel : button.dataset.darkLabel;
      button.setAttribute("aria-label", label);
      button.setAttribute("title", label);
      const icon = button.querySelector("[data-theme-icon]");
      if (icon) icon.textContent = dark ? "☀" : "☾";
    });
  }

  let savedTheme = "light";
  try {
    savedTheme = window.localStorage.getItem(storageKey) === "dark" ? "dark" : "light";
  } catch {
    savedTheme = "light";
  }
  applyTheme(savedTheme, false);

  document.addEventListener("DOMContentLoaded", () => {
    applyTheme(savedTheme, false);
    document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
      button.addEventListener("click", () => {
        applyTheme(root.dataset.theme === "dark" ? "light" : "dark", true);
      });
    });
  });
})();
