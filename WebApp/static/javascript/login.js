// ✅ parent_dashboard.js

document.addEventListener("DOMContentLoaded", () => {
  const notifBtn = document.getElementById("notifBtn");
  const profileBtn = document.getElementById("profileBtn");
  const profileMenu = document.getElementById("profileMenu");
  const logoutBtn = document.querySelector(".logout-btn");

  // 🔒 Logout Confirmation
  if (logoutBtn) {
    logoutBtn.addEventListener("click", function (e) {
      e.preventDefault();
      const logoutUrl = this.getAttribute("data-url");

      Swal.fire({
        title: 'Are you sure?',
        text: "You will be logged out of your account.",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#3085d6',
        cancelButtonColor: '#d33',
        confirmButtonText: 'Yes, log me out',
        cancelButtonText: 'Cancel'
      }).then((result) => {
        if (result.isConfirmed) {
          window.location.href = logoutUrl;
        }
      });
    });
  }

  // 🔔 Show Notification Popup
  if (notifBtn) {
    notifBtn.addEventListener("click", () => {
      if (typeof notifications === 'undefined' || notifications.length === 0) {
        Swal.fire({
          toast: true,
          position: 'top-end',
          icon: 'info',
          title: 'No new vaccination schedules.',
          showConfirmButton: false,
          timer: 3000,
          timerProgressBar: true,
        });
      } else {
        let htmlList = "<ul style='text-align:left'>";
        notifications.forEach(n => {
          htmlList += `<li>💉 <strong>${n.name}</strong> scheduled for <strong>${n.vaccine}</strong> on <strong>${n.date}</strong></li>`;
        });
        htmlList += "</ul>";

        Swal.fire({
          icon: 'info',
          title: '📌 Upcoming Vaccinations',
          html: htmlList,
          confirmButtonText: 'OK',
          width: 500
        });
      }
    });
  }

  // 👤 Profile Dropdown Toggle
  if (profileBtn && profileMenu) {
    profileBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      profileMenu.style.display = profileMenu.style.display === "flex" ? "none" : "flex";
    });

    document.addEventListener("click", (e) => {
      if (!e.target.closest(".profile-dropdown")) {
        profileMenu.style.display = "none";
      }
    });
  }

  // ✅ Toast Django messages with SweetAlert2
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

// ✅ Parent confirms vaccination schedule
document.addEventListener("click", function (e) {
  if (e.target.classList.contains("confirm-schedule-btn")) {
    const scheduleId = e.target.dataset.scheduleId;

    Swal.fire({
      title: "Confirm this schedule?",
      text: "You acknowledge that this vaccination has been done.",
      icon: "question",
      showCancelButton: true,
      confirmButtonColor: "#5bdab3",
      cancelButtonColor: "#d33",
      confirmButtonText: "Yes, Confirm"
    }).then((result) => {
      if (result.isConfirmed) {
        fetch(`/confirm-schedule/${scheduleId}/`, {
          method: "POST",
          headers: {
            "X-CSRFToken": getCookie("csrftoken"),
            "Content-Type": "application/json"
          }
        })
          .then((res) => res.json())
          .then((data) => {
            if (data.status === "success") {
              Swal.fire("Confirmed!", data.message, "success");
              e.target.closest(".sticky-note").remove();
            } else {
              Swal.fire("Oops!", data.message, "error");
            }
          })
          .catch((error) => {
            console.error("Error:", error);
            Swal.fire("Error", "An unexpected error occurred.", "error");
          });
      }
    });
  }
});

// ✅ Get CSRF token from cookie
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== "") {
    const cookies = document.cookie.split(";");
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.startsWith(name + "=")) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}
