class MedicationCard extends HTMLElement {
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
    card.header = this.config.title || 'Medications';

    const list = document.createElement('ul');
    list.style.listStyle = 'none';
    list.style.padding = '0 16px 16px 16px';

    for (const entity of this.config.entities) {
      const stateObj = this._hass.states[entity];
      if (!stateObj) continue;

      const li = document.createElement('li');
      li.style.display = 'flex';
      li.style.alignItems = 'center';
      li.style.justifyContent = 'space-between';
      li.style.margin = '6px 0';

      const left = document.createElement('div');
      left.textContent = `${stateObj.attributes.friendly_name || entity} - ${stateObj.state}`;
      li.appendChild(left);

      const right = document.createElement('div');

      const mkBtn = (label, service) => {
        const b = document.createElement('mwc-button');
        b.raised = true;
        b.label = label;
        b.addEventListener('click', () => this._action(entity, service));
        return b;
      };

      right.appendChild(mkBtn('Taken', 'mark_taken'));
      right.appendChild(mkBtn('Skip', 'mark_skipped'));
      right.appendChild(mkBtn('Snooze', 'mark_snoozed'));
      li.appendChild(right);

      list.appendChild(li);
    }

    // Clear and append
    this.innerHTML = '';
    card.appendChild(list);
    this.appendChild(card);
  }

  _action(entity, service) {
    if (!this._hass) return;
    this._hass.callService('medication_reminder', service, { entity_id: entity });
  }

  getCardSize() {
    return (this.config?.entities?.length || 1) + 1;
  }
}

customElements.define('medication-card', MedicationCard);

// Provide Lovelace card registry metadata (for some UIs/assistive tooling)
window.customCards = window.customCards || [];
window.customCards.push({
  type: 'medication-card',
  name: 'Medication Card',
  description: 'Display medications and take actions (Taken/Skip/Snooze).'
});
