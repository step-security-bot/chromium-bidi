# Copyright 2021 Google LLC.
# Copyright (c) Microsoft Corporation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import pytest
from test_helpers import json, read_JSON_message, send_JSON_command

# Tests for "handle an incoming message" error handling, when the message
# can't be decoded as known command.
# https://w3c.github.io/webdriver-bidi/#handle-an-incoming-message


@pytest.mark.asyncio
async def test_binary(websocket):
    # session.status is used in this test, but any simple command without side
    # effects would work. It is first sent as text, which should work, and then
    # sent again as binary, which should get an error response instead.
    command = {"id": 1, "method": "session.status", "params": {}}

    text_msg = json.dumps(command)
    await websocket.send(text_msg)
    resp = await read_JSON_message(websocket)
    assert resp['id'] == 1

    binary_msg = b'text_msg'
    await websocket.send(binary_msg)
    resp = await read_JSON_message(websocket)
    assert resp == {
        "type": "error",
        "error": "invalid argument",
        "message": "not supported type (binary)"
    }


@pytest.mark.asyncio
async def test_invalid_json(websocket):
    message = 'this is not json'
    await websocket.send(message)
    resp = await read_JSON_message(websocket)
    assert resp == {
        "type": "error",
        "error": "invalid argument",
        "message": "Cannot parse data as JSON"
    }


@pytest.mark.asyncio
async def test_empty_object(websocket):
    command = {}
    await websocket.send(json.dumps(command))
    resp = await read_JSON_message(websocket)
    assert resp == {
        "type": "error",
        "error": "invalid argument",
        "message": "Expected unsigned integer but got undefined"
    }


@pytest.mark.asyncio
async def test_session_status(websocket):
    command = {
        "type": "success",
        "id": 5,
        "method": "session.status",
        "params": {}
    }
    await send_JSON_command(websocket, command)
    resp = await read_JSON_message(websocket)
    assert resp == {
        "id": 5,
        "type": "success",
        "result": {
            "ready": False,
            "message": "already connected"
        }
    }


@pytest.mark.asyncio
async def test_channel_non_empty(websocket):
    await send_JSON_command(
        websocket, {
            "id": 6000,
            "method": "session.status",
            "params": {},
            "channel": "SOME_CHANNEL"
        })
    resp = await read_JSON_message(websocket)
    assert resp == {
        "id": 6000,
        "channel": "SOME_CHANNEL",
        "type": "success",
        "result": {
            "ready": False,
            "message": "already connected"
        }
    }


@pytest.mark.asyncio
async def test_channel_empty(websocket):
    await send_JSON_command(websocket, {
        "id": 7000,
        "method": "session.status",
        "params": {},
        "channel": ""
    })
    resp = await read_JSON_message(websocket)
    assert resp == {
        "id": 7000,
        "type": "success",
        "result": {
            "ready": False,
            "message": "already connected"
        }
    }
