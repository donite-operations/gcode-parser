# dialects/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from core.ir import (
    ModalState, Operation, Word
)

class Parser(ABC):
    @abstractmethod
    def parse(self, text: str) -> list[Operation]:
        """From G-Code text to an Operations list"""


class Writer(ABC):
    def reset(self) -> None:
        self.state = ModalState()
        self._next_n = self.LINE_NUMBER_STEP

    def write(self, program: list[list[Operation]]) -> str:
        """From Operations list to a G-Code text"""
        lines = [self._write_block(block) for block in program]
        return "\n".join(line for line in lines if line)

    def _write_block(self, block: list[Operation]) -> str:
        words: list[Word] = []
        seen: set[tuple[str, str]] = set()

        for operation in block:
            for word in self._dispatch_words(operation):
                key = (word.address, word.value)

                if key in seen:
                    continue

                seen.add(key)
                words.append(word)

        return self._render_block(words)
