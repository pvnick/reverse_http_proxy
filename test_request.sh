#!/bin/bash

REQUEST_STR="$(cat request.txt | unix2dos)"
REQUEST_LEN="$(cat request.txt | unix2dos | wc -c)"
rm payload
mkfifo payload
echo -n '{"length": '$REQUEST_LEN', "sane": 1}' > payload &
cat request.txt | unix2dos > payload &
nc -l 4444 < payload