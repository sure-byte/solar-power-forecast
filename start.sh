#!/bin/bash
pip install -r requirements.txt
exec gunicorn --bind 0.0.0.0:$PORT app:app
