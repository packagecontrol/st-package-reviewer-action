# review-bot-action
GitHub Action for reviewing package control channel changes

## Example workflow

Below is an example workflow for running this action.
It can be placed at `.github/workflows/on-pr.yaml` (file can have any name).

```yaml
name: On PR

# Use of "pull_request_target" rather than "pull_request" event is dictated by the fact that
# pull requests from forks don't have access to the GITHUB_TOKEN secret that is necessary to
# post review comments. "pull_request_target" runs workflow from the main branch instead,
# allowing access token to work. That of course means that workflows changed or added in PRs
# won't have any affect until merged.
on: [pull_request_target]

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
        # st_package_reviewer installed from repo as pypi release is not up to date currently
        run: python3 -m pip install pyyaml git+https://github.com/packagecontrol/st_package_reviewer.git@d2b43530442f227751c925d259df8fb324eee18f

      # Run repository unittests
      - uses: sublimelsp/st-schema-reviewer-action@v1

      # Run st package reviewer tests
      - uses: sublimelsp/st-package-reviewer-action@v1
        with:
          pr-url: ${{ github.event.pull_request.url }}
          base-sha: ${{ github.event.pull_request.base.sha }}
          current-sha: ${{ github.event.pull_request.head.sha }}
          token: ${{ secrets.GITHUB_TOKEN }}
```
