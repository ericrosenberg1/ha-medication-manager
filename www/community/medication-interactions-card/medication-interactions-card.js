class MedicationInteractionsCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._built = false;
  }

  static getConfigElement() {
    return document.createElement('medication-interactions-card-editor');
  }

  static getStubConfig() {
    return { entity: 'sensor.medication_interactions', title: 'Drug Interactions' };
  }

  setConfig(config) {
    if (!config || !config.entity) {
      throw new Error('entity is required');
    }
    this._config = { title: 'Drug Interactions', ...config };
    if (this._hass) this._update();
  }

  set hass(hass) {
    const oldState = this._hass?.states[this._config?.entity];
    this._hass = hass;
    const newState = hass?.states[this._config?.entity];
    if (
      oldState === newState ||
      (oldState && newState && oldState.state === newState.state &&
        oldState.last_changed === newState.last_changed)
    ) {
      return;
    }
    this._update();
  }

  getCardSize() {
    return 3;
  }

  getGridOptions() {
    return { columns: 12, min_columns: 6, rows: 3, min_rows: 2 };
  }

  _buildDom() {
    if (this._built) return;
    this._built = true;

    const style = document.createElement('style');
    style.textContent = `
      :host {
        display: block;
      }
      ha-card {
        height: 100%;
        box-sizing: border-box;
      }
      .content {
        padding: 0 16px 16px;
      }
      .no-interactions {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 12px;
        border-radius: 8px;
        background: var(--success-color, #4caf50);
        color: var(--text-primary-color, #fff);
        font-weight: 500;
      }
      .no-interactions .icon {
        font-size: 1.4em;
      }
      .missing-entity {
        padding: 12px;
        border-radius: 8px;
        background: var(--secondary-background-color);
        color: var(--secondary-text-color);
        font-size: 0.9em;
        line-height: 1.4;
      }
      .warning-list {
        display: flex;
        flex-direction: column;
        gap: 12px;
      }
      .warning-item {
        border: 1px solid var(--error-color, #db4437);
        border-radius: 8px;
        padding: 12px;
        background: var(--card-background-color, #fff);
      }
      .warning-item + .warning-item {
        border-top-color: var(--warning-color, #ffa600);
      }
      .drug-pair {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 8px;
        flex-wrap: wrap;
      }
      .drug-name {
        font-weight: 600;
        color: var(--primary-text-color);
      }
      .warning-icon {
        color: var(--error-color, #db4437);
        font-size: 1.1em;
      }
      .warning-text {
        color: var(--primary-text-color);
        font-size: 0.92em;
        line-height: 1.4;
        margin-bottom: 6px;
      }
      .source-badge {
        display: inline-block;
        background: var(--secondary-background-color);
        color: var(--secondary-text-color);
        border-radius: 4px;
        padding: 2px 6px;
        font-size: 0.75em;
        font-weight: 500;
      }
      .footer {
        margin-top: 12px;
        padding-top: 8px;
        border-top: 1px solid var(--divider-color);
        display: flex;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 4px;
        color: var(--secondary-text-color);
        font-size: 0.85em;
      }
    `;

    const card = document.createElement('ha-card');
    const content = document.createElement('div');
    content.className = 'content';

    card.appendChild(content);
    this.shadowRoot.appendChild(style);
    this.shadowRoot.appendChild(card);

    this._elCard = card;
    this._elContent = content;
  }

  _update() {
    if (!this._hass || !this._config) return;
    this._buildDom();

    const entityId = this._config.entity;
    const stateObj = this._hass.states[entityId];

    this._elCard.header = this._config.title;

    if (!stateObj) {
      this._elContent.innerHTML = '';
      const msg = document.createElement('div');
      msg.className = 'missing-entity';
      msg.textContent =
        'Interaction sensor not found. Add medications with drug lookup to enable interaction checking.';
      this._elContent.appendChild(msg);
      return;
    }

    const count = parseInt(stateObj.state, 10) || 0;
    const interactions = stateObj.attributes.interactions || [];
    const lastChecked = stateObj.attributes.last_checked || '';
    const medsChecked = stateObj.attributes.medications_checked || 0;

    this._elContent.innerHTML = '';

    if (count === 0) {
      const ok = document.createElement('div');
      ok.className = 'no-interactions';
      const icon = document.createElement('span');
      icon.className = 'icon';
      icon.textContent = '\u2713';
      const text = document.createElement('span');
      text.textContent = 'No known interactions';
      ok.appendChild(icon);
      ok.appendChild(text);
      this._elContent.appendChild(ok);
    } else {
      const list = document.createElement('div');
      list.className = 'warning-list';

      for (const item of interactions) {
        const row = document.createElement('div');
        row.className = 'warning-item';

        const pair = document.createElement('div');
        pair.className = 'drug-pair';

        const drugA = document.createElement('span');
        drugA.className = 'drug-name';
        drugA.textContent = item.drug_a || 'Unknown';

        const warnIcon = document.createElement('span');
        warnIcon.className = 'warning-icon';
        warnIcon.textContent = '\u26A0';

        const drugB = document.createElement('span');
        drugB.className = 'drug-name';
        drugB.textContent = item.drug_b || 'Unknown';

        pair.appendChild(drugA);
        pair.appendChild(warnIcon);
        pair.appendChild(drugB);
        row.appendChild(pair);

        if (item.warning) {
          const desc = document.createElement('div');
          desc.className = 'warning-text';
          desc.textContent = item.warning;
          row.appendChild(desc);
        }

        if (item.source) {
          const badge = document.createElement('span');
          badge.className = 'source-badge';
          badge.textContent = item.source;
          row.appendChild(badge);
        }

        list.appendChild(row);
      }

      this._elContent.appendChild(list);
    }

    const footer = document.createElement('div');
    footer.className = 'footer';
    if (lastChecked) {
      const lc = document.createElement('span');
      lc.textContent = 'Last checked: ' + lastChecked;
      footer.appendChild(lc);
    }
    if (medsChecked) {
      const mc = document.createElement('span');
      mc.textContent = 'Medications checked: ' + medsChecked;
      footer.appendChild(mc);
    }
    if (footer.children.length) {
      this._elContent.appendChild(footer);
    }

    // Healthcare disclaimer (always shown for interaction data)
    const disc = document.createElement('div');
    disc.style.cssText = 'padding: 8px 0; font-size: 0.7rem; color: var(--error-color, #f44336); text-align: center; font-style: italic;';
    disc.textContent = 'Drug interaction data from OpenFDA. May be incomplete. Always consult your physician or pharmacist.';
    this._elContent.appendChild(disc);
  }
}

customElements.define('medication-interactions-card', MedicationInteractionsCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'medication-interactions-card',
  name: 'Medication Interactions Card',
  description: 'Shows drug interaction warnings between your medications.',
});
