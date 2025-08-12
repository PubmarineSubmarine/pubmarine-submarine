from typing import ClassVar, Literal, Self
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
            val = getattr(self, key)
            if type(val) is tuple:
                val = ','.join(str(x) for x in val)
            cmd += f" {key.upper()}={val}"
        return cmd

    @classmethod
    def deserialize(cls, text: str):
        text = text.strip()
        chunks = text.split(" ")

        command_dict = {"flags": []}
        for chunk in chunks:
            if "name" not in command_dict:
                command_dict["name"] = chunk
                continue
            arg_name, delim, arg_val = chunk.partition("=")
            if delim != "=":
                command_dict["flags"].append(chunk)
                continue

            if "," in arg_val:
                arg_val = tuple(arg_val.split(","))

            command_dict[arg_name.lower()] = arg_val

        model = CommandModel(command=command_dict)
        return model.command


class ResetCmd(Command):
    name: Literal["RESET"] = "RESET"


class StopCmd(Command):
    name: Literal["STOP"] = "STOP"


class MotionCmd(Command):
    name: Literal["MOT"] = "MOT"
    x: float
    z: float
    sv1: int
    fu: int
    rd: int


class StateCmd(Command):
    name: Literal["STAT"] = "STAT"
    x: float
    z: float
    sv1: int
    fu: int
    rd: int
    acc: tuple[float, float, float]
    gyro: tuple[float, float, float]
    depth: float
    bat: float

    @classmethod
    def default(cls) -> Self:
        return StateCmd(
            x=1.0,
            z=-1.0,
            sv1=90,
            fu=1,
            rd=1,
            acc=(0, 2.1, 0),
            gyro=(-4.5, 0.1, 3.2),
            depth=0.5,
            bat=3.5,
        )

class CommandModel(BaseModel):
    command: ResetCmd | StopCmd | MotionCmd | StateCmd = Field(discriminator="name")


def test1():
    test = """
        STAT X=0.5 Z=-0.5 SV1=90 FU=1 RD=1 ACC=0.23,0.12,9.89 GYRO=0.12,0.23,0.34 DEPTH=0.5 BAT=11.6
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
        StopCmd(),
        MotionCmd(x=1.0, z=-1.0, sv1=90, fu=1, rd=1),
        ResetCmd(flags=["SAFE"]),
        ResetCmd(),
        StateCmd(
            x=1.0,
            z=-1.0,
            sv1=90,
            fu=1,
            rd=1,
            acc=(0, 2.1, 0),
            gyro=(-4.5, 0.1, 3.2),
            depth=0.5,
            bat=3.5,
        ),
    ]
    print([cmd.serialize() for cmd in commands])


if __name__ == "__main__":
    test()
