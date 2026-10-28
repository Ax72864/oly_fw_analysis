"""OM-3 read-only Wi-Fi research CLI. No writes are offered."""
import argparse
import json
from pathlib import Path
import sys

from penf_wifi.protocol import ClientError
from penf_wifi.transport import DEFAULT_AGENT, DEFAULT_REQUEST_GAP, HTTPTransport

from .client import Camera
from .storage import Run

DEFAULT_OUT = Path(__file__).resolve().parents[1] / "runs"


def parser():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--camera", default="http://192.168.0.10", help="Camera HTTP origin")
    p.add_argument("--timeout", type=float, default=40)
    p.add_argument("--ready-timeout", type=float, default=5)
    p.add_argument("--request-gap", type=float, default=DEFAULT_REQUEST_GAP)
    p.add_argument("--user-agent", default=DEFAULT_AGENT)
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    commands = p.add_subparsers(dest="command")
    commands.add_parser("discover", help="Read identity, connection mode and advertised commands")
    commands.add_parser("identify", help="Read-only model identification only")
    return p


def emit(result):
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


def main(argv=None):
    p = parser()
    args = p.parse_args(argv)
    if args.command is None:
        p.print_help()
        return 0
    run = None
    try:
        run = Run(args.out, args.command)
        transport = HTTPTransport(
            args.camera,
            timeout=args.timeout,
            ready_timeout=args.ready_timeout,
            request_gap=args.request_gap,
            user_agent=args.user_agent,
            record=run.record,
        )
        camera = Camera(transport, progress=lambda m: print(m, file=sys.stderr))
        result = camera.identify() if args.command == "identify" else camera.discover()
        run.save("result.json", result)
        emit(result)
        return 0
    except ClientError as e:
        print(json.dumps({"error": str(e)}, indent=2), file=sys.stderr)
        return 2
    finally:
        if run is not None:
            run.close()


if __name__ == "__main__":
    raise SystemExit(main())
