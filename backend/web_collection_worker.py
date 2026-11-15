
import argparse
import sys

from web_collection_routes import run_worker


def main():
    parser = argparse.ArgumentParser(
        description="FSI – Web Collection Worker"
    )

    parser.add_argument(
        "--worker-job",
        type=int,
        required=True,
    )

    args = parser.parse_args()

    return run_worker(args.worker_job)


if __name__ == "__main__":
    sys.exit(main())
