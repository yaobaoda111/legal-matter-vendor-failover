"""Set account-level chat routing before running the intake service."""

import argparse

from src.infrai_gateway import InfraiGateway


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exclude", action="append", default=[])
    args = parser.parse_args()

    gateway = InfraiGateway()
    try:
        result = gateway.configure_chat_routing(args.exclude)
        print("Routing preference saved:", result)
    finally:
        gateway.close()


if __name__ == "__main__":
    main()
