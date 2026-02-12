#!/bin/bash

# exit on first error
set -e

echo "Running entrypoint"

echo "Installing RapidCopy"
./expect_rapidcopy.exp

echo "Continuing docker CMD"
echo "$@"
exec $@
