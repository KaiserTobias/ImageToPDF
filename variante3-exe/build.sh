#!/bin/sh
# Baut Programme für Windows, macOS und Linux nach ./fertig
set -e
mkdir -p fertig
GOOS=windows GOARCH=amd64 go build -ldflags="-s -w" -o fertig/imagetopdf-windows.exe .
GOOS=darwin  GOARCH=arm64 go build -ldflags="-s -w" -o fertig/imagetopdf-mac-arm64 .
GOOS=darwin  GOARCH=amd64 go build -ldflags="-s -w" -o fertig/imagetopdf-mac-intel .
GOOS=linux   GOARCH=amd64 go build -ldflags="-s -w" -o fertig/imagetopdf-linux .
ls -lh fertig
