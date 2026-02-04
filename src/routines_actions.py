"""Actions invoked by callbacks for Home Assistant services."""


class DailyRoutinesActionsMixin:
    """
    Home Assistant action helpers for daily routines.
    """

    def activate_turn_off_lights_scene(self) -> None:
        """
        Activate the configured lights-off scene in Home Assistant.
        """
        self.turn_on(self.turn_off_lights_scene)

    def activate_goodmorning_lights_scene(self) -> None:
        """
        Activate the configured good-morning scene in Home Assistant.
        """
        if not self.goodmorning_lights_scene:
            self.log("No goodmorning_lights_scene configured.", level="WARNING")
            return
        self.turn_on(self.goodmorning_lights_scene)

    def close_blinds_and_curtains(self) -> None:
        """
        Close all automated blinds and curtains.
        """
        raise NotImplementedError

    def turn_warm_water(self, state: bool) -> None:
        """
        Turn warm water on or off.
        """
        if state:
            self.turn_on(self.warm_water_entity)
        else:
            self.turn_off(self.warm_water_entity)

    def turn_off_fans(self) -> None:
        """
        Turn off all fans.
        """
        raise NotImplementedError

    def turn_off_multimedia_devices(self) -> None:
        """
        Turn off all multimedia devices.
        """
        raise NotImplementedError

    def await_ha_confirmation(self) -> bool:
        """
        Await a confirmation from Home Assistant.

        Returns:
        - bool: True if confirmation received, False otherwise.
        """
        raise NotImplementedError

    def check_lights_and_ww_status(self) -> bool:
        """
        Check the status of lights and warm water.

        Returns:
        - bool: True if statuses are correct, False otherwise.
        """
        raise NotImplementedError
