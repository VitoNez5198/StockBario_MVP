(function () {
  const THEME_KEY = "sb_theme";
  const SIDEBAR_KEY = "sb_sidebar_collapsed";

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem(THEME_KEY, theme);
    const btn = document.getElementById("theme-toggle");
    if (btn) {
      btn.setAttribute(
        "title",
        theme === "dark" ? "Cambiar a modo claro" : "Cambiar a modo oscuro"
      );
      const iconSun = btn.querySelector("[data-icon='sun']");
      const iconMoon = btn.querySelector("[data-icon='moon']");
      if (iconSun && iconMoon) {
        iconSun.style.display = theme === "dark" ? "inline-flex" : "none";
        iconMoon.style.display = theme === "dark" ? "none" : "inline-flex";
      }
    }
  }

  function initTheme() {
    const saved = localStorage.getItem(THEME_KEY) || "light";
    applyTheme(saved);
    const btn = document.getElementById("theme-toggle");
    if (btn) {
      btn.addEventListener("click", () => {
        const current = document.documentElement.getAttribute("data-theme") || "light";
        applyTheme(current === "dark" ? "light" : "dark");
      });
    }
  }

  function initSidebar() {
    const sidebar = document.getElementById("sidebar");
    const toggle = document.getElementById("sidebar-toggle");
    if (!sidebar || !toggle) return;

    if (localStorage.getItem(SIDEBAR_KEY) === "1") {
      sidebar.classList.add("collapsed");
    }

    toggle.addEventListener("click", () => {
      sidebar.classList.toggle("collapsed");
      localStorage.setItem(
        SIDEBAR_KEY,
        sidebar.classList.contains("collapsed") ? "1" : "0"
      );
    });

    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        document.documentElement.classList.remove("no-sidebar-transition");
      });
    });
  }

  function showToast(mensaje, tipo = "ok") {
    let container = document.getElementById("toast-container");
    if (!container) {
      container = document.createElement("div");
      container.id = "toast-container";
      container.className = "toast-container";
      document.body.appendChild(container);
    }
    const el = document.createElement("div");
    el.className = `toast ${tipo}`;
    el.textContent = mensaje;
    container.appendChild(el);
    setTimeout(() => el.remove(), 3400);
  }

  async function apiFetch(url, options = {}) {
    const res = await fetch(url, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      credentials: "same-origin",
      ...options,
    });
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const msg = data.error || data.detail || "No se pudo completar la operacion";
      throw new Error(msg);
    }
    return data;
  }

  function initLogout() {
    const btn = document.getElementById("logout-btn");
    if (!btn) return;
    btn.addEventListener("click", async () => {
      try {
        await apiFetch("/api/v1/auth/logout", { method: "POST" });
        window.location.href = "/login";
      } catch (err) {
        showToast(err.message, "error");
      }
    });
  }

  window.StockBarrio = { showToast, apiFetch, applyTheme };

  document.addEventListener("DOMContentLoaded", () => {
    initTheme();
    initSidebar();
    initLogout();
    if (window.lucide) {
      window.lucide.createIcons();
    }
  });
})();
