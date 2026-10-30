// toasts
document.querySelectorAll('.toast').forEach(t => new bootstrap.Toast(t).show());

// live countdowns; reload when one reaches zero so the page shows the new state
const fmt = s => { const d = Math.floor(s / 86400), h = Math.floor(s % 86400 / 3600), m = Math.floor(s % 3600 / 60);
  return d ? `${d}d ${h}h` : h ? `${h}h ${m}m` : `${m}m ${String(s % 60).padStart(2, '0')}s`; };
document.querySelectorAll('[data-countdown]').forEach(el => {
  let left = +el.dataset.countdown; el.textContent = fmt(left);
  const t = setInterval(() => { left--; if (left <= 0) { clearInterval(t); location.reload(); } else el.textContent = fmt(left); }, 1000);
});

// copy buttons
document.querySelectorAll('[data-copy]').forEach(b => b.addEventListener('click', () => {
  navigator.clipboard.writeText(b.dataset.copy);
  const old = b.innerHTML; b.innerHTML = '<i class="bi bi-check2"></i> Copied'; setTimeout(() => b.innerHTML = old, 1400);
}));

// transaction in flight: show the pending state on any form that sends a transaction
document.addEventListener('submit', e => {
  if (e.target.matches('[data-tx]') && !e.defaultPrevented) document.getElementById('txOverlay').hidden = false;
});

// open the tab named in the URL hash (e.g. #updates)
const tabFromHash = () => { const b = document.querySelector(`[data-bs-target="#tab-${location.hash.slice(1)}"]`); if (b) bootstrap.Tab.getOrCreateInstance(b).show(); };
tabFromHash(); window.addEventListener('hashchange', tabFromHash);

// auto-submit filter selects
document.querySelectorAll('[data-autosubmit]').forEach(el => el.addEventListener('change', () => el.form.submit()));
