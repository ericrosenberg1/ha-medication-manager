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
      const td0 = document.createElement('td'); td0.textContent = title; tr.appendChild(td0);
      const td1 = document.createElement('td'); td1.textContent = `${d.taken || 0}/${d.expected || 0}`; tr.appendChild(td1);
      const td2 = document.createElement('td'); td2.textContent = `${d.skipped || 0}`; tr.appendChild(td2);
      const td3 = document.createElement('td'); td3.textContent = `${d.missed || 0}`; tr.appendChild(td3);
      const pct = (d.expected ? Math.round((d.taken || 0) / d.expected * 100) : 0);
      const td4 = document.createElement('td'); td4.textContent = `${isNaN(pct) ? 0 : pct}%`; tr.appendChild(td4);
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
      for (const h of ['Period', 'Taken/Expected', 'Skipped', 'Missed', 'Adherence']) {
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
      tbody.appendChild(mkRow('Daily', daily));
      tbody.appendChild(mkRow('Weekly', weekly));
      tbody.appendChild(mkRow('Monthly', monthly));
      tbody.appendChild(mkRow('Yearly', yearly));
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
