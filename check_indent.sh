#!/bin/bash
rg -tpy '^\t* +'; echo $?;
hexdump -C test.py
