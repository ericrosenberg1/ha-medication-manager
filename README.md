# Medication Reminder for Home Assistant

**Medication Reminder** is a [Home Assistant](https://www.home-assistant.io/) custom integration and Lovelace card designed to help you **manage medications, get timely reminders, and track adherence** — all directly within your smart home ecosystem.

Created by [Eric Rosenberg](https://ericrosenberg.com) • Projects/links: [eric.money](https://eric.money)

Unlike existing blueprints or cloud-dependent solutions, this project is **local-first**, **fully configurable in the UI**, and integrates seamlessly with Home Assistant automations.

---

## What's New in v0.2.0

- **Drug Autocomplete** — Search the FDA/NIH database (RxTerms + OpenFDA) when adding medications. Auto-populates name, dose, and stores drug identifiers.
- **Drug Interaction Warnings** — Automatic checking for interaction risks between your configured medications using OpenFDA data. A new `medication-interactions-card` displays warnings.
- **Improved Cards** — All cards rebuilt with Shadow DOM, HA theme support, responsive layouts, accessibility (ARIA labels, keyboard navigation), and proper card editors for visual configuration.
- **Reliability Improvements** — Reminders survive HA restarts, daily auto-reset at midnight, snoozed state persists across restarts, and HA events fire for automations.
- **Performance** — History manager with debounced saves, cached adherence calculations, and daily pruning.
- **Security** — Input validation on all service calls, entity ID validation, and proper error handling.

---

## **Features**
- **Local, Private, and Flexible**
  All reminders and history are stored locally in Home Assistant. No external accounts required.

- **UI-Based Setup**
  Add and manage medications directly from the Home Assistant UI — no YAML editing required.

- **Multiple Daily Reminders**
  Set one or more reminder times per medication.

- **Smart Notifications**
  Receive actionable mobile and in-app notifications:
  - **Taken**: Mark the dose as complete.
  - **Skip**: Log that you skipped the dose.
  - **Snooze**: Delay the reminder by a configurable time.
  - **Dismiss**: Dismiss counts as a skip (for convenience).
  - **Nags/Alarms**: Optional re-notifications every X minutes up to a limit until you take or skip.

- **Custom Lovelace Cards**
  Six built-in dashboard cards (see Cards section below) with Shadow DOM, theme support, and visual editors.

- **History Logging**
  Automatically logs Taken/Skipped/Snoozed events with timestamps.
  - Includes a 7-day adherence sensor per medication.
  - Optional history card shows recent events.
  - A statistics sensor exposes Daily/Weekly/Monthly/Yearly taken, skipped, and missed.

- **Drug Interaction Warnings**
  Automatically checks for interaction risks between configured medications using OpenFDA data.

- **Automation-Friendly**
  Expose medication states as entities for use in automations (e.g., flash lights every 5 minutes until a dose is marked Taken). HA events fire on state changes for automation triggers.

---

## **Cards**

| Card | Description |
|------|-------------|
| `medication-card` | Main medication tracker with action buttons |
| `medication-daily-card` | Today's doses: taken, upcoming, and missed |
| `medication-history-card` | Adherence percentage and recent event history |
| `medication-summary-card` | Daily/weekly/monthly/yearly stats table |
| `medication-planner-card` | 7-day adherence planner grid |
| `medication-interactions-card` | Drug interaction warnings (NEW in v0.2.0) |

All cards support Shadow DOM isolation, HA theme variables, responsive layouts, ARIA accessibility labels, keyboard navigation, and visual card editors.

---

## **Why This Project?**
While there are great blueprints for medication reminders and cloud-based integrations (like Medisafe), there was no **all-in-one, local-only solution** with:
- Per-medication entities
- A UI card for managing medications
- Built-in snooze and logging
- Full automation hooks

This project fills that gap.

---

## **Getting Started**
1. **Install the Integration**
   - Via HACS (recommended on HAOS):
     - Install HACS if not already installed.
     - In HACS → Integrations, open the menu (⋮) → Custom repositories → add `https://github.com/ericrosenberg1/ha-medication-manager` with category `Integration`.
     - Find "Medication Reminder" in HACS and Install. Restart Home Assistant.
   - Manual:
     - Copy `custom_components/medication_reminder` into `/config/custom_components/`.
     - Restart Home Assistant.
   - Configure:
     - Go to **Settings → Devices & Services → Add Integration → Medication Reminder**.
     - Add your medications (name, dose, times per day). Each medication is a separate config entry.
     - To edit later, open the integration entry and click Options.
     - Optional:
       - `notify_services` (comma-separated), e.g. `notify.mobile_app_my_phone, notify.family` for mobile actionable notifications.
       - `nag_interval_minutes` and `nag_max` to enable repeated reminders.
       - Refill tracking: `refill_total`, `refill_threshold`, and `dose_units_per_intake`.

2. **Install the Lovelace Cards**
   - Note: When installing this integration via HACS, the Lovelace cards in this repository are not installed automatically. Copy the files manually (or install the cards from their own repos if split in the future).
   - Copy each card folder from `www/community/` into `/config/www/community/` (create the folders if needed).
   - Add a Lovelace Resource for each card: **Settings → Dashboards → Resources → + Add Resource**
     - Resource type: `JavaScript Module`
   - Card resources:
     - `/local/community/medication-card/medication-card.js`
     - `/local/community/medication-daily-card/medication-daily-card.js`
     - `/local/community/medication-history-card/medication-history-card.js`
     - `/local/community/medication-summary-card/medication-summary-card.js`
     - `/local/community/medication-planner-card/medication-planner-card.js`
     - `/local/community/medication-interactions-card/medication-interactions-card.js`
   - Example card configurations:
     ```yaml
     type: custom:medication-card
     entities:
       - sensor.medication_aspirin
       - sensor.medication_vitamin_d
     ```
     ```yaml
     type: custom:medication-daily-card
     entities:
       - sensor.medication_aspirin
       - sensor.medication_vitamin_d
     ```
     ```yaml
     type: custom:medication-history-card
     entities:
       - sensor.medication_aspirin_adherence
       - sensor.medication_vitamin_d_adherence
     max_events: 10
     ```
     ```yaml
     type: custom:medication-summary-card
     entities:
       - sensor.medication_aspirin
       - sensor.medication_vitamin_d
     ```
     ```yaml
     type: custom:medication-planner-card
     entities:
       - sensor.medication_aspirin
     ```
     ```yaml
     type: custom:medication-interactions-card
     ```

3. **Automate**
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
- Wikidata/Wikipedia: images and general information (community-maintained)

Important: Always follow your doctor's instructions. Any auto-suggested info is informational only and may be incomplete or out of date. This integration is local-first and does not call external APIs by default.

If desired, a future optional provider can fetch and cache public info to prefill: name, common strengths, forms, links to reputable sources, and images via Wikimedia Commons. Opt-in only.

---

## **Roadmap**
- [ ] **Voice Assistant Support** (Alexa/Google: "Mark my medication as taken.")
- [ ] **History Dashboard** (View dose history in Lovelace)
- [ ] **Refill Reminders** (Optional supply tracking)
- [ ] **Weekly Reports** (Adherence summary)
- [ ] **Cloud-sync option** (Optional integration with services like Medisafe)

---

## **Contributing**
We welcome contributions! Here's how you can help:
1. **Report Bugs & Request Features**
   Open an issue here: https://github.com/ericrosenberg1/ha-medication-manager/issues

2. **Submit Code**
   - Fork the repo.
   - Create a feature branch: `git checkout -b feature/my-feature`.
   - Commit your changes: `git commit -m "Add new feature"`.
   - Push to your fork and open a pull request.

3. **Design Feedback**
   Help improve the Lovelace card UI/UX by submitting mockups or ideas.

4. **Testing & Feedback**
   Join as an **alpha/beta tester** and share feedback on performance and features.

Author: [Eric Rosenberg](https://ericrosenberg.com) • [eric.money](https://eric.money)

For consulting, support, or sponsorships, connect via either site.

---

## **Versioning**
We follow a **3-stage release model**:
- **Alpha:** Actively developed, breaking changes possible.
- **Beta:** Feature-complete for testing by supporters.
- **Stable:** Polished, production-ready releases.

---

## **Changelog**

### v0.2.0 (Beta)
- Added FDA/NIH medication database lookup (RxTerms + OpenFDA)
- Added drug interaction warnings sensor and card
- Rebuilt all cards with Shadow DOM and HA theme support
- Added card editors for visual configuration
- Fixed reminder persistence across HA restarts
- Added daily midnight reset to Pending state
- Added HA events for automation triggers
- Performance: debounced history saves, cached computations
- Security: input validation, entity ID checks, proper error handling

### v0.11.0
- Reminder scheduling reliability fixes
- Snooze state persistence
- Daily auto-reset
- Timezone fixes in cards

### v0.10.0
- Initial release
- Guard domain service registration and mobile action listener to register once
- Cleanup services/listener automatically when the last entry is removed
- Generate stable entity IDs using Home Assistant helpers
- Sanitize notification services in options to prevent invalid service names
- Expose `snooze_minutes` and configured `notify_services` as entity attributes
- Add `mark_pending` service to reset a medication to Pending
- Add nagging (repeat reminders) with configurable interval and max repeats
- Add refill tracking with threshold alert and services to set/add/acknowledge
- Add Dismiss action (treated as Skip) in notifications and card
- Add Medication Stats sensor (daily/weekly/monthly/yearly counts)
- Add three Lovelace cards: Daily, Planner (7 days), Summary table

---

## **License**
This project is licensed under the [MIT License](LICENSE).
