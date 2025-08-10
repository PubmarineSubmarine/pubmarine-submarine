from typing import ClassVar, Literal, Self
from pydantic import BaseModel, Field


class Command(BaseModel):
    name: ClassVar[str]

    def serialize(self) -> str:
        return self.name
    
    @classmethod
    def deserialize(cls, text: str):
        text = text.strip()
        chunks = text.split(" ")

        command_dict = {}
        for chunk in chunks:
            if "name" not in command_dict:
                command_dict["name"] = chunk
            arg_name, _, arg_val = chunk.partition("=")
            command_dict[arg_name] = arg_val
        
        model = CommandModel(command=command_dict)
        return model.command

class ResetCommand(BaseModel):
    name: Literal["RESET"]

class StopCommand(Command):
    name: Literal["STOP"]


class MotorCommand(Command):
    name: Literal["MOT"]
    X: float
    Z: float
    SV1: int
    FU: float
    RD: float

class CommandModel(BaseModel):
    command: ResetCommand | StopCommand | MotorCommand = Field(discriminator="name")


if __name__ == "__main__":
    test = """
        MOT X=1.0 Z=-0.5 SV1=90 FU=1.0 RD=1.0
        RESET
        BOOT
        STOP
        CAL
    """.strip()
    for txt_cmd in test.split("\n"):
        txt_cmd = txt_cmd.strip()
        try:
            cmd = Command.deserialize(txt_cmd)
            print(f"{txt_cmd} -> {cmd}")
        except Exception:
            print(f"failed to parse {txt_cmd}")
            pass
