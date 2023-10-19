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

    def __init__(self, visa_resource):

        self.rm = pyvisa.ResourceManager()
        self.resources = self.rm.list_resources()

        if visa_resource not in self.resources:
            print("(ERR) Could not find resource")
            return -1

        self.inst = self.rm.open_resource(visa_resource)

        self.id = self.get_id()

        if "TEKTRONIX" not in self.id:
            print("(ERR) Could not communicate with TektronixOscilloscope")
        else:
            print("TektronixOscilloscope set up correctly!")


    def get_id(self):
        return self.query("*IDN?")

    def query(self, query_text):
        return self.inst.query(query_text)

    def write(self, write_text):
        return self.inst.write(write_text)

    def get_wave(self,chan_num=1):

        #Specify the waveform source
        self.write(f"DATA:SOURCE CH{chan_num}")

        #Specify the waveform encoding
        self.write("DATA:ENCDG ASCII")
        
        #Specify the number of bytes per data point
        #(Not necessary in ASCII format)

        #Specify the portion of the waveform that you want to transfer
        
        
        #Transfer waveform preamble data
        print(self.query("WFMOutpre?"))
        
        #Transfer waveform data
        return self.query("CURVE?")


    #Get the current contents of all oscilloscope channels and display on-screen.
    def onscreen(self):
        raw_waves = []
        for chan_num in [1,2,3,4]:
            raw_waves.append(self.get_wave(chan_num))


        plt.plot(raw_waves[-1])
        plt.xlabel("Time")
        plt.ylabel("Amplitude")
        plt.title("Oscilloscope")
        plt.show()
        

#VISA_shell()
        
