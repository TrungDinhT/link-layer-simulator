#!/bin/csh

# Find current working directory
set CUR_DIR = `pwd`

# Include current working directory in path so that we can run script with name only
setenv PATH $PATH\:$CUR_DIR
