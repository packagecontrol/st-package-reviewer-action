# NOTES TO SELF

So this is the action seemingly exclusively used by the LSP project and a handful individuals.

The package_control is seemingly a severely outdated copy (from 2021) of the PC client package maintained at https://github.com/wbond/package_control. It's impossible to upgrade because it was never intended to be used in this way (ie. outside of ST) and recent versions deeply break the interface.

That's about package reviews, ie. static analysis. The other aspect is the schema, which is checked in an action called `packagecontrol/st-schema-reviewer-action`.


# review-bot-action

GitHub Action for reviewing package control channel changes.

## Usage

> **Note**
> Make sure that the repository that wants to use this action has the `Allow GitHub Actions to create and approve pull requests` option enabled in repository `Settings` -> `Actions`.

Below is an example workflow for running this action.
It can be placed at `.github/workflows/on-pr.yaml` (file can have any name).

```yaml
name: On PR

# Use of "pull_request_target" rather than "pull_request" event is dictated by the fact that
# pull requests from forks don't have access to the GITHUB_TOKEN secret that is necessary to
# post review comments. "pull_request_target" runs workflow from the main branch instead,
# allowing access token to work. That of course means that workflows changed or added in PRs
# won't have any affect until merged.
on:
  - pull_request_target

jobs:
  trigger-review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
        with:
          fetch-depth: 0
          # Checkout PR branch. By default main repository branch is checked out.
          ref: refs/pull/${{ github.event.pull_request.number }}/merge

      # Ensures that python3-setuptools is installed
      - name: Setup Python
        uses: actions/setup-python@v1
        with:
          python-version: 3.6

      - name: Install Python dependencies
        run: python3 -m pip install pyyaml

      # Run repository unittests
      - uses: packagecontrol/st-schema-reviewer-action@v1

      # Run st package reviewer tests
      - uses: packagecontrol/st-package-reviewer-action@v1
        with:
          base-sha: ${{ github.event.pull_request.base.sha }}
          current-sha: ${{ github.event.pull_request.head.sha }}
```

## Creating releases

When releasing this code action, it's recommended to create releases using semantically versioned tags – for example, v1.1.3 – and keeping major (v1) and minor (v1.1) tags current to the latest appropriate commit.
