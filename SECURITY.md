# Security policy

Korinnia stores family data — names, dates, photos and documents of real, often living, people —
so security reports are taken seriously.

## Reporting a vulnerability

Please **do not open a public issue**. Report it privately through GitHub:
**Security → Report a vulnerability** on this repository
([private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)).

Include what you found, how to reproduce it and what an attacker could do with it. You will get
an answer within a week. Once a fix is released, the advisory is published and you are credited
unless you prefer otherwise.

## Scope

- The code in this repository (backend, frontend, nginx configuration, Helm chart).
- The public demo at [korinnia.app](https://korinnia.app): test only with the demo login
  ("Try the demo"), which gives you a throwaway account. Do not try to reach other users' data,
  run denial-of-service or automated scanning at volume, or social-engineer anyone.

## Supported versions

Only the latest release gets security fixes.
