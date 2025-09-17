from lib import test_pull_request
import argparse
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--base-sha', required=True)
    parser.add_argument('--current-sha', required=True)
    args = parser.parse_args()
    res = test_pull_request(args.base_sha, args.current_sha)

    if res[0] == 1:
        sys.exit(res[1])
    else:
        print(res[1])


if __name__ == '__main__':
    main()
