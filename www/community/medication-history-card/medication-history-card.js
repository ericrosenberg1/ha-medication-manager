class MedicationHistoryCard extends HTMLElement {
  setConfig(config) {
    if (!config || !Array.isArray(config.entities) || config.entities.length === 0) {
      throw new Error("entities is required and must be a non-empty array");
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
    card.header = this.config.title || 'Medication History';

    const container = document.createElement('div');
    container.style.padding = '0 16px 16px 16px';

    for (const entity of this.config.entities) {
      const st = this._hass.states[entity];
      if (!st) continue;
      const name = st.attributes.friendly_name || entity;
      const percent = st.state;
      const recent = st.attributes.recent_events || [];

      const section = document.createElement('div');
      section.style.margin = '12px 0';

      const title = document.createElement('div');
      title.style.fontWeight = '600';
      title.textContent = `${name} — ${percent}${st.attributes.unit_of_measurement || ''}`;
      section.appendChild(title);

      const stats = document.createElement('div');
      const t = st.attributes.taken_7d || 0;
      const s = st.attributes.skipped_7d || 0;
      const z = st.attributes.snoozed_7d || 0;
      const e = st.attributes.expected_7d || 0;
      stats.textContent = `Last 7d: taken ${t}/${e}, skipped ${s}, snoozed ${z}`;
      stats.style.margin = '4px 0 8px 0';
      section.appendChild(stats);

      const table = document.createElement('table');
      table.style.width = '100%';
      table.style.borderCollapse = 'collapse';
      const thead = document.createElement('thead');
      const trh = document.createElement('tr');
      for (const h of ['When', 'Status']) {
        const th = document.createElement('th');
        th.textContent = h;
        th.style.textAlign = 'left';
        th.style.borderBottom = '1px solid var(--divider-color)';
        th.style.padding = '4px 8px';
        trh.appendChild(th);
      }
      thead.appendChild(trh);
      table.appendChild(thead);
      const tbody = document.createElement('tbody');
      const rows = recent.slice().reverse().slice(0, this.config.max_events || 10);
      for (const ev of rows) {
        const tr = document.createElement('tr');
        const td1 = document.createElement('td');
        const td2 = document.createElement('td');
        td1.style.padding = td2.style.padding = '4px 8px';
        const d = new Date(ev.timestamp || ev.time || 0);
        td1.textContent = isNaN(d.getTime()) ? (ev.timestamp || '') : d.toLocaleString();
        td2.textContent = ev.status || '';
        tr.appendChild(td1);
        tr.appendChild(td2);
        tbody.appendChild(tr);
      }
      table.appendChild(tbody);

      section.appendChild(table);
      container.appendChild(section);
    }

    this.innerHTML = '';
    card.appendChild(container);
    this.appendChild(card);
  }

  getCardSize() {
    return (this.config?.entities?.length || 1) * 2;
  }
}

customElements.define('medication-history-card', MedicationHistoryCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'medication-history-card',
  name: 'Medication History Card',
  description: 'Shows adherence percentage and recent events.'
});
