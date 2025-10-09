class MedicationPlannerCard extends HTMLElement {
  setConfig(config) {
    if (!config || !Array.isArray(config.entities) || config.entities.length === 0) {
      throw new Error('entities is required and must be a non-empty array');
    }
    this.config = config;
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _render() {
    if (!this._hass || !this.config) return;
    const card = document.createElement('ha-card');
    card.header = this.config.title || 'Medication Planner (7 days)';
    const container = document.createElement('div');
    container.style.padding = '0 16px 16px 16px';

    const now = new Date();
    const days = [];
    for (let i = 6; i >= 0; i--) {
      const d = new Date(now);
      d.setDate(d.getDate() - i);
      days.push(d);
    }

    for (const entity of this.config.entities) {
      const st = this._hass.states[entity];
      if (!st) continue;
      const name = st.attributes.friendly_name || entity;
      const times = st.attributes.times || [];
      const adh = this._hass.states[entity + '_adherence'];
      const events = (adh?.attributes?.recent_events || []).map(ev => ({
        ts: new Date(ev.timestamp || ev.time || 0),
        status: (ev.status || '').toLowerCase()
      }));

      const table = document.createElement('table');
      table.style.width = '100%';
      table.style.borderCollapse = 'collapse';

      const thead = document.createElement('thead');
      const trh = document.createElement('tr');
      const thName = document.createElement('th');
      thName.textContent = name;
      thName.style.textAlign = 'left';
      thName.style.padding = '4px 8px';
      thName.style.borderBottom = '1px solid var(--divider-color)';
      trh.appendChild(thName);
      for (const d of days) {
        const th = document.createElement('th');
        th.textContent = d.toLocaleDateString(undefined, { weekday: 'short', month: 'numeric', day: 'numeric' });
        th.style.textAlign = 'center';
        th.style.padding = '4px 8px';
        th.style.borderBottom = '1px solid var(--divider-color)';
        trh.appendChild(th);
      }
      thead.appendChild(trh);
      table.appendChild(thead);

      const tbody = document.createElement('tbody');
      const tr = document.createElement('tr');
      const tdLabel = document.createElement('td');
      tdLabel.textContent = `Expected per day: ${times.length}`;
      tdLabel.style.padding = '4px 8px';
      tr.appendChild(tdLabel);

      for (const d of days) {
        const start = new Date(d); start.setHours(0,0,0,0);
        const end = new Date(d); end.setHours(23,59,59,999);
        const dayEvents = events.filter(e => e.ts >= start && e.ts <= end);
        const taken = dayEvents.filter(e => e.status.startsWith('take')).length;
        const skipped = dayEvents.filter(e => e.status.startsWith('skip')).length;
        const missed = Math.max(0, times.length - taken - skipped);
        const td = document.createElement('td');
        td.style.textAlign = 'center';
        td.style.padding = '4px 8px';
        td.textContent = `${taken}/${times.length}${missed ? ` (missed ${missed})` : ''}`;
        tr.appendChild(td);
      }
      tbody.appendChild(tr);
      table.appendChild(tbody);

      container.appendChild(table);
    }

    this.innerHTML = '';
    card.appendChild(container);
    this.appendChild(card);
  }

  getCardSize() {
    return (this.config?.entities?.length || 1) * 2;
  }
}

customElements.define('medication-planner-card', MedicationPlannerCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'medication-planner-card',
  name: 'Medication Planner Card',
  description: '7-day planner shows taken/missed against schedule.'
});
