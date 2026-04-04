class MedicationHistoryCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._built = false;
  }

  static getConfigElement() {
    return document.createElement('medication-history-card-editor');
  }

  static getStubConfig() {
    return { entities: [], title: 'Medication History' };
  }

  static getGridOptions() {
    return { columns: 12, min_columns: 6, rows: 'auto' };
  }

  setConfig(config) {
    if (!config || !Array.isArray(config.entities) || config.entities.length === 0) {
      throw new Error('entities is required and must be a non-empty array');
    }
    this.config = config;
  }

  connectedCallback() {
    this._buildDom();
  }

  disconnectedCallback() {
    this._built = false;
  }

  _buildDom() {
    if (this._built) return;
    const root = this.shadowRoot;
    root.innerHTML = '';

    const style = document.createElement('style');
    style.textContent = `
      :host {
        display: block;
      }
      .container {
        padding: 0 16px 16px 16px;
      }
      .entity-section {
        margin: 12px 0;
      }
      .entity-name {
        font-weight: 600;
        color: var(--primary-text-color);
      }
      .stats {
        margin: 4px 0 8px 0;
        color: var(--secondary-text-color);
      }
      table {
        width: 100%;
        border-collapse: collapse;
      }
      th {
        text-align: left;
        border-bottom: 1px solid var(--divider-color, #e0e0e0);
        padding: 4px 8px;
        color: var(--primary-text-color);
      }
      td {
        padding: 4px 8px;
        color: var(--primary-text-color);
      }
      tr.row-even {
        background-color: var(--table-row-alternative-background-color, transparent);
      }
      .status-taken {
        color: var(--success-color, #4caf50);
        font-weight: 500;
      }
      .status-skipped {
        color: var(--warning-color, #ff9800);
        font-weight: 500;
      }
      .status-snoozed {
        color: var(--warning-color, #ffc107);
        font-weight: 500;
      }
      .entity-not-found {
        color: var(--error-color, #f44336);
        font-style: italic;
        margin: 8px 0;
      }
      .entity-section + .entity-section {
        border-top: 1px solid var(--divider-color, #e0e0e0);
        padding-top: 12px;
      }
    `;
    root.appendChild(style);

    this._card = document.createElement('ha-card');
    this._cardContainer = document.createElement('div');
    this._cardContainer.className = 'container';
    this._card.appendChild(this._cardContainer);
    root.appendChild(this._card);
    this._built = true;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._built) this._buildDom();
    this._render();
  }

  _formatPercent(value) {
    const num = parseFloat(value);
    if (isNaN(num)) return '--';
    return `${Math.round(num)}%`;
  }

  _getStatusClass(status) {
    const s = (status || '').toLowerCase();
    if (s.startsWith('take')) return 'status-taken';
    if (s.startsWith('skip')) return 'status-skipped';
    if (s.startsWith('snooz')) return 'status-snoozed';
    return '';
  }

  _render() {
    if (!this._hass || !this.config || !this._card) return;

    this._card.header = this.config.title || 'Medication History';
    const container = this._cardContainer;
    container.innerHTML = '';

    for (const entity of this.config.entities) {
      const st = this._hass.states[entity];
      if (!st) {
        const msg = document.createElement('div');
        msg.className = 'entity-not-found';
        msg.textContent = `Entity not found: ${entity}`;
        container.appendChild(msg);
        continue;
      }

      const name = st.attributes.friendly_name || entity;
      const percent = this._formatPercent(st.state);
      const recent = st.attributes.recent_events || [];

      const section = document.createElement('div');
      section.className = 'entity-section';

      const title = document.createElement('div');
      title.className = 'entity-name';
      title.textContent = `${name} \u2014 ${percent}`;
      section.appendChild(title);

      const stats = document.createElement('div');
      stats.className = 'stats';
      const t = st.attributes.taken_7d || 0;
      const s = st.attributes.skipped_7d || 0;
      const z = st.attributes.snoozed_7d || 0;
      const e = st.attributes.expected_7d || 0;
      stats.textContent = `Last 7d: taken ${t}/${e}, skipped ${s}, snoozed ${z}`;
      section.appendChild(stats);

      const table = document.createElement('table');
      const thead = document.createElement('thead');
      const trh = document.createElement('tr');
      for (const h of ['When', 'Status']) {
        const th = document.createElement('th');
        th.textContent = h;
        trh.appendChild(th);
      }
      thead.appendChild(trh);
      table.appendChild(thead);

      const tbody = document.createElement('tbody');
      const rows = recent.slice().reverse().slice(0, this.config.max_events || 10);
      rows.forEach((ev, idx) => {
        const tr = document.createElement('tr');
        if (idx % 2 === 1) tr.className = 'row-even';

        const td1 = document.createElement('td');
        const td2 = document.createElement('td');

        const d = new Date(ev.timestamp || ev.time || 0);
        td1.textContent = isNaN(d.getTime()) ? (ev.timestamp || '') : d.toLocaleString();

        const statusText = ev.status || '';
        td2.textContent = statusText;
        const statusClass = this._getStatusClass(statusText);
        if (statusClass) td2.className = statusClass;

        tr.appendChild(td1);
        tr.appendChild(td2);
        tbody.appendChild(tr);
      });

      table.appendChild(tbody);
      section.appendChild(table);
      container.appendChild(section);
    }
  }

  getCardSize() {
    return (this.config?.entities?.length || 1) * 2;
  }
}

/* ---- Basic Config Editor ---- */
class MedicationHistoryCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
  }

  setConfig(config) {
    this._config = config;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
  }

  _render() {
    if (!this._config) return;
    this.shadowRoot.innerHTML = `
      <style>
        .editor { padding: 16px; }
        label { display: block; margin: 8px 0 4px 0; font-weight: 500; color: var(--primary-text-color); }
        input, textarea { width: 100%; box-sizing: border-box; padding: 8px; border: 1px solid var(--divider-color, #ccc); border-radius: 4px; font-family: inherit; }
        textarea { min-height: 80px; font-family: monospace; }
      </style>
      <div class="editor">
        <label>Title</label>
        <input id="title" type="text" value="${this._config.title || 'Medication History'}" />
        <label>Entities (one per line)</label>
        <textarea id="entities">${(this._config.entities || []).join('\n')}</textarea>
        <label>Max Events</label>
        <input id="max_events" type="number" value="${this._config.max_events || 10}" min="1" max="50" />
      </div>
    `;
    this.shadowRoot.getElementById('title').addEventListener('input', (e) => {
      this._config = { ...this._config, title: e.target.value };
      this._dispatch();
    });
    this.shadowRoot.getElementById('entities').addEventListener('input', (e) => {
      const entities = e.target.value.split('\n').map(s => s.trim()).filter(Boolean);
      this._config = { ...this._config, entities };
      this._dispatch();
    });
    this.shadowRoot.getElementById('max_events').addEventListener('input', (e) => {
      this._config = { ...this._config, max_events: parseInt(e.target.value, 10) || 10 };
      this._dispatch();
    });
  }

  _dispatch() {
    this.dispatchEvent(new CustomEvent('config-changed', { detail: { config: this._config } }));
  }
}

customElements.define('medication-history-card-editor', MedicationHistoryCardEditor);
customElements.define('medication-history-card', MedicationHistoryCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'medication-history-card',
  name: 'Medication History Card',
  description: 'Shows adherence percentage and recent events.',
  preview: false,
});
