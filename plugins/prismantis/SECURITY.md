# Security

## Reporting a vulnerability

Please report it privately: [open a security advisory](https://github.com/NahumLitvin/prismantis/security/advisories/new). Do not open a public issue, since the fix is not out yet. I aim to answer within a week and credit the report in the release notes, unless you ask me not to.

## What counts

prismantis draws text the model wrote, and that text can be shaped by anything the model read. A vulnerability is anything a reply, tool output or prompt can make prismantis do beyond drawing it, for example:

- read a file it should not, or reach another machine (#182)
- put reply text into a command line instead of stdin
- make a link other than `https` clickable
- pass terminal escape sequences through to the screen
- send anything over the network (the plugin never does)

## Supported versions

Only the latest release gets fixes. Installs pin a release tag, so update with `claude plugin marketplace update prismantis && claude plugin update prismantis@prismantis`.
