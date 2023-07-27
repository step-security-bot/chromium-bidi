# Copyright 2023 Google LLC.
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
from anys import ANY_DICT, ANY_STR
from test_helpers import (ANY_UUID, AnyExtending, execute_command,
                          read_JSON_message, send_JSON_command, subscribe)


@pytest.mark.asyncio
async def test_preloadScript_add_setGlobalVariable(websocket, context_id,
                                                   html):
    result = await execute_command(
        websocket, {
            "method": "script.addPreloadScript",
            "params": {
                "functionDeclaration": "() => { window.foo='bar'; }",
            }
        })
    assert result == {'script': ANY_UUID}

    await execute_command(
        websocket, {
            "method": "browsingContext.navigate",
            "params": {
                "url": html(),
                "wait": "complete",
                "context": context_id
            }
        })

    result = await execute_command(
        websocket, {
            "method": "script.evaluate",
            "params": {
                "expression": "window.foo",
                "target": {
                    "context": context_id
                },
                "awaitPromise": True,
                "resultOwnership": "root"
            }
        })
    assert result["result"] == {"type": "string", "value": 'bar'}


@pytest.mark.asyncio
async def test_preloadScript_add_logging(websocket, context_id, html):
    await subscribe(websocket, ["log.entryAdded"])

    result = await execute_command(
        websocket, {
            "method": "script.addPreloadScript",
            "params": {
                "functionDeclaration": "() => console.log('my preload script')",
            }
        })
    assert result == {'script': ANY_UUID}

    command_id = await send_JSON_command(
        websocket, {
            "method": "browsingContext.navigate",
            "params": {
                "url": html(),
                "wait": "complete",
                "context": context_id
            }
        })

    # Log event should happen before navigation.
    result = await read_JSON_message(websocket)
    assert result == AnyExtending({
        "type": "event",
        "method": "log.entryAdded",
        "params": {
            "args": [{
                "type": "string",
                "value": "my preload script"
            }]
        }
    })

    # Assert navigation is finished.
    result = await read_JSON_message(websocket)
    assert result == AnyExtending({"type": "success", "id": command_id})


@pytest.mark.asyncio
async def test_preloadScript_add_multipleScripts(websocket, context_id, html):
    await execute_command(
        websocket, {
            "method": "script.addPreloadScript",
            "params": {
                "functionDeclaration": "() => { window.foo1=1; }",
            }
        })
    await execute_command(
        websocket, {
            "method": "script.addPreloadScript",
            "params": {
                "functionDeclaration": "() => { window.foo2=2; }",
            }
        })

    await execute_command(
        websocket, {
            "method": "browsingContext.navigate",
            "params": {
                "url": html(),
                "wait": "complete",
                "context": context_id
            }
        })

    result = await execute_command(
        websocket, {
            "method": "script.evaluate",
            "params": {
                "expression": "window.foo1 + window.foo2",
                "target": {
                    "context": context_id
                },
                "awaitPromise": True,
                "resultOwnership": "root"
            }
        })
    assert result["result"] == {"type": "number", "value": 3}


@pytest.mark.asyncio
async def test_preloadScript_add_sameScript_multipleTimes(
        websocket, context_id, html):
    EXPRESSION = "() => { window.foo1 = (window.foo1 ?? 0) + 1; }"

    result = await execute_command(
        websocket, {
            "method": "script.addPreloadScript",
            "params": {
                "functionDeclaration": EXPRESSION,
            }
        })
    assert result == {'script': ANY_UUID}
    id1 = result['script']

    result = await execute_command(
        websocket, {
            "method": "script.addPreloadScript",
            "params": {
                "functionDeclaration": EXPRESSION,
            }
        })
    assert result == {'script': ANY_UUID}
    id2 = result['script']

    # Same script added twice should result in different ids.
    assert id1 != id2

    await execute_command(
        websocket, {
            "method": "browsingContext.navigate",
            "params": {
                "url": html(),
                "wait": "complete",
                "context": context_id
            }
        })

    result = await execute_command(
        websocket, {
            "method": "script.evaluate",
            "params": {
                "expression": "window.foo1",
                "target": {
                    "context": context_id
                },
                "awaitPromise": True,
                "resultOwnership": "root"
            }
        })
    assert result["result"] == {"type": "number", "value": 2}


@pytest.mark.asyncio
async def test_preloadScript_add_loadedInNewIframes(websocket, context_id,
                                                    url_all_origins, html,
                                                    read_sorted_messages):
    await subscribe(websocket, ["log.entryAdded"])

    await execute_command(
        websocket, {
            "method": "script.addPreloadScript",
            "params": {
                "functionDeclaration": "() => console.log('my preload script')",
            }
        })

    command_id = await send_JSON_command(
        websocket, {
            "method": "browsingContext.navigate",
            "params": {
                "url": html(),
                "wait": "complete",
                "context": context_id
            }
        })

    # Log event should happen before navigation.
    result = await read_JSON_message(websocket)
    assert result == AnyExtending({
        "type": "event",
        "method": "log.entryAdded",
        "params": {
            "args": [{
                "type": "string",
                "value": "my preload script"
            }]
        }
    })

    # Assert navigation is finished.
    result = await read_JSON_message(websocket)
    assert result == {"type": "success", "id": command_id, "result": ANY_DICT}

    # Create a new iframe within the same context.
    command_id = await send_JSON_command(
        websocket, {
            "method": "script.evaluate",
            "params": {
                "expression": f"""const iframe = document.createElement('iframe');
                    iframe.src = '{url_all_origins}';
                    document.body.appendChild(iframe);""",
                "target": {
                    "context": context_id
                },
                "awaitPromise": True,
                "resultOwnership": "root"
            }
        })

    # Event order is not guaranteed, so read 2 messages, sort them and assert.
    [command_result, log_entry_added] = await read_sorted_messages(2)

    assert command_result == {
        "type": "success",
        "id": command_id,
        "result": ANY_DICT
    }

    # Asset that the preload script is executed in the new iframe.
    assert log_entry_added == AnyExtending({
        "type": "event",
        "method": "log.entryAdded",
        "params": {
            "args": [{
                "type": "string",
                "value": "my preload script"
            }]
        }
    })


@pytest.mark.asyncio
async def test_preloadScript_add_loadedInNewIframes_withChildScript(
        websocket, context_id, html):
    await subscribe(websocket, ["log.entryAdded"])

    await execute_command(
        websocket, {
            "method": "script.addPreloadScript",
            "params": {
                "functionDeclaration": "() => console.log('my preload script')",
            }
        })

    command_id = await send_JSON_command(
        websocket, {
            "method": "browsingContext.navigate",
            "params": {
                "url": html(),
                "wait": "complete",
                "context": context_id
            }
        })

    # Log event should happen before navigation.
    result = await read_JSON_message(websocket)
    assert result == AnyExtending({
        "type": "event",
        "method": "log.entryAdded",
        "params": {
            "args": [{
                "type": "string",
                "value": "my preload script"
            }]
        }
    })

    # Assert navigation is finished.
    result = await read_JSON_message(websocket)
    assert result == {"type": "success", "id": command_id, "result": ANY_DICT}

    # Create a new iframe within the same context.
    result = await execute_command(
        websocket, {
            "method": "script.evaluate",
            "params": {
                "expression": f"""const iframe = document.createElement('iframe');
                    iframe.src = `{html('<script>console.log("I am the child");</script>')}`;
                    document.body.appendChild(iframe);""",
                "target": {
                    "context": context_id
                },
                "awaitPromise": True,
                "resultOwnership": "root"
            }
        })

    # Asset that the preload script is executed in the new iframe.
    result = await read_JSON_message(websocket)
    assert result == AnyExtending({
        "type": "event",
        "method": "log.entryAdded",
        "params": {
            "args": [{
                "type": "string",
                "value": "my preload script"
            }]
        }
    })

    # Asset that the child script is executed last.
    result = await read_JSON_message(websocket)
    assert result == AnyExtending({
        "type": "event",
        "method": "log.entryAdded",
        "params": {
            "args": [{
                "type": "string",
                "value": "I am the child"
            }]
        }
    })


@pytest.mark.asyncio
async def test_preloadScript_add_loadedInMultipleContexts(
        websocket, context_id, html):
    await execute_command(
        websocket, {
            "method": "script.addPreloadScript",
            "params": {
                "functionDeclaration": "() => { window.foo='bar'; }",
            }
        })

    await execute_command(
        websocket, {
            "method": "browsingContext.navigate",
            "params": {
                "url": html(),
                "wait": "complete",
                "context": context_id
            }
        })

    response = await execute_command(
        websocket, {
            "method": "script.evaluate",
            "params": {
                "expression": "window.foo",
                "target": {
                    "context": context_id
                },
                "awaitPromise": True,
                "resultOwnership": "root"
            }
        })
    assert response["result"] == {"type": "string", "value": 'bar'}


@pytest.mark.asyncio
async def test_preloadScript_add_loadedInMultipleContexts_withIframes(
        websocket, context_id, url_all_origins, html, read_sorted_messages):
    await execute_command(
        websocket, {
            "method": "script.addPreloadScript",
            "params": {
                "functionDeclaration": "() => { window.foo='bar'; }",
            }
        })

    await execute_command(
        websocket, {
            "method": "browsingContext.navigate",
            "params": {
                "url": html(),
                "wait": "complete",
                "context": context_id
            }
        })

    result = await execute_command(
        websocket, {
            "method": "script.evaluate",
            "params": {
                "expression": "window.foo",
                "target": {
                    "context": context_id
                },
                "awaitPromise": True,
                "resultOwnership": "root"
            }
        })
    assert result["result"] == {"type": "string", "value": 'bar'}

    # Needed to make sure the iFrame loaded.
    await subscribe(websocket, ["browsingContext.load"])

    # Create a new iframe within the same context.
    command_id = await send_JSON_command(
        websocket, {
            "method": "script.evaluate",
            "params": {
                "expression": f"""const iframe = document.createElement('iframe');
                    iframe.src = `{url_all_origins}`;
                    document.body.appendChild(iframe);""",
                "target": {
                    "context": context_id
                },
                "awaitPromise": True,
                "resultOwnership": "root"
            }
        })

    # Depending on the URL, the iframe can be loaded before or after the script
    # is done.
    [command_result, browsing_context_load] = await read_sorted_messages(2)
    assert command_result == {
        "type": "success",
        "id": command_id,
        "result": ANY_DICT
    }
    assert browsing_context_load == {
        'type': 'event',
        "method": "browsingContext.load",
        "params": AnyExtending({
            "context": ANY_STR,
            "url": url_all_origins
        })
    }

    iframe_context_id = browsing_context_load["params"]["context"]
    assert iframe_context_id != context_id

    result = await execute_command(
        websocket, {
            "method": "script.evaluate",
            "params": {
                "expression": "window.foo",
                "target": {
                    "context": iframe_context_id
                },
                "awaitPromise": True,
                "resultOwnership": "root"
            }
        })
    assert result["result"] == {"type": "string", "value": 'bar'}


@pytest.mark.asyncio
async def test_preloadScript_add_loadedInNewContexts(websocket, context_id,
                                                     create_context, html):
    await execute_command(
        websocket, {
            "method": "script.addPreloadScript",
            "params": {
                "functionDeclaration": "() => { window.foo='bar'; }",
            }
        })

    await execute_command(
        websocket, {
            "method": "browsingContext.navigate",
            "params": {
                "url": html(),
                "wait": "complete",
                "context": context_id
            }
        })

    result = await execute_command(
        websocket, {
            "method": "script.evaluate",
            "params": {
                "expression": "window.foo",
                "target": {
                    "context": context_id
                },
                "awaitPromise": True,
                "resultOwnership": "root"
            }
        })
    assert result["result"] == {"type": "string", "value": 'bar'}

    new_context_id = await create_context()

    result = await execute_command(
        websocket, {
            "method": "script.evaluate",
            "params": {
                "expression": "window.foo",
                "target": {
                    "context": new_context_id
                },
                "awaitPromise": True,
                "resultOwnership": "root"
            }
        })
    assert result["result"] == {"type": "string", "value": 'bar'}

    await execute_command(
        websocket, {
            "method": "browsingContext.navigate",
            "params": {
                "url": html(),
                "wait": "complete",
                "context": new_context_id
            }
        })

    result = await execute_command(
        websocket, {
            "method": "script.evaluate",
            "params": {
                "expression": "window.foo",
                "target": {
                    "context": new_context_id
                },
                "awaitPromise": True,
                "resultOwnership": "root"
            }
        })
    assert result["result"] == {"type": "string", "value": 'bar'}


@pytest.mark.asyncio
async def test_preloadScript_add_sandbox(websocket, context_id, html):
    result = await execute_command(
        websocket, {
            "method": "script.addPreloadScript",
            "params": {
                "functionDeclaration": "() => { window.foo='bar'; }",
                "sandbox": "MY_SANDBOX",
            }
        })
    assert result == {'script': ANY_UUID}

    await execute_command(
        websocket, {
            "method": "browsingContext.navigate",
            "params": {
                "url": html(),
                "wait": "complete",
                "context": context_id
            }
        })

    # Evaluate in the standard sandbox, script takes no effect.
    result = await execute_command(
        websocket, {
            "method": "script.evaluate",
            "params": {
                "expression": "window.foo",
                "target": {
                    "context": context_id
                },
                "awaitPromise": True,
                "resultOwnership": "root"
            }
        })
    assert result["result"] == {"type": "undefined"}

    # Evaluate in the given sandbox, script takes effect.
    result = await execute_command(
        websocket, {
            "method": "script.evaluate",
            "params": {
                "expression": "window.foo",
                "target": {
                    "context": context_id,
                    "sandbox": "MY_SANDBOX",
                },
                "awaitPromise": True,
                "resultOwnership": "root"
            }
        })
    assert result["result"] == {"type": "string", "value": 'bar'}


@pytest.mark.asyncio
@pytest.mark.parametrize("with_reload", [True, False],
                         ids=["with reload", "without reload"])
async def test_preloadScript_add_runImmediately(websocket, html, context_id,
                                                with_reload):
    await execute_command(
        websocket, {
            "method": "browsingContext.navigate",
            "params": {
                "url": html(),
                "wait": "complete",
                "context": context_id
            }
        })

    await execute_command(
        websocket, {
            "method": "script.addPreloadScript",
            "params": {
                "functionDeclaration": "() => { window.foo='bar'; }",
            }
        })

    if with_reload:
        await execute_command(
            websocket, {
                "method": "browsingContext.reload",
                "params": {
                    "wait": "complete",
                    "context": context_id
                }
            })

        result = await execute_command(
            websocket, {
                "method": "script.evaluate",
                "params": {
                    "expression": "window.foo",
                    "target": {
                        "context": context_id
                    },
                    "awaitPromise": True,
                    "resultOwnership": "root"
                }
            })
        assert result["result"] == {"type": "string", "value": 'bar'}
    else:
        result = await execute_command(
            websocket, {
                "method": "script.evaluate",
                "params": {
                    "expression": "window.foo",
                    "target": {
                        "context": context_id
                    },
                    "awaitPromise": True,
                    "resultOwnership": "root"
                }
            })
        assert result["result"] == {"type": "undefined"}


@pytest.mark.asyncio
async def test_preloadScript_add_withUserGesture_blankTargetLink(
        websocket, context_id, html, read_sorted_messages, get_cdp_session_id):
    LINK_WITH_BLANK_TARGET = html(
        '<a href="https://example.com" target="_blank">new tab</a>')

    await execute_command(
        websocket, {
            "method": "script.addPreloadScript",
            "params": {
                "functionDeclaration": """() => {
                    console.log('my preload script', window.location.href);
                }""",
            }
        })

    await execute_command(
        websocket, {
            "method": "browsingContext.navigate",
            "params": {
                "context": context_id,
                "url": LINK_WITH_BLANK_TARGET,
                "wait": "complete",
            }
        })

    await subscribe(websocket, ["log.entryAdded"])

    session_id = await get_cdp_session_id(context_id)

    # XXX: Execute via BiDi once supported: https://github.com/w3c/webdriver-bidi/issues/359
    command_id = await send_JSON_command(
        websocket, {
            "method": "cdp.sendCommand",
            "params": {
                "method": "Runtime.evaluate",
                "params": {
                    "expression": "document.querySelector('a').click();",
                    "userGesture": True,
                },
                "session": session_id
            }
        })

    [command_result, log_entry_added] = await read_sorted_messages(2)
    assert command_result == AnyExtending({
        "id": command_id,
        "type": "success",
        "result": ANY_DICT
    })
    assert log_entry_added == AnyExtending({
        "type": "event",
        "method": "log.entryAdded",
        "params": {
            "args": [{
                "type": "string",
                "value": "my preload script"
            }, {
                'type': 'string',
                'value': 'https://example.com/',
            }]
        }
    })


@pytest.mark.asyncio
async def test_preloadScript_channel_navigate(websocket, context_id, html,
                                              read_sorted_messages):
    await subscribe(websocket, ["script.message"])

    result = await execute_command(
        websocket, {
            "method": "script.addPreloadScript",
            "params": {
                "functionDeclaration": """
                (channel) => {
                    setTimeout(() => {
                        channel({'foo': 'bar', 'baz': {'1': 2}})
                    }, 1);
                }""",
                "arguments": [{
                    "type": "channel",
                    "value": {
                        "channel": "channel_name",
                        "serializationOptions": {
                            "maxObjectDepth": 0
                        },
                    },
                }, ],
                "context": context_id,
            }
        })
    assert result == {'script': ANY_UUID}

    command_id = await send_JSON_command(
        websocket, {
            "method": "browsingContext.navigate",
            "params": {
                "url": html(),
                "wait": "complete",
                "context": context_id
            }
        })

    [command_result, channel_message] = await read_sorted_messages(2)
    assert command_result == {
        "type": "success",
        "id": command_id,
        "result": ANY_DICT
    }

    assert channel_message == AnyExtending({
        "type": "event",
        "method": "script.message",
        "params": {
            "channel": "channel_name",
            "data": {
                "type": "object"
            },
            "source": {
                "realm": ANY_STR,
                "context": context_id,
            },
        }
    })


@pytest.mark.asyncio
async def test_preloadScript_channel_newContext(websocket,
                                                read_sorted_messages):
    await subscribe(websocket, ["script.message"])

    result = await execute_command(
        websocket, {
            "method": "script.addPreloadScript",
            "params": {
                "functionDeclaration": """
                (channel) => {
                    channel({'foo': 'bar', 'baz': {'1': 2}});
                }""",
                "arguments": [{
                    "type": "channel",
                    "value": {
                        "channel": "channel_name"
                    },
                }, ],
            }
        })
    assert result == {'script': ANY_UUID}

    command_id = await send_JSON_command(websocket, {
        "method": "browsingContext.create",
        "params": {
            "type": "tab"
        }
    })

    [command_result, channel_message] = await read_sorted_messages(2)
    assert command_result == {
        "type": "success",
        "id": command_id,
        "result": ANY_DICT
    }
    new_context_id = command_result["result"]["context"]

    assert channel_message == AnyExtending({
        "type": "event",
        "method": "script.message",
        "params": {
            "channel": "channel_name",
            "data": {
                "type": "object"
            },
            "source": {
                "realm": ANY_STR,
                "context": new_context_id,
            },
        }
    })
