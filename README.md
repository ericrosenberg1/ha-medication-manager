# Medication Reminder for Home Assistant

**Medication Reminder** is a [Home Assistant](https://www.home-assistant.io/) custom integration and Lovelace card designed to help you **manage medications, get timely reminders, and track adherence** — all directly within your smart home ecosystem.  

Unlike existing blueprints or cloud‑dependent solutions, this project is **local‑first**, **fully configurable in the UI**, and integrates seamlessly with Home Assistant automations.

---

## **Features**
- **Local, Private, and Flexible**  
  All reminders and history are stored locally in Home Assistant. No external accounts required.
  
- **UI‑Based Setup**  
  Add and manage medications directly from the Home Assistant UI — no YAML editing required.

- **Multiple Daily Reminders**  
  Set one or more reminder times per medication.

- **Smart Notifications**  
  Receive actionable mobile and in‑app notifications:
  - **Taken**: Mark the dose as complete.
  - **Skip**: Log that you skipped the dose.
  - **Snooze**: Delay the reminder by a configurable time.

- **Custom Lovelace Card**  
  A built‑in dashboard card shows all medications with their statuses and allows one‑tap actions.

- **History Logging**  
  Automatically logs Taken/Skipped/Snoozed events with timestamps.
  - Includes a 7‑day adherence sensor per medication.
  - Optional history card shows recent events.

- **Automation‑Friendly**  
  Expose medication states as entities for use in automations (e.g., flash lights every 5 minutes until a dose is marked Taken).

---

## **Why This Project?**
While there are great blueprints for medication reminders and cloud‑based integrations (like Medisafe), there was no **all‑in‑one, local‑only solution** with:
- Per‑medication entities
- A UI card for managing medications
- Built‑in snooze and logging
- Full automation hooks

This project fills that gap.

---

## **Getting Started**
1. **Install the Integration**
   - Copy `custom_components/medication_reminder` into your `/config/custom_components/` directory.
   - Restart Home Assistant.
   - Go to **Settings → Devices & Services → Add Integration → Medication Reminder**.
   - Add your medications (name, dose, times per day). Each medication is a separate config entry.
   - To edit later, open the integration entry and click Options.
   - Optional: set `notify_services` (comma‑separated), e.g. `notify.mobile_app_my_phone, notify.family` for mobile actionable notifications.

2. **Install the Lovelace Card**
   - Copy `www/community/medication-card` into `/config/www/community/`.
   - Add the card to your dashboard:
     ```yaml
     type: custom:medication-card
     entities:
       - sensor.medication_aspirin
       - sensor.medication_vitamin_d
     ```

3. **Add the History Card (optional)**
   - Copy `www/community/medication-history-card` into `/config/www/community/`.
   - Add to your dashboard:
     ```yaml
     type: custom:medication-history-card
     entities:
       - sensor.medication_aspirin_adherence
       - sensor.medication_vitamin_d_adherence
     max_events: 10
     ```

4. **Automate**
   - Use the medication sensor states (`Pending`, `Taken`, `Skipped`, `Snoozed`) in your automations (e.g., voice announcements, flashing lights, reminders until taken).
   - Services support entity targets and optional snooze minutes:
     - `medication_reminder.mark_taken` (target an entity or pass `entity_id`)
     - `medication_reminder.mark_skipped`
     - `medication_reminder.mark_snoozed` (optional `minutes: 10`)
   - If mobile notify services are configured in Options, reminders include action buttons (Taken/Skip/Snooze) that work from your phone lock screen.

---

## **Roadmap**
- [ ] **Voice Assistant Support** (Alexa/Google: “Mark my medication as taken.”)  
- [ ] **History Dashboard** (View dose history in Lovelace)  
- [ ] **Refill Reminders** (Optional supply tracking)  
- [ ] **Weekly Reports** (Adherence summary)  
- [ ] **Cloud‑sync option** (Optional integration with services like Medisafe)

---

## **Contributing**
We welcome contributions! Here’s how you can help:
1. **Report Bugs & Request Features**  
   Open an issue here: https://github.com/YOURNAME/ha-medication-manager/issues

2. **Submit Code**  
   - Fork the repo.
   - Create a feature branch: `git checkout -b feature/my-feature`.
   - Commit your changes: `git commit -m "Add new feature"`.
   - Push to your fork and open a pull request.

3. **Design Feedback**  
   Help improve the Lovelace card UI/UX by submitting mockups or ideas.

4. **Testing & Feedback**  
   Join as an **alpha/beta tester** and share feedback on performance and features.

---

## **Versioning**
We follow a **3‑stage release model**:
- **Alpha:** Actively developed, breaking changes possible.
- **Beta:** Feature‑complete for testing by supporters.
- **Stable:** Polished, production‑ready releases.

---

## **License**
This project is licensed under the [MIT License](LICENSE).  
