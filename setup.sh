#!/bin/sh

# Find current working directory
CUR_DIR=`pwd`

# Include current working directory in path so that we can run script with name only
export PATH=$PATH:$CUR_DIR
