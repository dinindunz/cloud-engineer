#!/bin/bash

exec "/root/.local/bin/mcp-proxy" \
    --pass-environment \
    --port=8096 \
    --host=0.0.0.0 \
    --sse-host=0.0.0.0 \
    --named-server-config=./mcp-servers.json