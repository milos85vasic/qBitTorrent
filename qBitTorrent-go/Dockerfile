FROM golang:1.23-alpine AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o /qbittorrent-proxy ./cmd/qbittorrent-proxy
RUN CGO_ENABLED=0 GOOS=linux go build -o /webui-bridge ./cmd/webui-bridge

FROM alpine:3.19
RUN apk --no-cache add ca-certificates tzdata
WORKDIR /app
COPY --from=builder /qbittorrent-proxy .
COPY --from=builder /webui-bridge .
COPY .env.example .env
EXPOSE 7187 7188
CMD ["/app/qbittorrent-proxy"]