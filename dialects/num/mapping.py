from core.ir import RapidMove, LinearMove, ProgramEnd

MOTION_CODES = {
    0: RapidMove,
    1: LinearMove,
}

# Códigos que indican modo absoluto/incremental
ABSOLUTE_MODE_CODES = {90: True, 91: False}

# Códigos de unidades
UNIT_CODES = {21: "mm", 20: "inch"}

# Qué valores de M indican fin de programa
PROGRAM_END_CODES = {30, 2}

