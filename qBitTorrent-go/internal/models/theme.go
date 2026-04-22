package models

type ThemeState struct {
	PaletteID string `json:"palette_id"`
	Mode      string `json:"mode"`
}

type ThemeUpdate struct {
	PaletteID string `json:"paletteId"`
	Mode      string `json:"mode"`
}