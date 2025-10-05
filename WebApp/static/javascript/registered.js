const preschoolers = [
    {
      id: 1,
      name: "Juan Dela Cruz",
      age: 5,
      barangay: "Barangay 1",
      details: "Juan is a 5-year-old with excellent attendance."
    },
    {
      id: 2,
      name: "Maria Santos",
      age: 4,
      barangay: "Barangay 2",
      details: "Maria loves arts and crafts."
    },
    {
      id: 3,
      name: "Pedro Reyes",
      age: 5,
      barangay: "Barangay 3",
      details: "Pedro enjoys reading books and sports."
    }
  ];
  
  window.onload = () => {
    const tbody = document.querySelector("#preschoolerTable tbody");
    preschoolers.forEach(child => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><a href="#" class="child-name" data-id="${child.id}">${child.name}</a></td>
        <td>${child.age}</td>
        <td>${child.barangay}</td>
      `;
      tbody.appendChild(tr);
    });
  
    const modal = document.getElementById("detailModal");
    const detailContent = document.getElementById("detailContent");
    const closeModal = document.getElementById("closeModal");
  
    document.querySelectorAll(".child-name").forEach(link => {
      link.addEventListener("click", (e) => {
        e.preventDefault();
        const id = e.target.dataset.id;
        const child = preschoolers.find(c => c.id == id);
        if (child) {
          detailContent.innerHTML = `
            <div class="preschooler-details">
              <div style="display: flex; gap: 20px;">
                <div style="width: 150px; height: 150px; background: #ccc;">Photo</div>
                <div>
                  <p><strong>${child.name}</strong></p>
                  <p>Age: ${child.age} year(s) old</p>
                  <p>Barangay: ${child.barangay}</p>
                  <p>Gender: Male</p>
                  <p>Birth Date: 01/2024</p>
                  <p>Weight: 7.60 kg</p>
                  <p>Height: 65.00 cm</p>
                </div>
                <div>
                  <p><strong>Weight for Age:</strong> -2.0 - Normal</p>
                  <p><strong>Height for Age:</strong> -2.1 - Normal</p>
                  <p><strong>Weight to Height for Age:</strong> 1.6 - Normal</p>
                  <p><strong>BMI:</strong> 18.4</p>
                </div>
              </div>
  
              <h4>Immunization Schedule</h4>
              <table>
                <tr><th>Vaccine Name</th><th>Doses</th><th>Required Doses</th><th>Immunization Date</th><th>Next Vaccine Schedule</th></tr>
                <tr><td>Hepatitis B</td><td>1</td><td>3</td><td>01/02/2025</td><td>03/02/2025</td></tr>
              </table>
  
              <h4>Immunization History</h4>
              <table>
                <tr><th>Vaccine Name</th><th>Doses</th><th>Required Doses</th></tr>
                <tr><td>BCG</td><td>1</td><td>1</td></tr>
              </table>
  
              <h4>Nutritional Status History</h4>
              <table>
                <tr>
                  <th>Date Measured</th><th>Height (cm)</th><th>Weight (kg)</th>
                  <th>BMI</th><th>BMI Category</th>
                  <th>Weight for Age</th><th>Height for Age</th><th>Weight for Height for Age</th>
                </tr>
                <tr>
                  <td>06/2025</td><td>65.00</td><td>7.60</td>
                  <td>18.4</td><td>Normal</td><td>-2.0</td><td>-2.1</td><td>1.6</td>
                </tr>
              </table>
            </div>
          `;
          modal.style.display = "flex";
        }
      });
    });
  
    closeModal.onclick = () => {
      modal.style.display = "none";
    };
  
    window.onclick = (event) => {
      if (event.target == modal) {
        modal.style.display = "none";
      }
    };
  };
  
