# Medication Reminder for Home Assistant

**Medication Reminder** is a [Home Assistant](https://www.home-assistant.io/) custom integration and Lovelace card designed to help you **manage medications, get timely reminders, and track adherence** — all directly within your smart home ecosystem.  

Created by [Eric Rosenberg](https://ericrosenberg.com) • Projects/links: [eric.money](https://eric.money)

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
  - **Dismiss**: Dismiss counts as a skip (for convenience).
  - **Nags/Alarms**: Optional re‑notifications every X minutes up to a limit until you take or skip.

- **Custom Lovelace Card**  
  A built‑in dashboard card shows all medications with their statuses and allows one‑tap actions.

- **History Logging**  
  Automatically logs Taken/Skipped/Snoozed events with timestamps.
  - Includes a 7‑day adherence sensor per medication.
  - Optional history card shows recent events.
  - A statistics sensor exposes Daily/Weekly/Monthly/Yearly taken, skipped, and missed.

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
   - Via HACS (recommended on HAOS):
     - Install HACS if not already installed.
     - In HACS → Integrations, open the menu (⋮) → Custom repositories → add `https://github.com/ericrosenberg1/ha-medication-manager` with category `Integration`.
     - Find “Medication Reminder” in HACS and Install. Restart Home Assistant.
   - Manual:
     - Copy `custom_components/medication_reminder` into `/config/custom_components/`.
     - Restart Home Assistant.
   - Configure:
     - Go to **Settings → Devices & Services → Add Integration → Medication Reminder**.
     - Add your medications (name, dose, times per day). Each medication is a separate config entry.
     - To edit later, open the integration entry and click Options.
     - Optional:
       - `notify_services` (comma‑separated), e.g. `notify.mobile_app_my_phone, notify.family` for mobile actionable notifications.
       - `nag_interval_minutes` and `nag_max` to enable repeated reminders.
       - Refill tracking: `refill_total`, `refill_threshold`, and `dose_units_per_intake`.

2. **Install the Lovelace Card**
   - Note: When installing this integration via HACS, the Lovelace cards in this repository are not installed automatically. Copy the files manually (or install the cards from their own repos if split in the future).
   - Copy `www/community/medication-card` into `/config/www/community/` (create the folders if needed).
   - Add a Lovelace Resource: **Settings → Dashboards → Resources → + Add Resource**
     - URL: `/local/community/medication-card/medication-card.js`
     - Resource type: `JavaScript Module`
   - Add the card to a dashboard:
     ```yaml
     type: custom:medication-card
     entities:
       - sensor.medication_aspirin
       - sensor.medication_vitamin_d
     ```

   - Daily details card (today’s taken/upcoming/missed):
     - Copy `www/community/medication-daily-card` into `/config/www/community/`.
     - Add a Resource: `/local/community/medication-daily-card/medication-daily-card.js` (JavaScript Module)
     - Example card:
       ```yaml
       type: custom:medication-daily-card
       entities:
         - sensor.medication_aspirin
         - sensor.medication_vitamin_d
       ```

   - Planner card (7‑day planner):
     - Copy `www/community/medication-planner-card` into `/config/www/community/`.
     - Add a Resource: `/local/community/medication-planner-card/medication-planner-card.js` (JavaScript Module)
     - Example card:
       ```yaml
       type: custom:medication-planner-card
       entities:
         - sensor.medication_aspirin
       ```

3. **Add the History Card (optional)**
   - Copy `www/community/medication-history-card` into `/config/www/community/`.
   - Add a Lovelace Resource for it as well:
     - URL: `/local/community/medication-history-card/medication-history-card.js`
     - Resource type: `JavaScript Module`
   - Add to a dashboard:
     ```yaml
     type: custom:medication-history-card
     entities:
       - sensor.medication_aspirin_adherence
       - sensor.medication_vitamin_d_adherence
     max_events: 10
     ```

4. **Add the Summary Card (optional)**
   - Copy `www/community/medication-summary-card` into `/config/www/community/`.
   - Add a Resource: `/local/community/medication-summary-card/medication-summary-card.js` (JavaScript Module)
   - Example card (uses the new stats sensor automatically created per med):
     ```yaml
     type: custom:medication-summary-card
     entities:
       - sensor.medication_aspirin
       - sensor.medication_vitamin_d
     ```

5. **Automate**
   - Use the medication sensor states (`Pending`, `Taken`, `Skipped`, `Snoozed`) in your automations (e.g., voice announcements, flashing lights, reminders until taken).
   - Services support entity targets and optional snooze minutes:
     - `medication_reminder.mark_taken` (target an entity or pass `entity_id`)
     - `medication_reminder.mark_skipped`
     - `medication_reminder.mark_snoozed` (optional `minutes: 10`)
     - `medication_reminder.mark_pending` (reset state back to Pending)
     - `medication_reminder.refill_set` (set remaining/threshold/units)
     - `medication_reminder.refill_add` (add units after refill)
     - `medication_reminder.refill_acknowledge` (clear refill alert)
   - If mobile notify services are configured in Options, reminders include action buttons (Taken/Skip/Snooze) that work from your phone lock screen.

---

## **Medication Info (Optional, External APIs)**
To help users autofill medication details (images, common dosages, forms), these free sources are suitable:
- NIH RxNorm API (US): strength/dose forms, ingredients, RXCUIs
- NIH DailyMed API: label information, images (when available)
- OpenFDA Drug Label API: structured labeling data
- Wikidata/Wikipedia: images and general information (community‑maintained)

Important: Always follow your doctor’s instructions. Any auto‑suggested info is informational only and may be incomplete or out of date. This integration is local‑first and does not call external APIs by default.

If desired, a future optional provider can fetch and cache public info to prefill: name, common strengths, forms, links to reputable sources, and images via Wikimedia Commons. Opt‑in only.

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
Open an issue here: https://github.com/ericrosenberg1/ha-medication-manager/issues

Author: [Eric Rosenberg](https://ericrosenberg.com) • [eric.money](https://eric.money)

For consulting, support, or sponsorships, connect via either site.

---

## **Changelog**

0.10.0
- Guard domain service registration and mobile action listener to register once.
- Cleanup services/listener automatically when the last entry is removed.
- Generate stable entity IDs using Home Assistant helpers.
- Sanitize notification services in options to prevent invalid service names.
- Expose `snooze_minutes` and configured `notify_services` as entity attributes.
- Add `mark_pending` service to reset a medication to Pending.
- Update docs with HACS guidance and Lovelace resource instructions.
- Add nagging (repeat reminders) with configurable interval and max repeats.
- Add refill tracking with threshold alert and services to set/add/acknowledge.
- Add Dismiss action (treated as Skip) in notifications and card.
- Add Medication Stats sensor (daily/weekly/monthly/yearly counts).
- Add three Lovelace cards: Daily, Planner (7 days), Summary table.

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
