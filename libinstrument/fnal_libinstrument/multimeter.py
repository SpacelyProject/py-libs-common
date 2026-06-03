



class Multimeter():

    def __init__(self, logger, io):

        self.log = logger
        self.io = io

        #self.io.set_timeout(2000)

    def report(self):
        print("Multimeter Info: ", self.io.query("*IDN?").strip())
        print("Function: ", self.io.query("FUNC?").strip())
        print("Range: ", self.io.query("VOLT:RANG?").strip())
        print("NPLC: ", self.io.query("VOLT:NPLC?").strip())

    def get_error(self):
        """Get the latest error code from the instrument."""
        return self.io.query("SYST:ERR?").strip()

    def shell(self):
        """Shell for interacting with the multimeter, with error reporting."""
        while True:
            user_input = input("cmd>")

            if user_input == "exit":
                break
            else:
                try:
                    if "?" in user_input:
                        print(self.io.query(user_input))
                    else:
                        self.io.write(user_input)

                except Exception as e:
                    print(e)
                    print(self.get_error())

    #
    # Measurement configuration
    #

    def set_function(self, function):
        """
        Valid functions:
            VOLT:DC
            VOLT:AC
            CURR:DC
            CURR:AC
            RES
            FRES
            FREQ
            PER
            CONT
            DIOD
        """

        valid_functions = [
            "VOLT:DC",
            "VOLT:AC",
            "CURR:DC",
            "CURR:AC",
            "RES",
            "FRES",
            "FREQ",
            "PER",
            "CONT",
            "DIOD"
        ]

        if function not in valid_functions:
            self.log.error(f"{function} is not a valid measurement function.")
            return

        self.io.write(f'FUNC "{function}"')

    def get_function(self):
        return self.io.query("FUNC?").strip()

    def set_range(self, value):
        """
        Set measurement range for the currently selected function.
        Example:
            meter.set_function("VOLT:DC")
            meter.set_range(10)
        """
        func = self.get_function().replace('"', '')

        if func.startswith("VOLT"):
            self.io.write(f"VOLT:RANG {value}")

        elif func.startswith("CURR"):
            self.io.write(f"CURR:RANG {value}")

        elif func in ["RES", "FRES"]:
            self.io.write(f"{func}:RANG {value}")

        else:
            self.log.warning(
                f"Range setting not implemented for function {func}"
            )

    def set_auto_range(self, enable=True):

        state = "ON" if enable else "OFF"

        func = self.get_function().replace('"', '')

        if func.startswith("VOLT"):
            self.io.write(f"VOLT:RANG:AUTO {state}")

        elif func.startswith("CURR"):
            self.io.write(f"CURR:RANG:AUTO {state}")

        elif func in ["RES", "FRES"]:
            self.io.write(f"{func}:RANG:AUTO {state}")

        else:
            self.log.warning(
                f"Autorange setting not implemented for function {func}"
            )

    def set_nplc(self, nplc):
        """
        Set integration time in power line cycles.

        Typical values:
            0.02
            0.2
            1
            10
            100
        """

        func = self.get_function().replace('"', '')

        if func.startswith("VOLT"):
            self.io.write(f"VOLT:NPLC {nplc}")

        elif func.startswith("CURR"):
            self.io.write(f"CURR:NPLC {nplc}")

        elif func in ["RES", "FRES"]:
            self.io.write(f"{func}:NPLC {nplc}")

        else:
            self.log.warning(
                f"NPLC setting not implemented for function {func}"
            )

    #
    # Triggering and acquisition
    #

    def set_trigger_source(self, source):
        """
        Valid sources:
            IMM
            BUS
            EXT
        """

        valid_sources = ["IMM", "BUS", "EXT"]

        if source not in valid_sources:
            self.log.error(
                f"{source} is not a valid trigger source."
            )
            return

        self.io.write(f"TRIG:SOUR {source}")

    def trigger(self):
        """Generate a bus trigger."""
        self.io.write("*TRG")

    def get_data(self):
        """
        Initiates a measurement and returns a float.
        """

        return float(self.io.query("READ?"))

    def fetch(self):
        """
        Returns the latest completed reading without
        initiating a new measurement.
        """

        return float(self.io.query("FETC?"))

    #
    # Convenience measurement methods
    #

    def measure_dc_voltage(self):
        return float(self.io.query("MEAS:VOLT:DC?"))

    def measure_ac_voltage(self):
        return float(self.io.query("MEAS:VOLT:AC?"))

    def measure_dc_current(self):
        return float(self.io.query("MEAS:CURR:DC?"))

    def measure_ac_current(self):
        return float(self.io.query("MEAS:CURR:AC?"))

    def measure_resistance(self):
        return float(self.io.query("MEAS:RES?"))

    def measure_four_wire_resistance(self):
        return float(self.io.query("MEAS:FRES?"))

    def measure_frequency(self):
        return float(self.io.query("MEAS:FREQ?"))

    #
    # Utility
    #

    def reset(self):
        self.io.write("*RST")

    def clear_status(self):
        self.io.write("*CLS")

    def beep(self):
        self.io.write("SYST:BEEP")