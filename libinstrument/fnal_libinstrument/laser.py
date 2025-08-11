# TSL-570 Laser Control Software







class Laser():
    
    
    def __init__(self, logger, io):

        self.log = logger
        self.io = io
        
        self.io.set_timeout(1000)
        
        
    def report(self):
        print("Laser Info: ",self.io.query("*IDN?").strip())
        print("Firmware Version: ",self.io.query(":SYST:VERSION?").strip())
        print("Product Code: ",self.io.query(":SYST:CODE?").strip())
        
        
    def get_error(self):
        """Get the latest error code from the instrument."""
        return self.io.query(":SYST:ERR?").strip()
      
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
        self.io.write(f":WAV {wavelength_nm}NM")
        
    def set_power_level_dBm(self,power_level_dBm):
        self.io.write(f":POW:LEV {power_level_dBm}DBM")
    
    def set_output_on(self):
        self.io.write(":POW:STAT 1")

    def set_output_off(self):
        self.io.write(":POW:STAT 0")
    