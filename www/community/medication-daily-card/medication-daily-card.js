class MedicationDailyCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._built = false;
  }

  static getConfigElement() {
    return document.createElement('medication-daily-card-editor');
  }

  static getStubConfig() {
    return { entities: [], title: "Today's Medications" };
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
      .summary {
        margin: 4px 0 8px 0;
        color: var(--secondary-text-color);
      }
      .slots-grid {
        display: grid;
        grid-template-columns: 1fr 1fr 1fr;
        gap: 8px 16px;
      }
      .slot-header {
        font-weight: 500;
        color: var(--primary-text-color);
      }
      .slot-list {
        list-style: none;
        margin: 4px 0 0 0;
        padding: 0;
      }
      .slot-list li {
        padding: 2px 0;
      }
      .time-taken {
        color: var(--success-color, #4caf50);
      }
      .time-missed {
        color: var(--error-color, #f44336);
      }
      .time-upcoming {
        color: var(--secondary-text-color, #888);
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

  _getLocalDateStr(date) {
    return date.toLocaleDateString('sv-SE');
  }

  _render() {
    if (!this._hass || !this.config || !this._card) return;

    this._card.header = this.config.title || "Today's Medications";
    const container = this._cardContainer;
    container.innerHTML = '';

    const now = new Date();
    const todayStr = this._getLocalDateStr(now);

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
      const times = st.attributes.times || [];
      const adherenceId = entity + '_adherence';
      const adh = this._hass.states[adherenceId];

      if (!adh) {
        const section = document.createElement('div');
        section.className = 'entity-section';
        const title = document.createElement('div');
        title.className = 'entity-name';
        title.textContent = name;
        section.appendChild(title);
        const msg = document.createElement('div');
        msg.className = 'entity-not-found';
        msg.textContent = `Adherence entity not found: ${adherenceId}`;
        section.appendChild(msg);
        container.appendChild(section);
        continue;
      }

      const events = (adh.attributes.recent_events || []).filter(e => {
        const ts = e.timestamp || '';
        if (!ts) return false;
        const eventDate = new Date(ts);
        return this._getLocalDateStr(eventDate) === todayStr;
      });

      // Build today time slots
      const slots = times.map(t => {
        const parts = String(t).split(':');
        const hh = parseInt(parts[0], 10);
        const mm = parseInt(parts[1], 10);
        const d = new Date(now);
        d.setHours(hh, mm, 0, 0);
        return { label: t, date: d };
      }).sort((a, b) => a.date - b.date);

      // Count taken and skipped events in a single pass
      let takenCount = 0;
      let skippedCount = 0;
      for (const e of events) {
        const s = (e.status || '').toLowerCase();
        if (s.startsWith('take')) takenCount++;
        else if (s.startsWith('skip')) skippedCount++;
      }
      const accountedCount = takenCount + skippedCount;

      const pastSlots = slots.filter(s => s.date <= now);
      const futureSlots = slots.filter(s => s.date > now);

      const missedCount = Math.max(0, pastSlots.length - accountedCount);

      const takenLabels = new Set();
      const missedLabels = new Set();

      // Mark earliest past slots as accounted (taken/skipped), remainder as missed
      let remaining = accountedCount;
      for (const slot of pastSlots) {
        if (remaining > 0) {
          takenLabels.add(slot.label);
          remaining--;
        } else {
          missedLabels.add(slot.label);
        }
      }

      const section = document.createElement('div');
      section.className = 'entity-section';

      const title = document.createElement('div');
      title.className = 'entity-name';
      title.textContent = name;
      section.appendChild(title);

      const summary = document.createElement('div');
      summary.className = 'summary';
      summary.textContent = `Taken ${takenCount}/${slots.length}, Skipped ${skippedCount}, Missed ${missedCount}`;
      section.appendChild(summary);

      const grid = document.createElement('div');
      grid.className = 'slots-grid';

      const mkList = (label, items, cssClass) => {
        const d = document.createElement('div');
        const h = document.createElement('div');
        h.className = 'slot-header';
        h.textContent = label;
        d.appendChild(h);
        const ul = document.createElement('ul');
        ul.className = 'slot-list';
        if (items.length === 0) {
          const li = document.createElement('li');
          li.textContent = 'None';
          ul.appendChild(li);
        } else {
          for (const it of items) {
            const li = document.createElement('li');
            li.className = cssClass;
            li.textContent = it;
            ul.appendChild(li);
          }
        }
        d.appendChild(ul);
        return d;
      };

      const takenTimes = pastSlots.filter(s => takenLabels.has(s.label)).map(s => s.label);
      const missedTimes = pastSlots.filter(s => missedLabels.has(s.label)).map(s => s.label);
      const upcomingTimes = futureSlots.map(s => s.label);

      grid.appendChild(mkList('Taken', takenTimes, 'time-taken'));
      grid.appendChild(mkList('Missed', missedTimes, 'time-missed'));
      grid.appendChild(mkList('Upcoming', upcomingTimes, 'time-upcoming'));

      section.appendChild(grid);
      container.appendChild(section);
    }
  }

  getCardSize() {
    return (this.config?.entities?.length || 1) * 2;
  }
}

/* ---- Basic Config Editor ---- */
class MedicationDailyCardEditor extends HTMLElement {
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
        <input id="title" type="text" value="${this._config.title || "Today's Medications"}" />
        <label>Entities (one per line)</label>
        <textarea id="entities">${(this._config.entities || []).join('\n')}</textarea>
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
  }

  _dispatch() {
    this.dispatchEvent(new CustomEvent('config-changed', { detail: { config: this._config } }));
  }
}

customElements.define('medication-daily-card-editor', MedicationDailyCardEditor);
customElements.define('medication-daily-card', MedicationDailyCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'medication-daily-card',
  name: 'Medication Daily Card',
  description: "Shows today's doses: taken, upcoming, and missed.",
  preview: false,
});
