from fastapi import FastAPI, Request
from starlette.middleware.cors import CORSMiddleware

from langgraph_lite import multiagent_app

app = FastAPI()

# Allow specific origins or use ["*"] to allow all
origins = [
    "https://localhost:3000",  # your frontend origin
    "http://localhost:8080",
    "https://127.0.0.1:3000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # or ["*"] to allow all origins
    allow_credentials=True,
    allow_methods=["*"],  # or ["POST", "GET", "OPTIONS"] as needed
    allow_headers=["*"],
)

@app.post("/multiagentchat")
async def multiagentchat(request: Request):
    data = await request.json()
    input_text = data["input"]
    try:
        result = multiagent_app.invoke({"input": input_text})
        output = result["output"]
        return output
    except Exception as e:
        return {"result": f"Error: {e}"}
