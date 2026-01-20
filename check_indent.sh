#!/bin/bash
rg -tpy '^\t* +'; [[ $? -eq 1 ]]
