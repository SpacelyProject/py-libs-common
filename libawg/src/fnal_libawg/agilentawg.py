from __future__ import annotations
from fnal_libprologix import PrologixDevice
from fnal_log_wizard import LOG_DEBUG
import time
import re

class AgilentError(RuntimeError):
    __error_regex: re.Pattern = None

    def __init__(self, remote_message: str, code: int, cause: str | None = None):
        super().__init__(f"Error {code}: {remote_message}")

        self.remote_message = remote_message  # remote instrument's error message
        self.remote_code = code  # remote instrument's error code
        self.remote_cmd = cause  # what command caused the error

    def is_error(self) -> bool:
        return self.remote_code != 0

    def __str__(self) -> str:
        error = f"error #{self.remote_code}: {self.remote_message}"
        if self.remote_cmd is not None:
            error = f"{error} due to \"{self.remote_cmd}\" command"

        return error

    @classmethod
    def from_error_string(cls, raw_msg: str) -> AgilentError:
        if cls.__error_regex is None:
            cls.__error_regex = re.compile('([-+]\d+),"(.+)"')

        matches = cls.__error_regex.match(raw_msg)
        if matches is None:
            raise ValueError(f"Error string >>{raw_msg}<< is not a valid Agilent error string")

        groups = matches.groups()
        return cls(groups[1], int(groups[0]))


class AgilentAWG(PrologixDevice):
    def __init__(self, logger, ip_address, device_addr, default_data_timeout = 2):
        super().__init__(logger, ip_address, device_addr, default_data_timeout)

        self.limit = None
        self.log = logger

    def connect(self, max_attempts = 10, tcp_timeout = 0.5) -> bool:
        """Connects to Agilent AWG"""
        connected = super().connect(max_attempts, tcp_timeout)
        if not connected:
            return False

        self.display_text("Configuring...")
        # Read all errors stroed in the instrument
        self.log.blocking("Reading remote instrument errors", LOG_DEBUG)
        errors = self.read_all_errors()
        errors_count = len(errors)
        self.log.block_res(level=LOG_DEBUG)

        if errors_count == 0:
            self.log.debug("No errors stored")
        else:
            self.log.notice(f"Agilent AWG has {errors_count} error(s) stored "
                             "from previous commands. They will be listed below.")
            for error in errors:
                self.log.error(f"Agilent AWG {str(error)}")

        self.restart()
        self.display_text("-- Remote Operation --")

        return connected


    def read_first_error(self) -> AgilentError | None:
        """Reads the first error in FIFO queue of the instrument

           * This method will read only the first error as it was generated, as
             the instrument uses a First-In-First-Out queue for errors. The error
             queue will NOT be cleared when the instrument is restarted.
           * Reading an error from the queue WILL REMOVE the error from the
             instrument's queue.
           * To clear the error queue you need to call clear_errors().
        """
        error_str = super().query("SYSTem:ERRor?", True) # this uses super() to avoid loop
        error = AgilentError.from_error_string(error_str)

        return error if error.is_error() else None

    def read_all_errors(self) -> list[AgilentError]:
        """Reads the instrument's errors queue and clear it"""
        errors = []
        while True:
            error = self.read_first_error()
            if error is None:
                break
            errors.append(error)

        return errors


    def clear_errors(self) -> None:
        """Clears instrument's error queue.

           This method can safely be used blindly, i.e. you can call it even
           if there may not be any errors in the queue.
        """
        self.send_line("*CLS")

    def query_awg(self, cmd_txt: str, trim: bool = False) -> str:
        """Queries the instrument and handles erorrs

           This method works like query() but asks the instrument
           for errors after each query. If an error occurs this method
           will raise an AgilentError, so that errors will not go
           unnoticed.

           Since the Agilent uses FIFO for errors, you need to be sure
           error queue is empty before using this method. If it's not,
           this method will report an error even if the command executed
           last didn't fail.
        """
        output = self.query(cmd_txt, trim)
        error = self.read_first_error()
        if error is None:
            return output

        error.remote_cmd = cmd_txt
        self.log.debug(f"Query \"{cmd_txt}\" generated remote error #{error.remote_code}: "
                       f"{error.remote_message} - raising error")
        raise error

    def send_line_awg(self, cmd_txt: str) -> str:
        """Sends a line command to the instrument and handles errors

           This method works like send_line() but asks the instrument
           for errors after each command. If an error occurs this method
           will raise an AgilentError, so that errors will not go
           unnoticed.

           Since the Agilent uses FIFO for errors, you need to be sure
           error queue is empty before using this method. If it's not,
           this method will report an error even if the command executed
           last didn't fail.
        """

        output = self.send_line(cmd_txt)
        error = self.read_first_error()
        if error is None:
            return output

        error.remote_cmd = cmd_txt
        self.log.debug(f"Line command \"{cmd_txt}\" generated remote error #{error.remote_code}: "
                       f"{error.remote_message} - raising error")
        raise error

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
        self.send_line_awg(f"OUTP {state}")
        self.log.debug(f"AWG output set to {state}")
        time.sleep(0.5)

    def display_text(self, text: bool) -> None:
        """Displays a text on the front panel of the instrument"""
        if len(text) > 41:
            raise ValueError("The display text cannot be longer than 41 characters")
        self.send_line_awg(f"DISP:TEXT \"{text}\"")

    def restart(self) -> None:
        """Restarts the instrument, restoring volatile memory to defaults"""
        self.log.blocking("Restarting AWG to restore volatile memory")
        self.send_line_awg("*RST")
        self.log.block_res(True)
        time.sleep(1)