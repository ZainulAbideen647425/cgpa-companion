(function () {
  // Confirm-before-delete. Without JS, the link still works as before.
  var dlg = document.getElementById('confirm-dialog');
  if (!dlg || typeof dlg.showModal !== 'function') return;
  var target = null, pendingForm = null, msg = dlg.querySelector('[data-msg]');
  document.addEventListener('click', function (e) {
    var a = e.target.closest('[data-confirm]');
    if (!a) return;
    e.preventDefault();
    pendingForm = null;
    target = a.getAttribute('href');
    msg.textContent = a.getAttribute('data-confirm');
    dlg.showModal();
  });
  dlg.querySelector('[data-cancel]').addEventListener('click', function () { dlg.close(); });
  dlg.querySelector('[data-ok]').addEventListener('click', function () {
    if (pendingForm) { pendingForm.submit(); } else if (target) { window.location.href = target; }
  });
  // POST deletes: <form data-confirm="..."> asks first, then submits.
  document.addEventListener('submit', function (e) {
    var f = e.target.closest('form[data-confirm]');
    if (!f || f === pendingForm) return;
    e.preventDefault();
    pendingForm = f; target = null;
    msg.textContent = f.getAttribute('data-confirm');
    dlg.showModal();
  });
})();
