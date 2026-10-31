#!/bin/bash
# Paste this whole file into the Oracle console when creating the VM:
#   Create instance > Show advanced options > Management > Initialization script > Paste cloud-init script
# The VM then installs and starts Vayu on first boot, no SSH needed.
# Progress log on the VM: /var/log/vayu-setup.log  (about 10 minutes)
export HOME=/root USER=root
exec > /var/log/vayu-setup.log 2>&1
until curl -fsS https://raw.githubusercontent.com >/dev/null 2>&1; do sleep 5; done
curl -fsSL https://raw.githubusercontent.com/PrachiYadav-16/vayu-aqi/main/deploy/oracle/setup.sh | VAYU_DIR=/opt/vayu-aqi bash
