class MedicationCard extends HTMLElement {
    setConfig(config) { this.config = config; }
    set hass(hass) {
        this.innerHTML = `<ha-card header="Medications">
            <ul>
            ${this.config.entities.map(entity => `
                <li>
                  ${hass.states[entity].attributes.friendly_name} - ${hass.states[entity].state}
                  <button onclick="this._action('${entity}', 'mark_taken')">Taken</button>
                  <button onclick="this._action('${entity}', 'mark_skipped')">Skip</button>
                  <button onclick="this._action('${entity}', 'mark_snoozed')">Snooze</button>
                </li>
            `).join("")}
            </ul>
        </ha-card>`;
    }
    _action(entity, service) {
        this.hass.callService('medication_reminder', service, { entity_id: entity });
    }
}
customElements.define('medication-card', MedicationCard);
