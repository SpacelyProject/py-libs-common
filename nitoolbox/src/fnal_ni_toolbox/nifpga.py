from __future__ import annotations
from typing import Final
import nifpga
from fnal_log_wizard import Logger
import ast

# Random dev notes:
#  - add IRQ when each loop finishes writing (so we can change Wrtie_to/from_Mem = False again)


class NiFpgaError(IOError):
    pass


class NiFpga:
    def __init__(self, logger: Logger, resource: str):
        self._log = logger
        self._resource = resource
        self._session: nifpga.Session = None
        self._running: bool = False
        self._fifos: dict[str, NiFifo] = {}

    def start(self, bitfile: str) -> None:
        if self._running:
            self._log.debug(f"FPGA already running - resetting before new bitfile")
            self.reset()

        self.close()  # otherwise it will leak memory
        self._session = nifpga.Session(bitfile, self._resource, no_run=True)
        self.reset()  # ensure clean state
        self._session.run()

    def reset(self) -> None:
        if self._session is None:
            self._log.error("Cannot reset FPGA: session not running")
            raise NiFpgaError("Reset failed - session not running")
        self._session.reset()

    def close(self) -> None:
        if self._session is None:
            return
        self._log.info("Closing NI FPGA session")
        self._session.close()

    def has_fifo(self, name: str) -> bool:
        return name in self._session.fifos

    def get_fifo(self, name: str) -> NiFifo:
        if not self.has_fifo(name):
            if self.has_register(name):
                raise NiFpgaError(f"There's no FIFO named \"{name}\" - did you mean to use get_register({name})?")
            else:
                raise NiFpgaError(f"There's no FIFO named \"{name}\"")

        if name not in self._fifos.keys():
            self._fifos[name] = NiFifo(self._log, self._session.fifos[name])

        return self._fifos[name]

    def list_fifos(self) -> list[str]:
        return self._session.registers.keys()

    def has_register(self, name: str) -> bool:
        return name in self._session.registers

    def get_register(self, name: str) -> NiRegister:
        if not self.has_register(name):
            if self.has_fifo(name):
                raise NiFpgaError(f"There's no register named \"{name}\" - did you mean to use get_fifo({name})?")
            else:
                raise NiFpgaError(f"There's no register named \"{name}\"")

        return NiRegister(self._session.registers[name])

    def list_registers(self) -> list[str]:
        return self._session.registers.keys()

    def _stop_fifos(self) -> None:
        """Discards all used FIFOs"""
        for name, fifo in self._fifos.items():
            self._log.debug(f"NI FPGA: destroying {name} FIFO")
            fifo.stop()

        self._fifos = {}
        self._log.info("NI FPGA FIFOs stopped")

    def __del__(self):
        if self._session is None:
            self._log.debug("NI FPGA: no session open, skipping de-init")
            return

        self._stop_fifos()
        self.reset()
        self._session.abort()
        self.close()

class NiFifo:
    def __init__(self, logger: Logger, ref, flow_control=True):
        self.log = logger
        self.ref: nifpga = ref  # nifpga._FIFO object; I don't think we can import it for typing
        self.running: bool = False
        self.flow_control: bool = flow_control
        self._size: int | None = None
        self._start()

    def set_flow_control(self, enabled: bool = True) -> None:
        """Enables/disables FIFO flow control"""
        self.flow_control = enabled
        if not self.running:
            return

        self.log.debug(f"{'Enabling' if enabled else 'Disabling'} \"{self.ref.name}\" FIFO flow control")
        self.ref.flow_control = nifpga.FlowControl.EnableFlowControl if enabled \
                                else nifpga.FlowControl.DisableFlowControl

    @property
    def size(self) -> int | None:
        """Returns default size for FIFO operations (if available)"""
        return self._size

    @size.setter
    def size(self, size: int) -> None:
        """Sets default size for FIFO operations"""
        self._size = size

    def read(self, size=None, timeout=0) -> list[str | int | float]:
        """Reads data from the FIFO

           If the size for the FIFO was set (using set_size()) all reads can be
           made without specifying the "size" parameter.
        """
        if not self.running:
            raise NiFpgaError(f"Cannot read - FIFO \"{self.ref.name}\" is not running")

        if size is None:
            if self._size is None:
                raise RuntimeError(f"Cannot read FIFO \"{self.ref.name}\" without specifying read size")
            size = self._size

        return self.ref.read(size, timeout)

    def write(self, data: list, timeout=0) -> None:
        """Write elements to the FIFO"""
        if not self.running:
            raise NiFpgaError(f"Cannot write - FIFO \"{self.ref.name}\" is not running")

        if self._size is not None and len(data) > self._size:
            raise ValueError(f"Cannot write {len(data)} elements to FIFO \"{self.ref.name}\" of size {self._size}")

        self.ref.write(data, timeout)

    def _start(self) -> None:
        if self.running:
            return

        self.ref.stop()  # ensure clean state when multi-session
        self.set_flow_control(self.flow_control)
        self.ref.start()
        self.running = True

    def stop(self) -> None:
        if not self.running:
            return

        self.log.blocking(f"Stopping \"{self.ref.name}\" FIFO")
        self.ref.stop()
        self.running = False
        self.log.block_res(True)


class NiRegister:
    _numeric_ranges: Final[dict[nifpga.DataType, tuple[int, int]]] = {
        nifpga.DataType.I8: (-128, 127),
        nifpga.DataType.U8: (0, 255),
        nifpga.DataType.I16: (-32768, 32767),
        nifpga.DataType.U16: (0, 65535),
        nifpga.DataType.I32: (-2147483648, 2147483647),
        nifpga.DataType.U32: (0, 4294967295),
        nifpga.DataType.I64: (-9223372036854775808, 9223372036854775807),
        nifpga.DataType.U64: (0, 18446744073709551615)
    }

    def __init__(self, ref):
        self.ref = ref

    @property
    def type(self) -> nifpga.DataType:
        return self.ref.datatype

    @property
    def value(self) -> int | float | bool | list:
        return self.ref.read()

    @value.setter
    def value(self, value: int | float | bool | list) -> None:
        if type(value) is list:
            for wrappedVal in value:
                self._ensure_type(wrappedVal)

        self.ref.write(value)

    def _ensure_type(self, value) -> None:
        val_type = type(value)

        if self.ref.datatype == nifpga.DataType.Bool:
            if val_type != 'bool':
                raise ValueError(f"Register \"{self.ref.name}\" expected bool but {val_type}")
            return

        if self.ref.datatype in self._numeric_ranges.keys():
            if val_type != 'int':
                raise ValueError(f"Register \"{self.ref.name}\" expected an integer but {val_type}")

            if value < self._numeric_ranges[self.ref.datatype][0] or value > self._numeric_ranges[self.ref.datatype][1]:
                raise ValueError(f"Value {value} is out of range for \"{self.ref.name}\" register "
                                 f"(<={self._numeric_ranges[self.ref.datatype][0]} ; >={self._numeric_ranges[self.ref.datatype][1]})")
            return

        raise ValueError(
            f"Register \"{self.ref.name}\" expected a value of type {self.ref.datatype} but got {val_type}")


class NiFpgaDebugger:
    def __init__(self, logger: Logger, fpga: NiFpga):
        self._log = logger
        self._fpga = fpga

    def cast(self, my_data: str | int | float, my_type):
        if type(my_data) == my_type:
            return my_data
        if my_type == int:
            return int(my_data)
        elif my_type == bool:
            return ast.literal_eval(my_data)
        elif my_type == list:
            return eval(my_data)  # Allow list construction.
        else:
            raise NiFpgaError(f"Casting to unknown type: {my_type}")

    def interact(self, operation: str | None = None, choice: int | str | None = None, user_data=None):
        registers = self._fpga.list_registers()
        fifos = self._fpga.list_fifos()
        all_fpga_entities = list(registers) + list(fifos)

        if operation is None or choice is None:
            choice = self._pick_target(all_fpga_entities)
            if choice is None:
                print("-- Aborted")
                return
            operation, index = choice

        if operation not in ['r', 'w']:
            raise NiFpgaError(f"Invalid operation \"{operation}\"")

        #interact() should be able to accept str names or int indices
        if type(choice) == str:
            pass
        elif type(choice) == int:
            if choice < 0 or choice > len(all_fpga_entities):
                raise NiFpgaError(f"Invalid index \"{index}\" for entity")
            choice = all_fpga_entities[choice]
        elif type(choice) == None:
            raise NiFpgaError(f"You can't interact with 'None' :p")
        
        if self._fpga.has_register(choice):
            return self._interact_with_register(choice, operation, user_data)
        elif self._fpga.has_fifo(choice):
            return self._interact_with_fifo(choice, operation, user_data)
        else:
            raise NiFpgaError(f"{choice} is neither a register nor a FIFO?!")

    def _interact_with_register(self, name: str, operation: str, user_data: any) -> any:
        reg = self._fpga.get_register(name)
        reg_val = reg.value
        if operation == 'r':
            return reg_val

        if user_data is None:
            user_data = input("Data to write >>> ").strip()
        reg.value = self.cast(user_data, type(reg_val))

    def _interact_with_fifo(self, name: str, operation: str, user_data: any) -> any:
        fifo = self._fpga.get_fifo(name)

        if operation == 'r':
            fifo_size = 16384 if fifo.size is None else 16384  # todo: a sensible default, but maybe it should ask?
            return fifo.read(fifo_size)

        if user_data is None:
            user_data = input("Data to write >>> ").strip()
            fifo.write(self.cast(user_data, list))

    def _pick_target(self, elements: list) -> tuple[str, int] | None:
        assert any(elements.count(el) > 1 for el in elements) is False, "List of elements cannot contain duplicates!"

        idx = -1
        for entity in elements:
            idx += 1

            if self._fpga.has_register(entity):
                reg = self._fpga.get_register(entity)
                reg_val = reg.value

                print(f"{idx}\tRegister \"{entity}\" (type: {reg.type}", end='\t')
                if type(reg_val) is list:
                    print(f"sum(cur_val): {sum(reg_val)}")
                else:
                    print(f"cur_val: {reg_val}")

            elif self._fpga.has_fifo(entity):
                fifo = self._fpga.get_fifo(entity)
                print(f"{idx}\tFIFO \"{entity}\" (size: {fifo.size}", end='\t')

        # Get User input
        print(f"Pick the target; prepend it with \"r\" (e.g. r3) to read or with \"w\" (e.g. w3) to write")

        while True:
            user_idx = input(">>> ").strip()
            user_idx_len = len(user_idx)

            if user_idx_len < 1:
                return
            elif user_idx_len < 2 or (user_idx[0] != 'r' and user_idx[1] != 'w'):
                print("Invalid syntax")
                continue

            real_idx = int(user_idx[:+1])
            if real_idx < 0 or real_idx > len(elements):
                print(f"Index out of bounds")
                continue

            return user_idx[0], real_idx
