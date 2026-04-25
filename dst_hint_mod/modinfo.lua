name = "DST Hint System - State Exporter"
description = [[Collects and exports player game state metadata for the DST In-Game Hint System.
Exports: character, vitals, world state, biome, inventory, equipped items, tech level, nearby entities.
Press [H] to manually trigger state export. Data is saved to persistent storage and printed to log.]]
author = "dst-hint-system"
version = "1.0.0"

api_version = 6
api_version_dst = 10
priority = 0

dont_starve_compatible = false
reign_of_giants_compatible = false
shipwrecked_compatible = false
hamlet_compatible = false
dst_compatible = true

all_clients_require_mod = false
client_only_mod = true

server_filter_tags = {"hint", "utility"}

configuration_options = {
    {
        name = "EXPORT_INTERVAL",
        label = "Export Interval (seconds)",
        hover = "How often to automatically export game state.",
        options = {
            {description = "5s",  data = 5},
            {description = "10s", data = 10},
            {description = "15s", data = 15},
            {description = "30s", data = 30},
        },
        default = 10,
    },
    {
        name = "NEARBY_RADIUS",
        label = "Nearby Entity Radius",
        hover = "Radius to scan for nearby entities.",
        options = {
            {description = "10", data = 10},
            {description = "15", data = 15},
            {description = "20", data = 20},
        },
        default = 15,
    },
    {
        name = "SHOW_NOTIFICATION",
        label = "Show Export Notification",
        hover = "Show an on-screen message when state is exported.",
        options = {
            {description = "Yes", data = true},
            {description = "No",  data = false},
        },
        default = true,
    },
    {
        name = "HOTKEY",
        label = "Manual Export Key",
        hover = "Key to manually trigger state export.",
        options = {
            {description = "H", data = "H"},
            {description = "J", data = "J"},
            {description = "K", data = "K"},
            {description = "None", data = ""},
        },
        default = "H",
    },
}
