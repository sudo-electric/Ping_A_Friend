const $ = (id) => document.getElementById(id);
const labels = {healthy: 'Responding', delayed: 'Delayed', failed: 'Unreachable', unknown: 'Unknown', unconfigured: 'Set up needed', unavailable: 'Unavailable', stale: 'Stale', degraded: 'Needs a look', suspected_outage: 'Group unreachable'};
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const time = (ts) => ts == null ? 'Not checked yet' : new Date(ts * 1000).toLocaleString();
const stateClass = (s) => ['failed','suspected_outage'].includes(s) ? 'fault' : ['delayed','degraded'].includes(s) ? 'warning' : ['unknown','stale','unavailable'].includes(s) ? 'offline' : s === 'healthy' ? '' : 'neutral';
let pending = false;
let lastSuccess = 0;
let actionError = '';
let latestData = null;
let latestReport = null;
let observerInstance = null;
let errorMessage = '';
const privateText = value => esc(addressPrivacy.screen(value));

function targetCard(t) {
  const targetText = t.kind === 'external' ? esc : privateText;
  const incident = t.incident;
  const alert = incident ? (incident.confirmed_at ? 'Confirmed incident · Host notification saved locally' : `Checking again · ${Math.ceil(t.confirmation_remaining)}s until confirmation is eligible`) : '';
  return `<article class="device ${stateClass(t.status)}"><h4>${targetText(t.name)}</h4><p class="host">${targetText(t.host)}${t.method === 'tcp' ? ':' + t.port : ''} · ${t.method === 'tcp' ? 'TCP connection' : 'ICMP ping'}</p><div class="metrics"><div class="metric"><span>Reachability</span><strong>${esc(labels[t.status] || t.status)}</strong></div><div class="metric latency"><span>${t.method === 'icmp' ? 'Round-trip' : 'Connect time'}</span><strong>${t.status === 'stale' || t.latency_ms == null ? '—' : esc(t.latency_ms)} <small>ms</small></strong></div></div><p class="detail">${targetText(t.detail)}</p><p class="stamp">${esc(time(t.checked_at))} · Delay threshold ${t.delayed_ms}ms</p>${alert ? `<div class="incident">${esc(alert)}</div>` : ''}</article>`;
}

function render(data) {
  document.body.classList.remove('observer-offline');
  if (data.observer_instance) {
    if (observerInstance && observerInstance !== data.observer_instance) {
      addressPrivacy.setShown(false);
      hidePairingDetails();
      syncAddressPrivacy();
    }
    observerInstance = data.observer_instance;
  }
  latestData = data;
  const chosen = $('group-filter').value;
  const options = '<option value="">All groups</option>' + data.peers.map(p => `<option value="${esc(p.id)}">${privateText(p.name)}</option>`).join('');
  if ($('group-filter').innerHTML !== options) {
    $('group-filter').innerHTML = options;
    $('group-filter').value = data.peers.some(p => p.id === chosen) ? chosen : '';
  }
  $('username').textContent = addressPrivacy.screen(data.local_user);
  if (data.network_access) { $('sign-out').hidden = data.network_access !== 'lan'; $('owner-access').hidden = data.network_access !== 'lan'; }
  $('freshness').textContent = data.checking ? (data.progress ? `${data.progress.group_name} · batch ${data.progress.batch}/${data.progress.batches}` : 'Observer is checking…') : `Dashboard updated ${new Date().toLocaleTimeString()}`;
  $('cadence').textContent = `Checks every ${data.interval_seconds}s after each cycle · ${data.confirmation_seconds}s confirmation · up to ${data.batch_size} checks at once`;
  $('peers').innerHTML = data.peers.length ? data.peers.filter(p => !$('group-filter').value || p.id === $('group-filter').value).map(p => `<section class="peer"><div class="peerhead"><div><h3>${privateText(p.name)}</h3><small>Host: ${privateText(p.owner)} · ${p.transport === 'local' ? 'Checks from this computer' : 'Remote · Later phase'}</small></div>${p.can_recheck && p.transport === 'local' ? `<button type="button" data-peer="${esc(p.id)}" ${pending ? 'disabled' : ''}>${pending ? 'Checking…' : '↻ Recheck now'}</button>` : ''}</div><div class="summary ${stateClass(p.status)}"><span class="badge">Group status</span><p class="availability ${esc(p.availability.state)}">Device availability: ${esc(p.availability.state)} · ${p.availability.reachable}/${p.availability.total} reachable</p><h4>${esc(labels[p.status] || p.status)}</h4><p>${privateText(p.advice)}</p></div><div class="grid">${p.targets.filter(t => t.kind === 'device').map(targetCard).join('')}</div>${p.targets.some(t => t.kind === 'external' && t.enabled) ? `<h4 class="external-title">External network paths</h4><div class="grid">${p.targets.filter(t => t.kind === 'external' && t.enabled).map(targetCard).join('')}</div>` : ''}<details><summary>Incident history (${p.incidents.length})</summary>${p.incidents.map(i => `<p class="detail">${privateText(i.target)} · ${esc(time(i.started_at))} · ${i.resolved_at ? 'Resolved ' + esc(time(i.resolved_at)) : i.confirmed_at ? 'Confirmed' : 'Pending confirmation'}</p>`).join('') || '<p class="detail">No incidents recorded.</p>'}</details></section>`).join('') : '<p class="empty">No test groups are available for this local user.</p>';
  historyView.render('notifications', data.notifications, 'created_at', n => `<article class="notice"><small>To ${privateText(n.recipient)} · ${esc(time(n.created_at))} · Local dashboard only</small>${privateText(n.message)}</article>`, 'local notifications', data.now == null ? new Date() : new Date(data.now * 1000));
  if (data.observer_error) showError(data.observer_error);
}

function showError(message) { errorMessage = String(message); $('error').textContent = addressPrivacy.screen(message); $('error').hidden = false; }
async function request(path, options, timeoutMs = 45000) {
  const response = await fetch(path, {...options, signal: timeoutMs == null ? undefined : AbortSignal.timeout(timeoutMs)});
  const data = await response.json();
  if (response.status === 401) { location.replace('/login'); throw new Error('Please reconnect this browser'); }
  if (!response.ok) throw new Error(Array.isArray(data.detail) ? data.detail.map(e => e.msg).join('; ') : data.detail || 'Observer request failed');
  return data;
}
async function refresh() {
  try { const data = await request('/api/status'); $('error').hidden = true; render(data); if (actionError) showError(actionError); lastSuccess = Date.now(); }
  catch (error) { document.body.classList.add('observer-offline'); showError(`Observer unavailable: ${error.message}. Displayed cards are last-known measurements.`); $('freshness').textContent = lastSuccess ? `Connection lost · last dashboard update ${new Date(lastSuccess).toLocaleTimeString()}` : 'Observer unavailable'; }
}
$('peers').addEventListener('click', async event => {
  const button = event.target.closest('button[data-peer]');
  if (!button || pending) return;
  pending = true;
  actionError = '';
  button.disabled = true;
  button.textContent = 'Checking…';
  try { const data = await request(`/api/peers/${encodeURIComponent(button.dataset.peer)}/recheck`, {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'}, null); $('error').hidden = true; render(data); }
  catch (error) { actionError = error.message; showError(actionError); }
  finally { pending = false; await refresh(); }
});
refresh();
setInterval(refresh, 3000);

let setupConfig = null;
let fieldCounter = 0;
function deviceFields(d = {}) {
  const i = fieldCounter++;
  return `<fieldset class="setup-device" data-device-id="${esc(d.id || '')}"><legend>Device</legend>
    <label>Hostname / device name<input name="device-name" value="${esc(d.name || '')}" required maxlength="100" placeholder="Router, NAS, or IoT device"></label>
    <label>IP address or hostname<input name="host" type="${!addressPrivacy.shown && addressPrivacy.isIP(d.host) ? 'password' : 'text'}" value="${esc(d.host || '')}" required placeholder="Device address or hostname" autocomplete="off" autocapitalize="none" spellcheck="false"></label>
    <label>Check method<select name="method" data-method="${i}"><option value="icmp" ${d.method !== 'tcp' ? 'selected' : ''}>Ping (ICMP)</option><option value="tcp" ${d.method === 'tcp' ? 'selected' : ''}>TCP connection</option></select></label>
    <label id="port-label-${i}" ${d.method === 'tcp' ? '' : 'hidden'}>Service port<input name="port" type="number" min="1" max="65535" value="${esc(d.port ?? 443)}" required></label>
    <details><summary>Latency setting</summary><label>Flag delays above (milliseconds)<input name="delay" type="number" min="1" max="60000" step="any" value="${esc(d.delayed_ms ?? 100)}" required></label></details>
    <button type="button" data-remove-device>Remove device</button>
  </fieldset>`;
}
function groupFields(group = {}) {
  return `<section class="setup-group" data-group-id="${esc(group.id || '')}" aria-label="Test group">
    <div class="group-editor-head"><label>Group name<input name="group-name" value="${esc(group.name || '')}" required maxlength="100" placeholder="Basic tests, IoT, or Extended tests"></label><button type="button" data-remove-group>Remove group</button></div>
    <label class="check-label"><input name="external-checks" type="checkbox" ${group.external_checks ? 'checked' : ''}> Include external internet path checks</label>
    <div class="group-devices grid">${(group.devices || [{}]).map(deviceFields).join('')}</div>
    <button type="button" data-add-device>+ Add device</button>
  </section>`;
}
function openSetup() {
  if (!setupConfig) return;
  $('setup-user').value = setupConfig.local_user;
  $('setup-batch').value = String(setupConfig.batch_size);
  $('setup-groups').innerHTML = setupConfig.groups.map(groupFields).join('');
  $('setup-error').hidden = true;
  $('setup-result').textContent = '';
  $('close-setup').textContent = setupConfig.required ? 'Set up later' : 'Cancel';
  $('setup-panel').hidden = false;
  $('setup-user').focus();
}
async function loadSetup(firstLaunch = false) {
  try {
    setupConfig = await request('/api/setup');
    $('open-setup').hidden = false;
    $('open-setup').textContent = setupConfig.required ? 'Set up monitoring' : 'Settings';
    $('setup-hint').textContent = setupConfig.required ? 'Ready when you are. Add devices and groups to start monitoring.' : 'Manage groups, devices, and batch size in Settings.';
    if (firstLaunch && setupConfig.required) openSetup();
  } catch (error) { $('setup-hint').textContent = `Setup unavailable: ${error.message}`; }
}
$('group-filter').addEventListener('change', () => { if (latestData) render(latestData); });
$('open-setup').addEventListener('click', openSetup);
$('close-setup').addEventListener('click', () => { $('setup-panel').hidden = true; $('open-setup').focus(); });
$('add-group').addEventListener('click', () => {
  $('setup-groups').insertAdjacentHTML('beforeend', groupFields());
  $('setup-groups').lastElementChild.querySelector('input').focus();
});
$('setup-groups').addEventListener('input', event => {
  if (event.target.matches('[name="host"]')) {
    event.target.type = !addressPrivacy.shown && addressPrivacy.isIP(event.target.value) ? 'password' : 'text';
  }
});
$('setup-groups').addEventListener('change', event => {
  if (event.target.matches('[data-method]')) $('port-label-' + event.target.dataset.method).hidden = event.target.value !== 'tcp';
});
$('setup-groups').addEventListener('click', event => {
  const button = event.target.closest('button');
  if (!button) return;
  const group = button.closest('.setup-group');
  if (button.hasAttribute('data-add-device')) {
    group.querySelector('.group-devices').insertAdjacentHTML('beforeend', deviceFields());
    group.querySelector('.group-devices').lastElementChild.querySelector('input').focus();
  }
  if (button.hasAttribute('data-remove-device')) {
    if (group.querySelectorAll('.setup-device').length === 1) {
      $('setup-error').textContent = 'Keep at least one device in each group, or remove the group.';
      $('setup-error').hidden = false;
    } else button.closest('.setup-device').remove();
  }
  if (button.hasAttribute('data-remove-group')) {
    if ($('setup-groups').children.length === 1) {
      $('setup-error').textContent = 'Keep at least one test group.';
      $('setup-error').hidden = false;
    } else group.remove();
  }
});
$('setup-form').addEventListener('submit', async event => {
  event.preventDefault();
  if (pending) return;
  const payload = {
    local_user: $('setup-user').value.trim(), batch_size: Number($('setup-batch').value),
    groups: [...$('setup-groups').querySelectorAll('.setup-group')].map(group => ({
      id: group.dataset.groupId || null,
      name: group.querySelector('[name="group-name"]').value.trim(),
      external_checks: group.querySelector('[name="external-checks"]').checked,
      devices: [...group.querySelectorAll('.setup-device')].map(device => ({
        id: device.dataset.deviceId || null,
        name: device.querySelector('[name="device-name"]').value.trim(),
        host: device.querySelector('[name="host"]').value.trim(),
        method: device.querySelector('[name="method"]').value,
        port: Number(device.querySelector('[name="port"]').value),
        delayed_ms: Number(device.querySelector('[name="delay"]').value)
      }))
    }))
  };
  pending = true;
  $('save-setup').disabled = true;
  $('save-setup').textContent = 'Saving…';
  $('setup-error').hidden = true;
  try {
    const result = await request('/api/setup', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
    await loadSetup();
    // Refresh assigned IDs after saving so further edits preserve device history.
    $('setup-groups').innerHTML = setupConfig.groups.map(groupFields).join('');
    $('setup-result').textContent = result.message;
    $('close-setup').textContent = 'Done';
  } catch (error) { $('setup-error').textContent = error.message; $('setup-error').hidden = false; }
  finally { pending = false; $('save-setup').disabled = false; $('save-setup').textContent = 'Save and start monitoring'; await refresh(); }
});
loadSetup(true);

$('sign-out').addEventListener('click', async () => {
  try {
    await request('/api/logout', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'});
    location.replace('/login');
  } catch (error) { showError(error.message); }
});

// Provider credentials are write-only. Saved secrets never return to this page.
let notificationConfig = [];
let latestDeliveries = [];
const providerHelp = {
  discord: 'Create a channel webhook in Discord → Edit Channel → Integrations → Webhooks. Paste its URL. This sends channel messages; it does not enable commands.',
  slack: 'Create a Slack app for your workspace, enable Incoming Webhooks, and authorize a channel. Paste that webhook URL. Workspace app approval may be required.',
  telegram: 'Create a bot with @BotFather. Start a conversation with your bot, then enter its token and your numeric chat ID. This version sends alerts; it does not read commands.',
  twilio: 'Use a Twilio account SID, auth token, SMS-capable sender, and recipient in international format. Trial recipient restrictions and sender registration/verification may apply. SMS is charged by the provider.'
};
function showNotificationProvider() {
  const provider = $('notify-provider').value;
  const config = notificationConfig.find(d => d.provider === provider) || {};
  $('notify-help').textContent = providerHelp[provider];
  $('notify-enabled').checked = !!config.enabled;
  $('notify-recovery').checked = !!config.recovery;
  $('notify-monthly').checked = !!config.monthly;
  for (const key of ['secret', 'address', 'account', 'sender']) $('notify-' + key).value = '';
  $('notify-secret-label').textContent = provider === 'telegram' ? 'Bot token' : provider === 'twilio' ? 'Auth token' : 'Incoming webhook URL';
  $('notify-address-field').hidden = !['telegram', 'twilio'].includes(provider);
  $('notify-account-field').hidden = provider !== 'twilio';
  $('notify-sender-field').hidden = provider !== 'twilio';
  $('notify-limit-field').hidden = provider !== 'twilio';
  $('notify-limit').value = config.daily_limit || 20;
  $('notify-groups').innerHTML = (setupConfig?.groups || []).map(g => `<label class="check-label"><input type="checkbox" name="notify-group" value="${esc(g.id)}" ${(config.groups || []).includes(g.id) ? 'checked' : ''}>${privateText(g.name)}</label>`).join('');
  $('notify-result').textContent = config.configured ? 'Saved settings loaded. Private fields stay hidden.' : 'No settings saved for this provider.';
}
function renderDeliveryHistory() {
  historyView.render('delivery-history', latestDeliveries, 'created', d => `<article class="notice"><small>${esc(time(d.created))} · ${esc(d.provider)} · ${esc(d.state)}</small>${privateText(d.detail || 'Waiting for background delivery')}</article>`, 'delivery attempts');
}
async function loadNotificationSettings(reset = false) {
  try {
    const data = await request('/api/notifications/settings');
    notificationConfig = data.destinations;
    latestDeliveries = data.deliveries;
    renderDeliveryHistory();
    if (reset) showNotificationProvider();
  } catch (error) { $('notify-result').textContent = error.message; }
}
$('notification-settings').addEventListener('toggle', () => { if ($('notification-settings').open) loadNotificationSettings(true); });
$('notify-provider').addEventListener('change', showNotificationProvider);
function notificationPayload() {
  const payload = {provider: $('notify-provider').value, enabled: $('notify-enabled').checked,
    recovery: $('notify-recovery').checked, monthly: $('notify-monthly').checked, daily_limit: Number($('notify-limit').value),
    groups: [...document.querySelectorAll('[name="notify-group"]:checked')].map(el => el.value)};
  for (const key of ['secret', 'address', 'account', 'sender']) payload[key] = $('notify-' + key).value.trim();
  return payload;
}
$('notification-form').addEventListener('submit', async event => {
  event.preventDefault();
  const button = event.submitter;
  button.disabled = true;
  try {
    const payload = notificationPayload();
    await request('/api/notifications/settings', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)});
    await loadNotificationSettings(true);
    $('notify-result').textContent = 'Saved. Enabled providers send future alerts in the background.';
  } catch (error) { $('notify-result').textContent = error.message; }
  finally { button.disabled = false; }
});
$('notify-test').addEventListener('click', async () => {
  $('notify-test').disabled = true;
  $('notify-test').textContent = 'Testing…';
  $('notify-result').textContent = 'Sending one test using the entered values…';
  try {
    const payload = notificationPayload();
    const data = await request('/api/notifications/test/' + payload.provider, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)}, 60000);
    $('notify-result').textContent = data.message;
    await loadNotificationSettings();
  } catch (error) { $('notify-result').textContent = error.message; }
  finally { $('notify-test').disabled = false; $('notify-test').textContent = 'Send test notification'; }
});
function delaySummary(group) {
  const d = group.delays;
  if (!d) return '';
  const totals = `<p><strong>${esc(d.count)} delayed check(s)</strong>${d.worst_ms == null ? '' : ` · Worst ${esc(d.worst_ms)} ms`}</p>`;
  const devices = d.devices.map(t => `<p class="detail">${privateText(t.name)} · ${t.method === 'tcp' ? 'TCP connect' : 'ICMP round-trip'}: ${esc(t.count)} delayed check(s) · Average ${esc(t.average_ms)} ms · Worst ${esc(t.worst_ms)} ms</p>`).join('');
  const coverage = `<p class="detail">${d.logging_started_at == null ? 'Delay logging starts with the next enabled device check.' : `Delay logging began ${esc(time(d.logging_started_at))}. Earlier readings are not reconstructed.`} Counts are recorded slow checks, not outages or continuous delay duration. Delayed devices still count as reachable.</p>`;
  const log = d.recent.map(t => `<div class="delay-entry"><strong>${privateText(t.name)}</strong><p class="detail">${esc(time(t.checked_at))} · ${t.method === 'tcp' ? `TCP connect :${esc(t.port)}` : 'ICMP round-trip'} · ${esc(t.latency_ms)} ms · Threshold ${esc(t.threshold_ms)} ms</p></div>`).join('');
  return totals + devices + coverage + (log ? `<details data-delay-group="${esc(group.group_id)}"><summary>Delayed readings · latest ${esc(d.recent.length)} of ${esc(d.count)}</summary><div class="delay-log" tabindex="0" role="region" aria-label="Delayed device readings">${log}</div></details>` : '');
}
function renderMonthlyReport() {
  if (!latestReport) return;
  const open = new Map([...document.querySelectorAll('#monthly-report details[data-delay-group]')].map(el => [el.dataset.delayGroup, {open:el.open, scroll:el.querySelector('.delay-log').scrollTop}]));
  $('monthly-report').innerHTML = latestReport.groups.map(g => `<article class="notice"><h3>${privateText(g.name)}</h3><p><strong>Available ${g.available_days.toFixed(2)} days</strong></p><p class="detail">Fully reachable ${(g.seconds.green / 3600).toFixed(2)}h · Partial ${(g.seconds.yellow / 3600).toFixed(2)}h · Unreachable ${(g.seconds.red / 3600).toFixed(2)}h · Unknown ${(g.seconds.unknown / 3600).toFixed(2)}h</p><p>${g.device_incidents} confirmed device incident(s)</p>${g.devices.map(d => `<p class="detail">${privateText(d.name)}: ${d.incidents}</p>`).join('')}${delaySummary(g)}</article>`).join('');
  for (const el of document.querySelectorAll('#monthly-report details[data-delay-group]')) {
    const previous = open.get(el.dataset.delayGroup);
    if (previous) { el.open = previous.open; el.querySelector('.delay-log').scrollTop = previous.scroll; }
  }
}
async function loadMonthlyReport() {
  try {
    const data = await request('/api/reports/' + encodeURIComponent($('report-month').value));
    latestReport = data;
    renderMonthlyReport();
  } catch (error) { $('monthly-report').textContent = error.message; }
}
$('report-month').value = new Date().toISOString().slice(0, 7);
$('report-month').addEventListener('change', loadMonthlyReport);
loadMonthlyReport();
setInterval(() => { loadMonthlyReport(); if ($('notification-settings').open) loadNotificationSettings(); }, 15000);

function syncAddressPrivacy() {
  $('toggle-addresses').textContent = addressPrivacy.shown ? 'Hide IP addresses' : 'Show IP addresses';
  $('toggle-addresses').setAttribute('aria-pressed', String(addressPrivacy.shown));
  $('privacy-hint').textContent = addressPrivacy.shown ? 'IP addresses visible for this session.' : 'Device IP addresses hidden · External paths and hostnames stay visible.';
  document.querySelectorAll('input[name="host"]').forEach(input => {
    input.type = !addressPrivacy.shown && addressPrivacy.isIP(input.value) ? 'password' : 'text';
  });
  if (errorMessage) $('error').textContent = addressPrivacy.screen(errorMessage);
  renderMonthlyReport();
  renderDeliveryHistory();
}
function setAddressesShown(shown) {
  addressPrivacy.setShown(shown);
  syncAddressPrivacy();
  if (latestData) render(latestData);
}
$('toggle-addresses').addEventListener('click', () => setAddressesShown(!addressPrivacy.shown));
window.addEventListener('pagehide', () => setAddressesShown(false));
window.addEventListener('pageshow', () => setAddressesShown(false));

$('show-pairing').addEventListener('click', async () => {
  const output = $('pairing-details');
  if (!output.hidden) { hidePairingDetails(); return; }
  $('show-pairing').disabled = true;
  try {
    const data = await request('/api/access/pairing');
    output.textContent = ['Owner key: ' + data.key, ...data.links].join('\n');
    output.hidden = false;
    $('show-pairing').textContent = 'Hide private pairing details';
  } catch (error) { showError(error.message); }
  finally { $('show-pairing').disabled = false; }
});
function hidePairingDetails() {
  $('pairing-details').textContent = '';
  $('pairing-details').hidden = true;
  $('show-pairing').textContent = 'Show private pairing details';
}
window.addEventListener('pagehide', hidePairingDetails);
window.addEventListener('pageshow', hidePairingDetails);

function existingHostLink(value) {
  const url = new URL(value.trim());
  const parts = new URLSearchParams(url.hash.slice(1));
  const key = parts.get('key');
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password ||
      url.pathname !== '/login' || url.search || !key || key.length > 256 ||
      [...parts.keys()].some(name => name !== 'key') || parts.getAll('key').length !== 1) {
    throw new Error('Paste the complete host pairing link from Settings, ending in /login#key=…');
  }
  return url.href;
}
$('pair-existing-form').addEventListener('submit', event => {
  event.preventDefault();
  const input = $('existing-pairing-link');
  $('existing-pairing-error').hidden = true;
  try {
    const url = existingHostLink(input.value);
    input.value = '';
    location.assign(url);
  } catch {
    $('existing-pairing-error').textContent = 'Use a complete HTTP or HTTPS pairing link from the original host’s Settings.';
    $('existing-pairing-error').hidden = false;
  }
});
$('export-installation').addEventListener('click', async () => {
  $('export-installation').disabled = true;
  $('transfer-result').textContent = 'Preparing encrypted transfer…';
  try {
    const response = await fetch('/api/access/export', {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
    if (!response.ok) {
      const data = await response.json();
      throw new Error(typeof data.detail === 'string' ? data.detail : 'Unable to export installation');
    }
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement('a');
    link.href = url;
    link.download = 'Ping_A_Friend-transfer.paf';
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
    $('transfer-result').textContent = 'Transfer downloaded. Keep the original host’s pairing key to unlock it on the new computer.';
  } catch (error) { $('transfer-result').textContent = error.message; }
  finally { $('export-installation').disabled = false; }
});
$('import-installation-form').addEventListener('submit', async event => {
  event.preventDefault();
  const file = $('transfer-file').files[0];
  if (!file || !$('transfer-confirm').checked) return;
  if (file.size > 32 * 1024 * 1024) { $('transfer-result').textContent = 'Transfer file is too large (32 MB maximum).'; return; }
  $('import-installation').disabled = true;
  $('transfer-result').textContent = 'Unlocking and restoring…';
  try {
    const data = await request('/api/access/import', {method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({archive:await file.text(), key:$('transfer-key').value.trim(), confirm:true})});
    $('transfer-result').textContent = data.message;
    $('transfer-key').value = '';
    $('transfer-file').value = '';
    $('transfer-confirm').checked = false;
    await loadSetup();
    openSetup();
    await loadNotificationSettings(true);
    await loadMonthlyReport();
    await refresh();
  } catch (error) { $('transfer-result').textContent = error.message; }
  finally { $('import-installation').disabled = false; }
});
function clearTransferInputs() {
  $('existing-pairing-link').value = '';
  $('transfer-key').value = '';
  $('transfer-file').value = '';
  $('transfer-confirm').checked = false;
}
window.addEventListener('pagehide', clearTransferInputs);
window.addEventListener('pageshow', clearTransferInputs);
