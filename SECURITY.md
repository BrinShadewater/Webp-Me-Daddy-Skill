# Security Policy

## Reporting a vulnerability

Please **do not** open a public issue for a security problem.

Use GitHub's private vulnerability reporting on this repository
(**Security → Report a vulnerability**), which opens a private channel with the maintainer.

Please include what you found, how to reproduce it, and what an attacker could achieve.

## Scope

This tool reads and writes image files on the machine it runs on, and shells out to a
companion tool for animated assets. Reports about path handling, file overwriting,
or unsafe subprocess behaviour are in scope.

## What this project does not do

- It does not collect telemetry, and it does not phone home.
- It does not require credentials to run its core functionality.

Please do not paste secrets, tokens, or credentials into an issue or a pull request. If you
believe you have exposed one while using this tool, rotate it first and report second.
