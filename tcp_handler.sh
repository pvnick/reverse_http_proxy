#!/bin/bash

rm /tmp/append.dat

while read LINE; do
	echo $LINE >> /tmp/append.dat
	>&2 echo $LINE
	LINE_LEN=$(echo "$LINE" | wc -c) 
	if [[ $LINE_LEN -eq 2 ]]; then
		>&2 echo "found end of request"
		break
	fi
done 

REQUEST_LEN="$(cat /tmp/append.dat | wc -c)"
#rm payload
#mkfifo payload
echo -n '{"length": '$REQUEST_LEN', "sane": 1}' > payload
cat /tmp/append.dat >> payload &
ncat 127.0.0.1 5555 < payload > foobar
