const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
const node = (tag, text = "", className = "") => {
  const element = document.createElement(tag);
  if (text !== undefined && text !== null) element.textContent = String(text);
  if (className) element.className = className;
  return element;
};
const iconFor = (category) => ({ Technology: "⌘", Business: "↗", Design: "✳", Science: "✦", Mathematics: "∑", Creative: "✎" }[category] || "✦");

function setFeedback(element, message, kind = "error") {
  if (!element) return;
  element.textContent = message || "";
  element.classList.remove("error", "success");
  if (message) element.classList.add(kind);
}

function apiError(error, target) {
  setFeedback(target, error.message, "error");
  window.eduToast?.(error.message, true);
}

function element(tag, text, className, parent) {
  const created = node(tag, text, className);
  if (parent) parent.append(created);
  return created;
}

function button(label, className = "button", action) {
  const control = node("button", label, className);
  control.type = "button";
  if (action) control.addEventListener("click", action);
  return control;
}

function link(label, href, className = "") {
  const anchor = node("a", label, className);
  anchor.href = href;
  return anchor;
}

function courseCard(course) {
  const card = node("article", undefined, "card course-card");
  const art = node("div", undefined, "course-art");
  art.dataset.category = course.category || "Learning";
  art.append(node("span", course.category || "Learning", "pill"));
  const body = node("div", undefined, "course-card-body");
  body.append(node("div", `${iconFor(course.category)}  ${course.duration_hours || 0} hours  ·  ${course.level}`, "course-meta"));
  const titleNode = node("h3");
  titleNode.append(link(course.title, `/course.html?slug=${encodeURIComponent(course.slug || course.id)}`));
  body.append(titleNode);
  body.append(node("p", course.description || "Learn practical skills with expert guidance.", "small-text"));
  const meta = node("div", undefined, "course-meta");
  meta.append(node("span", `★ ${Number(course.rating_avg || 0).toFixed(1)}`, "rating"));
  meta.append(node("span", `by ${course.instructor || "EduHub faculty"}`));
  body.append(meta);
  const foot = node("div", undefined, "course-foot");
  const price = node("div", undefined, "price");
  price.append(document.createTextNode(`$${Number(course.discounted_price ?? course.price ?? 0).toFixed(0)}`));
  if (course.discounted_price !== null && course.discounted_price !== undefined && course.discounted_price < course.price) {
    price.append(node("del", `$${Number(course.price).toFixed(0)}`));
  }
  foot.append(price, link("Explore course →", `/course.html?slug=${encodeURIComponent(course.slug || course.id)}`, "small-text"));
  body.append(foot);
  card.append(art, body);
  return card;
}

function renderCourses(target, courses) {
  target.replaceChildren();
  if (!courses.length) {
    target.append(node("p", "No courses found. Try adjusting your filters.", "empty-state"));
    return;
  }
  courses.forEach((course) => target.append(courseCard(course)));
}

async function homePage() {
  const coursesTarget = $("#featured-courses");
  try {
    const courses = await window.eduApi("/api/courses?sort=popular&per_page=6");
    renderCourses(coursesTarget, courses.slice(0, 6));
  } catch (error) { apiError(error, $("#home-feedback")); }
  try {
    const popular = await window.eduApi("/api/courses?sort=rating&per_page=4");
    renderCourses($("#popular-courses"), popular.slice(0, 4));
  } catch (error) { apiError(error, $("#home-feedback")); }

  const categoriesTarget = $("#category-grid");
  if (categoriesTarget) {
    try {
      const categories = await window.eduApi("/api/categories");
      categories.forEach((category) => {
        const card = node("a", undefined, "category-card");
        card.href = `/courses.html?category=${encodeURIComponent(category.name)}`;
        card.append(node("span", iconFor(category.name), "category-icon"), node("strong", category.name), node("span", "Explore courses →", "small-text muted"));
        categoriesTarget.append(card);
      });
    } catch (error) { apiError(error, $("#home-feedback")); }
  }
}

async function catalogPage() {
  const form = $("#catalog-filters");
  const cards = $("#catalog-courses");
  const pageLabel = $("#catalog-count");
  const search = $("#catalog-search");
  const params = new URLSearchParams(location.search);
  if (params.has("q")) search.value = params.get("q");
  if (params.has("category")) form.elements.category.value = params.get("category");
  let page = 1;
  const load = async () => {
    const query = new URLSearchParams();
    if (search.value.trim()) query.set("q", search.value.trim());
    if (form.elements.category.value) query.set("category", form.elements.category.value);
    if (form.elements.level.value) query.set("level", form.elements.level.value);
    if (form.elements.max_price.value) query.set("max_price", form.elements.max_price.value);
    query.set("sort", form.elements.sort.value);
    query.set("page", String(page));
    query.set("per_page", "9");
    try {
      const result = await window.eduApi(`/api/courses?${query}`);
      renderCourses(cards, result);
      pageLabel.textContent = `${result.length ? `Showing ${result.length} ` : "No "}courses · page ${page}`;
      $("#catalog-prev").disabled = page <= 1;
      $("#catalog-next").disabled = result.length < 9;
    } catch (error) { apiError(error, $("#catalog-feedback")); }
  };
  form.addEventListener("submit", (event) => { event.preventDefault(); page = 1; load(); });
  $("#catalog-prev").addEventListener("click", () => { page = Math.max(1, page - 1); load(); });
  $("#catalog-next").addEventListener("click", () => { page += 1; load(); });
  try {
    const categories = await window.eduApi("/api/categories");
    categories.forEach(({ name }) => {
      const option = node("option", name);
      option.value = name;
      form.elements.category.append(option);
    });
    if (params.has("category")) form.elements.category.value = params.get("category");
  } catch (error) { apiError(error, $("#catalog-feedback")); }
  load();
}

async function coursePage() {
  const key = new URLSearchParams(location.search).get("slug") || new URLSearchParams(location.search).get("id");
  const target = $("#course-detail");
  if (!key) { setFeedback($("#course-feedback"), "Choose a course from the catalog."); return; }
  try {
    const course = await window.eduApi(`/api/courses/${encodeURIComponent(key)}`);
    document.title = `${course.title} | EduHub`;
    $("#course-title").textContent = course.title;
    $("#course-category").textContent = course.category;
    $("#course-description").textContent = course.description;
    $("#course-instructor").textContent = course.instructor;
    $("#course-level").textContent = `${course.level} · ${course.duration_hours} hours · ${course.language}`;
    $("#course-rating").textContent = `★ ${Number(course.rating_avg).toFixed(1)} (${course.rating_count} learners)`;
    $("#course-price").textContent = `$${Number(course.discounted_price ?? course.price).toFixed(2)}`;
    if (course.discounted_price !== null && course.discounted_price < course.price) {
      $("#course-original-price").textContent = `$${Number(course.price).toFixed(2)}`;
    }
    const curriculum = $("#course-curriculum");
    course.sections.forEach((section) => {
      const details = document.createElement("details");
      const summary = node("summary", `${section.title} · ${section.lessons.length} lessons`);
      details.append(summary);
      section.lessons.forEach((lesson) => details.append(node("p", `${lesson.title} · ${lesson.duration_minutes} min${lesson.preview ? " · Preview" : ""}`, "lesson-link")));
      curriculum.append(details);
    });
    $("#add-cart").addEventListener("click", async () => {
      try {
        await window.eduApi("/api/cart", { method: "POST", body: { course_id: course.id } });
        window.eduToast("Added to your cart.");
      } catch (error) {
        if (error.status === 401) location.href = `/login.html?next=${encodeURIComponent(location.pathname + location.search)}`;
        else apiError(error, $("#course-feedback"));
      }
    });
    $("#add-wishlist").addEventListener("click", async () => {
      try {
        await window.eduApi("/api/wishlist", { method: "POST", body: { course_id: course.id } });
        window.eduToast("Saved to your wishlist.");
      } catch (error) {
        if (error.status === 401) location.href = "/login.html";
        else apiError(error, $("#course-feedback"));
      }
    });
    const reviewList = $("#review-list");
    (course.reviews || []).forEach((review) => {
      const item = node("article", undefined, "card quote-card");
      item.append(node("div", `${"★".repeat(review.rating)}${"☆".repeat(5 - review.rating)}`, "rating"));
      item.append(node("p", review.comment));
      item.append(node("strong", review.name));
      reviewList.append(item);
    });
    if (!course.reviews?.length) {
      reviewList.append(node("p", "No reviews yet. Enrolled learners can share the first one.", "empty-state"));
    }
    const reviewForm = $("#review-form");
    reviewForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      const data = Object.fromEntries(new FormData(reviewForm));
      data.rating = Number(data.rating);
      try {
        await window.eduApi(`/api/courses/${course.id}/reviews`, { method: "POST", body: data });
        window.eduToast("Thanks for sharing your review.");
        location.reload();
      } catch (error) { apiError(error, $("#course-feedback")); }
    });
    target.classList.remove("hidden");
  } catch (error) { apiError(error, $("#course-feedback")); }
}

function formData(form) { return Object.fromEntries(new FormData(form).entries()); }
function redirectAfterLogin() {
  const next = new URLSearchParams(location.search).get("next");
  if (!next || !next.startsWith("/")) return "/dashboard.html";
  try {
    const destination = new URL(next, location.origin);
    return destination.origin === location.origin ? `${destination.pathname}${destination.search}${destination.hash}` : "/dashboard.html";
  } catch { return "/dashboard.html"; }
}

function authPage(kind) {
  const form = $(`#${kind}-form`);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    setFeedback($(`#${kind}-feedback`), "");
    try {
      await window.eduApi(`/api/auth/${kind}`, { method: "POST", body: formData(form) });
      location.assign(kind === "login" ? redirectAfterLogin() : "/dashboard.html");
    } catch (error) { apiError(error, $(`#${kind}-feedback`)); }
  });
}

function forgotPage() {
  $("#forgot-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const result = await window.eduApi("/api/auth/forgot-password", { method: "POST", body: formData(event.currentTarget) });
      setFeedback($("#forgot-feedback"), result.message, "success");
    } catch (error) { apiError(error, $("#forgot-feedback")); }
  });
}

function resetPage() {
  const token = new URLSearchParams(location.search).get("token") || "";
  $("#reset-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = formData(event.currentTarget);
    if (data.password !== data.confirm_password) {
      setFeedback($("#reset-feedback"), "Your passwords do not match.");
      return;
    }
    try {
      const result = await window.eduApi("/api/auth/reset-password", { method: "POST", body: { token, password: data.password } });
      setFeedback($("#reset-feedback"), result.message, "success");
    } catch (error) { apiError(error, $("#reset-feedback")); }
  });
}

async function profilePage() {
  const form = $("#profile-form");
  try {
    const user = await window.eduApi("/api/me");
    for (const name of ["name", "email", "age", "phone"]) form.elements[name].value = user[name] ?? "";
    $("#verified-status").textContent = user.email_verified ? "Email verified" : "Email verification is pending (mocked).";
  } catch (error) {
    if (error.status === 401) location.href = "/login.html?next=%2Fprofile.html";
    else apiError(error, $("#profile-feedback"));
    return;
  }
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = formData(form);
    data.age = data.age ? Number(data.age) : null;
    data.phone = data.phone || null;
    delete data.email;
    try {
      const user = await window.eduApi("/api/me", { method: "PUT", body: data });
      $("#verified-status").textContent = user.email_verified ? "Email verified" : "Email verification is pending (mocked).";
      setFeedback($("#profile-feedback"), "Your profile was saved.", "success");
      window.eduToast("Profile updated.");
    } catch (error) { apiError(error, $("#profile-feedback")); }
  });
  $("#change-password-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = formData(event.currentTarget);
    if (data.new_password !== data.confirm_password) return setFeedback($("#password-feedback"), "Your passwords do not match.");
    delete data.confirm_password;
    try {
      const result = await window.eduApi("/api/auth/change-password", { method: "POST", body: data });
      event.currentTarget.reset();
      setFeedback($("#password-feedback"), result.message, "success");
    } catch (error) { apiError(error, $("#password-feedback")); }
  });
  $("#verify-email-button").addEventListener("click", async () => {
    try {
      const result = await window.eduApi("/api/auth/verify-email", { method: "POST" });
      $("#verified-status").textContent = result.message;
      window.eduToast(result.message);
    } catch (error) { apiError(error, $("#profile-feedback")); }
  });
}

async function cartPage() {
  const target = $("#cart-items");
  const render = async () => {
    try {
      const data = await window.eduApi("/api/cart");
      target.replaceChildren();
      let total = 0;
      data.items.forEach((item) => {
        const price = Number(item.discounted_price ?? item.price);
        total += price;
        const row = node("article", undefined, "cart-row card");
        row.append(link(item.title, `/course.html?slug=${encodeURIComponent(item.slug)}`), node("span", `$${price.toFixed(2)}`));
        const remove = button("Remove", "button ghost small", async () => {
          try { await window.eduApi(`/api/cart/${item.course_id}`, { method: "DELETE" }); await render(); }
          catch (error) { apiError(error, $("#cart-feedback")); }
        });
        row.append(remove);
        target.append(row);
      });
      $("#cart-total").textContent = `$${total.toFixed(2)}`;
      $("#cart-checkout").classList.toggle("hidden", !data.items.length);
      if (!data.items.length) target.append(node("p", "Your cart is waiting for a great course.", "empty-state"));
    } catch (error) {
      if (error.status === 401) location.href = "/login.html?next=%2Fcart.html";
      else apiError(error, $("#cart-feedback"));
    }
  };
  await render();
}

async function checkoutPage() {
  const cart = await window.eduApi("/api/cart").catch((error) => {
    if (error.status === 401) location.href = "/login.html?next=%2Fcheckout.html";
    else apiError(error, $("#checkout-feedback"));
    return null;
  });
  if (!cart) return;
  if (!cart.items.length) {
    $("#checkout-items").append(node("p", "Your cart is empty.", "empty-state"));
    return;
  }
  const subtotal = cart.items.reduce((sum, item) => sum + Number(item.discounted_price ?? item.price), 0);
  $("#checkout-subtotal").textContent = `$${subtotal.toFixed(2)}`;
  $("#checkout-total").textContent = `$${subtotal.toFixed(2)}`;
  cart.items.forEach((item) => $("#checkout-items").append(node("p", `${item.title} · $${Number(item.discounted_price ?? item.price).toFixed(2)}`)));
  $("#coupon-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const result = await window.eduApi("/api/coupons/validate", { method: "POST", body: { code: $("#coupon-code").value, subtotal } });
      $("#checkout-total").textContent = `$${Number(result.total).toFixed(2)}`;
      $("#checkout-discount").textContent = `−$${Number(result.discount).toFixed(2)} (${result.code})`;
      $("#coupon-feedback").textContent = "Coupon applied.";
      $("#coupon-feedback").className = "feedback success";
    } catch (error) { apiError(error, $("#coupon-feedback")); }
  });
  $("#payment-method").addEventListener("change", (event) => {
    $("#last4-field").classList.toggle("hidden", event.target.value !== "card");
  });
  $("#checkout-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = formData(event.currentTarget);
    const payload = {
      course_ids: cart.items.map((item) => item.course_id),
      coupon_code: $("#coupon-code").value.trim() || null,
      payment_method: data.payment_method,
      last4: data.payment_method === "card" ? data.last4 : null
    };
    try {
      const order = await window.eduApi("/api/checkout", { method: "POST", body: payload });
      location.assign(`/order-success.html?id=${order.id}`);
    } catch (error) { apiError(error, $("#checkout-feedback")); }
  });
}

function renderOrder(order, container) {
  const card = node("article", undefined, "card order-card");
  const heading = node("div", undefined, "inline");
  heading.append(node("h3", order.invoice_number), node("span", order.status, "badge"));
  card.append(heading, node("p", new Date(order.created_at).toLocaleDateString()));
  order.items.forEach((item) => card.append(node("p", `${item.title} · $${Number(item.price).toFixed(2)}`)));
  card.append(node("p", `Total paid: $${Number(order.total).toFixed(2)}`));
  card.append(link("View receipt →", `/invoice.html?id=${order.id}`, "button secondary small"));
  container.append(card);
}

async function successPage() {
  const id = new URLSearchParams(location.search).get("id");
  if (!id) return setFeedback($("#success-feedback"), "No order was selected.");
  try {
    const order = await window.eduApi(`/api/orders/${encodeURIComponent(id)}`);
    $("#success-invoice").textContent = order.invoice_number;
    $("#success-total").textContent = `$${Number(order.total).toFixed(2)}`;
    $("#success-receipt").href = `/invoice.html?id=${order.id}`;
  } catch (error) { apiError(error, $("#success-feedback")); }
}

async function invoicePage() {
  const id = new URLSearchParams(location.search).get("id");
  if (!id) return setFeedback($("#invoice-feedback"), "No receipt was selected.");
  try {
    const [order, user] = await Promise.all([window.eduApi(`/api/orders/${encodeURIComponent(id)}`), window.eduApi("/api/me")]);
    $("#print-invoice").addEventListener("click", () => window.print());
    $("#invoice-number").textContent = order.invoice_number;
    $("#invoice-name").textContent = user.name;
    $("#invoice-email").textContent = user.email;
    $("#invoice-date").textContent = new Date(order.created_at).toLocaleDateString();
    order.items.forEach((item) => {
      const row = document.createElement("tr");
      [item.title, `$${Number(item.price).toFixed(2)}`].forEach((value) => row.append(node("td", value)));
      $("#invoice-lines").append(row);
    });
    $("#invoice-subtotal").textContent = `$${Number(order.subtotal).toFixed(2)}`;
    $("#invoice-discount").textContent = `−$${Number(order.discount).toFixed(2)}`;
    $("#invoice-total").textContent = `$${Number(order.total).toFixed(2)}`;
    $("#invoice-payment").textContent = `${order.payment_method}${order.payment_last4 ? ` · •••• ${order.payment_last4}` : ""} (mock payment)`;
  } catch (error) { apiError(error, $("#invoice-feedback")); }
}

async function dashboardPage() {
  try {
    const result = await window.eduApi("/api/learning/dashboard");
    $("#dashboard-enrolled").textContent = String(result.enrolled_count);
    $("#dashboard-completed").textContent = String(result.completed_count);
    const target = $("#dashboard-courses");
    if (!result.courses.length) target.append(node("p", "You have not enrolled yet. Explore a course to get started.", "empty-state"));
    result.courses.forEach((course) => {
      const card = node("article", undefined, "card learning-card");
      card.append(node("div", iconFor(course.category), "learning-art"));
      const details = node("div");
      details.append(node("span", course.category, "eyebrow"), node("h3", course.title));
      const progress = node("div", undefined, "progress");
      const meter = node("span");
      meter.style.width = `${course.progress}%`;
      progress.append(meter);
      details.append(progress, node("p", `${course.progress}% complete · ${course.completed_lessons}/${course.total_lessons} lessons`, "small-text"));
      if (course.progress === 100) details.append(link("View certificate", `/certificate.html?course=${course.course_id}`, "button secondary small"));
      else if (course.continue_lesson_id) details.append(link("Continue learning →", `/player.html?course=${encodeURIComponent(course.slug)}&lesson=${course.continue_lesson_id}`, "button small"));
      card.append(details);
      target.append(card);
    });
  } catch (error) {
    if (error.status === 401) location.href = "/login.html?next=%2Fdashboard.html";
    else apiError(error, $("#dashboard-feedback"));
  }
}

async function ordersPage() {
  try {
    const orders = await window.eduApi("/api/orders/me");
    if (!orders.length) $("#order-list").append(node("p", "Your orders will show up here after checkout.", "empty-state"));
    orders.forEach((order) => renderOrder(order, $("#order-list")));
    const enrollments = await window.eduApi("/api/enrollments/me");
    enrollments.forEach((row) => {
      const item = node("div", undefined, "inline enrollment-history-row");
      item.append(node("strong", row.course_title), node("span", row.status, "badge neutral"),
        node("span", `${row.progress || 0}% complete`, "small-text muted"));
      if (row.status === "confirmed") item.append(button("Cancel enrollment", "button outline small", async () => {
        try {
          await window.eduApi(`/api/enrollments/${row.id}`, { method: "DELETE" });
          window.eduToast("Enrollment canceled.");
          location.reload();
        } catch (error) { apiError(error, $("#orders-feedback")); }
      }));
      $("#enrollment-history").append(item);
    });
  } catch (error) {
    if (error.status === 401) location.href = "/login.html?next=%2Forders.html";
    else apiError(error, $("#orders-feedback"));
  }
}

async function wishlistPage() {
  try {
    const data = await window.eduApi("/api/wishlist");
    const target = $("#wishlist-items");
    if (!data.items.length) target.append(node("p", "Save a course to come back to it later.", "empty-state"));
    data.items.forEach((course) => {
      const card = node("article", undefined, "card learning-card");
      card.append(node("div", iconFor(course.category), "learning-art"));
      const details = node("div");
      details.append(node("h3", course.title), node("p", course.instructor));
      const remove = button("Remove", "button outline small", async () => {
        try { await window.eduApi(`/api/wishlist/${course.course_id}`, { method: "DELETE" }); location.reload(); }
        catch (error) { apiError(error, $("#wishlist-feedback")); }
      });
      details.append(link("View course", `/course.html?slug=${encodeURIComponent(course.slug)}`, "button secondary small"), remove);
      card.append(details);
      target.append(card);
    });
  } catch (error) {
    if (error.status === 401) location.href = "/login.html?next=%2Fwishlist.html";
    else apiError(error, $("#wishlist-feedback"));
  }
}

async function contactPage() {
  $("#contact-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const result = await window.eduApi("/api/contact", { method: "POST", body: formData(event.currentTarget) });
      setFeedback($("#contact-feedback"), result.message, "success");
      event.currentTarget.reset();
    } catch (error) { apiError(error, $("#contact-feedback")); }
  });
}

async function playerPage() {
  const params = new URLSearchParams(location.search);
  const key = params.get("course");
  try {
    const course = await window.eduApi(`/api/learning/courses/${encodeURIComponent(key || "")}`);
    $("#player-title").textContent = course.title;
    const lessonItems = course.sections.flatMap((section) => section.lessons.map((lesson) => ({ ...lesson, section: section.title })));
    const renderLesson = (lesson) => {
      $("#player-current-title").textContent = lesson.title;
      $("#player-section-title").textContent = lesson.section;
      $("#player-complete").dataset.lessonId = String(lesson.id);
      $("#player-complete").disabled = lesson.completed;
      $("#player-complete").textContent = lesson.completed ? "Completed ✓" : "Mark lesson complete";
    };
    const list = $("#player-lessons");
    course.sections.forEach((section) => {
      list.append(node("h3", section.title));
      section.lessons.forEach((lesson) => {
        const row = button(`${lesson.completed ? "✓ " : ""}${lesson.title} · ${lesson.duration_minutes} min`, "ghost player-lesson");
        row.addEventListener("click", () => renderLesson({ ...lesson, section: section.title }));
        list.append(row);
      });
    });
    const initial = lessonItems.find((item) => String(item.id) === params.get("lesson")) || lessonItems.find((item) => !item.completed) || lessonItems[0];
    if (initial) renderLesson(initial);
    $("#player-complete").addEventListener("click", async (event) => {
      try {
        const result = await window.eduApi(`/api/lessons/${event.currentTarget.dataset.lessonId}/complete`, { method: "POST", body: { completed: true } });
        $("#player-progress").textContent = `${result.progress}% complete`;
        if (result.certificate_available) {
          $("#certificate-link").href = `/certificate.html?course=${course.course_id}`;
          $("#certificate-link").classList.remove("hidden");
        }
        window.eduToast("Lesson marked complete.");
        location.reload();
      } catch (error) { apiError(error, $("#player-feedback")); }
    });
    $("#player-progress").textContent = `${course.progress}% complete`;
  } catch (error) {
    if (error.status === 401) location.href = "/login.html";
    else apiError(error, $("#player-feedback"));
  }
}

async function certificatePage() {
  const courseId = new URLSearchParams(location.search).get("course");
  try {
    const certificate = await window.eduApi(`/api/certificates/${encodeURIComponent(courseId || "")}`);
    $("#certificate-learner").textContent = certificate.learner;
    $("#certificate-course").textContent = certificate.course;
    $("#certificate-instructor").textContent = certificate.instructor;
    $("#certificate-date").textContent = new Date(certificate.issued_at).toLocaleDateString();
    $("#certificate-id").textContent = certificate.certificate_id;
    $("#certificate-content").classList.remove("hidden");
    $("#print-certificate").addEventListener("click", () => window.print());
  } catch (error) {
    if (error.status === 401) location.href = "/login.html";
    else apiError(error, $("#certificate-feedback"));
  }
}

function appendCell(row, text) { row.append(node("td", text)); }

async function adminPage() {
  try {
    const stats = await window.eduApi("/api/admin/stats");
    Object.entries({ "Total learners": stats.users, "Course revenue": `$${Number(stats.revenue).toFixed(2)}`, "Active enrollments": stats.enrollments, "Unread messages": stats.new_messages })
      .forEach(([label, value]) => {
        const card = node("div", undefined, "card stat-card");
        card.append(node("strong", value), node("span", label));
        $("#admin-stats").append(card);
      });
    const max = Math.max(1, stats.users, stats.enrollments, stats.new_messages);
    [stats.users, stats.enrollments, stats.new_messages, stats.users * .6, stats.enrollments * .8, max].forEach((value, index) => {
      const bar = node("span");
      bar.style.height = `${Math.max(10, Number(value) / max * 100)}%`;
      bar.title = `Activity ${index + 1}`;
      $("#admin-chart").append(bar);
    });
  } catch (error) { apiError(error, $("#admin-feedback")); return; }

  try {
    const [courses, categories, coupons, users, orders, messages] = await Promise.all([
      window.eduApi("/api/admin/courses"), window.eduApi("/api/admin/categories"),
      window.eduApi("/api/admin/coupons"), window.eduApi("/api/admin/users"),
      window.eduApi("/api/admin/orders"), window.eduApi("/api/admin/messages")
    ]);
    const courseTable = $("#admin-course-rows");
    courses.forEach((course) => {
      const row = document.createElement("tr");
      [course.title, course.category, `$${Number(course.price).toFixed(2)}`, course.is_published ? "Published" : "Hidden"].forEach((text) => appendCell(row, text));
      const actions = node("td");
      actions.append(button("Edit", "button secondary small", () => {
        const form = $("#admin-course-form");
        form.dataset.editId = String(course.id);
        ["title", "description", "level", "price", "discounted_price", "category", "instructor", "duration_hours", "language"].forEach((name) => {
          form.elements[name].value = course[name] ?? "";
        });
        $("#course-save-button").textContent = "Save course";
        $("#course-cancel-edit").classList.remove("hidden");
        form.scrollIntoView({ behavior: "smooth", block: "center" });
      }));
      if (course.is_published) actions.append(button("Archive", "button outline small", async () => {
        try { await window.eduApi(`/api/admin/courses/${course.id}`, { method: "DELETE" }); adminPage(); }
        catch (error) { apiError(error, $("#admin-feedback")); }
      }));
      row.append(actions);
      courseTable.append(row);
    });
    const categorySelect = $("#admin-category-select");
    categories.forEach((category) => {
      const row = document.createElement("tr");
      appendCell(row, category.name);
      const action = node("td");
      action.append(button("Edit", "button secondary small", () => {
        const form = $("#admin-category-form");
        form.dataset.editId = String(category.id);
        form.elements.name.value = category.name;
        $("#category-save-button").textContent = "Save category";
        $("#category-cancel-edit").classList.remove("hidden");
      }));
      action.append(button("Remove", "button outline small", async () => {
        try { await window.eduApi(`/api/admin/categories/${category.id}`, { method: "DELETE" }); location.reload(); }
        catch (error) { apiError(error, $("#admin-feedback")); }
      }));
      row.append(action);
      $("#admin-category-rows").append(row);
      const option = node("option", category.name);
      option.value = category.name;
      categorySelect.append(option);
    });
    coupons.forEach((coupon) => {
      const row = document.createElement("tr");
      [coupon.code, coupon.kind, coupon.value, `${coupon.usage_count}${coupon.usage_limit ? ` / ${coupon.usage_limit}` : ""}`, coupon.is_active ? "Active" : "Inactive"].forEach((text) => appendCell(row, text));
      const actions = node("td");
      actions.append(button("Edit", "button secondary small", () => {
        const form = $("#admin-coupon-form");
        form.dataset.editId = String(coupon.id);
        form.elements.code.value = coupon.code;
        form.elements.kind.value = coupon.kind;
        form.elements.value.value = String(coupon.value);
        form.elements.usage_limit.value = coupon.usage_limit ?? "";
        form.elements.expires_at.value = coupon.expires_at ? new Date(coupon.expires_at).toISOString().slice(0, 16) : "";
        form.querySelector('button[type="submit"]').textContent = "Save coupon";
      }));
      actions.append(button("Delete", "button outline small", async () => {
        try { await window.eduApi(`/api/admin/coupons/${coupon.id}`, { method: "DELETE" }); location.reload(); }
        catch (error) { apiError(error, $("#admin-feedback")); }
      }));
      row.append(actions);
      $("#admin-coupon-rows").append(row);
    });
    users.items.forEach((user) => {
      const row = document.createElement("tr");
      [user.name, user.email, user.is_admin ? "Admin" : "Learner", user.is_active ? "Active" : "Disabled"].forEach((text) => appendCell(row, text));
      const action = node("td");
      action.append(button(user.is_active ? "Disable" : "Enable", "button outline small", async () => {
        try { await window.eduApi(`/api/admin/users/${user.id}/active?enabled=${!user.is_active}`, { method: "PATCH" }); location.reload(); }
        catch (error) { apiError(error, $("#admin-feedback")); }
      }));
      row.append(action);
      $("#admin-user-rows").append(row);
    });
    orders.forEach((order) => {
      const row = document.createElement("tr");
      [order.invoice_number, order.user_id, `$${Number(order.total).toFixed(2)}`, new Date(order.created_at).toLocaleDateString(), order.status].forEach((text) => appendCell(row, text));
      $("#admin-order-rows").append(row);
    });
    messages.forEach((message) => {
      const row = document.createElement("tr");
      appendCell(row, message.email);
      appendCell(row, message.message);
      appendCell(row, new Date(message.created_at).toLocaleDateString());
      appendCell(row, message.is_read ? "Read" : "New");
      const action = node("td");
      if (!message.is_read) action.append(button("Mark read", "button secondary small", async () => {
        try { await window.eduApi(`/api/admin/messages/${message.id}/read`, { method: "PATCH" }); location.reload(); }
        catch (error) { apiError(error, $("#admin-feedback")); }
      }));
      row.append(action);
      $("#admin-message-rows").append(row);
    });
  } catch (error) { apiError(error, $("#admin-feedback")); }

  $("#admin-course-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = formData(event.currentTarget);
    data.price = Number(data.price);
    data.discounted_price = data.discounted_price ? Number(data.discounted_price) : null;
    data.duration_hours = Number(data.duration_hours);
    data.is_published = true;
    try {
      const editId = event.currentTarget.dataset.editId;
      await window.eduApi(editId ? `/api/admin/courses/${editId}` : "/api/admin/courses", {
        method: editId ? "PUT" : "POST",
        body: data
      });
      window.eduToast(editId ? "Course updated." : "Course created.");
      location.reload();
    } catch (error) { apiError(error, $("#admin-feedback")); }
  });
  $("#course-cancel-edit").addEventListener("click", () => {
    const form = $("#admin-course-form");
    delete form.dataset.editId;
    form.reset();
    $("#course-save-button").textContent = "Create course";
    $("#course-cancel-edit").classList.add("hidden");
  });
  $("#admin-category-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    try {
      const editId = event.currentTarget.dataset.editId;
      await window.eduApi(editId ? `/api/admin/categories/${editId}` : "/api/admin/categories", {
        method: editId ? "PUT" : "POST",
        body: formData(event.currentTarget)
      });
      location.reload();
    } catch (error) { apiError(error, $("#admin-feedback")); }
  });
  $("#category-cancel-edit").addEventListener("click", () => {
    const form = $("#admin-category-form");
    delete form.dataset.editId;
    form.reset();
    $("#category-save-button").textContent = "Create category";
    $("#category-cancel-edit").classList.add("hidden");
  });
  $("#admin-coupon-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const data = formData(event.currentTarget);
    data.value = Number(data.value);
    data.usage_limit = data.usage_limit ? Number(data.usage_limit) : null;
    data.expires_at = data.expires_at ? new Date(data.expires_at).toISOString() : null;
    try {
      const editId = event.currentTarget.dataset.editId;
      await window.eduApi(editId ? `/api/admin/coupons/${editId}` : "/api/admin/coupons", {
        method: editId ? "PUT" : "POST",
        body: data
      });
      location.reload();
    } catch (error) { apiError(error, $("#admin-feedback")); }
  });
  $$(".admin-tabs [data-target]").forEach((tab) => tab.addEventListener("click", () => {
    $$(".admin-tabs [data-target]").forEach((item) => item.setAttribute("aria-selected", String(item === tab)));
    $$(".admin-panel").forEach((panel) => panel.classList.toggle("hidden", panel.id !== tab.dataset.target));
  }));
}

async function initPage() {
  await window.eduReady;
  const page = document.body.dataset.page;
  const pages = {
    home: homePage,
    catalog: catalogPage,
    course: coursePage,
    login: () => authPage("login"),
    register: () => authPage("register"),
    forgot: forgotPage,
    reset: resetPage,
    profile: profilePage,
    cart: cartPage,
    checkout: checkoutPage,
    success: successPage,
    invoice: invoicePage,
    dashboard: dashboardPage,
    orders: ordersPage,
    wishlist: wishlistPage,
    contact: contactPage,
    player: playerPage,
    certificate: certificatePage,
    admin: adminPage
  };
  if (pages[page]) await pages[page]();
}
document.addEventListener("DOMContentLoaded", initPage);
