console.log("✅ login.js loaded");

document.addEventListener("DOMContentLoaded", () => {
  const emailInput = document.querySelector('input[name="email"]');
  const passwordInput = document.querySelector('input[name="password"]');
  const loginForm = document.querySelector("form");
  const togglePassword = document.getElementById("togglePassword");

  // Toggle password visibility with image icons
  togglePassword?.addEventListener("click", () => {
    const type = passwordInput.type === "password" ? "text" : "password";
    passwordInput.type = type;

    const showIcon = "/static/media/show-password.png";
    const hideIcon = "/static/media/hide-password.png";

    togglePassword.src = type === "password" ? showIcon : hideIcon;
    togglePassword.alt = type === "password" ? "Show Password" : "Hide Password";
  });

  // Show Django messages using toast-style SweetAlert2
  const djangoMessages = document.querySelectorAll("#django-messages li");
  djangoMessages.forEach((msg) => {
    const message = msg.dataset.message;
    const tag = msg.dataset.tag;

    Swal.fire({
      toast: true,
      position: 'top-end',
      icon: tag === "error"
        ? "error"
        : tag === "warning"
        ? "warning"
        : tag === "success"
        ? "success"
        : "info",
      title: message,
      showConfirmButton: false,
      timer: 4000,
      timerProgressBar: true,
      didOpen: (toast) => {
        toast.addEventListener("mouseenter", Swal.stopTimer);
        toast.addEventListener("mouseleave", Swal.resumeTimer);
      },
    });
  });

  // Sanitize password input in real-time
  passwordInput?.addEventListener("input", () => {
    passwordInput.value = passwordInput.value.replace(/[^A-Za-z0-9]/g, "");
  });

  // Validate form before submission
  loginForm?.addEventListener("submit", function (e) {
    const email = emailInput.value.trim();
    const password = passwordInput.value.trim();

    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    const passwordRegex = /^[A-Za-z0-9]+$/;

    if (!emailRegex.test(email)) {
      e.preventDefault();
      Swal.fire({
        toast: true,
        position: "top-end",
        icon: "error",
        title: "Invalid email format.",
        showConfirmButton: false,
        timer: 3000,
        timerProgressBar: true,
      });
      return;
    }

    if (!passwordRegex.test(password)) {
      e.preventDefault();
      Swal.fire({
        toast: true,
        position: "top-end",
        icon: "error",
        title: "Password must contain only letters and numbers.",
        showConfirmButton: false,
        timer: 3000,
        timerProgressBar: true,
      });
      return;
    }
  });
});
