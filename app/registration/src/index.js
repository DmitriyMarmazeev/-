import './styles.css';

document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("registration-form");
  const emailInput = document.getElementById("email");
  const passwordInput = document.getElementById("password");
  const confirmPasswordInput = document.getElementById("confirm-password");
  const errorMessage = document.getElementById("error-message");

  emailInput.addEventListener("input", () => {
      const emailSuffix = document.getElementById("email-suffix");
      emailSuffix.textContent = `${emailInput.value}@mycorpmail.ru`;
  });

  form.addEventListener("submit", (event) => {
      event.preventDefault();
      
      // Validate password confirmation
      if (passwordInput.value !== confirmPasswordInput.value) {
          errorMessage.textContent = "Пароли не совпадают!";
          errorMessage.style.visibility = "visible";
          return;
      }

      // Prepare data for backend
      const email = `${emailInput.value}@mycorpmail.ru`;
      const password = passwordInput.value;

      // Send data to backend
      fetch("http://localhost:8000/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password }),
      })
      .then((response) => {
          if (!response.ok) {
              throw new Error("User already exists");
          }
          return response.json();
      })
      .then(() => {
          window.location.href = "http://localhost:3001"; // Redirect to frontend
      })
      .catch((error) => {
          errorMessage.textContent = "Такой пользователь уже существует";
          errorMessage.style.visibility = "visible";
      });
  });
});