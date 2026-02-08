const cartTotalEl = document.getElementById("cartTotal");
const payBtn = document.getElementById("payBtn");
const cartBar = document.querySelector(".cart-bar");
const addButtons = document.querySelectorAll("[data-add]");
const questionForm = document.getElementById("questionForm");
const questionInput = document.getElementById("questionInput");

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

const sendQuestionToBot = (message) => {
  const payload = JSON.stringify({ type: "question", message });
  if (window.Telegram && window.Telegram.WebApp) {
    window.Telegram.WebApp.sendData(payload);
    window.Telegram.WebApp.showAlert("Запрос отправлен. Ответ придет в чат с ботом.");
  } else {
    alert("Запрос отправлен. Ответ придет в чат с ботом.");
  }
};

if (questionForm) {
  questionForm.addEventListener("submit", (event) => {
    event.preventDefault();
    const message = questionInput.value.trim();
    if (!message) {
      if (window.Telegram && window.Telegram.WebApp) {
        window.Telegram.WebApp.showAlert("Напишите вопрос перед отправкой.");
      } else {
        alert("Напишите вопрос перед отправкой.");
      }
      return;
    }
    sendQuestionToBot(message);
    questionInput.value = "";
  });
}

if (payBtn) {
  payBtn.addEventListener("click", () => {
    if (!total) return;
    if (window.Telegram && window.Telegram.WebApp) {
      window.Telegram.WebApp.showAlert(
        "Оплата звездами подключается через инвойс. Мы подготовим ее на этапе интеграции."
      );
    } else {
      alert("Оплата звездами будет доступна в Telegram WebApp.");
    }
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
