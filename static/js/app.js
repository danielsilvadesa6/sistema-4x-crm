// Sidebar mobile (hamburger)
(function () {
  var btn = document.getElementById('btn-menu');
  var sidebar = document.querySelector('.sidebar');
  var overlay = document.getElementById('sidebar-overlay');
  if (!btn || !sidebar || !overlay) return;

  function openSidebar()  { sidebar.classList.add('open');    overlay.classList.add('active'); }
  function closeSidebar() { sidebar.classList.remove('open'); overlay.classList.remove('active'); }

  // Suporte a click e touchend no botão hamburger (iOS Safari)
  function toggleHandler(e) {
    e.stopPropagation();
    sidebar.classList.contains('open') ? closeSidebar() : openSidebar();
  }
  btn.addEventListener('click', toggleHandler);
  btn.addEventListener('touchend', function (e) { e.preventDefault(); toggleHandler(e); });

  // Overlay fecha sidebar
  overlay.addEventListener('click', closeSidebar);
  overlay.addEventListener('touchend', function (e) { e.preventDefault(); closeSidebar(); });

  // Links da sidebar: navegar normalmente e fechar depois
  sidebar.querySelectorAll('a').forEach(function (a) {
    // Garante cursor pointer para iOS reconhecer como tappable
    a.style.cursor = 'pointer';
    // Fecha a sidebar sem interferir na navegação
    a.addEventListener('click', function () {
      // Pequeno delay para o browser processar o href antes de animar
      setTimeout(closeSidebar, 100);
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
