#  glue_converter.py
#
# PREREQUISITES MODULES: matplotlib, vcdvcd (both available via pip3)
#
# This file accepts a VCD file, which contains all the waveforms from a
# testbench, and an iospec file which tells which waveforms go in which
# spots of the resulting vector.
# glue_converter outputs a file "output.glue" which is basically a
# CSV containing all the waveforms in order.
#
# IO Spec Format:
# Each I/O line is: {name},{I/O},{position},{optional default value}
# Where: {name} is the signal name in the testbench
#        {I/O}  is I for inputs to the ASIC, O for outputs from the ASIC
#        {position} is the position of this signal in the bit vector that
#                   will be given to the FPGA, which is determined by the PCB.
#
# I/O lines are grouped by the hardware resource they belong to, with the following
# scope statements:
# HARDWARE SLOT/MODULE/FIFO BEGIN
# ...
# END
#
# Basic Example:
# Suppose the testbench contains 3 signals, A, B, and C with this pattern:
#
# A  0 0 1 1
# B  0 1 0 1
# C  1 0 1 1
#
# And the iospect file is the following:
#
# HARDWARE PXI1Slot5/NI6583/se_io BEGIN
# A,I,2
# B,I,0
# C,I,1
# END
#
# The expected content of output.glue is:
#
# 2, 1, 6, 7
# //HARDWARE:PXI1Slot5/NI6583/se_io
#
# Expressed in binary, these numbers are: 
#
# 3'b010, 3'b001, 3'b110, 3'b111


from vcdvcd import VCDVCD
import matplotlib.pyplot as plt
import tkinter as tk
from tkinter import filedialog


GCSHELL_HELPTEXT="""
< < < gcshell help > > >
getvcd    --\tLoad a new VCD file.
getglue   --\tLoad a new Glue file.
iospec    --\tLoad a new iospect file.
clr       --\tClear currently loaded files.

forcesignal--\tForce a particular bit high/low throughout the glue wave.
editbit    --\tEdit a single bit in the current Glue wave at timestep t
writeglue --\tWrite the current Glue wave to file.
bits      --\tExport a clocked bitstream from a Glue wave.

vcd2input/vcd2golden
          --\tConvert a VCD to an input Glue file (inputs only) or a golden Glue file (inputs+outputs)

compare   --\tGet a rough comparison of the signals in two Glue files.

plotglue  --\tPlot the current Glue wave.
diff      --\tPlot the diff between a given signal in two different Glue waves.

exit/quit --\tExit gcshell.

"""

#GlueWave() - Class to hold a Glue wave and all of its metadata.
#
# PROPERTIES:
# strobe_ps - The strobe period of the Glue waveform, i.e. how much (simulation) time each sample represents.
#             May not be the same as the actual length of the sample period as output by the FPGA, which is
#             fixed by the hardware clock.
# hardware  - 3-tuple of [SLOT, MODULE, FIFO]. Example: ["PXI1Slot5", "NI6583", "se_io"]
# metadata  - OPTIONAL additional metadata as key/value pairs.
class GlueWave():

    def __init__(self, vector, strobe_ps, hardware, metadata={}):
        self.vector = vector
        self.strobe_ps = strobe_ps
        self.len = len(self.vector)
        self.mask = 0
        if type(hardware) == str:
            self.hardware = hardware.split("/")
        else:
            self.hardware = hardware

        #Convenient access for the fpga-related or fifo-related
        #part of the hw designation.
        self.hardware_str = "/".join(self.hardware)
        self.fpga_name = "/".join(self.hardware[0:2])
        self.fifo_name = self.hardware[2]
            
        self.metadata = {}


    #Set all bits in the mask to true. Useful for efficiently setting
    #a large number of default bits. 
    def set_mask_bit(self, bit_pos, value):
        if value == 1:
            self.mask = self.mask | (1 << bit_pos)
        else:
            self.mask = self.mask & (~(1 << bit_pos))

    def apply_mask(self):
        self.vector = [x | self.mask for x in self.vector]

    def set_bit(self, t, bit_pos, value):
        if value == 1:
            self.vector[t] = self.vector[t] | (1 << bit_pos)
        else:
            self.vector[t] = self.vector[t] & (~(1 << bit_pos))                                     

    def get_trace(self, bit_pos):
        return [(v & 2**bit_pos > 0) for v in self.vector]




# AsciiWave()
#
# Class to create / print human-readable ascii waves
class AsciiWave():
    def __init__(self):
        self.signals = {}

    def init_signal(self, sig_name, init_val):
        self.signals[sig_name]=str(init_val)

    def init_signals(self, sig_val_list):
        for x in sig_val_list:
            self.init_signal(x[0],x[1])

    def _extend_signal(self, sig_name, n):
        last_val = self.signals[sig_name][-1]
        self.signals[sig_name] = self.signals[sig_name] + n*last_val

    
    #ex: AsciiWave.set_signal("scanEn", 1)
    def set_signal(self, sig_name, set_val):
        for signal in self.signals.keys():
            if signal == sig_name:
                self.signals[signal] = self.signals[signal]+str(set_val)
            else:
                self._extend_signal(signal,1)

    def pulse_signal(self, sig_name, posedge=True):

        if posedge:
            pulse = "010"
        else:
            pulse = "101"

        for signal in self.signals.keys():
            if signal == sig_name:
                self.signals[signal] = self.signals[signal]+pulse
            else:
                self._extend_signal(signal,3)

    # custom_wave()
    # Apply a custom wave across multiple signals simultaneously.
    # ex: AsciiWave.custom_wave({"A":"010","B":"101"})
    # Must have the same number of bits across all signals.
    def custom_wave(self, custom_wave):

        custom_wave_len = len(custom_wave[next(iter(custom_wave))])

        #Check wave lengths
        for w in custom_wave.keys():
            if len(custom_wave[w]) != custom_wave_len:
                print("ERR from custom wave: When generating a custom wave, all signals must have the same pattern length.")
                print("In the provided wave,",custom_wave.keys()[0],"has pattern length",custom_wave_len,"but",w,"has pattern length",len(custom_wave[w]))
                return

        
        for signal in self.signals.keys():
            if signal in custom_wave.keys():
                self.signals[signal] = self.signals[signal]+custom_wave[signal]
            else:
                self._extend_signal(signal,custom_wave_len)

    def write(self, filename):
        with open(filename,'w') as write_file:
            for sig in self.signals.keys():
                write_file.write(sig+":\t"+self.signals[sig]+"\n")
                
                

class GlueConverter():

    #Initialize Glue Converter.
    #You ALWAYS need an I/O spec file to interpret or write Glue files, so we initialize it
    #here. But we don't immediately ask for a VCD file / timebase bc you may want to use multiple
    #of those.
    def __init__(self, iospec_file=None):
        self.loaded_iospec_file = False
        if iospec_file is not None:
            self.parse_iospec_file(iospec_file)
                

    # VCD2Glue - Parses a VCD file into a glue file.
    # PARAMS:
    #       vcd_file_name - something.vcd
    #       strobe_ps - Basically the timebase of the output glue file in picoseconds. Should
    #                   equal GlueFPGA clock speed.
    #       output_file_tag - What the output files should be called.
    #
    # OPTIONAL PARAMS (these can be parsed from the VCD automatically, but you can also override them)
    #       tb_name - Name of the top-level testbench in your VCD
    #       vcd_timebase_ps - Timebase of your VCD file in picoseconds
    def VCD2Glue(self, vcd_file_name, strobe_ps, output_file_tag, inputs_only=True, tb_name=None, vcd_timebase_ps=None):
        
        # Use a library function to parse the input VCD
        vcd = VCDVCD(vcd_file_name, store_scopes=True)

        #Assume that all signals have the same starttime/endtime.
        endtime = vcd[vcd.signals[0]].endtime
        starttime = vcd[vcd.signals[0]].tv[0][0]

        #Parse timebase and VCD name automatically. 
        if vcd_timebase_ps == None:
            vcd_timebase_ps = 1e12 * float(vcd.get_timescale()["timescale"])

        if tb_name == None:
            tb_name = list(vcd.hierarchy.keys())[0]

        
        #The length of the output vector is endtime/STROBE
        strobe_ticks = int(strobe_ps/vcd_timebase_ps)
        vector_len = int((endtime-starttime)/strobe_ticks)

        print("Generating input w/ vector length:",vector_len,"...")

        #We will create a separate GlueWave() for EACH hardware found in the iospec file:
        # list(set(x)) == uniquify(x)
        hw_list = list(set(self.IO_hardware.values()))
        waves = {}
        for hw in hw_list:
            waves[hw] = GlueWave([0]*vector_len, strobe_ps, hw, {"VCD_TIMEBASE_PICOSECONDS":str(vcd_timebase_ps),
                                                                 "GLUE_TIMESTEPS":str(vector_len)})
            
        
        #Now we will go through each input and add them one by one to the correct Glue wave.
        if inputs_only:
            IOs_to_Plot = self.Input_IOs
        else:
            IOs_to_Plot = self.IOs


        defaults_mask = 0
        
        for io in IOs_to_Plot:
            hw = self.IO_hardware[io]

            print("Setting",tb_name+"."+io+"...",end='',flush=True)
            
            try:
                for t in range(len(waves[hw].vector)):
                    #print(t*strobe_ticks+starttime, vcd[tb_name+"."+io][t*strobe_ticks+starttime])
                    if vcd[tb_name+"."+io][t*strobe_ticks+starttime] == "1":
                        waves[hw].set_bit(t,self.IO_pos[io],1)
                print("done!")
                        
            except KeyError:
                print("(WARN) "+tb_name+"."+io+" is NOT FOUND in VCD. Setting to default",self.IO_default[io])
                waves[hw].set_mask_bit(self.IO_pos[io], self.IO_default[io])


        for hw in hw_list:
            print("Applying defaults mask for",hw,"...",end='',flush=True)
            waves[hw].apply_mask()
            print("done!")
            
        #Write glue waves to file.
        for glue_wave in waves.values():
            name = output_file_tag+"_"+glue_wave.hardware[2]+".glue"
            print("Writing",name,"...")
            self.write_glue(glue_wave, name)


        print("Glue Converter finished!")
        print("Total of",len(waves.keys()),"file(s) written.")
        print("Timebase of input file was:",vcd_timebase_ps,"ps")
        print("Length of input file was:",(endtime-starttime)*vcd_timebase_ps/1000000,"us")
        print("Strobe was:",strobe_ps,"ps")
        print("# of timesteps was:",vector_len)


    #ascii2Glue - Accepts an ascii-formatted file and converts it to a glue wave.
    def ascii2Glue(self, ascii_file_name, ticks_per_bit, output_file_tag, inputs_only=True):

        with open(ascii_file_name, 'r') as read_file:
            ascii_lines = read_file.readlines()

        #Each line in the ascii file should be:
        #{io_name}: {bitstring}
        bitstrings = {}

        for line in ascii_lines:
            x = line.split(":")
            bitstrings[x[0].strip()] = x[1].strip()

        #Vector length is determined by the length of the longest bitstring.
        bitstring_len = max([len(b) for b in bitstrings.values()])
        vector_len = ticks_per_bit*bitstring_len

        #We will create a separate GlueWave() for EACH hardware found in the iospec file:
        # list(set(x)) == uniquify(x)
        hw_list = list(set(self.IO_hardware.values()))
        waves = {}
        for hw in hw_list:
            #NOTE: strobe_ps of 25000 (=25 ns) comes from assuming a default FPGA clock of 40 MHz. 
            waves[hw] = GlueWave([0]*vector_len, 25000, hw, {"GLUE_TIMESTEPS":str(vector_len)})

        
        #Now we will go through each input and add them one by one to the correct Glue wave.
        if inputs_only:
            IOs_to_Plot = self.Input_IOs
        else:
            IOs_to_Plot = self.IOs
        
        for io in IOs_to_Plot:
            hw = self.IO_hardware[io]
            
            
            
            try:
                b = bitstrings[io]
                for t in range(bitstring_len):
                    if t < len(b):
                        if b[t] == "1":
                            for i in range(ticks_per_bit):
                                waves[hw].set_bit(t*ticks_per_bit+i,self.IO_pos[io],1)
                    else:
                        #If a bitstring ends early, that value should be held for the whole period.
                        if b[t-1] == "1":
                            for i in range(ticks_per_bit):
                                waves[hw].set_bit(t*ticks_per_bit+i,self.IO_pos[io],1)
                        
            except KeyError:
                print("(WARN) "+io+" is NOT FOUND in ascii file. Setting to default",self.IO_default[io])
                for t in range(len(waves[hw].vector)):
                    waves[hw].set_bit(t,self.IO_pos[io],self.IO_default[io])
            
        #Write glue waves to file.
        for glue_wave in waves.values():
            name = output_file_tag+"_"+glue_wave.hardware[2]+".glue"
            print("Writing",name,"...")
            self.write_glue(glue_wave, name)


        print("Glue Converter finished!")
        print("Total of",len(waves.keys()),"file(s) written.")
        print("# of timesteps was:",vector_len)

    #NOT COMPLETE
    def data2Glue(self, data_file_name, clock_pin_name, data_pin_name, output_file_tag, glue_ticks_per_bit, inputs_only=True):

        if glue_ticks_per_bit < 2:
            print("ERR: data2Glue requires glue_ticks_per_bit > 2, actual value:",glue_ticks_per_bit)
            return

        with open(data_file_name, 'r') as read_file:
            data_string = read_file.read()

        
        
        #We will create a separate GlueWave() for EACH hardware found in the iospec file:
        # list(set(x)) == uniquify(x)
        hw_list = list(set(self.IO_hardware.values()))
        waves = {}
        for hw in hw_list:
            waves[hw] = GlueWave([0]*vector_len, 0, hw, {"VCD_TIMEBASE_PICOSECONDS":str(vcd_timebase_ps),
                                                                 "GLUE_TIMESTEPS":str(vector_len)})
        

    #Write a GlueWave() object to file. 
    def write_glue(self, glue_wave, output_file_name, compress=True):

        if glue_wave is None or glue_wave.len < 1:
            print("(ERR) gc.write_glue: Cannot write a non-existent wave. :)")
            return -1
    
        if glue_wave.len > 10000:
            write_progress = True
        else:
            write_progress = False

        #Compress into a string with "@" symbols representing duplicates.
        if compress:

            if write_progress == True:
                print("Writing Glue Wave. Progress: [",end='',flush=True)
            

            #Optimization note (@aquinn)
            #Successive string concatenation with the + operator can potentially
            #be O(n^2) if the compiler decides to build a temporary string for
            #each + operation. By using a temp array instead we ensure it is
            #O(n) because ''.join(seq) is O(n) and arr.append() is amortized O(1).
            #
            #In testing, I have observed that string concatenation gets slower
            #as the process goes on (i.e. the operands get longer), which implies
            #that there is a temporary string copy being made for each intermediate
            #operation.
            #
            #Update: Confirmed this method is >100x faster for large strings.
            temp = [str(glue_wave.vector[0])]
            #writestring = str(glue_wave.vector[0])
            
            for i in range(1,glue_wave.len):

                if write_progress and i % (glue_wave.len/20)==0:
                    print("|",end="",flush=True)
                
                if glue_wave.vector[i] == glue_wave.vector[i-1]:
                    #writestring = writestring+"@"
                    temp.append("@")
                else:
                    #writestring = writestring+","+str(glue_wave.vector[i])
                    temp.append(",")
                    temp.append(str(glue_wave.vector[i]))

            writestring = ''.join(temp)

        else:
            writestring = ",".join([str(x) for x in glue_wave.vector])

        if write_progress:
            print("] (writing final result to file...)",flush=True)

        #Write to file
        with open(output_file_name,'w') as write_file:
            write_file.write(writestring)
            write_file.write("\n")
            #Mandatory metadata
            write_file.write("//STROBE_PICOSECONDS:"+str(glue_wave.strobe_ps)+"\n")
            write_file.write("//HARDWARE:"+"/".join(glue_wave.hardware)+"\n")
            #Optional metadata
            for key in glue_wave.metadata.keys():
                write_file.write("//"+str(key)+":"+str(glue_wave.metadata[key])+"\n")

    #Read a Glue file into a GlueWave() object.
    #Args:
    #   - glue_file_name = full file name of the glue file to be read.
    #Returns:
    #   - GlueWave(), or None on failure.
    def read_glue(self,glue_file_name):

        try:
            with open(glue_file_name,"r") as read_file:
                lines = read_file.readlines()
                
        except FileNotFoundError:
            print("(ERR) Could not read Glue file at:",glue_file_name)
            return None
            
        #Process the first line to get the entries.
        datastring = lines[0].strip()
        data_entries = datastring.split(",")

        expected_len = datastring.count(",")+datastring.count("@")+1
        print("Reading glue wave, expected length =",expected_len)

        
        vector = [0]*(expected_len)
        i = 0
        
        for entry in data_entries:
            #If this is a compressed entry...
            if "@" in entry:
                base_entry = int(entry.replace("@",""))
                #...first add the base entry,
                vector[i] = base_entry
                i = i+1
                #...then duplicate it entry.count("@")-many times.
                for j in range(entry.count("@")):
                    vector[i] = base_entry
                    i = i+1

            else:
                vector[i] = int(entry)
                i = i+1
        
        #vector = [int(x) for x in lines[0].strip().split(",")]

        #It processes the next two lines to extract floating point numbers (beren)
        #timebase_ps = float(lines[1].strip().split(":")[-1])
        for line in lines:
            if "STROBE" in line:   
                strobe_ps = float(line.strip().split(":")[-1])
            if "HARDWARE" in line:
                hardware = line.strip().split(":")[-1]

        return GlueWave(vector,strobe_ps,hardware)

    #Plots a glue waveform using matplotlib. Useful for debugging.
    def plot_glue(self,glue_file,time_interval_ps=None):

        if type(glue_file) == str:
            wave = self.read_glue(glue_file)
            if wave == None:
                print("(ERR) Cannot plot glue because file was not read.")
                return
        else:
            wave = glue_file
        vector = wave.vector
        strobe_ps = wave.strobe_ps

        if time_interval_ps is not None:
            start_time = time_interval_ps[0]
            end_time = time_interval_ps[1]
            vector = vector[int(start_time/strobe_ps):int(end_time/strobe_ps)]
        else:
            start_time = 0
            end_time = len(vector)*strobe_ps

        #Put the IO waves in list form.
        IO_waves = []  
        IO_wave_names = []

        for i in range(len(self.IOs)):
            io = self.IOs[i]
            #Only plot IOs which correspond to the hardware that generated this Glue wave (others will be zero)
            #print("(DBG)",self.IO_hardware[io],wave.hardware_str)
            if self.IO_hardware[io] == wave.hardware_str:
                IO_waves.append([(v & 2**self.IO_pos[self.IOs[i]] > 0) for v in vector])
                IO_wave_names.append(io)

        #Plot
        self.plot_waves(IO_waves,IO_wave_names, strobe_ps)
        
    # plot_waves
    # This plotting function is intended to work on an arbitrary number of binary signals.
    # PARAMS:
    #       waves - List of waves, defined as integer lists.
    #       wave_names - List of the names of these waves, matching 1-to-1 with the waves themselves.
    def plot_waves(self, waves, wave_names, strobe_ps):
        assert len(waves) > 0 and len(waves) == len(wave_names)
        
        #beren.this line is updates to work with more IO.
        #beren. Number of rows = number of IOs, dim of the figure scaled according to the number of IOs
        #beren. x-axis is shared among all subplots.
        fig, axes = plt.subplots(nrows=len(waves), figsize=(10, 2 * len(waves)), sharex=True)
        fig.subplots_adjust(hspace=0.5)

        #Create the time vector in nanoseconds.
        time_vector = [i*strobe_ps/1000 for i in range(len(waves[0]))]

        for i, ax in enumerate(axes):#beren

            #beren. I put spaces between the y-axis name and the IO name
            ax.set_ylabel(wave_names[i] + "                ", rotation='horizontal') #beren
            ax.step(time_vector, waves[i])#beren
            ax.set_ylim(-0.5, 1.5)#beren
            ax.set_yticks([0, 0.5,1])#beren
            ax.yaxis.set_tick_params(labelleft=False) #Hide y-axis ticks since they are redundant.
            ax.spines['right'].set_visible(False)
            ax.spines['bottom'].set_visible(False)
            ax.spines['top'].set_visible(False)
            ax.grid(True)#beren

        plt.xlabel("ns")
        plt.show()

    #Reads an IO spec in the format specified above, and parses
    #its information into lists and dictionaries so it can be
    #easily used.
    def parse_iospec_file(self,iospec_file):
        # Parse the iospec file
        with open(iospec_file, 'r') as iospec:
            iospec_lines = iospec.readlines()


        # Create dictionaries to hold the direction and position of every IO.
        self.IOs = []
        self.Input_IOs = []
        self.Output_IOs = []
        self.IO_dir = {}
        self.IO_pos = {}
        self.IO_default = {}
        self.IO_hardware = {} # str representation
        self.IO_hardware_count = 0


        current_hw = None
        
        for line in iospec_lines:
            if len(line) > 1 and not line.startswith("//"): #Allow empty lines and comments using "//" in the iospec file.

                if line.startswith("HARDWARE"):
                    current_hw = line.split()[1]
                    self.IO_hardware_count = self.IO_hardware_count + 1
                elif line.startswith("END"):
                    current_hw = ""
                elif current_hw != "":
                    line_tokens = line.split(",")
                    sig_name = line_tokens[0] #{name}
                    self.IOs.append(sig_name)
                    
                    self.IO_dir[sig_name] = line_tokens[1] #{I/O}
                    if line_tokens[1] == "I":
                        self.Input_IOs.append(sig_name)
                    else:
                        self.Output_IOs.append(sig_name)
                        
                    self.IO_pos[sig_name] = int(line_tokens[2]) #{position}

                    self.IO_hardware[sig_name] = current_hw #{hardware}

                    #Support {optional default value}
                    if len(line_tokens) > 3:
                        self.IO_default[sig_name] = int(line_tokens[3])
                    else:
                        self.IO_default[sig_name] = 0
                else:
                    print("IOSPEC PARSE ERR: Line \""+line+"\" has no hardware associated with it!")
                    return -1
                    
        self.loaded_iospec_file = True
            
    def compare(self, wave1, wave2):
        if wave1 is None or wave2 is None:
            print("(ERR) gc.compare: Cannot compare",wave1,"with",wave2)
            return -1

        print("Wave 1 len:",wave1.len)
        print("Wave 2 len:",wave2.len)
        
        print( "I/O             Dir.\tDC1 \tDC2 \tIn=Out?")
        for io in self.IOs:

            #Only worry about those IOs
            if not self.IO_hardware[io] == wave1.hardware_str:
                #print("(DBG) skipping",io,"because",self.IO_hardware[io],"!=",wave1.hardware_str)
                continue

            direction = self.IO_dir[io]
            position = self.IO_pos[io]
            pattern1_this_io = [1 if x & (1 << position) else 0 for x in wave1.vector]
            pattern2_this_io = [1 if x & (1 << position) else 0 for x in wave2.vector]

            DC1 = round(sum(pattern1_this_io)/len(pattern1_this_io),5)
            DC2 = round(sum(pattern2_this_io)/len(pattern2_this_io),5)
            passthrough = all([pattern1_this_io[i] == pattern2_this_io[i] for i in range(min(wave1.len,wave2.len))])

            
            print(f"{io:<15}\t{direction}\t{DC1}\t{DC2}\t{passthrough}")  


    def diff(self, wave1, wave2, diff_signals):

        #A single string should be treated as a list of length 1.
        if type(diff_signals) == str:
            diff_signals = [diff_signals]
        
        signals = []
        signal_names = []

        for i in range(len(diff_signals)):

            signal_names.append(diff_signals[i]+"(1)")
            sig1 = [1 if x & (1 << self.IO_pos[diff_signals[i]]) else 0 for x in wave1.vector]
            signals.append(sig1)

            signal_names.append(diff_signals[i]+"(2)")
            sig2 = [1 if x & (1 << self.IO_pos[diff_signals[i]]) else 0 for x in wave2.vector]
            signals.append(sig2)

            signal_names.append("diff("+diff_signals[i]+")")
            signals.append([1 if sig1[i] != sig2[i] else 0 for i in range(min(wave1.len, wave2.len))])
            

        self.plot_waves(signals,signal_names,wave1.strobe_ps)

    # export_clocked_bitstream
    # Converts a Glue waveform with a data signal and its corresponding clock into a bit stream!
    def export_clocked_bitstream(self, wave, clock_name, data_name, outfile):

        bitstream = []

        clock_sig = [1 if x & (1 << self.IO_pos[clock_name]) else 0 for x in wave.vector]
        data_sig =  [1 if x & (1 << self.IO_pos[data_name]) else 0 for x in wave.vector]
        
        for i in range(1,len(wave.vector)):
            if clock_sig[i] == 1 and clock_sig[i-1] == 0:
                bitstream.append(data_sig[i-1])

        with open(outfile,"w") as write_file:
            write_file.write(",".join([str(i) for i in bitstream]))
            

    #Open a mini shell that allows the user to run Glue Converter commands. 
    def gcshell(self):

        current_vcd = None
        current_glue = None
        wave1 = None
        wave2 = None

        command_list = ["iospec","getvcd","getglue","bits","compare","diff","plotglue","vcd2input","vcd2golden","exit","quit"]

        if not self.loaded_iospec_file:
            print("Load an iospec file...")
            file_path = filedialog.askopenfilename()
            self.parse_iospec_file(file_path)

        while True:

            user_input = input(">gcshell>").strip()

            if user_input == "iospec":
                file_path = filedialog.askopenfilename()
                self.parse_iospec_file(file_path)
                print(file_path)

            elif user_input == "clr":
                current_vcd = None
                current_glue = None
                wave1 = None
                wave2 = None

            elif user_input == "getvcd":
                current_vcd = filedialog.askopenfilename()
                print(current_vcd)

            elif user_input == "getglue":
                glue_file = filedialog.askopenfilename()
                print(glue_file)
                current_glue = self.read_glue(glue_file)


            elif user_input == "forcesignal":
                if current_glue == None:
                    glue_file = filedialog.askopenfilename()
                    print(glue_file)
                    current_glue = self.read_glue(glue_file)
                    if current_glue == None:
                        print("(ERR) Cannot proceed because read_glue failed.")
                        continue
                    
                sig_name = input("sig_name?")

                try:
                    bit_pos = self.IO_pos[sig_name]
                except ValueError:
                    print("(gcshell error) Couldn't find that signal in current iospec.")
                    continue
                force_val = int(input("force value (0 or 1)?"))
                for t in range(current_glue.len):
                    current_glue.set_bit(t,bit_pos,force_val)
                print("Done! Forced",sig_name,"to",force_val)

            elif user_input == "editbit":
                if current_glue == None:
                    glue_file = filedialog.askopenfilename()
                    print(glue_file)
                    current_glue = self.read_glue(glue_file)
                    if current_glue == None:
                        print("(ERR) Cannot proceed because read_glue failed.")
                        continue
                    
                t = int(input("t?"))
                bit_pos = int(input("bit_pos?"))
                value = int(input("value?"))
                current_glue.set_bit(t,bit_pos,value)
                print("Set bit",bit_pos,"at time",t,"to",value)

            elif user_input == "writeglue":
                if current_glue == None:
                    glue_file = filedialog.askopenfilename()
                    print(glue_file)
                    current_glue = self.read_glue(glue_file)
                    if current_glue == None:
                        print("(ERR) Cannot proceed because read_glue failed.")
                        continue
                filename = input("File name?").strip()
                self.write_glue(current_glue,filename)
                print("Wrote to",filename)

            elif user_input == "bits":
                glue_file = filedialog.askopenfilename()
                print(glue_file)
                current_glue = self.read_glue(glue_file)
                if current_glue == None:
                    print("(ERR) Cannot proceed because read_glue failed.")
                    continue
                clock_name = input("Clock name?").strip()
                data_name = input("Data name?").strip()
                outfile = input("Output file name?").strip()
                self.export_clocked_bitstream(current_glue, clock_name, data_name, outfile)

            elif user_input == "compare":
                if wave1 == None:
                    print("Getting Glue Wave 1...")
                    glue1 = filedialog.askopenfilename()
                    print("Getting Glue Wave 2...")
                    glue2 = filedialog.askopenfilename()
                    print("Glue 1:",glue1)
                    print("Glue 2:",glue2)
                    wave1 = self.read_glue(glue1)
                    wave2 = self.read_glue(glue2)
                    if wave1 == None or wave2 == None:
                        print("(ERR) Cannot proceed because read_glue failed.")
                        continue
                    
                self.compare(wave1,wave2)

            elif user_input == "diff":
                if wave1 == None:
                    print("Getting Glue Wave 1...")
                    glue1 = filedialog.askopenfilename()
                    print("Getting Glue Wave 2...")
                    glue2 = filedialog.askopenfilename()
                    print("Glue 1:",glue1)
                    print("Glue 2:",glue2)
                    wave1 = self.read_glue(glue1)
                    wave2 = self.read_glue(glue2)
                    if wave1 == None or wave2 == None:
                        print("(ERR) Cannot proceed because read_glue failed.")
                        continue

                diff_sig = input("Diff signal?").strip()

                #Allow multiple signals:
                if "," in diff_sig:
                    diff_sig = diff_sig.split(",")
                
                self.diff(wave1,wave2,diff_sig)

            elif user_input == "plotglue":
                if current_glue == None:
                    glue_file = filedialog.askopenfilename()
                    print(glue_file)
                    current_glue = self.read_glue(glue_file)
                    if current_glue == None:
                        print("(ERR) Cannot proceed because read_glue failed.")
                        continue
                self.plot_glue(current_glue)
                print("Done!")

            elif user_input == "vcd2input" or user_input == "vcd2golden":
                if current_vcd == None:
                    current_vcd = filedialog.askopenfilename()
                
                #vcd_timebase_ps = float(input("VCD timebase (ps)?"))
                #tb_name = input("tb name?").strip()
                strobe_ps = float(input("Strobe (ps)?"))
                output_file_name = input("Out file tag?").strip()

                if "golden" in user_input:
                    inputs_only = False
                else:
                    inputs_only = True
                
                self.VCD2Glue(current_vcd, strobe_ps, output_file_name, inputs_only)
                print("Done!")

            elif user_input == "ascii2input" or user_input == "ascii2golden":
                current_ascii = filedialog.askopenfilename()

                ticks_per_bit = int(input("ticks per bit?"))
                output_file_name = input("Out file tag?").strip()

                if "golden" in user_input:
                    inputs_only = False
                else:
                    inputs_only = True
                
                self.ascii2Glue(current_ascii, ticks_per_bit, output_file_name, inputs_only)
                print("Done!")

            elif user_input == "exit" or user_input == "quit":
                break

            else:
                print("Unrecognized.")
                print(GCSHELL_HELPTEXT)
                continue
                
                
