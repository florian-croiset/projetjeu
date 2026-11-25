"""Headless dedicated server (no window, no audio).

Usage::

    python -m net.dedicated [--slot N] [--new] [--tcp-port 5555] [--udp-port 5556]
                            [--relay-host HOST --relay-port 7777]

Players connect to this machine with the normal client ("Join" menu). The first
player to connect gets id 0, who owns the save slot (money, checkpoints).
"""

import argparse
import os
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame  # noqa: E402

from net.framing import list_local_ips  # noqa: E402
from net.server import Server  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="Echo dedicated server")
    parser.add_argument("--slot", type=int, default=0, help="save slot 0-2 (default 0)")
    parser.add_argument("--new", action="store_true", help="start a new game in that slot")
    parser.add_argument("--tcp-port", type=int, default=None)
    parser.add_argument("--udp-port", type=int, default=None)
    parser.add_argument("--relay-host", default="", help="relay server for room-code play")
    parser.add_argument("--relay-port", type=int, default=7777)
    args = parser.parse_args()

    pygame.init()
    pygame.display.set_mode((1, 1))
    server = Server(args.slot, args.new, relay_host=args.relay_host, relay_port=args.relay_port,
                    tcp_port=args.tcp_port, udp_port=args.udp_port)
    server.start()
    print(f"[DEDICATED] ready. Addresses: {', '.join(list_local_ips()) or '127.0.0.1'}"
          f" (TCP {server.tcp_port}, UDP {server.udp_port})")
    try:
        while True:
            time.sleep(1.0)
            if server.room_code:
                print(f"[DEDICATED] relay room code: {server.room_code}", end="\r")
    except KeyboardInterrupt:
        print("\n[DEDICATED] shutting down...")
    finally:
        server.stop()


if __name__ == "__main__":
    main()
