# vomit

Self-hosted remote desktop MVP.
FastAPI signaling server + WebRTC viewer + optional native Python agent.

## Deploy to Render

Connect this repo to Render. `render.yaml` configures everything.

## Run locally

    pip install -r requirements.txt
    cd server && python main.py
    # → http://localhost:8080

## Native agent

    pip install -r requirements-agent.txt
    python agent/agent.py --session <id> --server https://your-app.onrender.com