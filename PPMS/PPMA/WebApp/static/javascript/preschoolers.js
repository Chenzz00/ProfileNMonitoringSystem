document.addEventListener("DOMContentLoaded", () => {
  const notifBtn = document.getElementById("notifBtn");

  // 🔔 Notification alert
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
      });
    });
  }

  const barangaySelect = document.getElementById('barangay-select');
  const searchBtn = document.getElementById('search-btn');
  const searchInput = document.getElementById('search-input');

  // Filter by barangay dropdown
  barangaySelect.addEventListener('change', filterTable);

  // Search button click
  searchBtn.addEventListener('click', (e) => {
    e.preventDefault();
    filterTable();
  });

  // Search on Enter key
  searchInput.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') {
      e.preventDefault();
      filterTable();
    }
  });

  // Filtering logic
  function filterTable() {
    const selectedBarangay = barangaySelect.value.toLowerCase();
    const searchTerm = searchInput.value.toLowerCase();
    const rows = document.querySelectorAll('#preschoolers-table-body tr');

    rows.forEach(row => {
      const name = row.cells[0].textContent.toLowerCase();
      const barangay = row.cells[6].textContent.toLowerCase();
      const matchesBarangay = (selectedBarangay === 'all' || barangay === selectedBarangay);
      const matchesSearch = name.includes(searchTerm);
      row.style.display = (matchesBarangay && matchesSearch) ? '' : 'none';
    });
  }

 const rows = document.querySelectorAll(".clickable-row");
  rows.forEach(row => {
    row.style.cursor = "pointer";
    row.addEventListener("click", () => {
      const href = row.getAttribute("data-href");
      if (href) {
        window.location.href = href;
      }
    });
  });
});
