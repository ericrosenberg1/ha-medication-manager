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
          <label>Title</label>
          <input class="title-input" type="text" value="${this._config.title || ''}" placeholder="Medications">

          <label>Entities</label>
          <div class="hint">Add sensor.medication_* entities</div>
          <div class="entity-list" id="entity-list"></div>
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

    this._renderEntities();
  }

  _renderEntities() {
    const list = this.querySelector('#entity-list');
    if (!list) return;
    list.innerHTML = '';

    const entities = this._config.entities || [];
    entities.forEach((entity, idx) => {
      const row = document.createElement('div');
      row.className = 'entity-row';

      const input = document.createElement('input');
      input.type = 'text';
      input.value = entity;
      input.placeholder = 'sensor.medication_aspirin';
      input.addEventListener('input', (e) => {
        this._config.entities[idx] = e.target.value;
        this._fireChanged();
      });

      const removeBtn = document.createElement('button');
      removeBtn.className = 'remove-btn';
      removeBtn.textContent = '\u00d7';
      removeBtn.addEventListener('click', () => {
        this._config.entities.splice(idx, 1);
        this._renderEntities();
        this._fireChanged();
      });

      row.appendChild(input);
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
