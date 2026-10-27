// Calendar months follow the viewer's local timezone, matching displayed dates.
globalThis.historyView = (() => {
  const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const monthKey = date => `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}`;
  const monthLabel = key => {
    const [year, month] = key.split('-').map(Number);
    return new Date(year, month - 1, 1).toLocaleDateString(undefined, {month:'long', year:'numeric'});
  };
  class Months {
    constructor() { this.current = null; this.selected = null; this.groups = new Map(); this.expanded = false; }
    update(entries, timestamp, now = new Date()) {
      const current = monthKey(now);
      const groups = new Map([[current, []]]);
      for (const entry of [...entries].sort((a,b) => b[timestamp] - a[timestamp] || b.id - a.id)) {
        const date = new Date(entry[timestamp] * 1000);
        if (!Number.isFinite(date.getTime())) continue;
        const key = monthKey(date);
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key).push(entry);
      }
      if (current !== this.current || !groups.has(this.selected)) {
        this.selected = current;
        this.expanded = false;
      }
      this.current = current;
      this.groups = new Map([current, ...[...groups.keys()].filter(k => k !== current).sort().reverse()].map(k => [k, groups.get(k)]));
    }
    select(key) {
      if (!this.groups.has(key)) return;
      this.expanded = key === this.selected ? !this.expanded : true;
      this.selected = key;
    }
    visibleEntries(previewCount) {
      const rows = this.groups.get(this.selected) || [];
      return this.expanded ? rows : rows.slice(0, previewCount);
    }
  }
  const views = new Map();
  function remember(view) {
    const box = view.container.querySelector('.history-scroll');
    if (!box || !view.renderedMonth || !view.renderedExpanded) return;
    const first = [...box.children].find(child => child.offsetTop + child.offsetHeight > box.scrollTop);
    view.positions.set(view.renderedMonth, {top:box.scrollTop,
      anchor:first?.dataset.historyEntry, offset:first ? first.offsetTop - box.scrollTop : 0});
  }
  function render(id, entries, timestamp, row, label, now = new Date()) {
    const container = document.getElementById(id);
    let view = views.get(id);
    if (!view) {
      view = {container, model:new Months(), positions:new Map(), signature:null};
      views.set(id, view);
      container.addEventListener('click', event => {
        const button = event.target.closest('button[data-history-month]');
        const preview = event.target.closest('.history-preview .history-entry');
        if ((!button && !preview) || !container.contains(button || preview)) return;
        remember(view);
        if (button) view.model.select(button.dataset.historyMonth);
        else view.model.expanded = true;
        render(id, view.entries, view.timestamp, view.row, view.label);
        container.querySelector(`button[data-history-month="${view.model.selected}"]`)?.focus();
      });
    }
    remember(view);
    Object.assign(view, {entries, timestamp, row, label});
    view.model.update(entries, timestamp, now);
    const selected = view.model.selected;
    const title = monthLabel(selected);
    const rows = view.model.groups.get(selected);
    const expanded = view.model.expanded;
    const visible = view.model.visibleEntries(id === 'notifications' ? 2 : 1);
    const nav = [...view.model.groups].map(([key, values]) => `<button type="button" data-history-month="${key}" aria-pressed="${key === selected}" aria-expanded="${key === selected && expanded}" aria-controls="${id}-entries">${escape(monthLabel(key))}<small>${key === view.model.current ? 'Current month · ' : 'Archived · '}${values.length}${key === selected ? expanded ? ' · Collapse' : ' · Expand' : ''}</small></button>`).join('');
    const content = visible.map((entry, index) => `<div class="history-entry" data-history-entry="${escape(entry.id ?? `${entry[timestamp]}-${index}`)}">${row(entry)}</div>`).join('');
    const caption = expanded ? `${rows.length} ${rows.length === 1 ? 'entry' : 'entries'} · Select month to collapse` : `Latest ${visible.length} of ${rows.length} · Select month or preview to expand`;
    const signature = nav + content + title + caption;
    // Polling should not rebuild unchanged lists or reset keyboard/scroll focus.
    if (view.signature === signature) return;
    view.signature = signature;
    view.observer?.disconnect();
    container.innerHTML = `<div class="history-layout"><nav class="history-months" aria-label="${escape(label)} months">${nav}</nav><section class="history-panel" aria-label="${escape(title)} ${escape(label)}"><p class="history-caption">${escape(title)} · ${escape(caption)} · Last 60 days</p><div id="${id}-entries" class="history-scroll${expanded ? '' : ' history-preview'}" role="region" tabindex="0" aria-label="${escape(title)} ${escape(label)}">${content || '<p class="empty">No entries this month.</p>'}</div></section></div>`;
    view.renderedMonth = selected;
    view.renderedExpanded = expanded;
    const box = container.querySelector('.history-scroll');
    const resize = () => {
      const firstSix = [...box.children].filter(child => child.classList.contains('history-entry')).slice(0,6);
      const gap = parseFloat(getComputedStyle(box).rowGap) || 0;
      const height = firstSix.reduce((sum, child) => sum + child.getBoundingClientRect().height, 0) + Math.max(0, firstSix.length - 1) * gap;
      if (height > 0) box.style.maxHeight = `${Math.ceil(height)}px`;
    };
    resize();
    if (typeof ResizeObserver !== 'undefined') {
      view.observer = new ResizeObserver(resize);
      [...box.children].slice(0,6).forEach(child => view.observer.observe(child));
    }
    const saved = view.positions.get(selected);
    if (saved && expanded) {
      const anchor = [...box.children].find(child => child.dataset.historyEntry === saved.anchor);
      box.scrollTop = saved.top > 0 && anchor ? anchor.offsetTop - saved.offset : saved.top;
    }
  }
  return {Months, monthKey, render};
})();
