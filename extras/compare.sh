#!/bin/env bash
# this bash script checks if a file exists in $2 and if it does, vimdiffs or copies it 
to=$2

for fl in $(ls $1)
do
    if [[ -f $2/$fl ]]; then
        if cmp -s "$1/$fl" "$2/$fl"; then
            echo "$fl same"
        else
            echo "$fl different"
            #vimdiff $1/$fl $2/$fl
            cp $1/$fl $2/$fl
        fi
    fi
done
