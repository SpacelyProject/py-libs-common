# GENERIC NIDCPOWER #

# Generic comands for interfacing with NI-DCPower Compatible devices.


# NOTE: This software requires a relatively modern version of the NI-DCPower
# driver. To update, open the "NI Package Manager" software, go to Browse
# Products, find NI-DCPower and install a version at least as new as 2022 Q4.
# You may have to update NI Package Manager first.

# GENERAL USAGE NOTES:
# - PSU channels are 0,1,2 while SMU channels are 0,1,2,3

import nidcpower

#Wrapper class just to hold the instrument and channel info for a given port. 
class Source_Port:
    
    def __init__(self, instrument, channel, default_current_limit=0.001, default_voltage_limit=0.1):
        self.instrument = instrument;
        self.channel = channel;
        self.default_current_limit=default_current_limit;
        self.default_voltage_limit=default_voltage_limit;
        self.current_limit = default_current_limit;
        self.voltage_limit = default_voltage_limit;
        self.nominal_voltage = None;
        self.nominal_current = None;


    def set_voltage(self, voltage, current_limit=None):
        if current_limit == None:
            self.current_limit = self.default_current_limit
        else:
            self.current_limit = current_limit

        self.nominal_voltage = voltage
        self.nominal_current = None
        set_voltage(self.instrument, self.channel, self.nominal_voltage, self.current_limit)

    def set_current(self, current, voltage_limit=None):
        if voltage_limit == None:
            self.voltage_limit = self.default_voltage_limit
        else:
            self.voltage_limit = voltage_limit
        self.nominal_current = current
        self.nominal_voltage = None
        set_current(self.instrument, self.channel, self.nominal_current, self.voltage_limit)

    def report(self):
        if self.nominal_voltage is not None:
            print("VOLTAGE:",round(self.get_voltage(),7), "(nominal ",self.nominal_voltage,")")
            print("Current:",round(self.get_current(),7), "(limit ",self.current_limit,")")
        if self.nominal_current is not None:
            print("CURRENT:",round(self.get_current(),7), "(nominal ",self.nominal_current,")")
            print("Voltage:",round(self.get_voltage(),7), "(limit ",self.voltage_limit,")")

    def get_voltage(self):
        return get_voltage(self.instrument, self.channel)

    def get_current(self):
        return get_current(self.instrument, self.channel)

    def update_voltage_limit(self, voltage_limit):
        self.voltage_limit = voltage_limit
        set_current(self.instrument, self.channel, self.nominal_current, self.voltage_limit)

    def disable(self):
        disable_output(self.instrument, self.channel)


def nidcpower_init(resource_name):
    session = nidcpower.Session(resource_name=resource_name)
    #Default configuration: Measure_when = ON-DEMAND
    #print("Initializing NI-DCPower Instrument "+session.instrument_model+" ("+resource_name+") w/ "+str(session.channel_count)+" channels")

    #Always self-cal when initializing. It takes like 1 second and can improve accuracy by 10x.
    #The PSU (4110) does not have a self-cal function.
    if "4110" not in session.instrument_model:
        session.self_cal()
    
    #Disable outputs on initialization for safety.
    session.output_enabled = False
    session.initiate()
    return session

def nidcpower_deinit(session):
    """Deinitializes previously activated & configures NI DC Power session"""
    session.reset() # disable outputs & put in known state
    session.close() # closing session frees resources BUT does not disable outputs!
    

def set_voltage(instr, ch, voltage, current_limit=0.001):
    #Changing any output should automatically set the state of the instrument to non-committed.
    instr.channels[ch].abort()
    instr.channels[ch].output_function = nidcpower.OutputFunction.DC_VOLTAGE
    instr.channels[ch].current_limit=current_limit
    instr.channels[ch].current_limit_range=abs(current_limit) #Choose the smallest possible current limit range.
    instr.channels[ch].voltage_level=voltage
    instr.channels[ch].output_enabled = True
    instr.channels[ch].initiate()

def set_current(instr, ch, current, voltage_limit=0.1):
    #Changing any output should automatically set the state of the instrument to non-committed.
    instr.channels[ch].abort()
    instr.channels[ch].output_function = nidcpower.OutputFunction.DC_CURRENT
    instr.channels[ch].voltage_limit=voltage_limit
    instr.channels[ch].current_level=current
    instr.channels[ch].current_level_range=abs(current) #Choose the smallest possible current level range.
    instr.channels[ch].output_enabled = True
    instr.channels[ch].initiate()

    
def get_voltage(instr, ch):
    if type(ch) is list:
        return [instr.channels[i].measure(nidcpower.MeasurementTypes.VOLTAGE) for i in ch]
    else:
        return instr.channels[ch].measure(nidcpower.MeasurementTypes.VOLTAGE)
        
        
def get_current(instr, ch):
    if type(ch) is list:
        return [instr.channels[i].measure(nidcpower.MeasurementTypes.CURRENT) for i in ch]
    else:
        return instr.channels[ch].measure(nidcpower.MeasurementTypes.CURRENT)

def disable_output(instr,ch):
    instr.channels[ch].output_enabled = False
