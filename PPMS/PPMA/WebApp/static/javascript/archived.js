window.onload = () => {
  const tbody = document.querySelector("#archivedTable tbody");

  if (!archivedPreschoolers || archivedPreschoolers.length === 0) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td colspan="3">No archived preschoolers found.</td>`;
    tbody.appendChild(tr);
    return;
  }

  const seen = new Set();
  archivedPreschoolers.forEach(child => {
    if (!seen.has(child.id)) {
      seen.add(child.id);
      const tr = document.createElement("tr");
      tr.classList.add("archived-row");
      tr.dataset.id = child.id;
      tr.dataset.url = `/preschooler/${child.id}/`;  // ✅ view profile route
      tr.innerHTML = `
        <td>${child.name}</td>
        <td>${child.age}</td>
        <td>${child.barangay}</td>
      `;
      tbody.appendChild(tr);
    }
  });

  // --- Custom Menu Logic ---
  let selectedRow = null;

  const customMenu = document.getElementById("customMenu");
  const viewProfile = document.getElementById("viewArchivedProfile");

  document.querySelectorAll(".archived-row").forEach(row => {
    row.addEventListener("click", function (e) {
      e.preventDefault();

      if (selectedRow) selectedRow.classList.remove("selected");
      selectedRow = this;
      selectedRow.classList.add("selected");

      customMenu.style.top = `${e.pageY}px`;
      customMenu.style.left = `${e.pageX}px`;
      customMenu.style.display = "block";
    });
  });

  viewProfile.addEventListener("click", () => {
    if (selectedRow) {
      const profileUrl = selectedRow.dataset.url;
      window.location.href = profileUrl;
    }
  });

  // Close menu if clicked outside
  window.addEventListener("click", function (e) {
    if (!customMenu.contains(e.target) && !e.target.closest(".archived-row")) {
      customMenu.style.display = "none";
      if (selectedRow) selectedRow.classList.remove("selected");
    }
  });

  window.addEventListener("contextmenu", e => e.preventDefault());
};
