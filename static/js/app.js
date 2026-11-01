(function () {
  // Confirm-before-delete. Without JS, the link still works as before.
  var dlg = document.getElementById('confirm-dialog');
  if (!dlg || typeof dlg.showModal !== 'function') return;
  var target = null, msg = dlg.querySelector('[data-msg]');
  document.addEventListener('click', function (e) {
    var a = e.target.closest('[data-confirm]');
    if (!a) return;
    e.preventDefault();
    target = a.getAttribute('href');
    msg.textContent = a.getAttribute('data-confirm');
    dlg.showModal();
  });
  dlg.querySelector('[data-cancel]').addEventListener('click', function () { dlg.close(); });
  dlg.querySelector('[data-ok]').addEventListener('click', function () { if (target) window.location.href = target; });
})();
