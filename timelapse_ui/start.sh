#!/bin/bash

export TIMELAPSE_UI_SETTINGS=./default_config;
./venv/bin/gunicorn -b unix:./timelapse_ui.sock src:app
