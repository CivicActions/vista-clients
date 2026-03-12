# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-03-11

### Added

- `vista_clients.rpc` — RPC Broker client for VistA's XWB wire protocol over TCP.
  - TCP connection, XWB handshake, authentication with dual cipher support.
  - Application context management and RPC invocation.
  - Credential resolution: explicit args → environment variables → built-in defaults.
- `vista_clients.terminal` — SSH-based terminal driver for VistA's Roll-and-Scroll interface.
  - Paramiko-based SSH transport with expect-style prompt matching engine.
  - VistA login flow, pagination handling (auto-scroll), VT100 stripping.
  - Session history tracking and output inspection utilities.
- Three-tier test suite: unit, contract, and smoke tests.
- Full README with API reference, examples, and environment variable docs.
