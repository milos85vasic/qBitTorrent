package api

import (
	"encoding/json"
	"net/http"
	"os"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/milos85vasic/qBitTorrent-go/internal/models"
)

type HookStore struct {
	mu    sync.RWMutex
	file  string
	hooks map[string]models.Hook
}

func NewHookStore(file string) *HookStore {
	store := &HookStore{
		file:  file,
		hooks: make(map[string]models.Hook),
	}
	store.load()
	return store
}

func (s *HookStore) load() {
	data, err := os.ReadFile(s.file)
	if err != nil {
		return
	}
	var hooks []models.Hook
	if err := json.Unmarshal(data, &hooks); err != nil {
		return
	}
	for _, h := range hooks {
		s.hooks[h.ID] = h
	}
}

func (s *HookStore) save() error {
	hooks := make([]models.Hook, 0, len(s.hooks))
	for _, h := range s.hooks {
		hooks = append(hooks, h)
	}
	data, err := json.MarshalIndent(hooks, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(s.file, data, 0644)
}

func (s *HookStore) List() []models.Hook {
	s.mu.RLock()
	defer s.mu.RUnlock()
	hooks := make([]models.Hook, 0, len(s.hooks))
	for _, h := range s.hooks {
		hooks = append(hooks, h)
	}
	return hooks
}

func (s *HookStore) Create(hook models.Hook) models.Hook {
	s.mu.Lock()
	defer s.mu.Unlock()
	hook.ID = generateHookID()
	hook.Enabled = true
	hook.CreatedAt = time.Now()
	s.hooks[hook.ID] = hook
	s.save()
	return hook
}

func (s *HookStore) Delete(id string) bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, ok := s.hooks[id]; !ok {
		return false
	}
	delete(s.hooks, id)
	s.save()
	return true
}

func generateHookID() string {
	return "hook-" + time.Now().Format("20060102150405") + "-" + time.Now().Format("150405.000000000")
}

func ListHooksHandler(store *HookStore) gin.HandlerFunc {
	return func(c *gin.Context) {
		c.JSON(http.StatusOK, store.List())
	}
}

func CreateHookHandler(store *HookStore) gin.HandlerFunc {
	return func(c *gin.Context) {
		var hook models.Hook
		if err := c.ShouldBindJSON(&hook); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}
		created := store.Create(hook)
		c.JSON(http.StatusCreated, created)
	}
}

func DeleteHookHandler(store *HookStore) gin.HandlerFunc {
	return func(c *gin.Context) {
		id := c.Param("id")
		if !store.Delete(id) {
			c.JSON(http.StatusNotFound, gin.H{"error": "hook not found"})
			return
		}
		c.Status(http.StatusNoContent)
	}
}