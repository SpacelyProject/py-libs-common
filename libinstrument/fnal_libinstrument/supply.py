import time

# Supply


class Supply():


    def __init__(self, logger, io):

        self.log = logger
        self.io = io

        self.id = self.get_id()

        #Defaults 
        self.voltage_limits = [0,5]
        
        self.valid_channels = ["P6V","P25V","N25V"]

    def get_id(self):
        #*IDN? is a common command that should work across all models.
        return self.query("*IDN?")

    def query(self, query_text):
        return self.io.query(query_text)

    def write(self, write_text):
        return self.io.write(write_text)

    
    #Set voltage limits in software that will be respected by this command.
    def set_voltage_limits(limit_tuple):
        assert(len(limit_tuple)==2)
        self.voltage_limits = limit_tuple
    
    def get_voltage(self, channel):

        if self.channel_lint_check(channel) == -1:
            return

        response = self.io.query(f"APPLY? {channel}")

        (voltage, current) = response.replace("\"","").split(",")

        return float(voltage)


    def set_voltage(self, channel, voltage, current_limit=None):
        if self.channel_lint_check(channel) == -1:
            self.log.error(f"Attempted to set voltage on non-existent channel {channel} of instr {self.id}")
            return -1
        
        if voltage > self.voltage_limits[1] or voltage < self.voltage_limits[0]:
            self.log.error(f"Attempted to set voltage = {voltage} on instr {self.id}. Voltage limits are {self.voltage_limits[0]} V to {self.voltage_limits[1]} V. To change this, use instr.set_voltage_limits([min,max])")
            return -1
        
        if current_limit == None:
            current = "DEF"
        else:
            current = str(current_limit)

        self.io.write(f"APPLY {channel}, {voltage}, {current}")


    def set_output_on(self):
        self.io.write("OUTPUT ON")

    def set_output_off(self):
        self.io.write("OUTPUT OFF")

    def get_voltage(self, channel):
        if self.channel_lint_check(channel) == -1:
            return None
        else:
            self.io.write(f"INST:SELECT {channel}")
            response = self.io.query(f"MEAS:VOLT?").replace("@","").strip()
            time.sleep(0.1)
            return float(response)

    def get_current(self, channel):
        if self.channel_lint_check(channel) == -1:
            return None
        else:
            self.io.write(f"INST:SELECT {channel}")
            response = self.io.query(f"MEAS:CURR?").replace("@","").strip()
            time.sleep(0.1)
            return float(response)

    #Returns channel settings as (voltage, current)
    def _get_channel_settings(self,channel):
        if self.channel_lint_check(channel) == -1:
            return

        response = self.io.query(f"APPLY? {channel}")

        return [float(x) for x in response.replace("\"","").split(",")]

    def channel_lint_check(self, channel):
        if channel not in self.valid_channels:
            self.log.error(f"Channel {channel} is not valid for instrument {self.id}")
            return -1

        return 0
