import pyvisa
import matplotlib.pyplot as plt
import time

    

class Oscilloscope():
    
    #Arguments:
    #  logger - class that implements debug(), notice(), and error()
    #  io     - Spacely Interface, i.e. VISA or Prologix
    def __init__(self, logger, io):
        
        if logger is None:
            self.log = basic_logger()
        else:
            self.log = logger
        
        self.DEBUG_MODE = True

        #VISA or Prologix Interface
        self.io = io
        
        self.preamble = None

        self.write(":STOP")
        self.reset()

        #Write some gratuitous newline characters to make sure we get back to a good state?
        self.write("\n")
        
        self.id = self.get_id()

        if "TEKTRONIX" in self.id:
            #Only instrument that is definitely supported is the Tektronix DPO5000 series.
            self.flavor = "TEKTRONIX"
            self.log.notice("TektronixOscilloscope set up correctly!")
        elif "AGILENT TECHNOLOGIES,MSO70" in self.id:
            self.flavor = "AGILENT MSO7000"
            self.log.notice("Agilent MSO7000 series Oscilloscope set up correctly!")
        else:
            self.log.debug(f"Response to ID String: {self.id}")
            self.log.error("This scope is not supported by fnal-libvisa.")
            return
            

    #Convert a wave (represented by an integer list) from display units to Volts.
    def wave_display_units_to_Volts(self,chan_num,wave):
    
        if "TEKTRONIX" in self.flavor:
            if self.preamble is None:
                self._Tektronix_get_preamble()
            return [(x-self.preamble["YOFF"])*self.preamble["YMULT"] for x in wave]
        else:
            #time.sleep(1)
            #offset = float(self.query(":CHANNEL1:OFFSET?"))
            #time.sleep(1)
            scale  = float(self.query(f":CHANNEL{chan_num}:SCALE?"))
            #time.sleep(1)
            return [(x)*scale for x in wave]

    #The preamble helps you interpret the data you get from the scope.
    #This function parses the preamble into correct fields.
    def _Tektronix_get_preamble(self):
        self.preamble = {}
        preamble_str = self.query("WFMOutpre?")
        preamble_fields = preamble_str.split(";")

        self.preamble["BYT_NR"] = preamble_fields[0]
        self.preamble["BIT_NR"] = preamble_fields[1]
        self.preamble["ENCDG"] = preamble_fields[2]
        self.preamble["BN_FMT"] = preamble_fields[3]
        self.preamble["BYT_OR"] = preamble_fields[4]
        self.preamble["WFID"] = preamble_fields[5]
        self.preamble["NR_PT"] = preamble_fields[6]
        self.preamble["PT_FMT"] = preamble_fields[7]
        self.preamble["XUNIT"] = preamble_fields[8]
        self.preamble["XINCR"] = float(preamble_fields[9])
        self.preamble["XZERO"] = float(preamble_fields[10])
        self.preamble["PT_OFF"] = preamble_fields[11]
        self.preamble["YUNIT"] = preamble_fields[12]
        self.preamble["YMULT"] = float(preamble_fields[13])
        self.preamble["YOFF"] = float(preamble_fields[14])
        self.preamble["YZERO"] = preamble_fields[15]
        self.preamble["NR_FR"] = preamble_fields[16]
        
        self.log.debug(str(self.preamble))
        

    def get_id(self):
        #*IDN? is a common command that should work across all models.
        return self.query("*IDN?")

    def reset(self):
        return self.write("*RST")

    # Pop the next error from the error queue.
    def get_error(self):
        return self._query("SYST:ERR?")
    
    # Return a list of all errors in the error queue. (The total queue is 30 errors deep)
    def get_all_errors(self):
        errors = []
        got_all_errors = False

        while not got_all_errors:
            next_error = self.get_error()
            if "No error" in next_error:
                got_all_errors = True
            else:
                errors.append(next_error)

        return errors

    #Raw Query
    def _query(self,query_text):
        return self.io.query(query_text)
    
    #Raw Write
    def _write(self,write_text):
        return self.io.write(write_text)
    
    #Query with print and error handling
    def query(self, query_text):
        if self.DEBUG_MODE:
            self.log.debug(f"Oscilloscope.query: '{query_text}'")
        return_val = self._query(query_text)
        if self.DEBUG_MODE:
            self.log.debug(f"Errors Returned: {self.get_all_errors()}")
        
        return return_val

    #Write with print and error handling
    def write(self, write_text):
        if self.DEBUG_MODE:
            self.log.debug(f"Oscilloscope.write: '{write_text}'")
        return_val = self._write(write_text)
        if self.DEBUG_MODE:
            self.log.debug(f"Errors Returned: {self.get_all_errors()}")
        
        return return_val


    
    def set_scale(self,scale_V,chan_num=None):
        if chan_num == None:
            for i in [1,2,3,4]:
                self.write(f":CHAN{i}:SCALE {scale_V}")
        else:
            return self.write(f":CHAN{chan_num}:SCALE {scale_V}")
        
    def set_timebase(self,timebase_s):
        return self.write(f":TIMEBASE:SCALE {timebase_s}")

    def set_time_offset(self, time_offset_s):
        return self.write(f":TIMEBASE:POSITION {time_offset_s}")

    def set_bandwidth_limit(self,value,chan_num=None):
        if value:
            value = 1
        else:
            value = 0
        if chan_num == None:
            for i in [1,2,3,4]:
                self.write(f":CHAN{i}:BWL {value}")
        else:
            return self.write(f":CHAN{chan_num}:BWL {value}")

    def set_voltage_offset(self,offset_V,chan_num=None):
        if chan_num == None:
            for i in [1,2,3,4]:
                self.write(f":CHAN{i}:OFFSET {offset_V}")
        else:
            return self.write(f":CHAN{chan_num}:OFFSET {offset_V}")
    
    def get_wave(self,chan_num=1, convert_to_volts=True):
        if self.flavor == "TEKTRONIX":
            raw_wave = self._Tektronix_get_wave(chan_num)
            if convert_to_volts:
                return self.wave_display_units_to_Volts(chan_num,raw_wave)
            else:
                return raw_wave  
        elif self.flavor == "AGILENT MSO7000":
            raw_wave = self._Agilent_get_wave(chan_num)
            #Agilent automatically converts to Volts
            return raw_wave
            
          

        
    def _Agilent_get_wave(self, chan_num=1):
        #Specify the waveform source
        self.write(f":WAVEFORM:SOURCE CHAN{chan_num}")
        
        #Set format to ASCII
        self.write(":WAVEFORM:FORMAT ASCII")
        
        #Get 1000 points (max) from the measurement record.
        self.write(":WAVEFORM:POINTS:MODE NORMAL")
        self.write(":WAVEFORM:POINTS 1000")
        
        #Note Byte Order and do not need to be set in ASCII format.
        
        #Waveform data is returned as a float list which corresponds to the Y-axis
        #The first 10 ASCII characters form a header which can be discarded.
        try:
            query_data = self.query(":WAVEFORM:DATA?")
        except Exception as e:
            print(e)
            self.log.error("Failed to read data from Scope!")
            #query_data = self.query(":WAVEFORM:DATA?")
            return None
        
        raw_wave = [float(x) for x in query_data[10:].split(",")]
        
        return raw_wave

    def _Tektronix_get_wave(self,chan_num=1):

        #Specify the waveform source
        self.write(f"DATA:SOURCE CH{chan_num}")

        #Specify the waveform encoding
        self.write("DATA:ENCDG ASCII")

        #Each data point will be represented by 1 byte, -127 thru 127.
        self.write("WFMOutpre:BYT_Nr 1")
        
        #Get number of points equal to the record length:
        rl = int(self.query("HORIZONTAL:MODE:RECORDLENGTH?"))
        print(f"(DBG) RL = {rl}")
        self.write("DATA:START 1")
        self.write(f"DATA:STOP {rl}")
        
        #Transfer waveform preamble data
        self.get_preamble()
        
        #Return waveform data as an integer list.
        raw_wave = [int(x) for x in self.query("CURVE?").split(",")]

        return raw_wave

    #Enables the channels specified by enable_nums
    def enable_channels(self,enable_nums):
        
        for chan in [1,2,3,4]:
            if chan in enable_nums:
                if "TEKTRONIX" in self.flavor:
                    self.write(f"SELECT:CH{chan} ON")
                else:
                    self.write(f":CHAN{chan}:DISPLAY ON")
            else:
                if "TEKTRONIX" in self.flavor:
                    self.write(f"SELECT:CH{chan} OFF")
                else:
                    self.write(f":CHAN{chan}:DISPLAY OFF")

    def setup_trigger(self,trigger_channel,threshold_V):
        if self.flavor == "TEKTRONIX":
            self._Tektronix_setup_trigger(trigger_channel,threshold_V)
        elif self.flavor == "AGILENT MSO7000":
            self._Agilent_setup_trigger(trigger_channel,threshold_V)

    def _Tektronix_setup_trigger(self,trigger_channel,threshold_V):

        self.write("TRIGGER:A:EDGE:COUPLING DC")
        self.write(f"TRIGGER:A:EDGE:SOURCE CH{trigger_channel}")
        self.write("TRIGGER:A:EDGE:SLOPE RISE")
        self.write(f"TRIGGER:A:LEVEL {threshold_V}")
        self.write("TRIGGER:MODE SINGLE")

        #These two commands are equivalent to hitting the "single" button on the scope:
        self.write("ACQUIRE:STOPAFTER SEQUENCE")
        self.write("ACQUIRE:STATE 1")
        
        
    def _Agilent_setup_trigger(self,trigger_channel,threshold_V):
        
        self.write(":TRIGGER:SWEEP NORMAL") #This is equivalent to setting Mode=Normal (not Auto)
        self.write(":TRIGGER:MODE EDGE")
        self.write(":TRIGGER:EDGE:COUPLING DC")
        self.write(f":TRIGGER:EDGE:LEVEL {threshold_V}")
        self.write(":TRIGGER:EDGE:SLOPE POS")
        self.write(f":TRIGGER:EDGE:SOURCE CHAN{trigger_channel}")
        
        self.write(":SINGLE")

    #Get the current contents of all oscilloscope channels and display on-screen.
    def onscreen(self, channels=[1,2,3,4]):
        raw_waves = []

        self.enable_channels(channels)
        
        for chan_num in channels:
            raw_waves.append(self.get_wave(chan_num))


            plt.plot(raw_waves[-1])
            
        plt.xlabel("Time")
        plt.ylabel("Amplitude [V]")
        plt.legend([f"Ch{i}" for i in channels])
        plt.title("Oscilloscope")
        plt.show()
        

        
