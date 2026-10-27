const form = document.getElementById('login-form');
const input = document.getElementById('access-key');
const button = document.getElementById('connect');
const errorBox = document.getElementById('login-error');
form.addEventListener('submit', async event => {
  event.preventDefault();
  button.disabled = true;
  errorBox.hidden = true;
  document.getElementById('login-status').textContent = 'Connecting…';
  try {
    const response = await fetch('/api/login', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({key: input.value.trim()}), signal: AbortSignal.timeout(15000)});
    const result = await response.json();
    if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Unable to connect. Check your access key.');
    input.value = '';
    location.replace('/');
  } catch (error) {
    errorBox.textContent = error.message;
    errorBox.hidden = false;
    document.getElementById('login-status').textContent = '';
    button.disabled = false;
  }
});
// Fragments are not sent in HTTP requests or server access logs. Remove it before login.
function applyPairingLink() {
  const pairingKey = new URLSearchParams(location.hash.slice(1)).get('key');
  if (location.hash) history.replaceState(null, '', '/login');
  if (pairingKey) {
    input.value = pairingKey;
    form.requestSubmit();
  }
}
window.addEventListener('hashchange', applyPairingLink);
applyPairingLink();
