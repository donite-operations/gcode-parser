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
                # print(block)
                file.write(str(block) + "\n")

def read_file(filepath):
    filename = filepath

    with open(filename, "r") as file:
        content = file.read()

    return content

def create_file(output: str, parsed):
    with open(output, "w") as file:
        file.write(parsed)


def convert_test() -> str:
    content = read_file("./examples/num_ares.nc")
    parser = FanucParser()
    writer = NumWriter()

    operations = parser.parse(content)
    writer_output = writer.write(operations)
    create_file("new_test.txt", writer_output)
    # return writer.write(operations)

convert_test()