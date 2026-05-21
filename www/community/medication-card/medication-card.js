class MedicationCard extends HTMLElement {
  static getConfigElement() {
    return document.createElement('medication-card-editor');
  }

  static getStubConfig() {
    return { entities: [], title: 'Medications' };
  }

  setConfig(config) {
    if (!config || !Array.isArray(config.entities) || config.entities.length === 0) {
      throw new Error("entities is required and must be a non-empty array");
    }
    this.config = config;
    if (this._hass) this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _render() {
    if (!this._hass || !this.config) return;

    if (!this.shadowRoot) {
      this.attachShadow({ mode: 'open' });
    }

    const root = this.shadowRoot;
    root.innerHTML = '';

    const style = document.createElement('style');
    style.textContent = `
      :host {
        display: block;
      }
      .med-list {
        padding: 0 16px 16px 16px;
      }
      .med-item {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 12px 0;
        border-bottom: 1px solid var(--divider-color, #e0e0e0);
      }
      .med-item:last-child {
        border-bottom: none;
      }
      .med-info {
        flex: 1;
        min-width: 0;
      }
      .med-name {
        font-weight: 600;
        font-size: 1rem;
        display: flex;
        align-items: center;
        gap: 8px;
      }
      .med-detail {
        font-size: 0.85rem;
        color: var(--secondary-text-color, #888);
        margin-top: 2px;
      }
      .med-status {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.5px;
      }
      .status-pending {
        background: var(--info-color, #039be5);
        color: white;
      }
      .status-taken {
        background: var(--success-color, #4caf50);
        color: white;
      }
      .status-skipped {
        background: var(--warning-color, #ff9800);
        color: white;
      }
      .status-snoozed {
        background: var(--accent-color, #ff6f00);
        color: white;
      }
      .status-reminder {
        background: var(--error-color, #f44336);
        color: white;
      }
      .refill-badge {
        display: inline-block;
        padding: 1px 6px;
        border-radius: 8px;
        font-size: 0.7rem;
        font-weight: 600;
        background: var(--error-color, #f44336);
        color: white;
      }
      .med-actions {
        display: flex;
        gap: 4px;
        flex-shrink: 0;
        flex-wrap: wrap;
        justify-content: flex-end;
        margin-left: 8px;
      }
      .action-btn {
        border: none;
        border-radius: 8px;
        padding: 10px 14px;
        min-height: 44px;
        min-width: 44px;
        font-size: 0.8rem;
        font-weight: 500;
        cursor: pointer;
        transition: opacity 0.2s;
        color: white;
      }
      .action-btn:active {
        opacity: 0.7;
      }
      .action-btn:disabled {
        opacity: 0.4;
        cursor: not-allowed;
      }
      .btn-taken {
        background: var(--success-color, #4caf50);
      }
      .btn-skip {
        background: var(--warning-color, #ff9800);
      }
      .btn-snooze {
        background: var(--accent-color, #ff6f00);
      }
      .btn-dismiss {
        background: var(--secondary-text-color, #888);
      }
      .empty-msg {
        padding: 16px;
        text-align: center;
        color: var(--secondary-text-color, #888);
      }
    `;
    root.appendChild(style);

    const liveRegion = document.createElement('div');
    liveRegion.setAttribute('aria-live', 'polite');
    liveRegion.setAttribute('aria-atomic', 'true');
    liveRegion.style.cssText = 'position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;';
    root.appendChild(liveRegion);
    this._liveRegion = liveRegion;

    const card = document.createElement('ha-card');
    card.header = this.config.title || 'Medications';

    let hasEntities = false;
    const list = document.createElement('div');
    list.className = 'med-list';

    for (const entity of this.config.entities) {
      const stateObj = this._hass.states[entity];
      if (!stateObj) continue;
      hasEntities = true;

      const attrs = stateObj.attributes || {};
      const state = (stateObj.state || 'Pending').toLowerCase();
      const name = attrs.friendly_name || attrs.name || entity;
      const dose = attrs.dose || '';
      const times = attrs.times || [];
      const refillNeeded = attrs.refill_needed || false;
      const remaining = attrs.refill_remaining;
      const lastAction = attrs.last_action;

      const item = document.createElement('div');
      item.className = 'med-item';

      // Left: info
      const info = document.createElement('div');
      info.className = 'med-info';

      const nameRow = document.createElement('div');
      nameRow.className = 'med-name';

      const statusClass = state.startsWith('take') ? 'status-taken'
        : state.startsWith('skip') ? 'status-skipped'
        : state.startsWith('snooz') ? 'status-snoozed'
        : state.startsWith('remind') ? 'status-reminder'
        : 'status-pending';

      const statusBadge = document.createElement('span');
      statusBadge.className = `med-status ${statusClass}`;
      statusBadge.textContent = stateObj.state;
      nameRow.appendChild(statusBadge);

      const nameText = document.createElement('span');
      nameText.textContent = name;
      nameRow.appendChild(nameText);

      if (refillNeeded) {
        const refillBadge = document.createElement('span');
        refillBadge.className = 'refill-badge';
        refillBadge.textContent = remaining != null ? `Refill (${remaining} left)` : 'Refill needed';
        nameRow.appendChild(refillBadge);
      }

      info.appendChild(nameRow);

      const detail = document.createElement('div');
      detail.className = 'med-detail';
      const parts = [];
      if (dose) parts.push(dose);
      if (times.length) parts.push(`at ${times.join(', ')}`);
      if (lastAction && lastAction.timestamp) {
        const d = new Date(lastAction.timestamp);
        if (!isNaN(d.getTime())) {
          parts.push(`last: ${d.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}`);
        }
      }
      detail.textContent = parts.join(' · ');
      info.appendChild(detail);

      item.appendChild(info);

      // Right: action buttons
      const actions = document.createElement('div');
      actions.className = 'med-actions';

      const isTaken = state.startsWith('take');
      const isSkipped = state.startsWith('skip');

      const mkBtn = (label, cls, service, disabled = false) => {
        const b = document.createElement('button');
        b.className = `action-btn ${cls}`;
        b.textContent = label;
        b.setAttribute('aria-label', `${label} ${name}`);
        b.disabled = disabled;
        if (!disabled) {
          b.addEventListener('click', () => {
            b.disabled = true;
            b.textContent = '...';
            this._action(entity, service);
            if (liveRegion) liveRegion.textContent = `${name} marked as ${label.toLowerCase()}`;
            // Re-enable after state update (fallback timeout)
            setTimeout(() => { b.disabled = false; b.textContent = label; }, 3000);
          });
        }
        return b;
      };

      const isSnoozed = state.startsWith('snooz');
      actions.appendChild(mkBtn('Taken', 'btn-taken', 'mark_taken', isTaken));
      actions.appendChild(mkBtn('Skip', 'btn-skip', 'mark_skipped', isSkipped));
      actions.appendChild(mkBtn('Snooze', 'btn-snooze', 'mark_snoozed', isTaken || isSkipped || isSnoozed));

      item.appendChild(actions);
      list.appendChild(item);
    }

    if (!hasEntities) {
      const msg = document.createElement('div');
      msg.className = 'empty-msg';
      msg.textContent = 'No medications configured. Add one in Settings → Devices & Services → Medication Reminder.';
      list.appendChild(msg);
    }

    // Healthcare disclaimer footer
    const disclaimer = document.createElement('div');
    disclaimer.style.cssText = 'padding: 8px 16px; font-size: 0.7rem; color: var(--secondary-text-color, #888); border-top: 1px solid var(--divider-color, #e0e0e0); text-align: center;';
    disclaimer.textContent = 'Reminder tool only. Not medical advice. Consult your physician.';
    card.appendChild(list);
    card.appendChild(disclaimer);
    root.appendChild(card);
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

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'medication-card',
  name: 'Medication Card',
  description: 'Display medications with status indicators and action buttons.',
  preview: true,
});
