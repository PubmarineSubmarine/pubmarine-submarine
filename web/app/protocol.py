from typing import ClassVar, Literal
from pydantic import BaseModel, Field


class Command(BaseModel):
    name: ClassVar[str]
    flags: list[str] = []

    def serialize(self) -> str:
        cmd = self.name
        for mod in self.flags:
            cmd += f" {mod}"
        for key, val in self.__class__.model_fields.items():
            if key in Command.model_fields.keys() or key == "name":
                continue
            cmd += f" {key}={getattr(self, key)}"
        return cmd
    
    @classmethod
    def deserialize(cls, text: str):
        text = text.strip()
        chunks = text.split(" ")

        command_dict = {"modifiers": []}
        for chunk in chunks:
            if "name" not in command_dict:
                command_dict["name"] = chunk
                continue
            arg_name, delim, arg_val = chunk.partition("=")
            if delim != "=":
                command_dict["modifiers"].append(chunk)
            command_dict[arg_name] = arg_val
        
        model = CommandModel(command=command_dict)
        return model.command

class ResetCommand(Command):
    name: Literal["RESET"] = "RESET"

class StopCommand(Command):
    name: Literal["STOP"] = "STOP"


class MotionCommand(Command):
    name: Literal["MOT"] = "MOT"
    X: float
    Z: float
    SV1: int
    FU: float
    RD: float

class CommandModel(BaseModel):
    command: ResetCommand | StopCommand | MotionCommand = Field(discriminator="name")

def test1():
    test = """
        MOT X=1.0 Z=-0.5 SV1=90 FU=1.0 RD=1.0
        RESET
        RESET SAFE
        BOOT
        STOP
        CAL
    """.strip()
    for txt_cmd in test.split("\n"):
        txt_cmd = txt_cmd.strip()
        try:
            cmd = Command.deserialize(txt_cmd)
        except Exception:
            print(f"failed to parse {txt_cmd}")
            exit()

        try:
            txt_cmd2 = cmd.serialize()
            print(f"{txt_cmd} -> {cmd} -> {txt_cmd2}")
        except Exception:
            print(f"failed to serialize {cmd}")


def test():
    commands = [
        StopCommand(),
        MotionCommand(X=1.0, Z=-1.0, SV1=90, FU=1.0, RD=1.0),
        ResetCommand(flags=["SAFE"]),
        ResetCommand(),
    ]
    print([cmd.serialize() for cmd in commands])

if __name__ == "__main__":
    test()