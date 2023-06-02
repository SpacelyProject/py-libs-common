# @todo this should be split into seprate modules/files

import sys
import platform
from datetime import datetime
from . import levels

class OutputStrategy:
    def write_bytes(self, data: str) -> None:
        pass


class HandleOutputStrategy(OutputStrategy):
    def __init__(self, fhandle=sys.stderr):
        self.fhandle = fhandle

    def write_bytes(self, data: str) -> None:
        self.fhandle.write(data)
        self.fhandle.flush()
        # print(data, end='', flush=True, file=output)

    @classmethod
    def create_with_stderr(cls) -> OutputStrategy:
        return cls(sys.stderr)

    @classmethod
    def create_with_stdout(cls) -> OutputStrategy:
        return cls(sys.stdout)


class FileOutputStrategy(HandleOutputStrategy):
    def __init__(self, path: str, fmode: str = 'a'):
        self.file = open(path, fmode)
        super().__init__(self.file)
        self.write_bytes("#FILE OPENED#\n")

    def __del__(self):
        self.write_bytes("#FILE CLOSED#\n")
        self.file.close()


class Logger:
    """
    Common interface for all loggers
    """
    def emerg(self, text, format: bool = True) -> None:
        pass

    def alert(self, text, format: bool = True) -> None:
        pass

    def critical(self, text, format: bool = True) -> None:
        pass

    def error(self, text, format: bool = True) -> None:
        pass

    def warning(self, text, format: bool = True) -> None:
        pass

    def notice(self, text, format: bool = True) -> None:
        pass

    def info(self, text, format: bool = True) -> None:
        pass

    def debug(self, text, format: bool = True) -> None:
        pass

    def blocking(self, text, level: int | None = None) -> None:
        pass

    def block_res(self, status: bool = True, level: int | None = None) -> None:
        pass


class ChainLogger(Logger):
    def __init__(self, loggers: list = []):
        self.loggers = loggers

    def emerg(self, text, format: bool = True) -> None:
        self.__call_chain('emerg', {'text': text, 'format': format})

    def alert(self, text, format: bool = True) -> None:
        self.__call_chain('alert', {'text': text, 'format': format})

    def critical(self, text, format: bool = True) -> None:
        self.__call_chain('critical', {'text': text, 'format': format})

    def error(self, text, format: bool = True) -> None:
        self.__call_chain('error', {'text': text, 'format': format})

    def warning(self, text, format: bool = True) -> None:
        self.__call_chain('warning', {'text': text, 'format': format})

    def notice(self, text, format: bool = True) -> None:
        self.__call_chain('notice', {'text': text, 'format': format})

    def info(self, text, format: bool = True) -> None:
        self.__call_chain('info', {'text': text, 'format': format})

    def debug(self, text, format: bool = True) -> None:
        self.__call_chain('debug', {'text': text, 'format': format})

    def blocking(self, text, level: int | None = None) -> None:
        self.__call_chain('blocking', {'text': text, 'level': level})

    def block_res(self, status: bool = True, level: int | None = None) -> None:
        self.__call_chain('block_res', {'level': level})

    def add_logger(self, logger: Logger) -> None:
        self.loggers.append(logger)

    def __call_chain(self, method: str, args: dict) -> None:
        for logger in self.loggers:
            getattr(logger, method)(**args)


class PlainLogger(Logger):
    LV_MAP = ["EMRG", "ALRT", "CRIT", "ERR", "WARN", "NOTI", "INF", "DBG"]

    def __init__(self, output_strategy: OutputStrategy):
        self.output = output_strategy
        self.last_msg = None
        self.curr_block = None

    def emerg(self, text, format: bool = True) -> None:
        self._log(text, levels.LOG_EMERG, dt_mark=format, lv_mark=format)

    def alert(self, text, format: bool = True) -> None:
        self._log(text, levels.LOG_ALERT, dt_mark=format, lv_mark=format)

    def critical(self, text, format: bool = True) -> None:
        self._log(text, levels.LOG_CRIT, dt_mark=format, lv_mark=format)

    def error(self, text, format: bool = True) -> None:
        self._log(text, levels.LOG_ERR, dt_mark=format, lv_mark=format)

    def warning(self, text, format: bool = True) -> None:
        self._log(text, levels.LOG_WARN, dt_mark=format, lv_mark=format)

    def notice(self, text, format: bool = True) -> None:
        self._log(text, levels.LOG_NOTICE, dt_mark=format, lv_mark=format)

    def info(self, text, format: bool = True) -> None:
        self._log(text, levels.LOG_INFO, dt_mark=format, lv_mark=format)

    def debug(self, text, format: bool = True) -> None:
        self._log(text, levels.LOG_DEBUG, dt_mark=format, lv_mark=format)

    def blocking(self, text, level: int | None = None) -> None:
        """Starts a blocking operation"""
        if level == None:
            level = levels.LOG_DEBUG

        if text is None:
            self._log(self.curr_block, level, nl=False)
        else:
            text = f"{text}... "
            self._log(text, level, nl=False)
            self.curr_block = text

    def block_res(self, status: bool = True, level: int | None = None) -> None:
        """Finishes a blocking operation with result"""
        if self.curr_block is None:
            self.notice("BUG: bloc_res() called without blocking()")
            return

        if level == None:
            level = levels.LOG_DEBUG

        # if something was printed during the block we need to repeat it
        if self.last_msg != self.curr_block and self.last_msg is not None:
            # print(f"REPEAT BLOCK! LM>>{self.last_msg}<< LB>>{self.curr_block}<<")
            self.blocking(None, level)

        self.curr_block = None
        text = "[OK]" if status else "[ERR]"
        self._print_level(f"{text}\n", level)

    def _log(self, text, level: int, dt_mark: bool = True, lv_mark: bool = True, nl: bool = True) -> None:
        """Prints something with a correct debug level"""
        if self.curr_block is not None:
            if self.curr_block == self.last_msg:  # we last printed a msg w/o NL (i.e. blocking one)
                self._print_level("\n", level)
        self.last_msg = text

        if dt_mark:
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            text = f"<{now}> {text}"
        if lv_mark:
            text = f"<{self.LV_MAP[level]}> {text}"

        if nl:
            text = f"{text}\n"

        self._print_level(text, level)

    def _print_level(self, text: str, level: int) -> None:
        self.output.write_bytes(text)
        pass


class AnsiTerminalLogger(PlainLogger):
    """
    ANIS-aware logger that is intended to print to a TTY terminal. It also supports limiting log levels.
    """
    COL_CLR = "\033[0m"
    COL_MAP = ["\033[1m\033[0;31m", "\033[1m\033[0;31m", "\033[0;31m", "\033[1;31m", "\033[1;33m", "\033[0;32m", "",
               "\033[3m\033[1;30m"]

    def __init__(self, output_strategy: OutputStrategy, max_level: int = 9999, ansi: bool | None = None):
        super().__init__(output_strategy)
        self.max_level = max_level
        self.ansi = sys.stdout.isatty() if ansi is None else ansi
        if self.ansi:
            self._configure_term()

    def _print_level(self, text: str, level: int) -> None:
        if self.max_level < level:
            return

        if self.ansi:
            text = f"{self.COL_MAP[level]}{text}{self.COL_CLR}"
        print(text, end='', flush=True, file=sys.stderr)

    def _configure_term(self) -> None:
        if platform.system() == "Windows":
            win32 = __import__("ctypes").windll.kernel32
            win32.SetConsoleMode(win32.GetStdHandle(-11), 7)
