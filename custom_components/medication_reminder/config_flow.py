"""Config flow for Medication Reminder integration."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries

from .const import DOMAIN, ATTR_NAME, ATTR_DOSE, ATTR_TIMES


def _slugify(name: str) -> str:
    base = "".join(ch if ch.isalnum() else "_" for ch in name.lower())
    return "_".join([p for p in base.split("_") if p])


def _normalize_times(value: str) -> list[str]:
    items = [v.strip() for v in value.split(",")]
    out: list[str] = []
    for t in items:
        if not t:
            continue
        try:
            hh, mm = t.split(":")
            hhi = int(hh)
            mmi = int(mm)
        except Exception as err:
            raise vol.Invalid(f"Invalid time format: {t}") from err
        if not (0 <= hhi <= 23 and 0 <= mmi <= 59):
            raise vol.Invalid(f"Invalid time value: {t}")
        out.append(f"{hhi:02d}:{mmi:02d}")
    # de-duplicate
    seen = set()
    unique: list[str] = []
    for t in out:
        if t not in seen:
            seen.add(t)
            unique.append(t)
    return unique


class MedicationReminderConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                name = user_input.get(ATTR_NAME, "").strip()
                dose = user_input.get(ATTR_DOSE, "").strip()
                times_raw = user_input.get(ATTR_TIMES, "").strip()
                times = _normalize_times(times_raw)

                if not name:
                    errors[ATTR_NAME] = "required"
                elif not times:
                    errors[ATTR_TIMES] = "required"
                else:
                    slug = _slugify(name)
                    await self.async_set_unique_id(f"med_{slug}")
                    self._abort_if_unique_id_configured()
                    title = name
                    data = {ATTR_NAME: name, ATTR_DOSE: dose, ATTR_TIMES: times}
                    return self.async_create_entry(title=title, data=data)
            except vol.Invalid as err:
                errors["base"] = "invalid_times"

        schema = vol.Schema(
            {
                vol.Required(ATTR_NAME): str,
                vol.Optional(ATTR_DOSE, default=""): str,
                vol.Required(
                    ATTR_TIMES,
                    description={
                        "suggested_value": "08:00, 20:00",
                    },
                ): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)


class MedicationReminderOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                dose = (user_input.get(ATTR_DOSE) or "").strip()
                times_raw = (user_input.get(ATTR_TIMES) or "")
                times = _normalize_times(times_raw)
                snooze = int(user_input.get("snooze_minutes", 5))
                if snooze < 1:
                    snooze = 1
                if snooze > 1440:
                    snooze = 1440
                notify_services = (user_input.get("notify_services") or "").strip()
                return self.async_create_entry(
                    title="",
                    data={
                        ATTR_DOSE: dose,
                        ATTR_TIMES: times,
                        "snooze_minutes": snooze,
                        "notify_services": notify_services,
                    },
                )
            except vol.Invalid:
                errors["base"] = "invalid_times"

        current = {
            ATTR_DOSE: self.config_entry.options.get(ATTR_DOSE, self.config_entry.data.get(ATTR_DOSE, "")),
            ATTR_TIMES: ", ".join(self.config_entry.options.get(ATTR_TIMES, self.config_entry.data.get(ATTR_TIMES, [])) or []),
            "snooze_minutes": self.config_entry.options.get("snooze_minutes", 5),
            "notify_services": self.config_entry.options.get("notify_services", ""),
        }

        schema = vol.Schema(
            {
                vol.Optional(ATTR_DOSE, default=current[ATTR_DOSE]): str,
                vol.Optional(ATTR_TIMES, default=current[ATTR_TIMES]): str,
                vol.Optional("snooze_minutes", default=current["snooze_minutes"]): int,
                vol.Optional(
                    "notify_services",
                    default=current["notify_services"],
                    description={
                        "suggested_value": "notify.mobile_app_my_phone, notify.family",
                    },
                ): str,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)


async def async_get_options_flow(config_entry: config_entries.ConfigEntry):
    return MedicationReminderOptionsFlow(config_entry)
