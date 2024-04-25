from __future__ import annotations
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


class AgilentAWG():
    
    
    def __init__(self, logger, io):
        #super().__init__(logger, ip_address, device_addr, default_data_timeout)

        self.limit = None
        self.log = logger
        self.io = io

        self.connect()

    def connect(self, max_attempts = 10, tcp_timeout = 0.5) -> bool:
        """Connects to Agilent AWG"""
        connected = self.io.is_connected()
        if not connected:
            self.log.error("Attempted to connect to Agilent AWG() while io is not connected.")
            return False

        self.display_text("Configuring...")
        # Read all errors stroed in the instrument
        self.log.blocking("Reading remote instrument errors", 7)
        errors = self.read_all_errors()
        errors_count = len(errors)
        self.log.block_res(level=7)

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
        error_str = ""
        
        for i in range(10): #Try up to 10 times.
            error_str = self.io.query("SYSTem:ERRor?").strip() # this directly calls io.query to avoid loop
            if error_str == "":
                self.log.warning("When queried for errors, AWG returned null string, trying again.")
                time.sleep(0.1)
            else:
                break
                
        if i > 9:
            self.log.critical("Communication failure with AWG, returning -1.")
            return -1
        
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
        self.io.write("*CLS")

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
        output = self.io.query(cmd_txt)
        if trim:
            output = output.strip()
        error = self.read_first_error()
        if error is None:
            return output

        error.remote_cmd = cmd_txt
        self.log.debug(f"Query \"{cmd_txt}\" generated remote error #{error.remote_code}: "
                       f"{error.remote_message} - raising error")
        raise error

    def send_line_awg(self, cmd_txt: str, check_for_errors=False) -> str:
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
        output = self.io.write(cmd_txt)
        self.log.debug(f"AWG cmd:{cmd_txt}")
        
        if check_for_errors:
            error = self.read_first_error()
            if error is None:
                return output

            error.remote_cmd = cmd_txt
            self.log.debug(f"Line command \"{cmd_txt}\" generated remote error #{error.remote_code}: "
                           f"{error.remote_message} - raising error")
            raise error
        else:
            return output

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
            self.log.critical("Refusing to execute AWG \"{cmd}\" - {voltage_volts}V is over limit of {self.limit}V")
            return False

        self.io.write(cmd)
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
        
        
    def query(self, query_text):
        return self.io.query(query_text)

    def write(self, write_text):
        return self.io.write(write_text)
        
        
        
        
    def config_AWG_as_DC(self, val_mV: float) -> None:
        #if USE_ARDUINO and EMULATE_ASIC:
        #   emucomp = str(val_mV*0.001)
        #    sg.log.debug(f"EMULATE_ASCI compinp={emucomp}")
        #    command_ng(sg.log, sg.port,"compinp:"+str(val_mV*0.001))
        #else:
        
        awgdc = str(round(val_mV/1000,4))
        self.send_line_awg("FUNC DC")
        self.set_offset(val_mV)
        self.set_output(True)

    def set_Vin_mV(self, val_mV: float) -> None:
        #if USE_ARDUINO and EMULATE_ASIC:
        #    command_ng(sg.log, sg.port,"compinp:"+str(val_mV*0.001))
        #else:
            
        self.set_offset(val_mV)
        self.log.notice(f"Set AWG DC to: {val_mV} mV")


    def set_pulse_mag(self, val_mV: float) -> None:
        pulse = round(val_mV / 1000,6)
        try:
            self.send_line_awg("VOLT "+str(pulse))
            self.log.notice(f"Set pulse mag to: {val_mV} mV")
        except fnal_libawg.agilentawg.AgilentError as e:
            print(e)
            self.log.critical(f"Failed to set pulse magnitude to  {val_mV} mV")


    def config_AWG_as_Pulse(self, pulse_mag_mV, pulse_width_us=0.28, pulse_period_us=9,trig_delay_ns=0):
        self.set_output(False)
        self.send_line_awg("FUNC PULS", check_for_errors=False)

        #Pulse will be from (2.5 - pulse) to 2.5
        pulse = round(pulse_mag_mV / 1000,6)
        offset = round(2.5 - pulse_mag_mV/2000,6)
        
        w = round(pulse_width_us*1e-6,10)
        
        pd = round(pulse_period_us*1e-6,10)
        
        self.send_line_awg("PULSE:WIDTH 50e-9") #Start out with pw of just 50 ns (very short)
        self.send_line_awg("PULSE:PERIOD "+str(pd)) #Update period first and then pulsewidth to avoid errors. 
        self.send_line_awg("PULSE:WIDTH "+str(w)) 
        
        self.send_line_awg("VOLT:OFFS "+str(offset))
        self.send_line_awg("VOLT "+str(pulse))

        #Bursts will be triggered by Trig In (w/ a positive slope)
        #Note: Trig In will be connected to PreSamp
       
        self.send_line_awg("BURS:MODE TRIG")
        self.send_line_awg("TRIG:SOUR EXT")
        self.send_line_awg("TRIG:SLOP POS")

        self.send_line_awg(f"TRIG:DELAY {trig_delay_ns}")

        #Each Trig In will result in 1 burst
        self.send_line_awg("BURS:NCYC 1")

        #Enable bursts
        self.send_line_awg("BURS:STAT ON")

        self.set_output(True)
