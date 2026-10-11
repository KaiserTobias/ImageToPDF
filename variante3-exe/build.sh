#!/bin/sh
# Baut Programme für Windows, macOS und Linux nach ./dist
set -e
mkdir -p dist
GOOS=windows GOARCH=amd64 go build -ldflags="-s -w" -o dist/imagetopdf-windows.exe .
GOOS=darwin  GOARCH=arm64 go build -ldflags="-s -w" -o dist/imagetopdf-mac-arm64 .
GOOS=darwin  GOARCH=amd64 go build -ldflags="-s -w" -o dist/imagetopdf-mac-intel .
GOOS=linux   GOARCH=amd64 go build -ldflags="-s -w" -o dist/imagetopdf-linux .
ls -lh dist
