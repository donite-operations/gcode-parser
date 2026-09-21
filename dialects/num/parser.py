import re
from dialects.base import Parser
from core.ir import (Block, Word, Program, HandlerContext, ModalState, Operation)
from dialects.num.ir_handler.mapping import COMMAND_CODES
from dialects.num.ir_handler.handler import NumHandler

class NumParser(Parser) :
    TOKEN_PATTERN = re.compile(r'([A-Z]{1,2}|#)(#\d+|\d+\s*=\s*-?\d+\.?\d*|-?\d+\.?\d*)')
    COMMENT_PATTERN =  re.compile(r'\((.*?)\)')          # sin cambios
    LINE_NUMBER_PATTERN = re.compile(r'^N(\d+)\s*')

    VAR_MARKER_PATTERN = re.compile(r'^(VAR|ENDV)$')
    VAR_ASSIGN_PATTERN = re.compile(r'^\[(\w+)\]\s*=\s*(.+)$')
    CONDITIONAL_PATTERN = re.compile(
        r'^G79\s+\[(\w+)\]\s*([<>=]+)\s*(-?\d+\.?\d*)\s*N(\d+)$'
    )

    """Parser: Num Text -> list[Operations]."""
    def _parse_line(self, raw_line: str) -> Block:
        line = raw_line.strip()

        comment = None
        match = self.COMMENT_PATTERN.search(line)
        if match:
            comment = match.group(1)
            line = self.COMMENT_PATTERN.sub('', line).strip()

        if self.VAR_MARKER_PATTERN.match(line):
            return Block(words=[Word(address='VAR_MARKER', value=line)], comment=comment)

        match = self.VAR_ASSIGN_PATTERN.match(line)
        if match:
            name, expr = match.groups()
            return Block(words=[Word(address=f'[{name}]', value=expr)], comment=comment)

        match = self.CONDITIONAL_PATTERN.match(line)
        if match:
            name, op, threshold, target = match.groups()
            return Block(words=[
                Word(address='G79', value=f'{name}{op}{threshold}->{target}')
            ], comment=comment)

        return super()._parse_line(raw_line)

    # --- Step 2: Blocks -> Operations (semantic) ---

    def _interpret_block(self, block: Block, state: ModalState) -> list[Operation]:
        if len(block.words) == 0:
            return

        operations = []
        for word in block.words:
            if word.address not in COMMAND_CODES :
                continue
            ctx = HandlerContext(command=word.address, value=word.value, state=state, block=block)
            op = NumHandler.dispatch(ctx)

            if op is not None:
                operations.append(op)

        return operations

    def _interpret_program(self, program: Program) -> list[Operation]:
        state = ModalState()
        operations = []

        for index, block in enumerate(program.blocks):
            # if (block.line_number)  != None and block.line_number > 34:
            #     return operations
            interpreted_block = None
            interpreted_block = self._interpret_block(block, state)
            # print(interpreted_block)
            if interpreted_block is not None:
                operations.append(interpreted_block)
        return operations
