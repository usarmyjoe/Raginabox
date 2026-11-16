# VLAN basics

## Why segment
Put IoT devices, guests and trusted machines on separate VLANs (virtual LANs) so a compromised smart plug cannot reach your NAS. Default-deny between VLANs, then allow specific flows.

## Access vs trunk ports
An access port carries one untagged VLAN to an end device. A trunk port carries many VLANs tagged with 802.1Q between switches, routers and access points.

## Discovery across VLANs
mDNS (multicast DNS) does not cross VLAN boundaries. Run an mDNS reflector such as Avahi on the router, and limit it to the VLAN pairs that need it.
