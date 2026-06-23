// Modal de aviso global
function mostrarAviso(msg) {
  document.getElementById('modal-msg').textContent = msg;
  document.getElementById('modal-aviso').style.display = 'flex';
}

// Fecha modal ao clicar fora
document.getElementById('modal-aviso').addEventListener('click', function(e) {
  if (e.target === this) this.style.display = 'none';
});
