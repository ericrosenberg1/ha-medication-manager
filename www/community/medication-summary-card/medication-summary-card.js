class MedicationSummaryCard extends HTMLElement {
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
    card.header = this.config.title || 'Medication Summary';
    const container = document.createElement('div');
    container.style.padding = '0 16px 16px 16px';

    const mkRow = (title, d) => {
      const tr = document.createElement('tr');
      const taken = d.taken || 0;
      const expected = d.expected || 0;
      const skipped = d.skipped || 0;
      const missed = d.missed || 0;
      const pct = expected > 0 ? Math.round((taken / expected) * 100) : 0;

      const td0 = document.createElement('td'); td0.textContent = title; tr.appendChild(td0);
      const td1 = document.createElement('td'); td1.textContent = `${taken}/${expected}`; tr.appendChild(td1);
      const td2 = document.createElement('td'); td2.textContent = `${skipped}`; tr.appendChild(td2);
      const td3 = document.createElement('td'); td3.textContent = `${missed}`; tr.appendChild(td3);
      const td4 = document.createElement('td');
      td4.textContent = `${pct}%`;
      // Color the adherence percentage
      if (pct >= 80) td4.style.color = 'var(--success-color, #4caf50)';
      else if (pct >= 50) td4.style.color = 'var(--warning-color, #ff9800)';
      else if (expected > 0) td4.style.color = 'var(--error-color, #f44336)';
      td4.style.fontWeight = '600';
      tr.appendChild(td4);

      // Style all cells
      [td0, td1, td2, td3, td4].forEach(td => {
        td.style.padding = '4px 8px';
        td.style.fontSize = '0.85rem';
      });

      return tr;
    };

    for (const entity of this.config.entities) {
      const st = this._hass.states[entity];
      if (!st) continue;
      const name = st.attributes.friendly_name || entity;
      const statsId = entity + '_stats';
      const s = this._hass.states[statsId];
      const daily = s?.attributes?.daily || {};
      const weekly = s?.attributes?.weekly || {};
      const monthly = s?.attributes?.monthly || {};
      const yearly = s?.attributes?.yearly || {};

      const section = document.createElement('div');
      section.style.margin = '12px 0';
      const title = document.createElement('div');
      title.style.fontWeight = '600';
      title.textContent = name;
      section.appendChild(title);

      const table = document.createElement('table');
      table.style.width = '100%';
      table.style.borderCollapse = 'collapse';
      const thead = document.createElement('thead');
      const trh = document.createElement('tr');
      for (const h of ['Period', 'Taken', 'Skipped', 'Missed', 'Adherence']) {
        const th = document.createElement('th');
        th.textContent = h;
        th.style.textAlign = 'left';
        th.style.borderBottom = '1px solid var(--divider-color)';
        th.style.padding = '4px 8px';
        th.style.fontSize = '0.85rem';
        trh.appendChild(th);
      }
      thead.appendChild(trh);
      table.appendChild(thead);

      const tbody = document.createElement('tbody');
      tbody.appendChild(mkRow('Today', daily));
      tbody.appendChild(mkRow('7 Days', weekly));
      tbody.appendChild(mkRow('30 Days', monthly));
      tbody.appendChild(mkRow('Year', yearly));
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

customElements.define('medication-summary-card', MedicationSummaryCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'medication-summary-card',
  name: 'Medication Summary Card',
  description: 'Table of daily/weekly/monthly/yearly taken/missed stats.'
});
