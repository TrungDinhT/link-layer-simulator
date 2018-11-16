#!/bin/csh

# Find current dir
set CUR_DIR = `pwd`

# Include current dir to path
setenv PATH $CUR_DIR\:$PATH

chmod u+x ./run_*
