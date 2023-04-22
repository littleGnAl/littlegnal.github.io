#!/usr/bin/env bash
set -e
set -x

POST_PATH=$1
MY_PATH=$(realpath $(dirname "$0"))

pushd ${MY_PATH}

python3 md_to_jekyll_post.py ${POST_PATH}

popd