"""End-to-end WebSocket test: load default scene, list prims, receive a frame, pick."""
import asyncio
import json
import urllib.request
import websockets


async def main():
    # Fetch the default scene path from the HTTP API.
    with urllib.request.urlopen("http://localhost:8080/api/default_scene") as res:
        default = json.loads(res.read().decode())["path"]
    print("Default scene:", default)

    uri = "ws://localhost:8080/ws"
    async with websockets.connect(uri) as ws:
        print("Connected")

        # Load default scene
        await ws.send(json.dumps({"cmd": "load", "path": default}))
        msg = await ws.recv()
        print("Load response:", msg)

        # List prims
        await ws.send(json.dumps({"cmd": "list_prims"}))
        msg = await ws.recv()
        print("Prims response:", msg[:200])

        # Wait for a frame (binary message)
        for i in range(30):
            msg = await ws.recv()
            if isinstance(msg, bytes):
                print(f"Received frame {len(msg)} bytes")
                break
            else:
                print("Text:", msg)

        await ws.send(json.dumps({"cmd": "pick", "x": 0.5, "y": 0.5}))
        msg = await ws.recv()
        print("Pick response:", msg)


asyncio.run(main())
