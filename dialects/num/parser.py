# dialects/num/parser.py

import re
from dialects.base import Parser
from core.ir import Block, Word, Program, ModalState, Operation, LinearMove, RapidMove, ProgramEnd
from dialects.num.mapping import (
    G_MOTION_CODES, G_MODE_CODES, G_UNIT_CODES, PROGRAM_END_CODES, 
    COMMAND_CODES
)

from dialects.num.handler import NumHandler

LINE_NUMBER_PATTERN = re.compile(r'^N(\d+)\s*')
COMMENT_PATTERN = re.compile(r'\((.*?)\)')
# TOKEN_PATTERN = re.compile(r'([A-Z])(-?\d+\.?\d*)')
# TOKEN_PATTERN = re.compile(r'([A-Z#])(#?-?\d+\.?\d*(?:=-?\d+\.?\d*)?)')
TOKEN_PATTERN = re.compile(r'([A-Z#])(#\d+|\d+=-?\d+\.?\d*|-?\d+\.?\d*)')

class NumParser(Parser):
    """Parser: Num Text -> list[Operations]."""

    def parse(self, text: str) -> list[Operation]:
        program = self._parse_program(text)
        return self._interpret_program(program)

    # --- Step 1: texto -> Blocks (syntax) ---

    def _tokenize(self, line: str) -> list[tuple[str, str]]:
        return TOKEN_PATTERN.findall(line)

    def _parse_line(self, raw_line: str) -> Block:
        line = raw_line.strip()

        comment = None
        match = COMMENT_PATTERN.search(line)
        if match:
            comment = match.group(1)
            line = COMMENT_PATTERN.sub('', line)

        line_number = None
        match = LINE_NUMBER_PATTERN.match(line)
        if match:
            line_number = int(match.group(1))
            line = LINE_NUMBER_PATTERN.sub('', line)

        tokens = self._tokenize(line)

        words = []
        adresses_list = []

        for addr, val in tokens:
            words.append(Word(address=addr, value=val))
            adresses_list.append(addr)

        return Block(
            line_number=line_number,
            words=words,
            comment=comment,
            adresses_list=adresses_list
        )

    def _parse_program(self, text: str) -> Program:
        program = Program()
        for raw_line in text.splitlines():
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            program.blocks.append(self._parse_line(raw_line))
        return program

    # --- Step 2: Blocks -> Operations (semantic) ---

    def _interpret_block(self, block: Block, state: ModalState) -> list[Operation]:
        if len(block.adresses_list) == 0:
            return

        operations = []

        for adress in block.adresses_list:
            if adress not in COMMAND_CODES :
                continue

            op = NumHandler.dispatch(adress, block.get(adress), state)
            if op is not None:
                operations.append(op)


    def _interpret_program(self, program: Program) -> list[Operation]:
        state = ModalState()
        operations = []
        for index, block in enumerate(program.blocks):
            print(block)
            print("")
            if (block.line_number)  != None and block.line_number > 34:
                return operations
            op = None
            # op = self._interpret_block(block, state)
            if op is not None:
                operations.append(op)
        return operations
