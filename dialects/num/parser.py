# dialects/num/parser.py

import re
from dialects.base import Parser
from core.ir import Block, Word, Program, ModalState, Operation, LinearMove, RapidMove, ProgramEnd
from dialects.num.mapping import PARSE_MOTION_CODES, ABSOLUTE_MODE_CODES, UNIT_CODES, PROGRAM_END_CODES


LINE_NUMBER_PATTERN = re.compile(r'^N(\d+)\s*')
COMMENT_PATTERN = re.compile(r'\((.*?)\)')
TOKEN_PATTERN = re.compile(r'([A-Z])(-?\d+\.?\d*)')


class NumParser(Parser):
    """Parser del dialecto NUM: texto -> lista de Operations."""

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

        words = [Word(address=addr, value=float(val)) for addr, val in self._tokenize(line)]
        return Block(line_number=line_number, words=words, comment=comment)

    def _parse_program(self, text: str) -> Program:
        program = Program()
        for raw_line in text.splitlines():
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            program.blocks.append(self._parse_line(raw_line))
        return program

    # --- Step 2: Blocks -> Operations (semantic) ---

    def _interpret_block(self, block: Block, state: ModalState) -> Operation | None:
        g = block.get('G')

        # Declare type of movement
        if g is not None:
            g = int(g)
            if g in ABSOLUTE_MODE_CODES:
                state.absolute_mode = ABSOLUTE_MODE_CODES[g]
                return None
            if g in UNIT_CODES:
                state.units_mm = (UNIT_CODES[g] == "mm")
                return None
            if g in PARSE_MOTION_CODES:
                state.active_g = g

        # Declare feed for the movement
        f = block.get('F')
        if f is not None:
            state.last_feed = f

        # Get coordinates of the move
        x, y, z = block.get('X'), block.get('Y'), block.get('Z')

        active = g if g in PARSE_MOTION_CODES else state.active_g
        if active in PARSE_MOTION_CODES and (x is not None or y is not None or z is not None):
            op_class = PARSE_MOTION_CODES[active]
            if op_class is LinearMove:
                return LinearMove(x=x, y=y, z=z, feed=state.last_feed)
            elif op_class is RapidMove:
                return RapidMove(x=x, y=y, z=z)

        m = block.get('M')
        if m is not None and int(m) in PROGRAM_END_CODES:
            return ProgramEnd()

        return None

    def _interpret_program(self, program: Program) -> list[Operation]:
        state = ModalState()
        operations = []
        for index, block in enumerate(program.blocks):
            print(program.blocks)
            if index == 15:
                return operations
            op = self._interpret_block(block, state)
            if op is not None:
                operations.append(op)
        return operations
