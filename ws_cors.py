import asyncio
import websockets

async def test_ws_cors():
    try:
        async with websockets.connect(
            "ws://127.0.0.1:8091/ws/coach?token=invalidtoken",
            extra_headers={"Origin": "http://127.0.0.1:8100"}
        ) as websocket:
            print("Connected successfully")
            await websocket.recv()
    except Exception as e:
        print(f"Connection failed: {e}")

asyncio.run(test_ws_cors())
