import argparse
import dataclasses
import enum
import getpass
import re
import sys
import typing

import pexpect

VARIABLE_START = r"([^{]?){"
VARIABLE_MIDDLE = r"([a-z_][a-z_0-9]+)"
VARIABLE_END = r"}([^}]?)"

VARIABLE_PATTERN = re.compile(VARIABLE_START + VARIABLE_MIDDLE + VARIABLE_END)


class InstructionType(enum.Enum):
    Command = re.compile(r"^[ \t]*cmd:([^\n\r]+)$")
    Expect = re.compile(r"^[ \t]*expect:([^\n\r]+)$")
    Input = re.compile(r"^[ \t]*input:([^\n\r]+)$")
    InputSecret = re.compile(r"^[ \t]*input!:([^\n\r]+)$")
    Send = re.compile(r"^[ \t]*send:([^\n\r]+)$")
    Interactive = re.compile(r"^[ \t]*interactive:([^\n\r]+)$")


@dataclasses.dataclass
class Instruction:
    type: InstructionType
    content: str
    prompt: str


def get_args():
    parser = argparse.ArgumentParser("automate expect", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--prompt", type=str, default="$")
    parser.add_argument("--interact", action="store_true")
    parser.add_argument("file", nargs=1)
    return parser.parse_args()


def parse_instructions(lines: typing.List[str], prompt: str) -> typing.List[Instruction]:
    instructions = []
    for i, line in enumerate(lines):
        if not line.strip():
            continue

        if line.strip().startswith("#"):
            continue

        instruction = _detect_instruction(line, prompt)
        if not instruction:
            raise ValueError(f"Unknown command on line {i + 1}: {line.strip()}")

        instructions.append(instruction)

    return instructions


def _detect_instruction(line: str, prompt: str) -> typing.Optional[Instruction]:
    for instruction_type in InstructionType:
        matched = instruction_type.value.match(line)
        if not matched:
            continue

        return Instruction(type=instruction_type, content=matched.group(1).strip(), prompt=prompt)

    return None


def _assign_variables(variables: typing.Dict[str, str], items: typing.List[str], secret: bool):
    for i in items:
        _assign_variable(variables, i, secret)


def _assign_variable(variables: typing.Dict[str, str], variable: str, secret: bool):
    message = f"Input {'secret ' if secret else ''}value for \"{variable}\":"
    if secret:
        variables[variable] = getpass.getpass(message)
    else:
        print(message)
        variables[variable] = input()


def _get_variables(command: str) -> typing.List[str]:
    return [matched.groups()[1] for matched in VARIABLE_PATTERN.finditer(command)]


def _expand_variables(variables: typing.Dict[str, str], command: str) -> str:
    temp_command = command
    items = _get_variables(temp_command)
    for i in items:
        value = variables.get(i)
        if not value:
            raise ValueError(f"variable {i} is not assigned in command: {temp_command}")

        temp_command = re.sub(VARIABLE_START + f"{i}" + VARIABLE_END, f"\\1{value}\\2", temp_command)

    return temp_command


def execute_one_instruction(child: pexpect.spawn, variables: typing.Dict[str, str], instruction: Instruction):
    if instruction.type == InstructionType.Command:
        child.expect(instruction.prompt)
        child.sendline(_expand_variables(variables, instruction.content))
    elif instruction.type == InstructionType.Input:
        child.expect(instruction.prompt)
        _assign_variables(variables, _get_variables(instruction.content), False)
    elif instruction.type == InstructionType.InputSecret:
        child.expect(instruction.prompt)
        _assign_variables(variables, _get_variables(instruction.content), True)
    elif instruction.type == InstructionType.Expect:
        child.expect(_expand_variables(variables, instruction.content))
    elif instruction.type == InstructionType.Send:
        child.sendline(_expand_variables(variables, instruction.content))


def main():
    args = get_args()

    with open(args.file[0], "rt") as f:
        lines = f.readlines()

    instructions = parse_instructions(lines, args.prompt)

    child = pexpect.spawn("bash")
    child.logfile = sys.stdout.buffer

    variables = {}
    for instruction in instructions:
        execute_one_instruction(child=child, variables=variables, instruction=instruction)

    child.expect(args.prompt)
    child.flush()

    if args.interact:
        child.logfile = None
        print(f"auto_pexpect interactive mode is active")
        child.interact()
        return

    child.close()
