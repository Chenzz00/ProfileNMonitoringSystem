document.addEventListener("DOMContentLoaded", function () {
  const modal = document.getElementById("registerModal");
  const closeButton = document.querySelector(".close-button");
  const parentLinks = document.querySelectorAll(".parent-link");
  const modalParentName = document.getElementById("modalParentName");
  const hiddenParentInput = document.getElementById("hidden_parent_name");
  const form = document.getElementById("registerForm");

  let selectedParent = null;

  parentLinks.forEach(link => {
    link.addEventListener("click", function (e) {
      e.preventDefault();
      selectedParent = e.target.getAttribute("data-parent");
      modalParentName.textContent = selectedParent;
      hiddenParentInput.value = selectedParent;
      modal.style.display = "flex";
    });
  });

  if (closeButton) {
    closeButton.addEventListener("click", function () {
      modal.style.display = "none";
    });
  }

  window.addEventListener("click", function (e) {
    if (e.target === modal) {
      modal.style.display = "none";
    }
  });

  const searchInput = document.getElementById("parentSearch");
  const tableRows = document.querySelectorAll("tbody tr");

  if (searchInput) {
    searchInput.addEventListener("keyup", function () {
      const query = this.value.toLowerCase();
      tableRows.forEach(row => {
        const parentNameCell = row.querySelector("td");
        const name = parentNameCell?.innerText.toLowerCase() || "";
        row.style.display = name.includes(query) ? "" : "none";
      });
    });
  }

  form.addEventListener("submit", async function (e) {
    e.preventDefault();

    const data = {
      parent_name: hiddenParentInput.value,
      last_name: document.getElementById("child_last_name").value,
      first_name: document.getElementById("child_first_name").value,
      birthdate: document.getElementById("child_birthdate").value,
      gender: document.getElementById("child_gender").value,
      csrfmiddlewaretoken: document.querySelector('[name=csrfmiddlewaretoken]').value
    };

    try {
      const response = await fetch("/register-preschooler-entry/", {
        method: "POST",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded"
        },
        body: new URLSearchParams(data)
      });

      const result = await response.json();

      if (result.status === "success") {
        alert("Preschooler registered successfully!");
        modal.style.display = "none";
        form.reset();
        window.location.reload();
      } else {
        alert(result.message || "Something went wrong.");
      }
    } catch (error) {
      alert("Error submitting form. Please try again.");
      console.error(error);
    }
  });
});
