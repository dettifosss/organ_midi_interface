from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from loguru import logger

from organ_interface.voices import VoiceManager, WebVoice, WebVoiceController

app = FastAPI()

clients: dict[str, dict] = {}

# ✅ WebSocket FIRST
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    vm: VoiceManager = websocket.app.state.voice_manager

    client_id = None
    client_voice = None
    
    try:

        await websocket.send_json({"type": "ping"})
        hello = await websocket.receive_json()
        
        client_id = hello.get("client_id")
        if client_id is None:
            await websocket.close(code=4000)
            return
        
        if client_id not in clients:
            client_voice = vm.create_random_voice(voice_id=client_id, voice_cls=WebVoice)
            client_voice.assign_random_range(["C", "E", "G"], keep_current = False, reset=True)
            clients[client_id] = {
                "voice": client_voice,
                "slider": 0,
                "visible": True,
            }
        else:
            client_voice = clients[client_id]["voice"]

        state = clients[client_id]
        logger.info(f"Client connected: {client_id}, voice: {client_voice}")
        logger.info(vm)

        await websocket.send_json({"state": {"slider": state["slider"], "visible": state["visible"]}})
        await websocket.send_json({
            "type": "config",
            "slider": {
                "max": len(client_voice) - 1,
                "value": state["slider"],
            }
        })

        while True:
            data = await websocket.receive_json()


            if data["type"] == "slider":
                state["slider"] = data["value"]
                if hasattr(client_voice, "set_note_num"):
                    client_voice.set_note_num(data["value"])
                    if data["touching"]:
                        client_voice.on()
                    else:
                        client_voice.off()
                    vm.queue_all_midi()

            # Respond with simple state values only
            await websocket.send_json({"state": {"slider": state["slider"], "visible": state["visible"]}})

    except WebSocketDisconnect:
        print(f"Client disconnected: {client_id}")

# ✅ Static files LAST
app.mount(
    "/",
    StaticFiles(directory="frontend", html=True),
    name="frontend",
)

