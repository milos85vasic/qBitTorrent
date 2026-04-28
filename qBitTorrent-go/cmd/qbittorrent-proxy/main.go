package main

import (
	"fmt"
	"net/http"
	"os"

	"github.com/gin-gonic/gin"
	"github.com/milos85vasic/qBitTorrent-go/internal/api"
	"github.com/milos85vasic/qBitTorrent-go/internal/client"
	"github.com/milos85vasic/qBitTorrent-go/internal/config"
	"github.com/milos85vasic/qBitTorrent-go/internal/middleware"
	"github.com/milos85vasic/qBitTorrent-go/internal/service"
	"github.com/rs/zerolog"
	"github.com/rs/zerolog/log"
)

func main() {
	cfg := config.Load()

	zerolog.SetGlobalLevel(parseLogLevel(cfg.LogLevel))
	log.Info().Str("port", fmt.Sprintf("%d", cfg.ServerPort)).Msg("starting merge search service")

	var qbitClient *client.Client
	qc, err := client.NewClient(cfg.QBittorrentURL(), cfg.QBittorrentUsername, cfg.QBittorrentPassword)
	if err != nil {
		log.Warn().Err(err).Msg("failed to connect to qBittorrent on startup, will retry on requests")
	} else {
		qbitClient = qc
		log.Info().Msg("connected to qBittorrent")
	}

	searchSvc := service.NewMergeSearchService(qbitClient, cfg.MaxConcurrentSearches)
	hookStore := api.NewHookStore("/config/download-proxy/hooks.json")
	scheduleStore := api.NewScheduleStore("/config/merge-service/scheduling.json")
	themeStore := api.NewThemeStore("/config/merge-service/theme.json")

	if os.Getenv("GIN_MODE") == "debug" || os.Getenv("GIN_MODE") == "test" {
		gin.SetMode(gin.DebugMode)
	} else {
		gin.SetMode(gin.ReleaseMode)
	}

	r := gin.Default()
	r.Use(middleware.CORS("*"))
	r.Use(middleware.Logger())

	r.GET("/health", api.HealthHandler)

	bridgeHost := cfg.QBittorrentHost
	if h := os.Getenv("BRIDGE_HOST"); h != "" {
		bridgeHost = h
	}
	r.GET("/api/v1/bridge/health", api.BridgeHealthHandler(fmt.Sprintf("http://%s:%d", bridgeHost, cfg.BridgePort)))

	r.GET("/api/v1/config", api.ConfigHandler(map[string]interface{}{
		"qbittorrent_url":          fmt.Sprintf("http://%s:%d", cfg.QBittorrentHost, cfg.ProxyPort),
		"qbittorrent_internal_url": cfg.QBittorrentURL(),
		"qbittorrent_port":         cfg.QBittorrentPort,
		"qbittorrent_host":         cfg.QBittorrentHost,
		"proxy_port":               cfg.ProxyPort,
	}))

	r.GET("/api/v1/stats", func(c *gin.Context) {
		c.JSON(http.StatusOK, searchSvc.Stats())
	})

	v1 := r.Group("/api/v1")
	{
		v1.POST("/search", api.SearchHandler(searchSvc))
		v1.POST("/search/sync", api.SearchSyncHandler(searchSvc))
		v1.GET("/search/stream/:id", api.SearchStreamHandler(searchSvc))
		v1.GET("/search/:id", api.GetSearchHandler(searchSvc))
		v1.POST("/search/:id/abort", api.AbortSearchHandler(searchSvc))

		v1.POST("/download", api.DownloadHandler(searchSvc, cfg.QBittorrentURL(), cfg.QBittorrentUsername, cfg.QBittorrentPassword))
		v1.POST("/download/file", api.DownloadFileHandler(searchSvc))
		v1.POST("/magnet", api.MagnetHandler(searchSvc))
		v1.GET("/downloads/active", api.ActiveDownloadsHandler(cfg.QBittorrentURL(), cfg.QBittorrentUsername, cfg.QBittorrentPassword))
		v1.POST("/auth/qbittorrent", api.QBittorrentAuthHandler(cfg.QBittorrentURL()))

		v1.GET("/theme", api.GetThemeHandler(themeStore))
		v1.PUT("/theme", api.PutThemeHandler(themeStore))

		v1.GET("/hooks", api.ListHooksHandler(hookStore))
		v1.POST("/hooks", api.CreateHookHandler(hookStore))
		v1.DELETE("/hooks/:id", api.DeleteHookHandler(hookStore))
	}

	schedules := r.Group("/api/v1/schedules")
	{
		schedules.GET("", api.ListSchedulesHandler(scheduleStore))
		schedules.POST("", api.CreateScheduleHandler(scheduleStore))
		schedules.DELETE("/:id", api.DeleteScheduleHandler(scheduleStore))
	}

	addr := fmt.Sprintf(":%d", cfg.ServerPort)
	log.Info().Str("addr", addr).Msg("server listening")
	if err := r.Run(addr); err != nil {
		log.Fatal().Err(err).Msg("server failed")
		os.Exit(1)
	}
}

func parseLogLevel(level string) zerolog.Level {
	switch level {
	case "debug":
		return zerolog.DebugLevel
	case "warn":
		return zerolog.WarnLevel
	case "error":
		return zerolog.ErrorLevel
	default:
		return zerolog.InfoLevel
	}
}