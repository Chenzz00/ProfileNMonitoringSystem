function openVaccineForm() {
  document.getElementById('vaccineFormModal').style.display = 'flex';
}

function closeVaccineForm() {
  document.getElementById('vaccineFormModal').style.display = 'none';
}

function addVaccine() {
  const name = document.getElementById('vaccineName').value.trim();
  const age = document.getElementById('scheduledAge').value.trim();
  const date = document.getElementById('dateGiven').value;
  const givenBy = document.getElementById('givenBy').value.trim();

  if (name && age && date && givenBy) {
    const table = document.querySelector('.vaccine-table tbody');
    const row = document.createElement('tr');
    row.innerHTML = `
      <td>${name}</td>
      <td>${age}</td>
      <td>${date}</td>
      <td>${givenBy}</td>
    `;
    table.appendChild(row);
    closeVaccineForm();
    document.querySelectorAll('#vaccineFormModal input').forEach(input => input.value = '');
  } else {
    alert('Please fill in all fields.');
  }
}
