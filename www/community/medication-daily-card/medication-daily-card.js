class MedicationDailyCard extends HTMLElement {
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
    card.header = this.config.title || 'Today\'s Medications';
    const container = document.createElement('div');
    container.style.padding = '0 16px 16px 16px';

    const now = new Date();
    const todayStr = now.toISOString().slice(0, 10);

    for (const entity of this.config.entities) {
      const st = this._hass.states[entity];
      if (!st) continue;
      const name = st.attributes.friendly_name || entity;
      const times = st.attributes.times || [];
      const adherenceId = entity + '_adherence';
      const adh = this._hass.states[adherenceId];
      const events = (adh?.attributes?.recent_events || []).filter(e => (e.timestamp || '').startsWith(todayStr));
      const takenToday = events.filter(e => (e.status || '').toLowerCase().startsWith('take')).length;
      const skippedToday = events.filter(e => (e.status || '').toLowerCase().startsWith('skip')).length;

      // Build today time slots
      const slots = times.map(t => {
        const [hh, mm] = String(t).split(':').map(x => parseInt(x, 10));
        const d = new Date(now);
        d.setHours(hh, mm, 0, 0);
        return { label: t, date: d };
      }).sort((a, b) => a.date - b.date);

      const pastSlots = slots.filter(s => s.date <= now);
      const futureSlots = slots.filter(s => s.date > now);
      const missedCount = Math.max(0, pastSlots.length - takenToday - skippedToday);
      const missedSlots = pastSlots.slice(-missedCount).map(s => s.label);
      const upcoming = futureSlots.map(s => s.label);

      const section = document.createElement('div');
      section.style.margin = '12px 0';
      const title = document.createElement('div');
      title.style.fontWeight = '600';
      title.textContent = name;
      section.appendChild(title);

      const summary = document.createElement('div');
      summary.textContent = `Taken ${takenToday}/${slots.length}, Skipped ${skippedToday}, Missed ${missedCount}`;
      summary.style.margin = '4px 0 8px 0';
      section.appendChild(summary);

      const lists = document.createElement('div');
      lists.style.display = 'grid';
      lists.style.gridTemplateColumns = '1fr 1fr';
      lists.style.gap = '8px 16px';

      const mkList = (label, items) => {
        const d = document.createElement('div');
        const h = document.createElement('div');
        h.style.fontWeight = '500';
        h.textContent = label;
        d.appendChild(h);
        const ul = document.createElement('ul');
        ul.style.listStyle = 'none';
        ul.style.margin = '4px 0 0 0';
        ul.style.padding = '0';
        if (items.length === 0) {
          const li = document.createElement('li');
          li.textContent = 'None';
          ul.appendChild(li);
        } else {
          for (const it of items) {
            const li = document.createElement('li');
            li.textContent = it;
            ul.appendChild(li);
          }
        }
        d.appendChild(ul);
        return d;
      };

      lists.appendChild(mkList('Upcoming', upcoming));
      lists.appendChild(mkList('Missed', missedSlots));
      section.appendChild(lists);
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

customElements.define('medication-daily-card', MedicationDailyCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'medication-daily-card',
  name: 'Medication Daily Card',
  description: 'Shows today\'s doses: taken, upcoming, and missed.'
});
