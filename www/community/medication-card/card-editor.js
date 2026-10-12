class MedicationCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = { ...config };
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _render() {
    if (!this._hass || !this._config) return;

    if (!this.innerHTML) {
      this.innerHTML = `
        <style>
          .editor-row {
            display: flex;
            flex-direction: column;
            gap: 8px;
            padding: 16px;
          }
          .editor-row label {
            font-weight: 500;
            font-size: 0.9rem;
          }
          .entity-list {
            display: flex;
            flex-direction: column;
            gap: 4px;
          }
          .entity-row {
            display: flex;
            align-items: center;
            gap: 8px;
          }
          .entity-row input {
            flex: 1;
            padding: 8px;
            border: 1px solid var(--divider-color, #ccc);
            border-radius: 4px;
            font-size: 0.9rem;
          }
          .remove-btn {
            background: none;
            border: none;
            cursor: pointer;
            color: var(--error-color, #f44336);
            font-size: 1.2rem;
            padding: 4px;
          }
          .add-btn {
            background: var(--primary-color, #03a9f4);
            color: white;
            border: none;
            border-radius: 4px;
            padding: 6px 12px;
            cursor: pointer;
            font-size: 0.85rem;
            align-self: flex-start;
          }
          .title-input {
            padding: 8px;
            border: 1px solid var(--divider-color, #ccc);
            border-radius: 4px;
            font-size: 0.9rem;
            width: 100%;
            box-sizing: border-box;
          }
          .hint {
            font-size: 0.8rem;
            color: var(--secondary-text-color, #888);
          }
        </style>
        <div class="editor-row">
          <label for="med-card-title">Title</label>
          <input class="title-input" id="med-card-title" type="text" placeholder="Medications">

          <label id="med-card-entities-label">Entities</label>
          <div class="hint">Add sensor.medication_* entities</div>
          <div class="entity-list" id="entity-list" aria-labelledby="med-card-entities-label"></div>
          <button class="add-btn" id="add-btn">+ Add Entity</button>
        </div>
      `;

      this.querySelector('.title-input').addEventListener('input', (e) => {
        this._config.title = e.target.value;
        this._fireChanged();
      });

      this.querySelector('#add-btn').addEventListener('click', () => {
        if (!this._config.entities) this._config.entities = [];
        this._config.entities.push('');
        this._renderEntities();
        this._fireChanged();
      });
    }

    // Set the title through the DOM property, never the markup above, so a
    // title holding quotes or angle brackets can't break the input.
    const titleInput = this.querySelector('.title-input');
    const title = this._config.title || '';
    if (titleInput.value !== title) titleInput.value = title;

    this._renderEntities();
  }

  _renderEntities() {
    const list = this.querySelector('#entity-list');
    if (!list) return;

    const entities = this._config.entities || [];

    // hass is set on every state change in Home Assistant, and setConfig runs
    // after each edit. Rebuilding the rows on each call would drop focus while
    // someone types an entity id, so only rebuild when rows are added or
    // removed, and otherwise sync the values in place.
    const rows = list.querySelectorAll('.entity-row');
    if (rows.length === entities.length) {
      rows.forEach((row, idx) => {
        const input = row.querySelector('input');
        if (input.value !== entities[idx]) input.value = entities[idx];
        row.querySelector('.remove-btn')
          .setAttribute('aria-label', `Remove entity ${entities[idx] || idx + 1}`);
      });
      return;
    }

    list.innerHTML = '';
    entities.forEach((entity, idx) => {
      const row = document.createElement('div');
      row.className = 'entity-row';

      const input = document.createElement('input');
      input.type = 'text';
      const inputId = `med-entity-${idx}`;
      input.id = inputId;
      input.value = entity;
      input.placeholder = 'sensor.medication_aspirin';
      input.addEventListener('input', (e) => {
        this._config.entities[idx] = e.target.value;
        this._fireChanged();
      });

      const label = document.createElement('label');
      label.textContent = `Entity ${idx + 1}`;
      label.style.cssText = 'position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)';
      label.setAttribute('for', inputId);
      row.appendChild(label);
      row.appendChild(input);

      const removeBtn = document.createElement('button');
      removeBtn.className = 'remove-btn';
      removeBtn.textContent = '\u00d7';
      removeBtn.setAttribute('aria-label', `Remove entity ${entity || idx + 1}`);
      removeBtn.addEventListener('click', () => {
        this._config.entities.splice(idx, 1);
        this._renderEntities();
        this._fireChanged();
      });

      row.appendChild(removeBtn);
      list.appendChild(row);
    });
  }

  _fireChanged() {
    const event = new CustomEvent('config-changed', {
      detail: { config: { ...this._config } },
      bubbles: true,
      composed: true,
    });
    this.dispatchEvent(event);
  }
}

customElements.define('medication-card-editor', MedicationCardEditor);
