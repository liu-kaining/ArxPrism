#!/usr/bin/env python3
"""
ArxPrism Streamlit Frontend Launcher

Usage:
    python run_frontend.py
    streamlit run src/frontend/app.py
"""

import subprocess
import sys
from pathlib import Path


def main():
    """启动 Streamlit 前端."""
    frontend_path = Path(__file__).parent / "src" / "frontend" / "app.py"

    if not frontend_path.exists():
        print(f"❌ Error: {frontend_path} not found")
        sys.exit(1)

    print("🚀 Starting ArxPrism Frontend...")
    print(f"📂 Source: {frontend_path}")
    print("")
    print("🌐 Opening browser at: http://localhost:8501")
    print("Press Ctrl+C to stop")
    print("")

    try:
        subprocess.run([
            sys.executable, "-m", "streamlit", "run",
            str(frontend_path),
            "--server.headless", "true",
            "--server.port", "8501"
        ])
    except KeyboardInterrupt:
        print("\n\n👋 Frontend stopped")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
