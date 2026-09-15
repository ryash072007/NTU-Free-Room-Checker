"""Command-line entry point."""

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ntu-room-checker")
    parser.add_subparsers(dest="command", required=True).add_parser(
        "scrape", help="Scrape NTU public class schedules"
    )
    return parser


def main() -> None:
    build_parser().parse_args()


if __name__ == "__main__":
    main()
