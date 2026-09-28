# vomit

Minimal remote desktop MVP. Browser-based viewer + optional native Python agent
for real screen sharing and real input control.

## Setup

    python -m venv .venv
    # Windows:  .venv\Scripts\activate
    # Unix:     source .venv/bin/activate
    pip install -r requirements.txt

## Run server

    cd server
    python main.py
    # → http://localhost:8080

## Expose publicly (dev)

    cloudflared tunnel --url http://localhost:8080
    # or
    ngrok http 8080

Copy the https URL, open it in the browser.

## Browser agent (screen-only, no OS input)

1. Open /agent.html, click Start sharing, pick screen.
2. Copy the viewer link.
3. Friend opens the link in /viewer.html, clicks Connect.

## Native agent (real input control)

    python agent/agent.py --session <sessionId> --server http://localhost:8080

Then open /viewer.html?session=<sessionId> and click Connect.
Mouse + keyboard events are injected on the agent machine.

## macOS permissions

Grant Accessibility + Screen Recording to your terminal / python in:
System Settings → Privacy & Security.

## Linux

Wayland screen capture is not supported by mss. Use X11.
Input injection requires X11 too (pynput uses Xlib).