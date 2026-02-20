const cartTotalEl = document.getElementById("cartTotal");
const payBtn = document.getElementById("payBtn");
const cartBar = document.querySelector(".cart-bar");
const addButtons = document.querySelectorAll("[data-add]");
const questionForm = document.getElementById("questionForm");
const questionInput = document.getElementById("questionInput");
const leadModal = document.getElementById("leadModal");
const leadCard = document.querySelector(".lead-card");
const leadForm = document.getElementById("leadForm");
const leadSkip = document.getElementById("leadSkip");
const leadClose = document.getElementById("leadClose");
const actionButtons = document.querySelectorAll("[data-action]");

const APP_BACKEND_URL = window.APP_CONFIG?.backendUrl || "";
const LEAD_STORAGE_KEY = "leadFormCompleted_v1";

let total = 0;

const formatPrice = (value) =>
  new Intl.NumberFormat("ru-RU").format(value) + " ₽";

const updateCart = () => {
  cartTotalEl.textContent = formatPrice(total);
  payBtn.disabled = total === 0;
};

addButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    const value = Number(btn.dataset.add || 0);
    total += value;
    updateCart();
    btn.textContent = "Добавлено";
    btn.disabled = true;
    setTimeout(() => {
      btn.textContent = "В корзину";
      btn.disabled = false;
    }, 1600);
  });
});

if (!addButtons.length && cartBar) {
  cartBar.classList.add("hidden");
}

const getWebApp = () => (window.Telegram ? window.Telegram.WebApp : null);
const isTelegramContext = () => {
  const webapp = getWebApp();
  if (!webapp) return false;
  if (typeof webapp.initData === "string" && webapp.initData.length > 0) return true;
  return /Telegram/i.test(navigator.userAgent);
};
const notifyUser = (message) => {
  const webapp = getWebApp();
  if (webapp && typeof webapp.showAlert === "function") {
    try {
      webapp.showAlert(message);
      return;
    } catch (error) {
      // Fallback to native alert below.
    }
  }
  alert(message);
};

const storageGet = (key) => {
  try {
    return localStorage.getItem(key);
  } catch (error) {
    return null;
  }
};

const storageSet = (key, value) => {
  try {
    localStorage.setItem(key, value);
  } catch (error) {
    // Ignore storage errors in restricted WebView contexts.
  }
};

const fillLeadForm = () => {
  if (!leadForm) return;
  const nameInput = document.getElementById("leadName");
  const contactInput = document.getElementById("leadContact");
  const webapp = getWebApp();
  const user = webapp?.initDataUnsafe?.user;
  if (user && nameInput && !nameInput.value) {
    const fullName = [user.first_name, user.last_name].filter(Boolean).join(" ");
    nameInput.value = fullName || "";
  }
  if (user && user.username && contactInput && !contactInput.value) {
    contactInput.value = `@${user.username}`;
  }
};

const openLeadModal = () => {
  if (!leadModal) return;
  leadModal.classList.add("active");
  leadModal.setAttribute("aria-hidden", "false");
  if (leadCard) {
    leadCard.scrollTop = 0;
  }
  document.body.style.overflow = "hidden";
  fillLeadForm();
};

const closeLeadModal = () => {
  if (!leadModal) return;
  leadModal.classList.remove("active");
  leadModal.setAttribute("aria-hidden", "true");
  document.body.style.overflow = "";
};

if (leadModal && isTelegramContext() && !storageGet(LEAD_STORAGE_KEY)) {
  setTimeout(openLeadModal, 300);
}

if (leadSkip) {
  leadSkip.addEventListener("click", () => {
    storageSet(LEAD_STORAGE_KEY, "1");
    closeLeadModal();
  });
}

if (leadClose) {
  leadClose.addEventListener("click", closeLeadModal);
}

if (leadModal) {
  leadModal.addEventListener("click", (event) => {
    if (event.target === leadModal) {
      closeLeadModal();
    }
  });
}

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeLeadModal();
  }
});

const scrollToSection = (selector) => {
  const section = document.querySelector(selector);
  if (section) {
    section.scrollIntoView({ behavior: "smooth", block: "start" });
  }
};

actionButtons.forEach((button) => {
  button.addEventListener("click", () => {
    const action = button.dataset.action;
    if (action === "open-lead") {
      openLeadModal();
      return;
    }
    if (action === "scroll-questions") {
      scrollToSection("#questions");
      return;
    }
    if (action === "scroll-directions") {
      scrollToSection("#directions");
      return;
    }
    if (action === "scroll-about") {
      scrollToSection("#about");
    }
  });
});

const sendPayload = async (payload) => {
  const webapp = getWebApp();
  const queryId = webapp?.initDataUnsafe?.query_id;
  if (APP_BACKEND_URL) {
    const envelope = {
      query_id: queryId || "",
      init_data: webapp?.initData || "",
      payload,
    };
    try {
      const response = await fetch(`${APP_BACKEND_URL}/webapp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(envelope),
      });
      if (!response.ok) {
        throw new Error(`Backend error: ${response.status}`);
      }
      return;
    } catch (error) {
      // Fallback for strict CORS deployments: fire-and-forget delivery.
      await fetch(`${APP_BACKEND_URL}/webapp`, {
        method: "POST",
        mode: "no-cors",
        headers: { "Content-Type": "text/plain;charset=UTF-8" },
        body: JSON.stringify(envelope),
      });
    }
    return;
  }
  if (webapp && webapp.sendData) {
    webapp.sendData(JSON.stringify(payload));
    return;
  }
  throw new Error("No transport for payload");
};

if (leadForm) {
  const modalFields = leadForm.querySelectorAll("input, textarea, select");
  modalFields.forEach((field) => {
    field.addEventListener("focus", () => {
      setTimeout(() => {
        field.scrollIntoView({ behavior: "smooth", block: "center" });
      }, 120);
    });
  });

  leadForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const formData = new FormData(leadForm);
    const payload = {
      type: "lead",
      name: formData.get("name"),
      project: formData.get("project"),
      goal: formData.get("goal"),
      budget: formData.get("budget"),
      contact: formData.get("contact"),
      created_at: new Date().toISOString(),
    };
    const webapp = getWebApp();
    if (webapp?.initDataUnsafe?.user) {
      payload.user = webapp.initDataUnsafe.user;
    }

    try {
      await sendPayload(payload);
      storageSet(LEAD_STORAGE_KEY, "1");
      closeLeadModal();
      notifyUser("Спасибо! Мы получили запрос.");
    } catch (error) {
      notifyUser("Не удалось отправить форму. Попробуйте позже.");
    }
  });
}

const sendQuestionToBot = async (message) => {
  const payload = { type: "question", message, created_at: new Date().toISOString() };
  try {
    await sendPayload(payload);
    notifyUser("Запрос отправлен. Ответ придет в чат с ботом.");
  } catch (error) {
    notifyUser("Не удалось отправить запрос. Попробуйте позже.");
  }
};

if (questionForm) {
  questionForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const message = questionInput.value.trim();
    if (!message) {
      notifyUser("Напишите вопрос перед отправкой.");
      return;
    }
    sendQuestionToBot(message);
    questionInput.value = "";
  });
}

if (payBtn) {
  payBtn.addEventListener("click", () => {
    if (!total) return;
    notifyUser("Оплата звездами подключается через инвойс. Мы подготовим ее на этапе интеграции.");
  });
}

const setupTelegram = () => {
  if (window.Telegram && window.Telegram.WebApp) {
    const webapp = window.Telegram.WebApp;
    webapp.expand();
    webapp.setHeaderColor("#0B0B0B");
    webapp.setBackgroundColor("#080808");
  }
};

setupTelegram();
updateCart();
