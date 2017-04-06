#!/bin/sh -e
. ~/apps/frontpages-env/bin/activate
cd ~/apps/frontpages-env/app/
python frontpages.py
deactivate
cd ~
