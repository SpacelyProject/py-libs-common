from __future__ import annotations
from fnal_libprologix import PrologixDevice
import time

class AgilentAWG(PrologixDevice):
    def __init__(self, logger, ip_address, device_addr, default_data_timeout = 2):
        super().__init__(logger, ip_address, device_addr, default_data_timeout)

        self.limit = None
        
    def set_limit(self, voltage_volts: float) -> None:
        self.limit = voltage_volts
        self.log.debug(f"AWG voltage limit set to +/-{voltage_volts}V")

    def set_amplitude(self, voltage_mv: float) -> bool:
        ret = self._send_voltage_cmd("VOLT", voltage_mv)
        self.log.debug(f"AWG set to amplitude {voltage_mv}mV")
        return ret

    def set_offset(self, voltage_mv: float) -> bool:
        ret = self._send_voltage_cmd("VOLT:OFFS", voltage_mv)
        self.log.debug(f"AWG set to offset {voltage_mv}mV")
        return ret

    def _send_voltage_cmd(self, cmd: str, voltage_mv: float) -> bool:
        voltage_volts = round(voltage_mv/1000, 4)
        cmd = f"{cmd} {voltage_volts}"

        if self.limit is not None and abs(voltage_volts) > self.limit:
            log.critical("Refusing to execute AWG \"{cmd}\" - {voltage_volts}V is over limit of {self.limit}V")
            return False

        self.send_line(cmd)
        time.sleep(0.1)
        return True

    def set_output(self, enabled: bool) -> None:
        state = 'ON' if enabled else 'OFF'
        self.send_line(f"OUTP {state}")
        self.log.debug(f"AWG output set to {state}")
        time.sleep(0.5)
