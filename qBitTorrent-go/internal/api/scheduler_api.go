package api

import (
	"encoding/json"
	"fmt"
	"net/http"
	"os"
	"sync"
	"time"

	"github.com/gin-gonic/gin"
	"github.com/milos85vasic/qBitTorrent-go/internal/models"
)

type ScheduleStore struct {
	mu       sync.RWMutex
	file     string
	schedules map[string]models.ScheduledSearch
}

func NewScheduleStore(file string) *ScheduleStore {
	store := &ScheduleStore{
		file:     file,
		schedules: make(map[string]models.ScheduledSearch),
	}
	store.load()
	return store
}

func (s *ScheduleStore) load() {
	data, err := os.ReadFile(s.file)
	if err != nil {
		return
	}
	var schedules []models.ScheduledSearch
	if err := json.Unmarshal(data, &schedules); err != nil {
		return
	}
	for _, sch := range schedules {
		s.schedules[sch.ID] = sch
	}
}

func (s *ScheduleStore) save() error {
	schedules := make([]models.ScheduledSearch, 0, len(s.schedules))
	for _, sch := range s.schedules {
		schedules = append(schedules, sch)
	}
	data, err := json.MarshalIndent(schedules, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(s.file, data, 0644)
}

func (s *ScheduleStore) List() []models.ScheduledSearch {
	s.mu.RLock()
	defer s.mu.RUnlock()
	schedules := make([]models.ScheduledSearch, 0, len(s.schedules))
	for _, sch := range s.schedules {
		schedules = append(schedules, sch)
	}
	return schedules
}

func (s *ScheduleStore) Create(sched models.ScheduledSearch) models.ScheduledSearch {
	s.mu.Lock()
	defer s.mu.Unlock()
	sched.ID = fmt.Sprintf("sched-%d", time.Now().UnixNano())
	s.schedules[sched.ID] = sched
	s.save()
	return sched
}

func (s *ScheduleStore) Delete(id string) bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, ok := s.schedules[id]; !ok {
		return false
	}
	delete(s.schedules, id)
	s.save()
	return true
}

func ListSchedulesHandler(store *ScheduleStore) gin.HandlerFunc {
	return func(c *gin.Context) {
		c.JSON(http.StatusOK, store.List())
	}
}

func CreateScheduleHandler(store *ScheduleStore) gin.HandlerFunc {
	return func(c *gin.Context) {
		var sched models.ScheduledSearch
		if err := c.ShouldBindJSON(&sched); err != nil {
			c.JSON(http.StatusBadRequest, gin.H{"error": err.Error()})
			return
		}
		created := store.Create(sched)
		c.JSON(http.StatusCreated, created)
	}
}

func DeleteScheduleHandler(store *ScheduleStore) gin.HandlerFunc {
	return func(c *gin.Context) {
		id := c.Param("id")
		if !store.Delete(id) {
			c.JSON(http.StatusNotFound, gin.H{"error": "schedule not found"})
			return
		}
		c.Status(http.StatusNoContent)
	}
}