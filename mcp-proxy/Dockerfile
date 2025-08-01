FROM golang:1.23-alpine AS builder

# Install git for cloning
RUN apk add --no-cache git

# Clone and build GitHub MCP server
WORKDIR /build
RUN git clone https://github.com/github/github-mcp-server.git
WORKDIR /build/github-mcp-server

# Build the Go binary
RUN go mod download
RUN go build -o github-mcp-server ./cmd/github-mcp-server

# Production stage
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y git build-essential curl && \
    rm -rf /var/lib/apt/lists/*

# Install uv package manager
RUN pip install uv

# Install mcp-proxy
RUN uv tool install mcp-proxy

# Copy the built GitHub MCP server binary from builder stage
COPY --from=builder /build/github-mcp-server/github-mcp-server /usr/local/bin/github-mcp-server

# Make it executable
RUN chmod +x /usr/local/bin/github-mcp-server

# Create app directory
WORKDIR /app

# Copy configuration
COPY mcp-servers.json ./mcp-servers.json

# Create entrypoint script
COPY entrypoint.sh ./entrypoint.sh
RUN chmod +x ./entrypoint.sh

# Expose the port
EXPOSE 8096

# Run the proxy
ENTRYPOINT ["./entrypoint.sh"]