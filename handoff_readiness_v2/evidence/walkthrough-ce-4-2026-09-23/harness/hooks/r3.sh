#!/usr/bin/env bash
# Round 3. Photon Labs (team 2) builds far more stock than its markets will
# buy. Cost of goods is charged at resolution and is outside the affordability
# check, so nothing refuses it: the team simply makes a very large operating
# loss and its cash goes negative -- the ordinary way a company runs out of
# money, and the state integrator decision 13 says must still be playable.
set -u
cd "$(dirname "$0")/.."
python3 drive_overproduction.py en 2 3 600000
