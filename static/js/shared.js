(() => {
  const el = (tag, text, className) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  };

  function toast(message, isError = false) {
    let region = document.querySelector(".toast-region");
    if (!region) {
      region = el("div", undefined, "toast-region");
      region.setAttribute("aria-live", "polite");
      document.body.append(region);
    }
    const item = el("div", message, `toast${isError ? " error" : ""}`);
    region.append(item);
    window.setTimeout(() => item.remove(), 4200);
  }
  window.eduToast = toast;

  async function request(url, options = {}) {
    const headers = new Headers(options.headers || {});
    const init = { ...options, headers, credentials: "same-origin" };
    if (options.body && typeof options.body !== "string") {
      headers.set("Content-Type", "application/json");
      init.body = JSON.stringify(options.body);
    }
    const response = await fetch(url, init);
    const contentType = response.headers.get("content-type") || "";
    const result = contentType.includes("application/json") ? await response.json() : await response.text();
    if (!response.ok) {
      let message = result?.detail || "Something went wrong. Please try again.";
      if (result?.errors && Object.keys(result.errors).length) {
        message = Object.entries(result.errors).map(([field, text]) => `${field}: ${text}`).join(" · ");
      }
      const error = new Error(String(message));
      error.status = response.status;
      throw error;
    }
    return result;
  }
  window.eduApi = request;

  function brand() {
    const link = el("a", undefined, "brandmark");
    link.href = "/index.html";
    const icon = el("span", "e", "brand-icon");
    const title = el("span", "eduhub");
    link.append(icon, title);
    return link;
  }

  function renderHeader(user) {
    const header = document.getElementById("site-header");
    if (!header) return;
    header.classList.add("site-header");
    const inner = el("div", undefined, "header-inner");
    inner.append(brand());

    const nav = el("nav", undefined, "site-nav");
    nav.id = "primary-navigation";
    nav.setAttribute("aria-label", "Main navigation");
    const links = [["Courses", "/courses.html"], ["About", "/about.html"], ["FAQ", "/faq.html"], ["Contact", "/contact.html"], ["Cart", "/cart.html"]];
    links.forEach(([label, href]) => {
      const link = el("a", label);
      link.href = href;
      nav.append(link);
    });
    if (user) {
      const menu = el("div", undefined, "user-menu");
      const trigger = el("button", user.name.split(/\s+/)[0], "nav-menu-trigger");
      trigger.type = "button";
      trigger.setAttribute("aria-expanded", "false");
      trigger.setAttribute("aria-haspopup", "true");
      const panel = el("div", undefined, "user-menu-panel hidden");
      const menuLinks = [["Dashboard", "/dashboard.html"], ["Profile", "/profile.html"], ["My courses", "/orders.html"], ["Wishlist", "/wishlist.html"], ["Admin", "/admin.html", user.is_admin]];
      menuLinks.filter(([, , show]) => show !== false).forEach(([label, href, show]) => {
        if (show === undefined && label === "Admin") return;
        const link = el("a", label);
        link.href = href;
        panel.append(link);
      });
      const logout = el("button", "Log out", "small");
      logout.type = "button";
      logout.addEventListener("click", async () => {
        try {
          await request("/api/auth/logout", { method: "POST" });
          window.location.assign("/index.html");
        } catch (error) {
          toast(error.message, true);
        }
      });
      panel.append(logout);
      trigger.addEventListener("click", () => {
        const open = panel.classList.toggle("hidden") === false;
        trigger.setAttribute("aria-expanded", String(open));
      });
      menu.append(trigger, panel);
      nav.append(menu);
    }

    const actions = el("div", undefined, "header-actions");
    const theme = el("button", "◐", "theme-toggle");
    theme.type = "button";
    theme.setAttribute("aria-label", "Toggle dark mode");
    theme.addEventListener("click", toggleTheme);
    actions.append(theme);
    if (!user) {
      const login = el("a", "Log in", "button outline small desktop-auth");
      login.href = "/login.html";
      const register = el("a", "Get started", "button small desktop-auth");
      register.href = "/register.html";
      actions.append(login, register);
    }
    const hamburger = el("button", "☰", "menu-toggle");
    hamburger.type = "button";
    hamburger.setAttribute("aria-label", "Open navigation menu");
    hamburger.setAttribute("aria-controls", nav.id);
    hamburger.setAttribute("aria-expanded", "false");
    hamburger.addEventListener("click", () => {
      const open = nav.classList.toggle("open");
      hamburger.setAttribute("aria-expanded", String(open));
      hamburger.setAttribute("aria-label", open ? "Close navigation menu" : "Open navigation menu");
    });
    actions.append(hamburger);
    inner.append(nav, actions);
    header.replaceChildren(inner);
    applyTheme(document.documentElement.dataset.theme || "light");
  }

  function renderFooter() {
    const footer = document.getElementById("site-footer");
    if (!footer) return;
    footer.classList.add("site-footer");
    const container = el("div", undefined, "container");
    const grid = el("div", undefined, "footer-grid");
    const intro = el("div", undefined, "footer-brand");
    intro.append(brand(), el("p", "Small steps today. Remarkable skills tomorrow."));
    const navigation = (title, rows) => {
      const group = el("div");
      group.append(el("h3", title));
      rows.forEach(([label, href]) => {
        const link = el("a", label);
        link.href = href;
        group.append(link);
      });
      return group;
    };
    grid.append(
      intro,
      navigation("Explore", [["Course catalog", "/courses.html"], ["Pricing", "/pricing.html"], ["About us", "/about.html"], ["FAQs", "/faq.html"]]),
      navigation("Your account", [["Student dashboard", "/dashboard.html"], ["My courses", "/orders.html"], ["Wishlist", "/wishlist.html"], ["Contact", "/contact.html"]])
    );
    const signup = el("div");
    signup.append(el("h3", "A little learning in your inbox"), el("p", "New courses, practical tips, and a note of inspiration."));
    const form = el("form", undefined, "newsletter-form");
    const input = document.createElement("input");
    input.type = "email";
    input.name = "email";
    input.placeholder = "Your email address";
    input.setAttribute("aria-label", "Email address for newsletter");
    input.required = true;
    const submit = el("button", "Join");
    submit.type = "submit";
    form.append(input, submit);
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      try {
        const result = await request("/api/newsletter/subscribe", { method: "POST", body: { email: input.value } });
        toast(result.message);
        form.reset();
      } catch (error) { toast(error.message, true); }
    });
    signup.append(form);
    grid.append(signup);
    const bottom = el("div", undefined, "footer-bottom");
    bottom.append(el("span", `© ${new Date().getFullYear()} EduHub Learning Co.`));
    const legal = el("div", undefined, "inline");
    [["Terms", "/terms.html"], ["Privacy", "/privacy.html"]].forEach(([label, href]) => {
      const link = el("a", label);
      link.href = href;
      legal.append(link);
    });
    bottom.append(legal);
    container.append(grid, bottom);
    footer.replaceChildren(container);
  }

  function getTheme() {
    return localStorage.getItem("eduhub-theme") || (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  }
  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem("eduhub-theme", theme);
    document.querySelectorAll(".theme-toggle").forEach((button) => {
      button.textContent = theme === "dark" ? "☀" : "◐";
      button.setAttribute("aria-label", theme === "dark" ? "Switch to light mode" : "Switch to dark mode");
    });
  }
  function toggleTheme() {
    applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
  }
  applyTheme(getTheme());

  window.eduReady = (async () => {
    renderFooter();
    let user = null;
    try { user = await request("/api/me"); }
    catch (error) { if (error.status !== 401) toast(error.message, true); }
    renderHeader(user);
    return user;
  })();
})();
