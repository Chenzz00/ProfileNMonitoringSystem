document.addEventListener("DOMContentLoaded", () => {
  const notifBtn = document.getElementById("notifBtn");
  const profileBtn = document.getElementById("profileBtn");
  const profileMenu = document.getElementById("profileMenu");

  // ✅ SweetAlert2 toast on notification button
  if (notifBtn) {
    notifBtn.addEventListener("click", () => {
      Swal.fire({
        toast: true,
        position: 'top-end',
        icon: 'info',
        title: 'No new notifications.',
        showConfirmButton: false,
        timer: 3000,
        timerProgressBar: true,
        didOpen: (toast) => {
          toast.addEventListener("mouseenter", Swal.stopTimer);
          toast.addEventListener("mouseleave", Swal.resumeTimer);
        }
      });
    });
  }

  // 🧠 Existing profile menu dropdown
  if (profileBtn && profileMenu) {
    profileBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      profileMenu.style.display = (profileMenu.style.display === "flex") ? "none" : "flex";
    });

    document.addEventListener("click", (e) => {
      if (!e.target.closest(".profile-dropdown")) {
        profileMenu.style.display = "none";
      }
    });
  }

  // ✅ Show Django messages via SweetAlert2 toast
  const djangoMessages = document.querySelectorAll("#django-messages li");

  djangoMessages.forEach((msg) => {
    const message = msg.dataset.message;
    const tag = msg.dataset.tag;

    Swal.fire({
      toast: true,
      position: 'top-end',
      icon: tag === "success" ? "success" : tag === "error" ? "error" : "info",
      title: message,
      showConfirmButton: false,
      timer: 4000,
      timerProgressBar: true,
      didOpen: (toast) => {
        toast.addEventListener("mouseenter", Swal.stopTimer);
        toast.addEventListener("mouseleave", Swal.resumeTimer);
      }
    });
  });
});
