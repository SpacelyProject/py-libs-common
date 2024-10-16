#
#  Unit Test for the Glue Converter Class
#
import pytest
import os
from .glue_converter import GlueConverter, GlueWave, AsciiWave

import fnal_log_wizard as liblog

# A simple example waves dict with three signals.
TEST_WAVES_DICT = {"A": [0,1,0,1,0,1,0,1],
                   "B": [1,1,0,0,0,0,1,1],
                   "C": [0,0,0,1,1,1,1,1]}

# The correct vector that should be produced from TEST_WAVES_DICT,
# assuming that A -> bit 0, B -> bit 1, C -> bit 2                   
TEST_WAVES_VECTOR = [2, 3, 0, 5, 4, 5, 6, 7]

#The result of capturing "B" every time it is "clocked" by "A".
TEST_WAVE_B_CLOCKED = [1,0,0,1]

TEST_IOSPEC = os.path.join("nitoolbox","src","test_files","test_iospec.txt")

TEST_ASCII = os.path.join("nitoolbox","src","test_files","test_ascii.txt")


def compare_txt_files(file1, file2):
    with open(file1,"r") as read_file:
        file1_lines = [x.strip() for x in read_file.readlines()]
    with open(file2,"r") as read_file:
        file2_lines = [x.strip() for x in read_file.readlines()]
    if file1_lines == file2_lines:
        return True
    else:
        return False 

@pytest.fixture
def dbg_log():
    return liblog.PlainLogger(liblog.HandleOutputStrategy())

@pytest.fixture
def gc(dbg_log):
    return GlueConverter(iospec_file=TEST_IOSPEC, logger=dbg_log)
    
@pytest.fixture
def example_glue_wave(gc):
    return gc.dict2Glue(TEST_WAVES_DICT)
    
def test_dict2Glue(example_glue_wave):
    """Test that dict2Glue produces the correct vector from a wave dict."""
    assert example_glue_wave.vector == TEST_WAVES_VECTOR

def test_dict2Glue_write_ascii(gc):
    gc.dict2Glue(TEST_WAVES_DICT, output_mode=1)
    assert compare_txt_files("genpattern.txt",TEST_ASCII)
    os.remove("genpattern.txt")
  
def test_dict2Glue_write_glue(gc):
    glue_obj = gc.dict2Glue(TEST_WAVES_DICT, output_mode=2)
    read_glue = gc.read_glue("Caribou_apg_write_gen.glue")
    assert read_glue == glue_obj
    os.remove("Caribou_apg_write_gen.glue")
  
def test_ascii2Glue(gc, example_glue_wave):
    read_glue_wave = gc.ascii2Glue(TEST_ASCII)
    assert read_glue_wave == example_glue_wave

def test_ascii2Glue_write_glue(gc):
    glue_obj = gc.ascii2Glue(TEST_ASCII, output_mode=1)
    read_glue = gc.read_glue("Caribou_apg_write_gen.glue")
    assert read_glue == glue_obj
    os.remove("Caribou_apg_write_gen.glue")

def test_readback(gc, example_glue_wave):
    """Test that we can write a glue wave to file and read it back."""
    gc.write_glue(example_glue_wave, "test.glue")
    read_wave = gc.read_glue("test.glue")
    assert read_wave == example_glue_wave
    #Cleanup
    os.remove("test.glue")
    
def test_re_read(gc, example_glue_wave):
    """If you attempt to invoke gc.read_glue() on a GlueWave, it should do nothing (except print an error)
       and it should return the same GlueWave. This is incorrect usage, but we allow it."""
    gc.write_glue(example_glue_wave, "test.glue")
    read_wave = gc.read_glue("test.glue")
    re_read_wave = gc.read_glue(read_wave)
    assert re_read_wave == example_glue_wave
    os.remove("test.glue")
    
def test_get_bitstream(gc, example_glue_wave):
    """Test gc.get_bitstream"""
    for key in TEST_WAVES_DICT.keys():
        assert gc.get_bitstream(example_glue_wave, key) == TEST_WAVES_DICT[key]
        
def test_get_clocked_bitstream(gc, example_glue_wave):
    assert gc.get_clocked_bitstream(example_glue_wave, "A","B") == TEST_WAVE_B_CLOCKED
    
    
def test_set_bit(gc, example_glue_wave):
    
    example_glue_wave.set_bit(4,0,1)
    example_glue_wave.set_bit(5,0,0)
    
    compare_vector = [2, 3, 0, 5, 5, 4, 6, 7]
    
    assert example_glue_wave.vector == compare_vector
    
    