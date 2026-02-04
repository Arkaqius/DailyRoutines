"""
DailyRoutines AppDaemon Application

This application automates goodnight and wake-up routines for a smart home,
triggering Home Assistant services and scheduling preparation tasks.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import appdaemon.plugins.hass.hassapi as hass

from routines_actions import DailyRoutinesActionsMixin

FIVE_MINUTES_SECONDS = 5 * 60


class DailyRoutines(DailyRoutinesActionsMixin, hass.Hass):
    """
    Initialize configuration, listeners, and shared utilities.
    """

    def initialize(self) -> None:
        """
        Initialize listeners and configuration.

        Required args:
        - turn_off_lights_scene (supports legacy alias turn_off_ligts_scene)
        - ww_activate
        - awake_state
        - next_awake_time
        - prep_offset_minutes

        Optional args:
        - goodmorning_lights_scene
        """
        self.log("Initializing DailyRoutines.", level="INFO")
        self.turn_off_lights_scene = self._get_required_arg(
            "turn_off_lights_scene", aliases=["turn_off_ligts_scene"]
        )
        self.warm_water_entity = self._get_required_arg("ww_activate")
        self.awake_state_entity = self._get_required_arg("awake_state")
        self.next_awake_entity = self._get_required_arg("next_awake_time")
        self.prep_offset_minutes = self._get_int_arg("prep_offset_minutes")
        self.goodmorning_lights_scene = self.args.get("goodmorning_lights_scene")

        self._local_tz = datetime.now().astimezone().tzinfo
        self._prep_timer_handle: Optional[str] = None
        self._prep_end_timer_handle: Optional[str] = None

        self.listen_state(
            self.goodnight_triggered, self.awake_state_entity, new="sleep"
        )
        self.listen_state(self.awake_triggered, self.awake_state_entity, new="awake")
        self.listen_state(self.next_awake_set, self.next_awake_entity)
        self.log(
            "DailyRoutines initialized.",
            level="INFO",
        )

    def _get_required_arg(self, key: str, aliases: Optional[list[str]] = None) -> str:
        """
        Fetch a required AppDaemon argument, optionally falling back to aliases.
        """
        value = self.args.get(key)
        if value is None and aliases:
            for alias in aliases:
                if alias in self.args:
                    value = self.args.get(alias)
                    self.log(
                        f"Using legacy arg '{alias}' for '{key}'. Please rename it.",
                        level="WARNING",
                    )
                    break
        if value is None:
            self.log(f"Missing required app argument '{key}'.", level="ERROR")
            raise ValueError(f"Missing required app argument '{key}'.")
        return value

    def _get_int_arg(self, key: str, default: Optional[int] = None) -> int:
        """
        Fetch an integer argument from AppDaemon config.
        """
        value = self.args.get(key, default)
        if value is None:
            self.log(f"Missing required app argument '{key}'.", level="ERROR")
            raise ValueError(f"Missing required app argument '{key}'.")
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            self.log(
                f"Invalid integer for app argument '{key}': {value}",
                level="ERROR",
            )
            raise ValueError(
                f"Invalid integer for app argument '{key}': {value}"
            ) from exc

    def _parse_next_awake_time(self, value: str) -> datetime:
        """
        Parse next-awake timestamp into a timezone-aware datetime.

        Accepts ISO-8601 with or without timezone. If the timezone is missing,
        the local timezone is assumed.
        """
        raw = value.strip()
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(raw)
        except ValueError:
            parsed = None
            for fmt in (
                "%Y-%m-%d %H:%M:%S%z",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%S",
            ):
                try:
                    parsed = datetime.strptime(raw, fmt)
                    break
                except ValueError:
                    continue
            if parsed is None:
                raise
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=self._local_tz)
        return parsed

    def next_awake_set(
        self, entity: str, attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """
        Handle the event when the next awake time is set.
        Schedule preparations prep_offset_minutes before wake-up time.
        """
        try:
            self.log(f"Next_awake_set [{new}].", level="DEBUG")
            next_awake_time = self._parse_next_awake_time(new)
            prep_time = next_awake_time - timedelta(minutes=self.prep_offset_minutes)

            current_time = datetime.now(timezone.utc).astimezone(next_awake_time.tzinfo)
            self.log(f"current_time [{current_time}].", level="DEBUG")

            if self._prep_timer_handle is not None:
                self.log("Cancelling previously scheduled prep timer.", level="DEBUG")
                self.cancel_timer(self._prep_timer_handle)
                self._prep_timer_handle = None

            if current_time < prep_time:
                seconds_until_prep = int((prep_time - current_time).total_seconds())
                self._prep_timer_handle = self.run_in(
                    self.awake_preparation_tasks, seconds_until_prep
                )
                self.log(
                    f"Scheduled preparation tasks in {seconds_until_prep} seconds."
                )
            elif current_time < next_awake_time:
                if self._prep_end_timer_handle is not None:
                    self.log(
                        "Preparation tasks already running; no immediate restart.",
                        level="DEBUG",
                    )
                    return
                self.log(
                    "Within preparation window; running preparation tasks immediately.",
                    level="DEBUG",
                )
                self.awake_preparation_tasks({})
            else:
                self.log(
                    f"current_time [{current_time}] was after prep_time {prep_time}.",
                    level="DEBUG",
                )
        except ValueError:
            self.log(
                f"Invalid datetime format for next awake time [{new}].",
                level="ERROR",
            )

    def awake_preparation_tasks(self, kwargs: Any) -> None:
        """
        Perform wake-up preparation tasks (e.g., warm water on).
        """
        self.log("Performing wake-up preparation tasks.", level="INFO")
        self._prep_timer_handle = None
        self.turn_warm_water(True)
        if self._prep_end_timer_handle is not None:
            self.log("Cancelling previous prep-end timer.", level="DEBUG")
            self.cancel_timer(self._prep_end_timer_handle)
        self._prep_end_timer_handle = self.run_in(
            self.awake_preparation_tasks_end, FIVE_MINUTES_SECONDS
        )
        self.log(
            f"Scheduled preparation end in {FIVE_MINUTES_SECONDS} seconds.",
            level="DEBUG",
        )

    def awake_preparation_tasks_end(self, _: Any) -> None:
        """
        Finish wake-up preparation tasks (e.g., warm water off).
        """
        self.log("Performing wake-up preparation tasks finishing", level="INFO")
        self.turn_warm_water(False)
        self._prep_end_timer_handle = None

    def goodnight_triggered(
        self, entity: str, attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """
        Handle the event when the goodnight status is triggered.
        """
        self.activate_turn_off_lights_scene()
        # self.close_blinds_and_curtains()
        self.turn_warm_water(False)
        # self.turn_off_fans()
        # self.turn_off_multimedia_devices()

        self.log("Goodnight routine executed successfully.", level="INFO")

    def awake_triggered(
        self, entity: str, attribute: str, old: str, new: str, kwargs: dict
    ) -> None:
        """
        Handle the event when the awake status is triggered.
        """
        self.activate_goodmorning_lights_scene()
        # self.open_blinds_and_curtains()
        self.log("Awake routine executed successfully.", level="INFO")
