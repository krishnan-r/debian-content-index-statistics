#!/usr/bin/env python3
"""
Utility script to print the top packages with the most number of files
in a Debian repository mirror.

For usage docs run `python3 package_statistics.py --help`
"""

import argparse
import gzip
import logging
import sys
import urllib.request
from collections import Counter
from typing import BinaryIO


def fetch_content_index_file(
    repository_url: str,
    code_name: str,
    architecture: str,
    component: str,
    udeb: bool = False,
) -> BinaryIO:
    """
    Fetch Content-<arch>.gz archive from repository and calculate statistics
    """

    if udeb:
        filename = f"Contents-udeb-{architecture}.gz"
    else:
        filename = f"Contents-{architecture}.gz"

    # TODO validate path segments and join path segments more robustly
    repository_url = repository_url.rstrip("/")
    content_index_url = f"{repository_url}/dists/{code_name}/{component}/{filename}"
    logging.info("Fetching content index from %s", content_index_url)
    response = urllib.request.urlopen(content_index_url)
    return response


def decompress_content_index(compressed_stream: BinaryIO):
    """Use gip to decompress the response stream into a new stream"""
    # The default mode is binary for gzip.open,
    # Explicitly use 't' - text mode to parse new lines correctly
    decompressed_response_stream = gzip.open(compressed_stream, "rt")
    return decompressed_response_stream


def calculate_package_file_count(content_stream: BinaryIO) -> Counter:
    """
    Given a stream `content_stream` to a content index file,
    calculates and returns a dict with counts of files in each
    package, indexed by the package name

    See https://wiki.debian.org/RepositoryFormat#A.22Contents.22_indices
    """
    package_file_count: Counter = Counter()
    for line in content_stream:
        # Each line in the file is of the form
        # some/path/segment with spaces/folder package1,package2...
        words = str(line).strip().split()

        # TODO Handle file headers
        # The specification describes a few lines of headers with no strict format,
        # Actual repositories are missing any headers

        # As filenames can contain spaces, look at the word after the last space
        # to get the comma separated list of packages associated with a file
        packages = words[-1].split(",")
        for package in packages:
            package_file_count[package] = package_file_count.get(package, 0) + 1
    return package_file_count


def parse_arguments() -> argparse.Namespace:
    """Parse CLI arguments using argparse"""
    parser = argparse.ArgumentParser(
        description="list the top packages with the most number of files in a Debian repository"
    )

    parser.add_argument(
        "architecture", help="processor architecture, eg: amd64, aarch64 etc"
    )

    parser.add_argument(
        "-r",
        "--repository-url",
        help="URL to a Debian like repository/mirror",
        default="http://ftp.uk.debian.org/debian/",
    )

    parser.add_argument(
        "--code-name",
        help="Codename of debian version/distribution, eg: bullseye, jessie etc",
        default="bullseye",
    )

    parser.add_argument(
        "--component",
        help="component of the distribution, eg. main, non-free etc",
        default="main",
    )

    parser.add_argument(
        "--count",
        help="number of packages to output",
        type=int,
        default=10,
    )

    parser.add_argument(
        "--udeb",
        help="Calculate statistics for udeb packages instead of deb packages",
        action="store_true",
    )

    parser.add_argument(
        "-v", "--verbose", help="increase output verbosity", action="store_true"
    )

    return parser.parse_args()


def pretty_print(package_file_count: Counter, count: int):
    """
    Given a dict with counts of files indexed by package name,
    prints the the top `count` packages in descending order
    """
    for index, item in enumerate(package_file_count.most_common(count)):
        package_name = item[0].split("/")[-1]  # Don't print category/area
        print(f"{index+1:4}. {package_name:60} {item[1]:10}")


def main() -> None:
    """Main entrypoint of the script"""

    args = parse_arguments()

    # Configure logging for the script
    logLevel = logging.ERROR
    if args.verbose:
        logLevel = logging.DEBUG
    logging.basicConfig(level=logLevel, format="%(levelname)s: %(message)s")

    response_stream = None
    content_index_stream = None
    try:
        # Fetch the compressed file, and process
        # the response body as a stream
        response_stream = fetch_content_index_file(
            architecture=args.architecture,
            code_name=args.code_name,
            repository_url=args.repository_url,
            component=args.component,
            udeb=args.udeb,
        )

        # Use gzip to decompress the response stream
        content_index_stream = decompress_content_index(response_stream)

        # Pipe the response stream in to calculate statistics incrementally
        package_file_count = calculate_package_file_count(content_index_stream)

        # Format and print statistics
        pretty_print(package_file_count, args.count)

    except Exception:
        logging.exception(
            "Failed to read content index from repository, Use -v for more verbose logging"
        )
        sys.exit(1)
    finally:
        logging.debug("Closing gzip.open stream")
        if content_index_stream:
            content_index_stream.close()

        # Closing the gzip.open file does not close the underlying file object
        # so close the underlying HTTP response stream
        logging.debug("Closing HTTP response stream")
        if response_stream:
            response_stream.close()


if __name__ == "__main__":
    main()
