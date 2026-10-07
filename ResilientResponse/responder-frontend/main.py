import os
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="templates")

# HOSPITAL or POLICE
RESPONDER_TYPE = os.getenv("RESPONDER_TYPE", "HOSPITAL")

@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "responder_type": RESPONDER_TYPE,
        "notification_service_url": "http://localhost:8007"
    })

if __name__ == "__main__":
    port = 3001 if RESPONDER_TYPE == "HOSPITAL" else 3002
    uvicorn.run(app, host="0.0.0.0", port=port)
