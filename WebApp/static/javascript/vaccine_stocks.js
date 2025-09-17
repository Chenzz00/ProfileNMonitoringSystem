function refreshData() {
  const btn = document.querySelector('.refresh-btn');
  btn.style.opacity = '0.7';
  btn.textContent = '🔄 Refreshing...';

  setTimeout(() => {
    window.location.reload();
  }, 1000); // Simulate refresh delay
}
 document.addEventListener('DOMContentLoaded', function () {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.style.opacity = '1';
        entry.target.style.transform = 'translateY(0)';
      }
    });
  });

  document.querySelectorAll('tbody tr').forEach(row => {
    row.style.opacity = '0';
    row.style.transform = 'translateY(20px)';
    row.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
    observer.observe(row);
  });
});
