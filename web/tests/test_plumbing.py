import os
import pytest
import plumbing
import math
from serial_client import DebugSerialClient
from unittest import mock

@pytest.fixture()
def setenvvar(monkeypatch):
    with mock.patch.dict(os.environ, clear=True):
        envvars = {
            "SERIAL_PORT": "DEBUG",
        }
        for k, v in envvars.items():
            monkeypatch.setenv(k, v)
        yield # This is the magical bit which restore the environment after 


@pytest.fixture()
def mock_serial():
    return mock.Mock(spec=DebugSerialClient)

@pytest.fixture()
async def mock_plumbing(mock_serial):
    p = plumbing.Plumbing(serial=mock_serial)
    p._main_thruster_boost_active = True
    await p.init()
    return p
    
async def test_full_forward(mock_plumbing, mock_serial):
    await mock_plumbing.stick_moved("left", 0.0, -1.0)
    mock_serial.write_cmd.assert_awaited_once()
    (cmd,), _ = mock_serial.write_cmd.call_args
    assert (cmd.a, cmd.b) == (1.0, 1.0)
    assert cmd.a == 1.0 and cmd.b == 1.0

async def test_full_reverse(mock_plumbing, mock_serial):
    await mock_plumbing.stick_moved("left", 0.0, 1.0)
    mock_serial.write_cmd.assert_awaited_once()
    (cmd,), _ = mock_serial.write_cmd.call_args
    assert cmd.a == -1.0 and cmd.b == -1.0

async def test_full_left(mock_plumbing, mock_serial):
    await mock_plumbing.stick_moved("left", -1.0, 0.0)
    mock_serial.write_cmd.assert_awaited_once()
    (cmd,), _ = mock_serial.write_cmd.call_args
    assert cmd.a == -1.0 and cmd.b == 1.0

async def test_full_right(mock_plumbing, mock_serial):
    await mock_plumbing.stick_moved("left", 1.0, 0.0)
    mock_serial.write_cmd.assert_awaited_once()
    (cmd,), _ = mock_serial.write_cmd.call_args
    assert cmd.a == 1.0 and cmd.b == -1.0

async def test_forward_left_square(mock_plumbing, mock_serial):
    await mock_plumbing.stick_moved("left", -1.0, -1.0)
    mock_serial.write_cmd.assert_awaited_once()
    (cmd,), _ = mock_serial.write_cmd.call_args
    assert cmd.a == 0.0 and cmd.b == 1.0

async def test_forward_right_square(mock_plumbing, mock_serial):
    await mock_plumbing.stick_moved("left", 1.0, -1.0)
    mock_serial.write_cmd.assert_awaited_once()
    (cmd,), _ = mock_serial.write_cmd.call_args
    assert cmd.a == 1.0 and cmd.b == 0.0

async def test_reverse_left_square(mock_plumbing, mock_serial):
    await mock_plumbing.stick_moved("left", -1.0, 1.0)
    mock_serial.write_cmd.assert_awaited_once()
    (cmd,), _ = mock_serial.write_cmd.call_args
    assert cmd.a == -1.0 and cmd.b == 0.0

async def test_reverse_right_square(mock_plumbing, mock_serial):
    await mock_plumbing.stick_moved("left", 1.0, 1.0)
    mock_serial.write_cmd.assert_awaited_once()
    (cmd,), _ = mock_serial.write_cmd.call_args
    assert cmd.a == 0.0 and cmd.b == -1.0

def rect(r, theta):
    x = r * math.cos(math.radians(theta))
    y = r * math.sin(math.radians(theta))
    return (x, y)

def polar(x, y):
    r = math.sqrt(x ** 2 + y ** 2)
    theta = math.degrees(math.atan2(y,x))
    return (r, theta)

# tests current behavior: non-cardinal directions result in less than full throttle
async def test_forward_left_circle(mock_plumbing, mock_serial):
    x, y = rect(1.0, 135)
    await mock_plumbing.stick_moved("left", x, -y)
    mock_serial.write_cmd.assert_awaited_once()
    (cmd,), _ = mock_serial.write_cmd.call_args
    assert (cmd.a, cmd.b) == (pytest.approx(0.0), pytest.approx(math.sqrt(2)/2))

async def test_forward_right_circle(mock_plumbing, mock_serial):
    x, y = rect(1.0, 45)
    await mock_plumbing.stick_moved("left", x, -y)
    mock_serial.write_cmd.assert_awaited_once()
    (cmd,), _ = mock_serial.write_cmd.call_args
    assert (cmd.a, cmd.b) == (pytest.approx(math.sqrt(2)/2), pytest.approx(0.0))

async def test_reverse_left_circle(mock_plumbing, mock_serial):
    x, y = rect(1.0, -135)
    await mock_plumbing.stick_moved("left", x, -y)
    mock_serial.write_cmd.assert_awaited_once()
    (cmd,), _ = mock_serial.write_cmd.call_args
    assert (cmd.a, cmd.b) == (pytest.approx(-math.sqrt(2)/2), pytest.approx(0.0))

async def test_reverse_right_circle(mock_plumbing, mock_serial):
    x, y = rect(1.0, -45)
    await mock_plumbing.stick_moved("left", x, -y)
    mock_serial.write_cmd.assert_awaited_once()
    (cmd,), _ = mock_serial.write_cmd.call_args
    assert (cmd.a, cmd.b) == (pytest.approx(0.0), pytest.approx(-math.sqrt(2)/2))
