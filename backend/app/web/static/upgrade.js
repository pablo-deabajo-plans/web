function startProCheckout() {
  // TODO: conectar proveedor de pago cuando se habilite monetizacion.
  // TODO: onPaymentSuccess debe actualizar user.plan = "pro" en backend.
  var note = document.getElementById('upgrade-placeholder-note');
  if (note) {
    note.textContent = 'Pago no habilitado aun. El checkout PRO se conectara aqui mas adelante.';
  }
}

document.addEventListener('DOMContentLoaded', function () {
  var btn = document.querySelector('[aria-describedby="upgrade-placeholder-note"]');
  if (btn) btn.addEventListener('click', startProCheckout);
});
