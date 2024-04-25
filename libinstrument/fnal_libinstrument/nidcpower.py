# GENERIC NIDCPOWER #

# Generic comands for interfacing with NI-DCPower Compatible devices.


# NOTE: This software requires a relatively modern version of the NI-DCPower
# driver. To update, open the "NI Package Manager" software, go to Browse
# Products, find NI-DCPower and install a version at least as new as 2022 Q4.
# You may have to update NI Package Manager first.

# GENERAL USAGE NOTES:
# - PSU channels are 0,1,2 while SMU channels are 0,1,2,3

import nidcpower
from fnal_libinstrument import Source_Instrument


#NOTE: NIDCPowerInstrument must implement the same interface as supply.py located in the /fnal_libinstrument/
#library, because both of them could be called by the Source_Port() class.

class NIDCPowerInstrument(Source_Instrument):


    def __init__(self, resource_name):
        self.session = nidcpower.Session(resource_name=resource_name)
        #Default configuration: Measure_when = ON-DEMAND
        #print("Initializing NI-DCPower Instrument "+session.instrument_model+" ("+resource_name+") w/ "+str(session.channel_count)+" channels")

        #Always self-cal when initializing. It takes like 1 second and can improve accuracy by 10x.
        #The PSU (4110) does not have a self-cal function.
        if "4110" not in self.session.instrument_model:
            self.session.self_cal()
    
        #Disable outputs on initialization for safety.
        self.session.output_enabled = False
        self.session.initiate()
    

    def deinit(self):
        """Deinitializes previously activated & configures NI DC Power session"""
        self.session.reset() # disable outputs & put in known state
        self.session.close() # closing session frees resources BUT does not disable outputs!
    

    def set_voltage(self, ch, voltage, current_limit=0.001):
        #Changing any output should automatically set the state of the instrument to non-committed.
        self.session.channels[ch].abort()
        self.session.channels[ch].output_function = nidcpower.OutputFunction.DC_VOLTAGE
        self.session.channels[ch].current_limit=current_limit
        self.session.channels[ch].current_limit_range=abs(current_limit) #Choose the smallest possible current limit range.
        self.session.channels[ch].voltage_level=voltage
        self.session.channels[ch].output_enabled = True
        self.session.channels[ch].initiate()

    def set_current(self, ch, current, voltage_limit=0.1):
        #Changing any output should automatically set the state of the instrument to non-committed.
        self.session.channels[ch].abort()
        self.session.channels[ch].output_function = nidcpower.OutputFunction.DC_CURRENT
        self.session.channels[ch].voltage_limit=voltage_limit
        self.session.channels[ch].current_level=current
        self.session.channels[ch].current_level_range=abs(current) #Choose the smallest possible current level range.
        self.session.channels[ch].output_enabled = True
        self.session.channels[ch].initiate()

        
    def get_voltage(self, ch):
        if type(ch) is list:
            return [self.session.channels[i].measure(nidcpower.MeasurementTypes.VOLTAGE) for i in ch]
        else:
            return self.session.channels[ch].measure(nidcpower.MeasurementTypes.VOLTAGE)
            
            
    def get_current(self, ch):
        if type(ch) is list:
            return [self.session.channels[i].measure(nidcpower.MeasurementTypes.CURRENT) for i in ch]
        else:
            return self.session.channels[ch].measure(nidcpower.MeasurementTypes.CURRENT)

    def disable_output(self,ch):
        self.session.channels[ch].output_enabled = False
        
        
    def set_output_on(self,ch):
        self.session.channels[ch].output_enabled = True

    def set_output_off(self,ch):
        self.session.channels[ch].output_enabled = False
