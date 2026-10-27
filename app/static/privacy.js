// Display privacy only: owner-authenticated API data and monitoring are unchanged.
// Intentionally never persisted, so every new page starts with addresses hidden.
globalThis.addressPrivacy = (() => {
  let shown = false;
  function isIP(value) {
    const text = String(value ?? '');
    if (/^(?:\d{1,3}\.){3}\d{1,3}$/.test(text)) return text.split('.').every(n => Number(n) <= 255);
    if (!text.includes(':')) return false;
    try { return new URL(`http://[${text.split('%')[0]}]/`).hostname.startsWith('['); }
    catch { return false; }
  }
  function screen(value) {
    const text = String(value ?? '');
    if (shown) return text;
    // IPv6 first, so IPv4-mapped IPv6 is screened as a single address. Validate
    // candidates to leave timestamps and ordinary hostnames untouched.
    return text.replace(/(?<![\w:])(?:[a-f\d]{0,4}:){2,}[a-f\d:.]*(?:%[\w.-]+)?/gi,
      match => {
        const ip = match.replace(/\.+$/, '');
        return isIP(ip) ? '[IP hidden]' + match.slice(ip.length) : match;
      }).replace(/(?<![\w.-])(?:\d{1,3}\.){3}\d{1,3}(?![\w-]|\.[\w-])/g,
        match => isIP(match) ? '[IP hidden]' : match);
  }
  return {isIP, screen, get shown() { return shown; }, setShown(value) { shown = Boolean(value); }};
})();
