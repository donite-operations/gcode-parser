# from dialects.base import parse_program

from dialects.num.parser import NumParser
from dialects.num.ir_writer.writer import NumWriter

from dialects.fanuc.parser import FanucParser
from dialects.fanuc.ir_writer.writer import FanucWriter

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
    # return writer.write(operations)

def test():
    filename = "./examples/num_ares.nc"

    with open(filename, "r") as file:
        contenido = file.read()

    parsed = NumParser().parse(contenido)
    with open("ir_output.txt", "w") as file:
        for block in parsed:
            if len(block) != 0 :
                file.write(str(block) + "\n")

def read_file(filepath):
    filename = filepath

    with open(filename, "r") as file:
        content = file.read()

    return content

def create_file(output: str, parsed):
    with open(output, "w") as file:
        file.write(parsed)


def convertion_test() -> str:
    content = read_file("./examples/fanuc_ares.nc")
    parser = FanucParser()
    writer = FanucWriter()

    operations = parser.parse(content)
    writer_output = writer.write(operations)
    create_file("fanuc_test.txt", writer_output)
    return writer.write(operations)


def block_lecture_test():
    filename = "./examples/fanuc_ares.nc"

    with open(filename, "r") as file:
        contenido = file.read()

    parsed = FanucParser().parse(contenido)
    with open("ir_output.txt", "w") as file:
        for block in parsed:
            file.write(str(block) + "\n")

convertion_test()
