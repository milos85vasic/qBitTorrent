package api

import (
	"encoding/json"
	"net/http"
	"os"
	"sync"

	"github.com/gin-gonic/gin"
	"github.com/milos85vasic/qBitTorrent-go/internal/models"
)

var allowedModes = map[string]bool{
	"light": true,
	"dark":  true,
}

type ThemeStore struct {
	mu    sync.RWMutex
	file  string
	state models.ThemeState
}

func NewThemeStore(file string) *ThemeStore {
	store := &ThemeStore{
		file:  file,
		state: models.ThemeState{PaletteID: "default", Mode: "dark"},
	}
	store.load()
	return store
}

func (s *ThemeStore) load() {
	data, err := os.ReadFile(s.file)
	if err != nil {
		return
	}
	json.Unmarshal(data, &s.state)
}

func (s *ThemeStore) save() error {
	data, err := json.MarshalIndent(s.state, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(s.file, data, 0644)
}

func (s *ThemeStore) Get() models.ThemeState {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.state
}

func (s *ThemeStore) Put(paletteID, mode string) (models.ThemeState, error) {
	if !allowedModes[mode] {
		return models.ThemeState{}, &ValidationError{Message: "mode must be 'light' or 'dark'"}
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	s.state = models.ThemeState{PaletteID: paletteID, Mode: mode}
	s.save()
	return s.state, nil
}

type ValidationError struct {
	Message string
}

func (e *ValidationError) Error() string {
	return e.Message
}

func GetThemeHandler(store *ThemeStore) gin.HandlerFunc {
	return func(c *gin.Context) {
		c.JSON(http.StatusOK, store.Get())
	}
}

func PutThemeHandler(store *ThemeStore) gin.HandlerFunc {
	return func(c *gin.Context) {
		var req models.ThemeUpdate
		if err := c.ShouldBindJSON(&req); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}
		state, err := store.Put(req.PaletteID, req.Mode)
		if err != nil {
			c.JSON(http.StatusUnprocessableEntity, gin.H{"error": err.Error()})
			return
		}
		c.JSON(http.StatusOK, state)
	}
}