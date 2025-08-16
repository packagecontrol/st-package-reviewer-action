from lib import test_pull_request
import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pr-url', required=True)
    parser.add_argument('--base-sha', required=True)
    parser.add_argument('--current-sha', required=True)
    args = parser.parse_args()
    res = test_pull_request(args.pr_url, args.base_sha, args.current_sha, args.token)
    if res['result'] == 'error':
        raise Exception(res['message'])


if __name__ == '__main__':
    main()
