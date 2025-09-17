# review-bot-action

GitHub Action for testing packages that are added or modified in a Package Control registry (i.e. the default channel, or those maintained by Sublime-LSP and SublimeLinter).

## Dependencies

This action vendors [st_package_reviewer](https://github.com/packagecontrol/st_package_reviewer) which deeply inspects the packages themselves, and a tweaked copy (from 2021-ish) of the [PC client package](https://github.com/wbond/package_control), from which it mostly borrows the downloader (to download the package and feed it to the reviewer script).

## Usage

Below is an example workflow for running this action.
It can be placed at `.github/workflows/on-pr.yaml` (file can have any name).

```yaml
name: On PR

on:
  - pull_request_target

jobs:
  trigger-review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
        with:
          fetch-depth: 0
          ref: refs/pull/${{ github.event.pull_request.number }}/merge

      - uses: packagecontrol/st-package-reviewer-action@07e1e0a137a468d13da8a4276fcbbcb1c4577ceb
        with:
          base-sha: ${{ github.event.pull_request.base.sha }}
          current-sha: ${{ github.event.pull_request.head.sha }}
```
