# ThorLabs PM100 Optical Power Meter







class OpticalPowerMeter():
    
    
    def __init__(self, logger, io):

        self.log = logger
        self.io = io
        
        self.io.set_timeout(2000)
        
        
    def report(self):
        print("Power Meter Info: ",self.io.query("*IDN?").strip())
        print("Calibration Date: ",self.io.query("CAL:STR?").strip())
        sensor_info = self.io.query("SYST:SENS:IDN?").strip()
        print("Sensor Info: ", sensor_info)
        print("Configured to Measure: ",self.io.query("CONF?").strip())
        
        if "no sensor" in sensor_info:
            wavelength = "(NO SENSOR)"
        else:
            wavelength = self.io.query("CORR:WAV?").strip()
            
        print("Configured for Wavelength: ",wavelength)
        
        
    def get_error(self):
        """Get the latest error code from the instrument."""
        return self.io.query("SYST:ERR?").strip()
      
    def shell(self):
        """Shell for interacting with the power meter, with error reporting."""
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
                    
                    
                    
    def set_wavelength_nm(self, wavelength_nm):
        self.io.write(f"CORR:WAV {wavelength_nm}")
        
    def set_power_unit(self, unit):
        if unit != "DBM" and unit != "W":
            self.log.error(f"{unit} is not a valid power unit! (W or DBM)")
            return
            
        self.io.write(f"POW:UNIT {unit}")
        #Necessary for the device to act on the new unit setting.
        self.io.write("CONF:POW")
        
    def get_data(self):
        return float(self.io.query("READ?"))