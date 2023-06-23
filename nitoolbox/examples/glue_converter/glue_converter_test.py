# glue_converter test cases #

import sys
import os
sys.path.append(os.path.abspath("..\\..\\src\\fnal_ni_toolbox"))
from glue_converter import *

DATA_FILE_PATH = "C:\\Users\\aquinn\\OneDrive - Fermi National Accelerator Laboratory\\Resources\\Software\\Glue_Data_Files"

INPUT_VCD = DATA_FILE_PATH + "\\xrocket1_test.vcd"

# IOSPEC_FILE = "sprocket3a_iospec.txt"
IOSPEC_FILE = "sprocket1_iospec_demo.txt"

OUTPUT_FILE = DATA_FILE_PATH + "\\xrocket1_input.glue"

TESTBENCH_NAME = "pixelAI_top_2Q_tb"

# STROBE in picoseconds
STROBE_PS = 5000  # 5 ns is the minimum

# Timebase of your VCD in ps. 
TIMEBASE_PS = 0.001


gc = GlueConverter(IOSPEC_FILE)
    
gc.parse_VCD(INPUT_VCD, TESTBENCH_NAME, TIMEBASE_PS, STROBE_PS, OUTPUT_FILE)

gc.plot_glue(OUTPUT_FILE)
