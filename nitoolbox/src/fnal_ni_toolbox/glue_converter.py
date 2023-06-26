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
# Each line is: {name},{I/O},{position},{optional default value}
# Where: {name} is the signal name in the testbench
#        {I/O}  is I for inputs to the ASIC, O for outputs from the ASIC
#        {position} is the position of this signal in the bit vector that
#                   will be given to the FPGA, which is determined by the PCB.
#
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
# A,I,2
# B,I,0
# C,I,1
#
# The expected content of output.glue is:
#
# 2, 1, 6, 7
#
# Expressed in binary, these numbers are: 
#
# 3'b010, 3'b001, 3'b110, 3'b111


from vcdvcd import VCDVCD
import matplotlib.pyplot as plt
import tkinter as tk
from tkinter import filedialog


class GlueWave():

    def __init__(self, vector, strobe_ps):
        self.vector = vector
        self.strobe_ps = strobe_ps
        self.len = len(self.vector)

class GlueConverter():

    #Initialize Glue Converter.
    #You ALWAYS need an I/O spec file to interpret or write Glue files, so we initialize it
    #here. But we don't immediately ask for a VCD file / timebase bc you may want to use multiple
    #of those.
    def __init__(self, iospec_file=None):
        self.loaded_iospec_file = False
        if iospec_file is not None:
            self.parse_iospec_file(iospec_file)



    # parse_VCD - Parses a VCD file into a glue file.
    # PARAMS:
    #       vcd_file_name - something.vcd
    #       strobe_ps - Basically the timebase of the output glue file in picoseconds. Should
    #                   equal GlueFPGA clock speed.
    #       output_file_name - something.glue
    #
    # OPTIONAL PARAMS (these can be parsed from the VCD automatically, but you can also override them)
    #       tb_name - Name of the top-level testbench in your VCD
    #       vcd_timebase_ps - Timebase of your VCD file in picoseconds
    def parse_VCD(self, vcd_file_name, strobe_ps, output_file_name, inputs_only=True, tb_name=None, vcd_timebase_ps=None):
        # Use a library function to parse the input VCD
        vcd = VCDVCD(vcd_file_name, store_scopes=True)

        #Assume that all signals have the same endtime.
        endtime = vcd[vcd.signals[0]].endtime

        #Parse timebase and VCD name automatically. 
        if vcd_timebase_ps == None:
            vcd_timebase_ps = 1e12 * float(vcd.get_timescale()["timescale"])

        if tb_name == None:
            tb_name = list(vcd.hierarchy.keys())[0]

            
        #The length of the output vector is endtime/STROBE
        strobe_ticks = int(strobe_ps/vcd_timebase_ps)
        vector = [0] * int(endtime/strobe_ticks)
        
        # For each timestep, find out if each input is high, and if it is,
        # then set that bit in the output vector high by adding 2^(pos) to
        # that vector.
        if inputs_only:
            IOs_to_Plot = self.Input_IOs
        else:
            IOs_to_Plot = self.IOs
        
        for io in IOs_to_Plot:
            try:
                for t in range(len(vector)):
                    if vcd[tb_name+"."+io][t*strobe_ticks] == "1":
                        vector[t] = vector[t] + 2**(self.IO_pos[io])
            except KeyError:
                print("(WARN) "+tb_name+"."+io+" is NOT FOUND in VCD. Setting to default",self.IO_default[io])
                for t in range(len(vector)):
                    vector[t] = vector[t] + (2**(self.IO_pos[io]))*self.IO_default[io]

        #Write the resulting vector to output.glue    
        with open(output_file_name,'w') as write_file:
            write_file.write(",".join([str(x) for x in vector]))
            write_file.write("\n")
            write_file.write("//VCD_TIMEBASE_PICOSECONDS:"+str(vcd_timebase_ps)+"\n")
            write_file.write("//STROBE_PICOSECONDS:"+str(strobe_ps)+"\n")
            write_file.write("//GLUE_TIMESTEPS:"+str(len(vector))+"\n")


        print("Glue Converter finished!")
        print("Timebase of input file was:",vcd_timebase_ps,"ps")
        print("Length of input file was:",endtime*vcd_timebase_ps/1000000,"us")
        print("Strobe was:",strobe_ps,"ps")
        print("# of timesteps was:",len(vector))
        
    def parse_glue(self,glue_file_name):
        with open(glue_file_name,"r") as read_file:
            lines = read_file.readlines()

        #It processes the first line to create a list of integers named vector.(beren)
        vector = [int(x) for x in lines[0].strip().split(",")]

        #It processes the next two lines to extract floating point numbers (beren)
        #timebase_ps = float(lines[1].strip().split(":")[-1])
        for line in lines:
            if "STROBE" in line:   
                strobe_ps = float(line.strip().split(":")[-1])

        return GlueWave(vector,strobe_ps)

    #Plots a glue waveform using matplotlib. Useful for debugging.
    def plot_glue(self,glue_file,time_interval_ps=None):

        wave = self.parse_glue(glue_file)
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
        IO_waves = [None] * len(self.IOs)

        for i in range(len(self.IOs)):
            IO_waves[i] = [(v & 2**self.IO_pos[self.IOs[i]] > 0) for v in vector]

        #Plot
        self.plot_waves(IO_waves,self.IOs, strobe_ps)
        
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

        for line in iospec_lines:
            if len(line) > 1 and not line.startswith("//"): #Allow empty lines and comments using "//" in the iospec file.
                line_tokens = line.split(",")
                sig_name = line_tokens[0] #{name}
                self.IOs.append(sig_name)              
                self.IO_dir[sig_name] = line_tokens[1] #{I/O}
                if line_tokens[1] == "I":
                    self.Input_IOs.append(sig_name)
                else:
                    self.Output_IOs.append(sig_name)
                self.IO_pos[sig_name] = int(line_tokens[2]) #{position}

                #Support {optional default value}
                if len(line_tokens) > 3:
                    self.IO_default[sig_name] = int(line_tokens[3])
                else:
                    self.IO_default[sig_name] = 0
                    
        self.loaded_iospec_file = True
            
    def compare(self, wave1, wave2):

        print("Wave 1 len:",wave1.len)
        print("Wave 2 len:",wave2.len)
        
        print( "I/O             Dir.\tDC1 \tDC2 \tIn=Out?")
        for io in self.IOs:

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
                current_glue = filedialog.askopenfilename()
                print(current_glue)

            elif user_input == "bits":
                current_glue = filedialog.askopenfilename()
                clock_name = input("Clock name?").strip()
                data_name = input("Data name?").strip()
                outfile = input("Output file name?").strip()
                self.export_clocked_bitstream(self.parse_glue(current_glue), clock_name, data_name, outfile)

            elif user_input == "compare":
                if wave1 == None:
                    print("Getting Glue Wave 1...")
                    glue1 = filedialog.askopenfilename()
                    print("Getting Glue Wave 2...")
                    glue2 = filedialog.askopenfilename()
                    print("Glue 1:",glue1)
                    print("Glue 2:",glue2)
                    wave1 = self.parse_glue(glue1)
                    wave2 = self.parse_glue(glue2)
                    
                self.compare(wave1,wave2)

            elif user_input == "diff":
                if wave1 == None:
                    print("Getting Glue Wave 1...")
                    glue1 = filedialog.askopenfilename()
                    print("Getting Glue Wave 2...")
                    glue2 = filedialog.askopenfilename()
                    print("Glue 1:",glue1)
                    print("Glue 2:",glue2)
                    wave1 = self.parse_glue(glue1)
                    wave2 = self.parse_glue(glue2)

                diff_sig = input("Diff signal?").strip()

                #Allow multiple signals:
                if "," in diff_sig:
                    diff_sig = diff_sig.split(",")
                
                self.diff(wave1,wave2,diff_sig)

            elif user_input == "plotglue":
                if current_glue == None:
                    current_glue = filedialog.askopenfilename()
                self.plot_glue(current_glue)
                print("Done!")

            elif user_input == "vcd2input" or user_input == "vcd2golden":
                if current_vcd == None:
                    current_vcd = filedialog.askopenfilename()
                
                #vcd_timebase_ps = float(input("VCD timebase (ps)?"))
                #tb_name = input("tb name?").strip()
                strobe_ps = float(input("Strobe (ps)?"))
                output_file_name = input("Out file name?").strip()

                if "golden" in user_input:
                    inputs_only = False
                else:
                    inputs_only = True
                
                self.parse_VCD(current_vcd, strobe_ps, output_file_name, inputs_only)
                print("Done!")
                

            elif user_input == "exit" or user_input == "quit":
                break

            else:
                print("Unrecognized. Try one of these commands: ","; ".join(command_list))
                continue
                
                