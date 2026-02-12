#!/bin/bash

red=`tput setaf 1`
green=`tput setaf 2`
reset=`tput sgr0`

END=$((SECONDS+10))
while [ ${SECONDS} -lt ${END} ];
do
  SERVER_UP=$(
      curl -s myapp:8800/server/status | \
        python ./parse_rapidcopy_status.py
  )
  if [[ "${SERVER_UP}" == 'True' ]]; then
    break
  fi
  echo "E2E Test is waiting for RapidCopy server to come up..."
  sleep 1
done


if [[ "${SERVER_UP}" == 'True' ]]; then
  echo "${green}E2E Test detected that RapidCopy server is UP${reset}"
  node_modules/protractor/bin/protractor tmp/conf.js
else
  echo "${red}E2E Test failed to detect RapidCopy server${reset}"
  exit 1
fi
