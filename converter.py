# from dialects.base import parse_program

from dialects.num.parser import NumParser
from dialects.num.writer import NumWriter

from dialects.fanuc.parser import FanucParser
from dialects.fanuc.writer import FanucWriter

PARSERS = {
    "num": NumParser,
    "fanuc": FanucParser,
}

WRITERS = {
    "num": NumWriter,
    "fanuc": FanucWriter,
}


def convert(text: str, source_dialect: str, target_dialect: str) -> str:
    parser = PARSERS[source_dialect]()
    writer = WRITERS[target_dialect]()

    operations = parser.parse(text)
    return writer.write(operations)

def test():
    filename = "./examples/num_short.nc"

    with open(filename, "r") as file:
        contenido = file.read()

    parsed = NumParser().parse(contenido)
    print("")
    print(parsed)
    return
    with open("output.txt", "w") as file:
        for block in parsed:
            line = " ".join(
                f"{word}"
                for word in block.words
            )

            file.write( line + "\n")

test()