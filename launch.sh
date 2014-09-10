#!/bin/bash

trap 'kill -HUP 0' EXIT

let "RAND_PORT_1 = 5000 + ($RANDOM % 100)"
let "RAND_PORT_2 = 7000 + ($RANDOM % 100)"
let "RAND_PORT_3 = 8000 + ($RANDOM % 100)"

cd server_proxy
python server.py $RAND_PORT_1 $RAND_PORT_2 $RAND_PORT_3 &
sleep 1
cd ..
python connect.py $RAND_PORT_1 &

sleep 1
echo "browser port=$RAND_PORT_2"
#curl -L 'http://127.0.0.1:'$RAND_PORT_2
wait
