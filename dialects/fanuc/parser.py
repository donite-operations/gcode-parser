# dialects/num/parser.py

import re
from dialects.base import Parser
from core.ir import (Block, Word, Program, HandlerContext, ModalState, Operation)
from dialects.fanuc.ir_handler.mapping import COMMAND_CODES

from dialects.fanuc.ir_handler.handler import FanucHandler

# LINE_NUMBER_PATTERN = re.compile(r'^N(\d+)\s*')
# COMMENT_PATTERN = re.compile(r'\((.*?)\)')
# self.TOKEN_PATTERN = re.compile(r'([A-Z])(-?\d+\.?\d*)')
# self.TOKEN_PATTERN = re.compile(r'([A-Z#])(#?-?\d+\.?\d*(?:=-?\d+\.?\d*)?)')
# self.TOKEN_PATTERN = re.compile(r'([A-Z#])(#\d+|\d+=-?\d+\.?\d*|-?\d+\.?\d*)')

class FanucParser(Parser):
    LINE_NUMBER_PATTERN = re.compile(r'^N(\d+)\s*')
    COMMENT_PATTERN = re.compile(r'\((.*?)\)')
    TOKEN_PATTERN = re.compile(r'([A-Z#])(#\d+|\d+=-?\d+\.?\d*|-?\d+\.?\d*)')

    """Parser: Num Text -> list[Operations]."""

    # --- Step 2: Blocks -> Operations (semantic) ---

    def _interpret_block(self, block: Block, state: ModalState) -> list[Operation]:
        if len(block.words) == 0:
            return

        operations = []
        for word in block.words:
            if word.address not in COMMAND_CODES :
                continue
            ctx = HandlerContext(command=word.address, value=word.value, state=state, block=block)
            op = FanucHandler.dispatch(ctx)

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
