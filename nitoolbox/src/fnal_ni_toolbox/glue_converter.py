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


class GlueConverter():

    #Initialize Glue Converter.
    #You ALWAYS need an I/O spec file to interpret or write Glue files, so we initialize it
    #here. But we don't immediately ask for a VCD file / timebase bc you may want to use multiple
    #of those.
    def __init__(self, iospec_file):
        self.parse_iospec_file(iospec_file)



    # parse_VCD - Parses a VCD file into a glue file.
    # PARAMS:
    #       vcd_file_name - something.vcd
    #       tb_name - Name of the top-level testbench in your VCD
    #       vcd_timebase_ps - Timebase of your VCD file in picoseconds
    #       strobe_ps - Basically the timebase of the output glue file in picoseconds. Should
    #                   equal GlueFPGA clock speed.
    #       output_file_name - something.glue
    def parse_VCD(self, vcd_file_name, tb_name, vcd_timebase_ps, strobe_ps, output_file_name):
        # Use a library function to parse the input VCD
        vcd = VCDVCD(vcd_file_name)

        #Assume that all signals have the same endtime.
        endtime = vcd[vcd.signals[0]].endtime

        #The length of the output vector is endtime/STROBE
        strobe_ticks = int(strobe_ps/vcd_timebase_ps)
        vector = [0] * int(endtime/strobe_ticks)
        
        # For each timestep, find out if each input is high, and if it is,
        # then set that bit in the output vector high by adding 2^(pos) to
        # that vector.
        for io in self.Input_IOs:
            try:
                for t in range(len(vector)):
                    if vcd[tb_name+"."+io][t*strobe_ticks] == "1":
                        vector[t] = vector[t] + 2**(self.IO_pos[io])
            except KeyError:
                print("(WARN) "+tb_name+"."+io+" is NOT FOUND in VCD. Setting to default",self.IO_default[io])


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
        
        

    #Plots a glue waveform using matplotlib. Useful for debugging.
    def plot_glue(self,glue_file,time_interval_ps=None):

        with open(glue_file,"r") as read_file:
            lines = read_file.readlines()

        #It processes the first line to create a list of integers named vector.(beren)
        vector = [int(x) for x in lines[0].strip().split(",")]
        #It processes the next two lines to extract floating point numbers (beren)
        timebase_ps = float(lines[1].strip().split(":")[-1])
        strobe_ps = float(lines[2].strip().split(":")[-1])

        if time_interval_ps is not None:
            start_time = time_interval_ps[0]
            end_time = time_interval_ps[1]
            vector = vector[int(start_time/strobe_ps):int(end_time/strobe_ps)]
        else:
            start_time = 0
            end_time = len(vector)*strobe_ps

        #Create the time vector in nanoseconds.
        time_vector = [i*strobe_ps/1000 for i in range(len(vector))]

        IO_wave = [None] * len(self.IOs)

        #beren.this line is updates to work with more IO.
        #beren. Number of rows = number of IOs, dim of the figure sclaed according to the number of IOs
        #beren. x-axis is shared among all subplots.
        # fig,ax = plt.subplots(len(IOs))
        fig, axes = plt.subplots(nrows=len(self.IOs), figsize=(10, 2 * len(self.IOs)), sharex=True)
        fig.subplots_adjust(hspace=0.5)


        #Get an individual wave for each IO which is 1 where that IO is
        #1 and zero otherwise.
        # for i in range(len(IOs)):
        for i, ax in enumerate(axes):#beren
            IO_wave[i] = [(v & 2**self.IO_pos[self.IOs[i]] > 0) for v in vector]

            # ax[i].set_ylabel(IOs[i].split(".")[-1], rotation='horizontal')
            # ax[i].plot(time_vector, IO_wave[i])
            
            #beren. I put spaces between the y-axis name and the IO name
            ax.set_ylabel(self.IOs[i] + "                ", rotation='horizontal') #beren
            ax.step(time_vector, IO_wave[i])#beren
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
            
        
    


