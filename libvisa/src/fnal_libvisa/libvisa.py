import pyvisa
import matplotlib.pyplot as plt


#Run an interactive shell.
def VISA_shell():
    rm = pyvisa.ResourceManager()
    resources = rm.list_resources()

    print("Available resources:")
    for i in range(len(resources)):
        print(f"{i}. {resources[i]}")

    resource_idx = int(input("Which one should we connect to?"))


    print(f"Attempting to configure {resources[resource_idx]} as an oscilloscope...")
    scope = TektronixOscilloscope(resources[resource_idx])

    while True:
        user_input = input("cmd>")

        if user_input == "exit":
            break
        elif user_input == "curve":
            print(scope.get_wave())
        elif user_input == "onscreen":
            print(scope.onscreen())
        else:
            print(scope.query(user_input))



class TektronixOscilloscope():

    def __init__(self, logger, visa_resource):
        self.log = logger
        self.rm = pyvisa.ResourceManager()
        self.resources = self.rm.list_resources()
        self.preamble = None

        if visa_resource not in self.resources:
            self.log.error(f"Could not find resource {visa_resource}")
            return -1

        self.inst = self.rm.open_resource(visa_resource)

        self.id = self.get_id()

        if "TEKTRONIX" not in self.id:
            self.log.error("Could not communicate with TektronixOscilloscope")
            return -1
        else:
            self.log.notice("TektronixOscilloscope set up correctly!")

    #Convert a wave (represented by an integer list) from display units to Volts.
    def wave_display_units_to_Volts(self,wave):
        if self.preamble is None:
            self.get_preamble()
        return [(x-self.preamble["YOFF"])*self.preamble["YMULT"] for x in wave]

    #The preamble helps you interpret the data you get from the scope.
    #This function parses the preamble into correct fields.
    def get_preamble(self):
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
        return self.query("*IDN?")

    def query(self, query_text):
        return self.inst.query(query_text)

    def write(self, write_text):
        return self.inst.write(write_text)

    def get_wave(self,chan_num=1,convert_to_volts=True):

        #Specify the waveform source
        self.write(f"DATA:SOURCE CH{chan_num}")

        #Specify the waveform encoding
        self.write("DATA:ENCDG ASCII")

        #Each data point will be represented by 1 byte, -127 thru 127.
        self.write("WFMOutpre:BYT_Nr 1")
        
        #Specify the number of bytes per data point
        #(Not necessary in ASCII format)
        
        #Transfer waveform preamble data
        self.get_preamble()
        
        #Return waveform data as an integer list.
        raw_wave = [int(x) for x in self.query("CURVE?").split(",")]

        if convert_to_volts:
            return self.wave_display_units_to_Volts(raw_wave)
        else:
            return raw_wave

    #Enables the channels specified by enable_nums
    def enable_channels(self,enable_nums):
        for chan in [1,2,3,4]:
            if chan in enable_nums:
                self.write("SELECT:CH{chan} ON")
            else:
                self.write("SELECT:CH{chan} OFF")

    def setup_trigger(self,trigger_channel,threshold_V):

        self.write("TRIGGER:A:EDGE:COUPLING DC")
        self.write(f"TRIGGER:A:EDGE:SOURCE CH{trigger_channel}")
        self.write("TRIGGER:A:EDGE:SLOPE RISE")
        self.write(f"TRIGGER:A:LEVEL {threshold_V}")
        self.write("TRIGGER:MODE SINGLE")

        #These two commands are equivalent to hitting the "single" button on the scope:
        self.write("ACQUIRE:STOPAFTER SEQUENCE")
        self.write("ACQUIRE:STATE 1")
        
        

    #Get the current contents of all oscilloscope channels and display on-screen.
    def onscreen(self, channels=[1,2,3,4]):
        raw_waves = []

        self.enable_channels(channels)
        
        for chan_num in channels:
            raw_waves.append(self.get_wave(chan_num))


            plt.plot(raw_waves[-1])
            
        plt.xlabel("Time")
        plt.ylabel("Amplitude [V]")
        plt.title("Oscilloscope")
        plt.show()
        

#VISA_shell()
        
