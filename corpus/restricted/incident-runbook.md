---
level: 1
---
# Incident runbook

## Break-glass access
If the identity provider is down, use the sealed admin account kept in the safe. Two people must be present. Record the time of use in the incident ticket and rotate the credential afterwards.

## Containing a compromised host
Move the host to the quarantine VLAN, snapshot its disk before touching it, then rebuild from the golden image. Never repair in place.
