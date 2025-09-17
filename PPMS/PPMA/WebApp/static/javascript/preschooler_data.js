document.addEventListener("DOMContentLoaded", function () {
  const vaccineCardModal = document.getElementById("vaccineCardModal");
  const addScheduleModal = document.getElementById("addScheduleModal");
  const addScheduleForm = document.getElementById("addScheduleForm");

  // Open Vaccine Card Modal
  window.openVaccineCardModal = function () {
    if (vaccineCardModal) {
      vaccineCardModal.style.display = "flex";
      vaccineCardModal.classList.add("active");
    }
  };

  // Close Vaccine Card Modal
  window.closeVaccineCardModal = function () {
    if (vaccineCardModal) {
      vaccineCardModal.style.display = "none";
      vaccineCardModal.classList.remove("active");
    }
  };

  // Open Add Schedule Modal
  window.openAddScheduleModal = function () {
    if (addScheduleModal) {
      addScheduleModal.style.display = "flex";
      addScheduleModal.classList.add("active");
    }
  };

  // Close Add Schedule Modal
  window.closeAddScheduleModal = function () {
    if (addScheduleModal) {
      addScheduleModal.style.display = "none";
      addScheduleModal.classList.remove("active");
    }
  };

  // ✅ ESC key closes modals
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") {
      if (vaccineCardModal?.classList.contains("active")) closeVaccineCardModal();
      if (addScheduleModal?.classList.contains("active")) closeAddScheduleModal();
    }
  });

  // ✅ Click outside modal to close
  document.addEventListener("click", function (e) {
    if (e.target === vaccineCardModal && vaccineCardModal.classList.contains("active")) {
      closeVaccineCardModal();
    }
    if (e.target === addScheduleModal && addScheduleModal.classList.contains("active")) {
      closeAddScheduleModal();
    }
  });

  // ✅ Django flash messages to SweetAlert2
  const djangoMessages = document.querySelectorAll("#django-messages li");
  djangoMessages.forEach((msg) => {
    const message = msg.dataset.message;
    const tag = msg.dataset.tag;

    Swal.fire({
      icon: tag === "success" ? "success" : tag === "error" ? "error" : "info",
      title: message,
      toast: true,
      position: 'top-end',
      showConfirmButton: false,
      timer: 3000,
      timerProgressBar: true,
      didOpen: (toast) => {
        toast.addEventListener("mouseenter", Swal.stopTimer);
        toast.addEventListener("mouseleave", Swal.resumeTimer);
      }
    });

    // Optional: auto-close modal if message is about success
    if (tag === "success" && addScheduleModal) {
      closeAddScheduleModal();
    }
  });
});
