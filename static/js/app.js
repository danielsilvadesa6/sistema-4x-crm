// Sidebar mobile (hamburger)
(function () {
  var btn = document.getElementById('btn-menu');
  var sidebar = document.querySelector('.sidebar');
  var overlay = document.getElementById('sidebar-overlay');
  if (!btn || !sidebar || !overlay) return;
  function open() { sidebar.classList.add('open'); overlay.classList.add('active'); }
  function close() { sidebar.classList.remove('open'); overlay.classList.remove('active'); }
  btn.addEventListener('click', function () {
    sidebar.classList.contains('open') ? close() : open();
  });
  overlay.addEventListener('click', close);
  // Fechar ao navegar (link clicado na sidebar)
  sidebar.querySelectorAll('a').forEach(function (a) {
    a.addEventListener('click', function () {
      if (window.innerWidth <= 768) close();
    });
  });
})();

// Modal de aviso global
function mostrarAviso(msg) {
  document.getElementById('modal-msg').textContent = msg;
  document.getElementById('modal-aviso').style.display = 'flex';
}

// Fecha modal ao clicar fora
document.getElementById('modal-aviso').addEventListener('click', function(e) {
  if (e.target === this) this.style.display = 'none';
});
