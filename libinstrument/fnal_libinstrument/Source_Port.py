##################
# SOURCE_PORT.PY #
##################
#
# Usage Model: 
# 
# All voltage and current rails controlled by Spacely will be controlled by a Source_Port 
# instance in the global V_PORT{} or I_PORT{} dictionaries under a user-defined key.  
# This allows user scripts to easily call V_PORT["myRail"].set_voltage(1.0)
# 
# The Source_Port class is initialized with:
#   -- An instrument, an object which implements the communication to whatever physical test instrument
#      controls the voltage channel.
#   -- A channel, which may be of any data type, which tells the instrument exactly which rail is being
#      controlled. 
#
# The instrument must implement the Source_Instrument abstract class!! This ensures that it follows a
# specific contract, namely supporting the methods that will be called by Source_Port. 
#

from abc import ABCMeta, abstractmethod


class Source_Instrument(object, metaclass=ABCMeta):

    @abstractmethod
    def set_voltage(self, channel, nominal_voltage, current_limit):
        pass
      
    @abstractmethod
    def set_current(self, channel, nominal_current, voltage_limit):
        pass
        
    @abstractmethod
    def get_voltage(self, channel):
        pass
      
    @abstractmethod
    def get_current(self, channel):
        pass
        
    @abstractmethod
    def set_output_on(self, channel):
        pass
        
    @abstractmethod
    def set_output_off(self, channel):
        pass



#Wrapper class just to hold the instrument and channel info for a given port. 
class Source_Port:

    # Arguments:
    #  * instrument = handle to the instrument responsible for this channel. (Could be nidcpower, or supply)
    def __init__(self, instrument, channel, default_current_limit=0.001, default_voltage_limit=0.1):
    
        if not issubclass(type(instrument), Source_Instrument):
            print(f"!!! WARNING !!! tried to instantiate Source_Port for {instrument}:{channel} but {instrument} does not implement the Source_Instrument abstract class.")
            
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
        self.instrument.set_voltage(self.channel, self.nominal_voltage, self.current_limit)

    def set_current(self, current, voltage_limit=None):
        if voltage_limit == None:
            self.voltage_limit = self.default_voltage_limit
        else:
            self.voltage_limit = voltage_limit
        self.nominal_current = current
        self.nominal_voltage = None
        self.instrument.set_current(self.channel, self.nominal_current, self.voltage_limit)

    def report(self):
        if self.nominal_voltage is not None:
            print("VOLTAGE:",round(self.get_voltage(),7), "(nominal ",self.nominal_voltage,")")
            print("Current:",round(self.get_current(),7), "(limit ",self.current_limit,")")
        if self.nominal_current is not None:
            print("CURRENT:",round(self.get_current(),7), "(nominal ",self.nominal_current,")")
            print("Voltage:",round(self.get_voltage(),7), "(limit ",self.voltage_limit,")")

    def get_voltage(self):
        return self.instrument.get_voltage(self.channel)

    def get_current(self):
        return self.instrument.get_current(self.channel)

    def update_voltage_limit(self, voltage_limit):
        self.voltage_limit = voltage_limit
        set_current(self.instrument, self.channel, self.nominal_current, self.voltage_limit)

    def set_output_on(self):
        self.instrument.set_output_on(self.channel)
        
    def set_output_off(self):
        self.instrument.set_output_off(self.channel)