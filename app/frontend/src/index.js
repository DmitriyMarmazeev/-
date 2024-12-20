import './styles.css';

const backendUrl = "http://localhost:8000"; // URL бэкенда
const authSection = document.getElementById("authSection");

// Проверка статуса авторизации
function checkAuthStatus() {
  const token = localStorage.getItem("token");
  const email = localStorage.getItem("email");
  if (token && email) {
    displayLoggedIn(email);
  } else {
    displayLoginForm();
  }
}

// Проверка учетных данных
async function login(email, password) {
  try {
    const response = await fetch(`${backendUrl}/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ email, password }),
    });

    if (response.ok) {
      const data = await response.json();
      localStorage.setItem("token", data.token);
      localStorage.setItem("email", email);
      displayLoggedIn(email);
    } else {
      alert("Invalid email or password.");
    }
  } catch (err) {
    console.error("Error during login:", err);
  }
}

// Форма входа
function displayLoginForm() {
  authSection.innerHTML = `
    <form id="loginForm" class="login-form">
      <div class="input-group">
        <input type="email" id="loginEmail" placeholder="Введите почту" required>
        <input type="password" id="loginPassword" placeholder="Введите пароль" required>
      </div>
      <div class="button-group">
        <button type="submit">Вход</button>
        <button id="registerButton" type="button">Регистрация</button>
      </div>
    </form>
  `;

  document.getElementById("loginForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = document.getElementById("loginEmail").value.trim();
    const password = document.getElementById("loginPassword").value.trim();
    await login(email, password);
  });

  document.getElementById("registerButton").addEventListener("click", () => {
    window.location.href = "http://localhost:3000";
  });
}

// Показ после входа
function displayLoggedIn(email) {
  authSection.innerHTML = `
    <div class="email-controls">
      <span class="email-display">${email}</span>
      <div class="control-buttons">
        <button id="logoutButton">Выход</button>
        <button id="deleteAccountButton">Удалить аккаунт</button>
      </div>
    </div>
  `;

  document.getElementById("emailSender").value = email;

  document.getElementById("logoutButton").addEventListener("click", () => {
    localStorage.removeItem("token");
    localStorage.removeItem("email");
    location.reload();
  });

  document.getElementById("deleteAccountButton").addEventListener("click", async () => {
    const token = localStorage.getItem("token");
    try {
      await fetch(`${backendUrl}/users/${token}`, { method: "DELETE" });
      localStorage.removeItem("token");
      localStorage.removeItem("email");
      location.reload();
    } catch (err) {
      console.error("Error deleting account:", err);
    }
  });

  loadEmails();
}

// Отправка письма
document.getElementById("sendEmail").addEventListener("click", async () => {
  const token = localStorage.getItem("token");
  const receiver = document.getElementById("emailReceiver").value.trim();
  const title = document.getElementById("emailTitle").value.trim();
  const text = document.getElementById("emailText").value.trim();
  const attachments = document.getElementById("emailAttachment").files;

  if (!token || !receiver || !title || (!text && attachments.length === 0)) {
    alert("All fields are required.");
    return;
  }

  const formData = new FormData();
  formData.append("sender", token);
  formData.append("receiver", receiver);
  formData.append("title", title);
  formData.append("text", text);
  Array.from(attachments).forEach((file) => formData.append("attachments", file));

  try {
    const response = await fetch(`${backendUrl}/emails`, {
      method: "POST",
      body: formData,
    });
    if (response.ok) {
      alert("Email sent successfully.");
      document.getElementById("emailReceiver").value = "";
      document.getElementById("emailTitle").value = "";
      document.getElementById("emailText").value = "";
      document.getElementById("emailAttachment").value = "";
      loadEmails();
    } else {
      const error = await response.json();
      alert(`Error: ${error.detail}`);
    }
  } catch (err) {
    console.error("Error sending email:", err);
  }
});

// Загрузка писем
async function loadEmails() {
  const token = localStorage.getItem("token");
  if (!token) return;

  try {
    const sentResponse = await fetch(`${backendUrl}/emails/sent/${token}`, {
      method: "GET"
    });

    const receivedResponse = await fetch(`${backendUrl}/emails/received/${token}`, {
      method: "GET"
    });

    const sentEmails = await sentResponse.json();
    const receivedEmails = await receivedResponse.json();

    renderEmails(sentEmails, "sentEmails");
    renderEmails(receivedEmails, "receivedEmails");
  } catch (err) {
    console.error("Error loading emails:", err);
  }
}

// Отображение писем
function renderEmails(emails, listId) {
  const emailList = document.getElementById(listId);
  emailList.innerHTML = "";

  emails.forEach((email) => {
    const emailDiv = document.createElement("div");
    emailDiv.className = "email";

    const header = `<strong>Отправитель:</strong> ${email.sender} <br> <strong>Получатель:</strong> ${email.receiver} <br> <strong>Тема:</strong> ${email.title}`;
    emailDiv.innerHTML = header + `<p>${email.text}</p>`;

    if (email.attachments.length > 0) {
      const attachmentsDiv = document.createElement("div");
      attachmentsDiv.className = "email-attachments";
      email.attachments.forEach((attachment) => {
        const fileName = attachment.split("/").pop();
        const link = document.createElement("a");
        link.href = `${backendUrl}/download/${attachment}`;
        link.textContent = fileName;
        link.download = fileName;
        link.style.marginRight = "10px";
        attachmentsDiv.appendChild(link);
      });
      emailDiv.appendChild(attachmentsDiv);
    }

    const deleteButton = document.createElement("button");
    deleteButton.className = "delete-email";
    deleteButton.textContent = "Удалить";
    deleteButton.addEventListener("click", async () => {
      try {
        await fetch(`${backendUrl}/emails/${email.id}`, {
          method: "DELETE",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ token: localStorage.getItem("token") }),
        });
        emailDiv.remove();
      } catch (err) {
        console.error("Error deleting email:", err);
      }
    });

    emailDiv.appendChild(deleteButton);
    emailList.appendChild(emailDiv);
  });
}

// Переключение между секциями
document.getElementById("writeEmailButton").addEventListener("click", () => {
  document.getElementById("writeEmailSection").style.display = "block";
  document.getElementById("sentEmails").style.display = "none";
  document.getElementById("receivedEmails").style.display = "none";
});

document.getElementById("sentEmailsButton").addEventListener("click", () => {
  document.getElementById("writeEmailSection").style.display = "none";
  document.getElementById("sentEmails").style.display = "block";
  document.getElementById("receivedEmails").style.display = "none";
});

document.getElementById("receivedEmailsButton").addEventListener("click", () => {
  document.getElementById("writeEmailSection").style.display = "none";
  document.getElementById("sentEmails").style.display = "none";
  document.getElementById("receivedEmails").style.display = "block";
});

// Инициализация
checkAuthStatus();