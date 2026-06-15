import json

from typing import ClassVar, Literal, Self, Any
from pydantic import BaseModel, ConfigDict, Field


class Command(BaseModel):
    name: ClassVar[str]
    flags: list[str] = []
    raw: str = ""

    def serialize(self) -> str:
        cmd = self.name
        for mod in self.flags:
            cmd += f" {mod}"
        for key, val in self.__class__.model_fields.items():
            if key in Command.model_fields.keys() or key == "name":
                continue
            val = getattr(self, key)
            if val is None:
                continue
            if type(val) is tuple:
                val = ','.join(str(x) for x in val)
            cmd += f" {key.upper()}={val}"
        return cmd

    @classmethod
    def deserialize(cls, text: str):
        text = text.strip()
        chunks = text.split(" ")
        
        if chunks[0] == "CONFIG":
            _, _, config = text.strip().partition(" ")
            return ConfigCmd(config=json.loads(config))


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
        command_dict["raw"] = text

        model = CommandModel(command=command_dict)
        return model.command


class ResetCmd(Command):
    name: Literal["RESET"] = "RESET"


class StopCmd(Command):
    name: Literal["STOP"] = "STOP"


class MotionCmd(Command):
    name: Literal["MOT"] = "MOT"
    a: float | None = None
    b: float | None = None
    sv1: int | None = None
    sv2: int | None = None
    fu: int | None = None
    fd: int | None = None
    fl: int | None = None
    fr: int | None = None
    ru: int | None = None
    rd: int | None = None
    rl: int | None = None
    rr: int | None = None
    lights: int | None = None


class StateCmd(Command):
    name: Literal["STAT"] = "STAT"
    a: float | None = None
    b: float | None = None
    sv1: float | None = None
    sv2: float | None = None
    fu: int | None = None
    fd: int | None = None
    fl: int | None = None
    fr: int | None = None
    ru: int | None = None
    rd: int | None = None
    rl: int | None = None
    rr: int | None = None
    lights: int | None = None
    acc: tuple[float, float, float] | None = None
    gyro: tuple[float, float, float] | None = None
    depth: float | None = None
    bat: float | None = None
    temp: float | None = None
    hum: float | None = None
    mcu: float | None = None
    ia: float | None = None
    ib: float | None = None
    fm: int | None = None
    fj: int | None = None
    pi: float | None = None
    td: float | None = None
    br: int | None = None

    model_config = ConfigDict(extra='allow')

    @classmethod
    def default(cls) -> Self:
        return StateCmd(
            a=1.0,
            b=-1.0,
            sv1=90,
            fu=1,
            rd=1,
            acc=(0, 2.1, 0),
            gyro=(-4.5, 0.1, 3.2),
            depth=0.5,
            bat=3.5,
        )


class ConsoleLog(Command):
    name: Literal["CONSOLE"] = "CONSOLE"
    level: str = "INFO"
    line: str


class PingCmd(Command):
    name: Literal["PING"] = "PING"


class PongCmd(Command):
    name: Literal["PONG"] = "PONG"


class ConfigCmd(Command):
    name: Literal["CONFIG"] = "CONFIG"
    config: dict[str, Any] = {}


class GetConfigCmd(Command):
    name: Literal["GET_CONFIG"] = "GET_CONFIG"


class SetConfigCmd(Command):
    name: Literal["SET_CONFIG"] = "SET_CONFIG"
    config: dict[str, Any] = {}

    def serialize(self) -> str:
        return f"SET_CONFIG {json.dumps(self.config)}"


class OriCmd(Command):
    """Absolute chassis orientation (ZYX Euler deg + wxyz quaternion)."""
    name: Literal["ORI"] = "ORI"
    roll: float | None = None
    pitch: float | None = None
    yaw: float | None = None
    qw: float | None = None
    qx: float | None = None
    qy: float | None = None
    qz: float | None = None
    ready: int = 0


class CommandModel(BaseModel):
    command: ResetCmd | StopCmd | MotionCmd | StateCmd | PingCmd | PongCmd | ConfigCmd | GetConfigCmd | SetConfigCmd | OriCmd = Field(discriminator="name")


def test1():
    test = """
        STAT A=0.5 B=-0.5 SV1=90 FU=1 RD=1 ACC=0.23,0.12,9.89 GYRO=0.12,0.23,0.34 DEPTH=0.5 BAT=11.6
        MOT A=1.0 B=-0.5 SV1=90 FU=1.0 RD=1.0
        RESET
        RESET SAFE
        BOOT
        STOP
        CAL
        ORI ROLL=1.2 PITCH=-3.4 YAW=90.0 QW=0.99 QX=0.01 QY=-0.03 QZ=0.00 READY=1
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
        MotionCmd(a=1.0, b=-1.0, sv1=90, fu=1, rd=1),
        ResetCmd(flags=["SAFE"]),
        ResetCmd(),
        StateCmd(
            a=1.0,
            b=-1.0,
            sv1=90,
            fu=1,
            rd=1,
            acc=(0, 2.1, 0),
            gyro=(-4.5, 0.1, 3.2),
            depth=0.5,
            bat=3.5,
        ),
        OriCmd(roll=1.2, pitch=-3.4, yaw=90.0, qw=0.99, qx=0.01, qy=-0.03, qz=0.0, ready=1),
    ]
    print([cmd.serialize() for cmd in commands])


if __name__ == "__main__":
    test()
