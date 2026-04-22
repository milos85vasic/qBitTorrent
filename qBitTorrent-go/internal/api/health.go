package api

import "github.com/gin-gonic/gin"

func HealthHandler(c *gin.Context) {
	c.JSON(200, gin.H{"status": "healthy", "service": "merge-search", "version": "1.0.0"})
}