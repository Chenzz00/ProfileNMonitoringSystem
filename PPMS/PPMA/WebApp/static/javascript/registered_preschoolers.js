const preschoolers = [
  {
    id: 1,
    name: "Juan Dela Cruz",
    age: 5,
    barangay: "Barangay 1",
    parent: "Maria Dela Cruz",
    details: "Juan is a 5-year-old with excellent attendance."
  },
  {
    id: 2,
    name: "Maria Santos",
    age: 4,
    barangay: "Barangay 2",
    parent: "Jose Santos",
    details: "Maria loves arts and crafts."
  },
  {
    id: 3,
    name: "Pedro Reyes",
    age: 5,
    barangay: "Barangay 3",
    parent: "Ana Reyes",
    details: "Pedro enjoys reading books and sports."
  }
];

window.onload = () => {
  const tbody = document.querySelector("#preschoolerTable tbody");
  preschoolers.forEach(child => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><a href="${preschoolerDataUrl}?id=${child.id}" class="child-name">${child.name}</a></td>
      <td>${child.age}</td>
      <td>${child.barangay}</td>
      <td>${child.parent}</td>
    `;
    tbody.appendChild(tr);
  });
};
