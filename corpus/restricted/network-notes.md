---
level: 2
---
# Core network notes

## Addressing plan
Management lives in 10.20.0.0/24, servers in 10.20.10.0/24, and the quarantine VLAN is 10.20.99.0/24.

## Firewall exceptions
The backup server may reach the NAS on port 445 only. No other server-to-NAS traffic is permitted.
