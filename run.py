#!/usr/bin/env python3
import uvicorn

if __name__ == "__main__":
    print("\n=" * 50)
    print("  English Learning Helper")
    print("  Open your browser: http://localhost:8000")
    print("=" * 50 + "\n")
    uvicorn.run("app.api:app", host="127.0.0.1", port=8000, reload=True)
