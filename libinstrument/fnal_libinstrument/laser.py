# TSL-570 Laser Control Software







class Laser():
    
    
    def __init__(self, logger, io):

        self.log = logger
        self.io = io
        #Default -10 dBm = 100 uW 
        #This is below power limits for a class 1 laser.
        self.power_limit_dBm = -10 
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
                    
    def set_power_limit_dBm(self,power_limit_dBm): 
        self.power_limit_dBm = power_limit_dBm
                    
    def set_wavelength_nm(self, wavelength_nm):
        self.io.write(f":WAV {wavelength_nm}NM")
        
    def set_power_level_dBm(self,power_level_dBm):
        if power_level_dBm > self.power_limit_dBm:
            self.log.warning(f"WARNING: Attempted to set illegal laser power {power_level_dBm} > {self.power_limit_dBm}. Please reconsider your life choices, and if you really need that much power, increase the limit with Laser.set_power_limit_dBm()")
            return
            
        self.io.write(f":POW:LEV {power_level_dBm}DBM")
    
    def set_output_on(self):
        self.io.write(":POW:STAT 1")

    def set_output_off(self):
        self.io.write(":POW:STAT 0")
    