const nutritionData = [
    { status: "Normal", count: 60 },
    { status: "Underweight", count: 25 },
    { status: "Overweight", count: 40 },
    { status: "Severely Underweight", count: 10 },
    { status: "Obese", count: 15 }
];

window.onload = () => {
    const tableBody = document.querySelector("#nutritionTable tbody");
    nutritionData.forEach(item => {
        const row = document.createElement("tr");
        row.innerHTML = `<td>${item.status}</td><td>${item.count}</td>`;
        tableBody.appendChild(row);
    });
};
