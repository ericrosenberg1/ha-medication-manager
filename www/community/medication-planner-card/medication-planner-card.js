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

  /** Return YYYY-MM-DD in LOCAL time. */
  _localDateStr(date) {
    const y = date.getFullYear();
    const m = String(date.getMonth() + 1).padStart(2, '0');
    const d = String(date.getDate()).padStart(2, '0');
    return `${y}-${m}-${d}`;
  }

  _render() {
    if (!this._hass || !this.config) return;
    const card = document.createElement('ha-card');
    card.header = this.config.title || 'Medication Planner (7 days)';
    const container = document.createElement('div');
    container.style.padding = '0 16px 16px 16px';
    container.style.overflowX = 'auto';
    container.style.WebkitOverflowScrolling = 'touch';

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
        localDate: this._localDateStr(new Date(ev.timestamp || ev.time || 0)),
        status: (ev.status || '').toLowerCase()
      }));

      const table = document.createElement('table');
      table.style.width = '100%';
      table.style.borderCollapse = 'collapse';
      table.style.minWidth = '500px';
      const caption = document.createElement('caption');
      caption.textContent = `${name} 7-day planner`;
      caption.style.cssText = 'position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)';
      table.appendChild(caption);

      const thead = document.createElement('thead');
      const trh = document.createElement('tr');
      const thName = document.createElement('th');
      thName.textContent = name;
      thName.style.textAlign = 'left';
      thName.style.padding = '4px 8px';
      thName.style.borderBottom = '1px solid var(--divider-color)';
      thName.style.whiteSpace = 'nowrap';
      trh.appendChild(thName);
      for (const d of days) {
        const th = document.createElement('th');
        th.textContent = d.toLocaleDateString(undefined, { weekday: 'short', month: 'numeric', day: 'numeric' });
        th.style.textAlign = 'center';
        th.style.padding = '4px 8px';
        th.style.borderBottom = '1px solid var(--divider-color)';
        th.style.whiteSpace = 'nowrap';
        th.style.fontSize = '0.85rem';
        trh.appendChild(th);
      }
      thead.appendChild(trh);
      table.appendChild(thead);

      const tbody = document.createElement('tbody');
      const tr = document.createElement('tr');
      const tdLabel = document.createElement('td');
      tdLabel.textContent = `${times.length}/day`;
      tdLabel.style.padding = '4px 8px';
      tdLabel.style.color = 'var(--secondary-text-color, #888)';
      tdLabel.style.fontSize = '0.85rem';
      tr.appendChild(tdLabel);

      for (const d of days) {
        const dayStr = this._localDateStr(d);
        const dayEvents = events.filter(e => e.localDate === dayStr);
        const taken = dayEvents.filter(e => e.status.startsWith('take')).length;
        const skipped = dayEvents.filter(e => e.status.startsWith('skip')).length;
        const missed = Math.max(0, times.length - taken - skipped);
        const td = document.createElement('td');
        td.style.textAlign = 'center';
        td.style.padding = '4px 8px';
        td.style.fontSize = '0.85rem';

        if (taken === times.length) {
          td.textContent = `${taken}/${times.length}`;
          td.style.color = 'var(--success-color, #4caf50)';
          td.style.fontWeight = '600';
        } else if (missed > 0) {
          td.textContent = `${taken}/${times.length}`;
          td.style.color = 'var(--error-color, #f44336)';
        } else {
          td.textContent = `${taken}/${times.length}`;
        }

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

  getGridOptions() { return { columns: 12, min_columns: 8, rows: 3, min_rows: 2 }; }

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
